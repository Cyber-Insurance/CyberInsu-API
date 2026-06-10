from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Utilisateur, AuditLog
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.mfa import generate_mfa_secret, generate_qr_base64, verify_totp
from app.core.dependencies import get_current_user
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MFAVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    id_role: int = 3


def log_action(db: Session, id_user: int, action: str, ip: str = None):
    db.add(AuditLog(id_user=id_user, action=action, ip_address=ip))
    db.commit()


@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Utilisateur).filter(Utilisateur.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    if body.id_role in [1, 2]:
        raise HTTPException(status_code=403, detail="Ce rôle ne peut pas s'inscrire publiquement")
    user = Utilisateur(email=body.email, password=hash_password(body.password), id_role=body.id_role)
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, user.id_user, "register")
    return {"message": "Compte créé", "id_user": user.id_user}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    log_action(db, user.id_user, "login", str(request.client.host))
    if user.mfa_enabled:
        temp_token = create_access_token({"sub": str(user.id_user), "mfa_pending": True})
        return TokenResponse(access_token=temp_token, refresh_token="", mfa_required=True)
    access = create_access_token({"sub": str(user.id_user)})
    refresh = create_refresh_token({"sub": str(user.id_user)})
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/verify-mfa", response_model=TokenResponse)
def verify_mfa(body: MFAVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == body.email).first()
    if not user or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA non configuré")
    if not verify_totp(user.mfa_secret, body.code):
        raise HTTPException(status_code=401, detail="Code MFA invalide")
    access = create_access_token({"sub": str(user.id_user)})
    refresh = create_refresh_token({"sub": str(user.id_user)})
    log_action(db, user.id_user, "mfa_verified")
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/setup-mfa", response_model=MFASetupResponse)
def setup_mfa(current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = generate_mfa_secret()
    qr = generate_qr_base64(secret, current_user.email)
    current_user.mfa_secret = secret
    current_user.mfa_enabled = True
    db.commit()
    log_action(db, current_user.id_user, "mfa_setup")
    return MFASetupResponse(secret=secret, qr_code=qr)


@router.get("/me")
def me(current_user: Utilisateur = Depends(get_current_user)):
    return {
        "id_user": current_user.id_user,
        "email": current_user.email,
        "role": current_user.role.status,
        "mfa_enabled": current_user.mfa_enabled,
        "permissions": [p.nom for p in current_user.role.permissions]
    }
