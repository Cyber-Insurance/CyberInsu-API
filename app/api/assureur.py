from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.db.database import get_db
from app.db.models import Utilisateur, Dossier, Entreprise, Score, Devis, AuditLog
from app.core.dependencies import require_permission
from app.schemas.assureur import (
    StatsResponse, DossierListResponse, DossierItem,
    ScoreResponse, DevisListResponse, RejeterRequest
)

router = APIRouter(prefix="/assureur", tags=["assureur"])


# ─── HELPERS ─────────────────────────────────────────────────────────

def fmt_date(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


def niveau_risque_from_score(score: float) -> str:
    if score < 30: return "Critique"
    if score < 50: return "Élevé"
    if score < 70: return "Moyen"
    if score < 85: return "Faible"
    return "Minimal"


def get_latest_score(db: Session, dossier_id: int) -> Optional[Score]:
    return (
        db.query(Score)
        .filter(Score.id_dossier == dossier_id)
        .order_by(Score.calculated_at.desc())
        .first()
    )


def format_dossier(db: Session, d: Dossier) -> dict:
    sc = get_latest_score(db, d.id_dossier)
    niveau = None
    score_val = None
    if sc:
        score_val = sc.score_global
        niveau = sc.niveau_risque or niveau_risque_from_score(sc.score_global)
    return {
        "id": d.id_dossier,
        "company": d.entreprise.nom if d.entreprise else "—",
        "secteur": d.entreprise.secteur if d.entreprise else None,
        "taille": d.entreprise.taille if d.entreprise else None,
        "status": d.status,
        "score": score_val,
        "niveau_risque": niveau,
        "date_creation": fmt_date(d.date_creation),
        "date_soumission": fmt_date(d.date_soumission),
    }


def log_action(db: Session, id_user: int, action: str,
               table_cible: str = None, id_cible: int = None, details: dict = None):
    db.add(AuditLog(
        id_user=id_user,
        action=action,
        table_cible=table_cible,
        id_cible=id_cible,
        details=details,
    ))
    db.commit()


# ─── STATS ───────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    total_dossiers = db.query(Dossier).count()

    a_valider = db.query(Devis).filter(Devis.status == "en_attente").count()
    valides   = db.query(Devis).filter(Devis.status == "valide").count()
    rejetes   = db.query(Devis).filter(Devis.status == "rejete").count()

    avg = db.query(func.avg(Score.score_global)).scalar()
    score_moyen = round(float(avg), 1) if avg else 0.0

    recent_rows = (
        db.query(Dossier)
        .order_by(Dossier.date_creation.desc())
        .limit(5)
        .all()
    )
    recent_dossiers = []
    for d in recent_rows:
        sc = get_latest_score(db, d.id_dossier)
        recent_dossiers.append({
            "id": d.id_dossier,
            "company": d.entreprise.nom if d.entreprise else "—",
            "status": d.status,
            "score": sc.score_global if sc else None,
            "date": fmt_date(d.date_creation),
        })

    return StatsResponse(
        total_dossiers=total_dossiers,
        a_valider=a_valider,
        valides=valides,
        rejetes=rejetes,
        score_moyen=score_moyen,
        recent_dossiers=recent_dossiers,
    )


# ─── DOSSIERS ────────────────────────────────────────────────────────

@router.get("/dossiers", response_model=DossierListResponse)
def list_dossiers(
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    query = db.query(Dossier)

    if status:
        query = query.filter(Dossier.status == status)
    if search:
        query = query.join(Entreprise, Dossier.id_company == Entreprise.id_company)
        query = query.filter(Entreprise.nom.ilike(f"%{search}%"))

    total = query.count()
    dossiers = query.order_by(Dossier.date_creation.desc()).offset(skip).limit(limit).all()

    return DossierListResponse(
        total=total,
        dossiers=[format_dossier(db, d) for d in dossiers],
    )


@router.get("/dossiers/{dossier_id}")
def get_dossier(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    d = db.query(Dossier).filter(Dossier.id_dossier == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return format_dossier(db, d)


@router.get("/dossiers/{dossier_id}/score", response_model=ScoreResponse)
def get_dossier_score(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_score"))
):
    d = db.query(Dossier).filter(Dossier.id_dossier == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    sc = get_latest_score(db, dossier_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Aucun score disponible pour ce dossier")

    return ScoreResponse(
        score_questionnaire=sc.score_questionnaire or 0.0,
        score_document=sc.score_document or 0.0,
        score_global=sc.score_global or 0.0,
        niveau_risque=sc.niveau_risque or niveau_risque_from_score(sc.score_global or 0),
        calculated_at=sc.calculated_at.isoformat() if sc.calculated_at else None,
    )


# ─── DEVIS ───────────────────────────────────────────────────────────

@router.get("/devis", response_model=DevisListResponse)
def list_devis(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("valider_devis"))
):
    query = db.query(Devis)
    if status:
        query = query.filter(Devis.status == status)

    total = query.count()
    devis_list = query.order_by(Devis.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for dv in devis_list:
        sc = dv.score
        d = sc.dossier if sc else None
        result.append({
            "id": dv.id_devis,
            "dossier_id": sc.id_dossier if sc else None,
            "company": d.entreprise.nom if d and d.entreprise else "—",
            "prime": dv.prime,
            "status": dv.status,
            "score": sc.score_global if sc else None,
            "niveau_risque": (
                sc.niveau_risque or niveau_risque_from_score(sc.score_global)
                if sc else None
            ),
            "date": fmt_date(dv.created_at),
        })

    return DevisListResponse(total=total, devis=result)


@router.put("/devis/{devis_id}/valider")
def valider_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("valider_devis"))
):
    dv = db.query(Devis).filter(Devis.id_devis == devis_id).first()
    if not dv:
        raise HTTPException(status_code=404, detail="Devis introuvable")
    if dv.status not in ("draft", "en_attente"):
        raise HTTPException(
            status_code=400,
            detail=f"Ce devis ne peut pas être validé (statut actuel : {dv.status})"
        )

    # Mettre à jour le statut du dossier lié
    sc = dv.score
    if sc and sc.dossier:
        sc.dossier.status = "valide"

    dv.status = "valide"
    db.commit()
    log_action(db, current_user.id_user, "valider_devis", "devis", devis_id)
    return {"message": "Devis validé", "id_devis": devis_id, "status": "valide"}


@router.put("/devis/{devis_id}/rejeter")
def rejeter_devis(
    devis_id: int,
    body: RejeterRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("valider_devis"))
):
    dv = db.query(Devis).filter(Devis.id_devis == devis_id).first()
    if not dv:
        raise HTTPException(status_code=404, detail="Devis introuvable")
    if dv.status not in ("draft", "en_attente"):
        raise HTTPException(
            status_code=400,
            detail=f"Ce devis ne peut pas être rejeté (statut actuel : {dv.status})"
        )

    # Mettre à jour le statut du dossier lié
    sc = dv.score
    if sc and sc.dossier:
        sc.dossier.status = "rejete"

    dv.status = "rejete"
    db.commit()
    log_action(
        db, current_user.id_user, "rejeter_devis", "devis", devis_id,
        details={"motif": body.motif} if body.motif else None
    )
    return {"message": "Devis rejeté", "id_devis": devis_id, "status": "rejete", "motif": body.motif}
