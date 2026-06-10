from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
import bcrypt

from app.db.database import get_db
from app.db.models import Utilisateur, Role, Permission, RolePermission, AuditLog
from app.core.dependencies import require_permission, get_current_user
from app.schemas.admin import (
    UserCreate, UserUpdate, UserResponse,
    RoleResponse, PermissionResponse, RolePermissionsUpdate,
    AuditLogResponse, StatsResponse
)

router = APIRouter(prefix="/admin", tags=["admin"])


def format_user(user: Utilisateur) -> dict:
    return {
        "id_user": user.id_user,
        "email": user.email,
        "mfa_enabled": user.mfa_enabled,
        "id_role": user.id_role,
        "role_status": user.role.status if user.role else "unknown",
        "permissions": [p.nom for p in user.role.permissions] if user.role else [],
        "created_at": user.created_at,
    }


def log_action(db: Session, id_user: int, action: str, table_cible: str = None, id_cible: int = None):
    db.add(AuditLog(
        id_user=id_user,
        action=action,
        table_cible=table_cible,
        id_cible=id_cible
    ))
    db.commit()


# ─── STATS ──────────────────────────────────────────────────────────
@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    total_users = db.query(Utilisateur).count()
    mfa_count = db.query(Utilisateur).filter(Utilisateur.mfa_enabled == True).count()
    total_logs = db.query(AuditLog).count()

    roles = db.query(Role).all()
    users_by_role = {}
    for role in roles:
        count = db.query(Utilisateur).filter(Utilisateur.id_role == role.id_role).count()
        users_by_role[role.status] = count

    recent = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(5).all()
    recent_actions = []
    for log in recent:
        user = db.query(Utilisateur).filter(Utilisateur.id_user == log.id_user).first()
        recent_actions.append({
            "action": log.action,
            "user_email": user.email if user else "Système",
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return StatsResponse(
        total_users=total_users,
        users_by_role=users_by_role,
        total_audit_logs=total_logs,
        recent_actions=recent_actions,
        mfa_enabled_count=mfa_count,
    )


# ─── USERS ──────────────────────────────────────────────────────────
@router.get("/users")
def list_users(
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    query = db.query(Utilisateur)

    if role:
        role_obj = db.query(Role).filter(Role.status == role).first()
        if role_obj:
            query = query.filter(Utilisateur.id_role == role_obj.id_role)

    if search:
        query = query.filter(Utilisateur.email.ilike(f"%{search}%"))

    users = query.order_by(Utilisateur.id_user.desc()).offset(skip).limit(limit).all()
    total = query.count()

    return {
        "total": total,
        "users": [format_user(u) for u in users]
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    user = db.query(Utilisateur).filter(Utilisateur.id_user == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return format_user(user)


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    if db.query(Utilisateur).filter(Utilisateur.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    role = db.query(Role).filter(Role.id_role == body.id_role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Rôle invalide")

    # Seul admin peut créer admin/assureur
    if body.id_role in [1, 2] and current_user.role.status != "admin":
        raise HTTPException(status_code=403, detail="Seul un admin peut créer ce rôle")

    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = Utilisateur(email=body.email, password=hashed, id_role=body.id_role)
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(db, current_user.id_user, "create_user", "utilisateurs", user.id_user)
    return {"message": "Utilisateur créé", "id_user": user.id_user, "user": format_user(user)}


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    user = db.query(Utilisateur).filter(Utilisateur.id_user == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if body.email:
        existing = db.query(Utilisateur).filter(
            Utilisateur.email == body.email,
            Utilisateur.id_user != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        user.email = body.email

    if body.id_role is not None:
        role = db.query(Role).filter(Role.id_role == body.id_role).first()
        if not role:
            raise HTTPException(status_code=400, detail="Rôle invalide")
        if body.id_role in [1, 2] and current_user.role.status != "admin":
            raise HTTPException(status_code=403, detail="Seul un admin peut assigner ce rôle")
        user.id_role = body.id_role

    if body.password:
        user.password = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    db.commit()
    db.refresh(user)
    log_action(db, current_user.id_user, "update_user", "utilisateurs", user_id)
    return {"message": "Utilisateur mis à jour", "user": format_user(user)}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    if user_id == current_user.id_user:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")

    user = db.query(Utilisateur).filter(Utilisateur.id_user == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    db.delete(user)
    db.commit()
    log_action(db, current_user.id_user, "delete_user", "utilisateurs", user_id)


# ─── ROLES ──────────────────────────────────────────────────────────
@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_roles"))
):
    roles = db.query(Role).all()
    return [
        {
            "id_role": r.id_role,
            "status": r.status,
            "permissions": [{"id": p.id_permission, "nom": p.nom} for p in r.permissions],
            "user_count": db.query(Utilisateur).filter(Utilisateur.id_role == r.id_role).count()
        }
        for r in roles
    ]


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_roles"))
):
    perms = db.query(Permission).order_by(Permission.nom).all()
    return [{"id_permission": p.id_permission, "nom": p.nom, "description": p.description} for p in perms]


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    body: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_roles"))
):
    role = db.query(Role).filter(Role.id_role == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")

    # Supprimer les anciennes permissions
    db.query(RolePermission).filter(RolePermission.id_role == role_id).delete()

    # Ajouter les nouvelles
    for perm_id in body.permission_ids:
        perm = db.query(Permission).filter(Permission.id_permission == perm_id).first()
        if perm:
            db.add(RolePermission(id_role=role_id, id_permission=perm_id))

    db.commit()
    log_action(db, current_user.id_user, "update_role_permissions", "roles", role_id)

    db.refresh(role)
    return {
        "message": "Permissions mises à jour",
        "role": {
            "id_role": role.id_role,
            "status": role.status,
            "permissions": [{"id": p.id_permission, "nom": p.nom} for p in role.permissions]
        }
    }


# ─── AUDIT LOGS ─────────────────────────────────────────────────────
@router.get("/audit-logs")
def list_audit_logs(
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("gerer_utilisateurs"))
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())

    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        query = query.filter(AuditLog.id_user == user_id)

    total = query.count()
    logs = query.offset(skip).limit(limit).all()

    result = []
    for log in logs:
        user = db.query(Utilisateur).filter(Utilisateur.id_user == log.id_user).first()
        result.append({
            "id_log": log.id_log,
            "id_user": log.id_user,
            "user_email": user.email if user else "Système",
            "action": log.action,
            "table_cible": log.table_cible,
            "id_cible": log.id_cible,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {"total": total, "logs": result}
