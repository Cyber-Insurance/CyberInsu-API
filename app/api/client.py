import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    Utilisateur, Dossier, Questionnaire, Question, Reponse,
    Document, Score, Devis, AuditLog
)
from app.core.dependencies import require_permission, get_current_user
from app.core.questionnaire_engine import (
    evaluate_condition, build_context_hint,
    compute_maturity, build_visibility_map,
)
from app.schemas.client import (
    QuestionnaireResponse, QuestionItem, SoumettreReponses, DossierOverview,
    EvaluateRequest, EvaluateResponse,
)

router = APIRouter(prefix="/client", tags=["client"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ─── HELPERS ─────────────────────────────────────────────────────────

def fmt_date(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


def niveau_risque_from_score(score: float) -> str:
    if score < 30: return "Critique"
    if score < 50: return "Élevé"
    if score < 70: return "Moyen"
    if score < 85: return "Faible"
    return "Minimal"


def score_reponse(question: Question, valeur: str) -> float:
    if question.type == "boolean":
        raw = 1.0 if valeur.lower() in ("oui", "true", "1", "yes") else 0.0
        return (1.0 - raw) if question.inverse else raw
    if question.type == "scale":
        try:
            raw = float(valeur) / 5.0
            return max(0.0, min(1.0, raw))
        except (ValueError, ZeroDivisionError):
            return 0.5
    if question.type == "choix_multiple":
        mapping = {"faible": 1.0, "moyen": 0.75, "élevé": 0.5, "critique": 0.25}
        return mapping.get(valeur.lower(), 0.5)
    return 0.5  # text → neutre


def get_client_dossier(db: Session, user_id: int) -> Optional[Dossier]:
    return (
        db.query(Dossier)
        .filter(Dossier.id_client == user_id)
        .order_by(Dossier.date_creation.desc())
        .first()
    )


def log_action(db: Session, id_user: int, action: str,
               table_cible: str = None, id_cible: int = None):
    db.add(AuditLog(id_user=id_user, action=action,
                    table_cible=table_cible, id_cible=id_cible))
    db.commit()


# ─── DOSSIER OVERVIEW ────────────────────────────────────────────────

@router.get("/dossier", response_model=DossierOverview)
def get_dossier(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("suivre_dossier"))
):
    d = get_client_dossier(db, current_user.id_user)
    if not d:
        raise HTTPException(status_code=404, detail="Aucun dossier associé à votre compte")

    sc = (
        db.query(Score)
        .filter(Score.id_dossier == d.id_dossier)
        .order_by(Score.calculated_at.desc())
        .first()
    )
    dv = (
        db.query(Devis)
        .join(Score)
        .filter(Score.id_dossier == d.id_dossier)
        .order_by(Devis.created_at.desc())
        .first()
    )

    devis_data = None
    if dv:
        devis_data = {
            "id": dv.id_devis,
            "prime": dv.prime,
            "status": dv.status,
            "motif": dv.motif,
            "date": fmt_date(dv.created_at),
        }

    return DossierOverview(
        id=d.id_dossier,
        company=d.entreprise.nom if d.entreprise else "—",
        secteur=d.entreprise.secteur if d.entreprise else None,
        taille=d.entreprise.taille if d.entreprise else None,
        status=d.status,
        score=sc.score_global if sc else None,
        niveau_risque=(sc.niveau_risque or niveau_risque_from_score(sc.score_global)) if sc else None,
        date_creation=fmt_date(d.date_creation),
        date_soumission=fmt_date(d.date_soumission),
        questionnaire_complete=len(d.reponses) > 0,
        documents_count=len(d.documents),
        devis=devis_data,
    )


# ─── QUESTIONNAIRE ───────────────────────────────────────────────────

@router.get("/questionnaire", response_model=QuestionnaireResponse)
def get_questionnaire(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("remplir_questionnaire"))
):
    questionnaire = (
        db.query(Questionnaire)
        .order_by(Questionnaire.id_questionnaire.desc())
        .first()
    )
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Aucun questionnaire disponible")

    d = get_client_dossier(db, current_user.id_user)

    reponses_existantes = {}
    if d:
        for rep in d.reponses:
            reponses_existantes[rep.id_question] = rep.valeur

    secteur = d.entreprise.secteur if d and d.entreprise else None
    taille = d.entreprise.taille if d and d.entreprise else None

    questions_sorted = sorted(
        questionnaire.questions,
        key=lambda x: (x.ordre or 0, x.id_question)
    )

    # Calculer la maturité une fois pour évaluer les conditions initiales
    initial_maturity = compute_maturity(reponses_existantes, questions_sorted)

    questions = [
        QuestionItem(
            id_question=q.id_question,
            texte=q.texte,
            type=q.type,
            categorie=q.categorie,
            poids=q.poids,
            options=q.options,
            inverse=q.inverse or False,
            condition=q.condition,
            ordre=q.ordre or 0,
            section=q.section or "general",
            visible=evaluate_condition(q.condition, reponses_existantes, secteur, taille, initial_maturity),
            contexte_hint=build_context_hint(q.condition, secteur, taille),
        )
        for q in questions_sorted
    ]

    return QuestionnaireResponse(
        id_questionnaire=questionnaire.id_questionnaire,
        nom=questionnaire.nom,
        version=questionnaire.version,
        questions=questions,
        reponses_existantes=reponses_existantes,
        secteur=secteur,
        taille=taille,
    )


@router.post("/questionnaire/evaluate", response_model=EvaluateResponse)
def evaluate_questionnaire(
    body: EvaluateRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("remplir_questionnaire"))
):
    questionnaire = (
        db.query(Questionnaire)
        .order_by(Questionnaire.id_questionnaire.desc())
        .first()
    )
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Aucun questionnaire disponible")

    d = get_client_dossier(db, current_user.id_user)
    secteur = d.entreprise.secteur if d and d.entreprise else None
    taille = d.entreprise.taille if d and d.entreprise else None

    reponses = {int(k): v for k, v in body.reponses.items()}

    visibility_int = build_visibility_map(questionnaire.questions, reponses, secteur, taille)
    visibility = {str(k): v for k, v in visibility_int.items()}
    maturity = compute_maturity(reponses, questionnaire.questions)
    visible_count = sum(1 for v in visibility.values() if v)

    return EvaluateResponse(
        visibility=visibility,
        maturity=maturity,
        visible_count=visible_count,
    )


@router.post("/questionnaire/soumettre")
def soumettre_questionnaire(
    body: SoumettreReponses,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("remplir_questionnaire"))
):
    d = get_client_dossier(db, current_user.id_user)
    if not d:
        raise HTTPException(status_code=404, detail="Aucun dossier associé à votre compte")

    # Supprimer les anciennes réponses
    for rep in list(d.reponses):
        db.delete(rep)
    db.flush()

    total_score = 0.0
    total_poids = 0

    for item in body.reponses:
        q = db.query(Question).filter(Question.id_question == item.id_question).first()
        if not q:
            continue
        s = score_reponse(q, item.valeur)
        rep = Reponse(
            id_question=item.id_question,
            id_dossier=d.id_dossier,
            valeur=item.valeur,
            score=s,
        )
        db.add(rep)
        total_score += s * q.poids
        total_poids += q.poids

    score_q = round((total_score / total_poids * 100) if total_poids > 0 else 50.0, 2)

    sc = (
        db.query(Score)
        .filter(Score.id_dossier == d.id_dossier)
        .order_by(Score.calculated_at.desc())
        .first()
    )
    if sc:
        sc.score_questionnaire = score_q
        sc.score_global = round((score_q + sc.score_document) / 2, 2)
        sc.niveau_risque = niveau_risque_from_score(sc.score_global)
        sc.calculated_at = datetime.utcnow()
    else:
        sc = Score(
            id_dossier=d.id_dossier,
            score_questionnaire=score_q,
            score_document=0.0,
            score_global=score_q,
            niveau_risque=niveau_risque_from_score(score_q),
        )
        db.add(sc)

    if d.status in ("draft", "soumis"):
        d.status = "en_analyse"

    db.commit()
    log_action(db, current_user.id_user, "remplir_questionnaire", "reponses", d.id_dossier)
    return {
        "message": "Questionnaire soumis",
        "score_questionnaire": score_q,
        "score_global": sc.score_global,
        "niveau_risque": sc.niveau_risque,
    }


# ─── DOCUMENTS ───────────────────────────────────────────────────────

@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("upload_documents"))
):
    d = get_client_dossier(db, current_user.id_user)
    if not d:
        raise HTTPException(status_code=404, detail="Aucun dossier associé à votre compte")

    return {
        "total": len(d.documents),
        "documents": [
            {
                "id_document": doc.id_document,
                "nom": doc.nom,
                "type": doc.type,
                "taille_ko": doc.taille_ko,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in sorted(d.documents, key=lambda x: x.uploaded_at, reverse=True)
        ],
    }


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    type_doc: str = Form("autre"),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("upload_documents"))
):
    d = get_client_dossier(db, current_user.id_user)
    if not d:
        raise HTTPException(status_code=404, detail="Aucun dossier associé à votre compte")

    safe_name = f"{d.id_dossier}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    taille_ko = os.path.getsize(path) // 1024

    doc = Document(
        nom=file.filename,
        type=type_doc,
        url=path,
        taille_ko=taille_ko,
        id_dossier=d.id_dossier,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_action(db, current_user.id_user, "upload_document", "documents", doc.id_document)
    return {
        "message": "Document uploadé",
        "id_document": doc.id_document,
        "nom": doc.nom,
        "taille_ko": taille_ko,
    }


# ─── DEVIS ───────────────────────────────────────────────────────────

@router.get("/devis")
def get_devis(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("suivre_dossier"))
):
    d = get_client_dossier(db, current_user.id_user)
    if not d:
        raise HTTPException(status_code=404, detail="Aucun dossier associé à votre compte")

    devis_list = (
        db.query(Devis)
        .join(Score)
        .filter(Score.id_dossier == d.id_dossier)
        .order_by(Devis.created_at.desc())
        .all()
    )
    return {
        "total": len(devis_list),
        "devis": [
            {
                "id": dv.id_devis,
                "prime": dv.prime,
                "status": dv.status,
                "motif": dv.motif,
                "date": fmt_date(dv.created_at),
            }
            for dv in devis_list
        ],
    }
