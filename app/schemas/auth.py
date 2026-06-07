from pydantic import BaseModel, EmailStr


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
