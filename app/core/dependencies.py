from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Utilisateur
from app.core.security import decode_token

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> Utilisateur:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
    if payload.get("mfa_pending"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA non vérifié")
    user = db.query(Utilisateur).filter(Utilisateur.id_user == int(payload.get("sub"))).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user


def require_permission(permission_nom: str):
    def checker(current_user: Utilisateur = Depends(get_current_user)):
        user_permissions = [p.nom for p in current_user.role.permissions]
        if permission_nom not in user_permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission refusée")
        return current_user
    return checker
