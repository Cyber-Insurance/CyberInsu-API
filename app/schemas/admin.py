from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    id_role: int


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    id_role: Optional[int] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id_user: int
    email: str
    mfa_enabled: bool
    id_role: int
    role_status: str
    permissions: List[str]
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id_role: int
    status: str
    permissions: List[str]


class PermissionResponse(BaseModel):
    id_permission: int
    nom: str
    description: Optional[str] = None


class RolePermissionsUpdate(BaseModel):
    permission_ids: List[int]


class AuditLogResponse(BaseModel):
    id_log: int
    id_user: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    table_cible: Optional[str] = None
    id_cible: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_users: int
    users_by_role: dict
    total_audit_logs: int
    recent_actions: List[dict]
    mfa_enabled_count: int
