import bcrypt
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db.models import (
    Utilisateur, Role, Dossier, Entreprise, Score, Devis, AuditLog
)
from app.core.dependencies import require_permission, get_current_user
from app.schemas.courtier import (
    DossierCreate, DossierListResponse, DossierItem,
    ClientListResponse, ClientItem, InviteClientRequest, StatsResponse
)

router = APIRouter(prefix="/courtier", tags=["courtier"])


# ─── HELPERS ─────────────────────────────────────────────────────────

def fmt_date(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


def niveau_risque_from_score(score: float) -> str:
    if score < 30: return "Critique"
    if score < 50: return "Élevé"
    if score < 70: return "Moyen"
    if score < 85: return "Faible"
    return "Minimal"


def calculate_prime(score_global: float, taille: str) -> float:
    base = {"Startup": 3000, "PME": 6000, "ETI": 12000, "GE": 25000}.get(taille, 5000)
    risk = (100 - score_global) / 100
    return round(base * (1 + risk * 2), 2)


def get_latest_score(db: Session, dossier_id: int) -> Optional[Score]:
    return (
        db.query(Score)
        .filter(Score.id_dossier == dossier_id)
        .order_by(Score.calculated_at.desc())
        .first()
    )


def format_dossier(db: Session, d: Dossier) -> dict:
    sc = get_latest_score(db, d.id_dossier)
    nb_reponses = len(d.reponses)
    return {
        "id": d.id_dossier,
        "company": d.entreprise.nom if d.entreprise else "—",
        "secteur": d.entreprise.secteur if d.entreprise else None,
        "taille": d.entreprise.taille if d.entreprise else None,
        "status": d.status,
        "score": sc.score_global if sc else None,
        "niveau_risque": (sc.niveau_risque or niveau_risque_from_score(sc.score_global)) if sc else None,
        "date_creation": fmt_date(d.date_creation),
        "date_soumission": fmt_date(d.date_soumission),
        "client_email": d.client_user.email if d.client_user else None,
        "questionnaire_complete": nb_reponses > 0,
        "documents_count": len(d.documents),
    }


def log_action(db: Session, id_user: int, action: str,
               table_cible: str = None, id_cible: int = None, details: dict = None):
    db.add(AuditLog(id_user=id_user, action=action,
                    table_cible=table_cible, id_cible=id_cible, details=details))
    db.commit()


# ─── STATS ───────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    query = db.query(Dossier).filter(Dossier.id_user == current_user.id_user)
    total = query.count()
    actifs = query.filter(Dossier.status.in_(["draft", "soumis", "en_analyse", "devis_genere"])).count()

    devis_envoyes = (
        db.query(Devis)
        .join(Score)
        .join(Dossier)
        .filter(Dossier.id_user == current_user.id_user)
        .count()
    )

    clients_actifs = (
        db.query(Dossier)
        .filter(Dossier.id_user == current_user.id_user, Dossier.id_client.isnot(None))
        .distinct(Dossier.id_client)
        .count()
    )

    avg = (
        db.query(func.avg(Score.score_global))
        .join(Dossier)
        .filter(Dossier.id_user == current_user.id_user)
        .scalar()
    )
    score_moyen = round(float(avg), 1) if avg else 0.0

    repartition = {}
    for status in ["draft", "soumis", "en_analyse", "devis_genere", "valide", "rejete"]:
        repartition[status] = query.filter(Dossier.status == status).count()

    recent = query.order_by(Dossier.date_creation.desc()).limit(5).all()
    recent_dossiers = [format_dossier(db, d) for d in recent]

    return {
        "total_dossiers": total,
        "dossiers_actifs": actifs,
        "devis_envoyes": devis_envoyes,
        "clients_actifs": clients_actifs,
        "score_moyen": score_moyen,
        "repartition": repartition,
        "recent_dossiers": recent_dossiers,
    }


# ─── DOSSIERS ────────────────────────────────────────────────────────

@router.get("/dossiers")
def list_dossiers(
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    query = db.query(Dossier).filter(Dossier.id_user == current_user.id_user)
    if status:
        query = query.filter(Dossier.status == status)
    if search:
        query = query.join(Entreprise).filter(Entreprise.nom.ilike(f"%{search}%"))

    total = query.count()
    dossiers = query.order_by(Dossier.date_creation.desc()).offset(skip).limit(limit).all()
    return {"total": total, "dossiers": [format_dossier(db, d) for d in dossiers]}


@router.get("/dossiers/{dossier_id}")
def get_dossier(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    d = db.query(Dossier).filter(
        Dossier.id_dossier == dossier_id,
        Dossier.id_user == current_user.id_user
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return format_dossier(db, d)


@router.post("/dossiers", status_code=201)
def create_dossier(
    body: DossierCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("creer_dossier"))
):
    # Créer ou retrouver l'entreprise
    entreprise = db.query(Entreprise).filter(
        Entreprise.nom == body.entreprise.nom
    ).first()
    if not entreprise:
        entreprise = Entreprise(
            nom=body.entreprise.nom,
            secteur=body.entreprise.secteur,
            taille=body.entreprise.taille,
        )
        db.add(entreprise)
        db.flush()

    # Lier le client si email fourni
    id_client = None
    if body.client_email:
        client = db.query(Utilisateur).filter(Utilisateur.email == body.client_email).first()
        if client:
            id_client = client.id_user

    dossier = Dossier(
        id_company=entreprise.id_company,
        id_user=current_user.id_user,
        id_client=id_client,
        status="draft",
    )
    db.add(dossier)
    db.commit()
    db.refresh(dossier)
    log_action(db, current_user.id_user, "creer_dossier", "dossiers", dossier.id_dossier)
    return {"message": "Dossier créé", "id_dossier": dossier.id_dossier, "dossier": format_dossier(db, dossier)}


@router.put("/dossiers/{dossier_id}/soumettre")
def soumettre_dossier(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("modifier_dossier"))
):
    d = db.query(Dossier).filter(
        Dossier.id_dossier == dossier_id,
        Dossier.id_user == current_user.id_user
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if d.status != "draft":
        raise HTTPException(status_code=400, detail="Seul un dossier en brouillon peut être soumis")

    d.status = "soumis"
    d.date_soumission = datetime.utcnow()
    db.commit()
    log_action(db, current_user.id_user, "soumettre_dossier", "dossiers", dossier_id)
    return {"message": "Dossier soumis", "status": "soumis"}


@router.post("/dossiers/{dossier_id}/demander-devis", status_code=201)
def demander_devis(
    dossier_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("demander_devis"))
):
    d = db.query(Dossier).filter(
        Dossier.id_dossier == dossier_id,
        Dossier.id_user == current_user.id_user
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if d.status not in ("soumis", "en_analyse"):
        raise HTTPException(status_code=400, detail="Le dossier doit être soumis pour demander un devis")

    # Récupérer ou créer un score
    sc = get_latest_score(db, dossier_id)
    if not sc:
        sc = Score(
            id_dossier=dossier_id,
            score_questionnaire=0,
            score_document=0,
            score_global=50.0,
            niveau_risque="Moyen",
        )
        db.add(sc)
        db.flush()

    # Calculer la prime
    taille = d.entreprise.taille if d.entreprise else "PME"
    prime = calculate_prime(sc.score_global, taille)

    devis = Devis(id_score=sc.id_score, prime=prime, status="en_attente")
    db.add(devis)
    d.status = "devis_genere"
    db.commit()
    db.refresh(devis)
    log_action(db, current_user.id_user, "demander_devis", "devis", devis.id_devis)
    return {"message": "Devis créé", "id_devis": devis.id_devis, "prime": prime}


# ─── CLIENTS ─────────────────────────────────────────────────────────

@router.get("/clients")
def list_clients(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("voir_dossiers"))
):
    dossiers = (
        db.query(Dossier)
        .filter(Dossier.id_user == current_user.id_user, Dossier.id_client.isnot(None))
        .all()
    )

    # Dédoublonner par client
    seen = {}
    for d in dossiers:
        cid = d.id_client
        if cid not in seen:
            seen[cid] = {
                "id_user": cid,
                "email": d.client_user.email if d.client_user else "—",
                "dossier_id": d.id_dossier,
                "company": d.entreprise.nom if d.entreprise else "—",
                "dossier_status": d.status,
                "created_at": fmt_date(d.client_user.created_at) if d.client_user else None,
            }

    clients = list(seen.values())
    return {"total": len(clients), "clients": clients}


@router.post("/clients/inviter", status_code=201)
def inviter_client(
    body: InviteClientRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("inviter_client"))
):
    # Vérifier que le dossier appartient au courtier
    d = db.query(Dossier).filter(
        Dossier.id_dossier == body.dossier_id,
        Dossier.id_user == current_user.id_user
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    # Créer ou récupérer le client
    client = db.query(Utilisateur).filter(Utilisateur.email == body.email).first()
    if client:
        if client.role.status != "client":
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé par un autre rôle")
    else:
        role_client = db.query(Role).filter(Role.status == "client").first()
        if not role_client:
            raise HTTPException(status_code=500, detail="Rôle client introuvable en base")
        hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
        client = Utilisateur(email=body.email, password=hashed, id_role=role_client.id_role)
        db.add(client)
        db.flush()

    d.id_client = client.id_user
    db.commit()
    log_action(db, current_user.id_user, "inviter_client", "utilisateurs", client.id_user,
               details={"dossier_id": body.dossier_id})
    return {"message": "Client invité", "id_user": client.id_user, "email": client.email}
