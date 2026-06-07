from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.db.database import Base


class Role(Base):
    __tablename__ = "roles"
    id_role = Column(Integer, primary_key=True)
    status = Column(String(50), unique=True, nullable=False)
    utilisateurs = relationship("Utilisateur", back_populates="role")
    permissions = relationship("Permission", secondary="roles_permissions", back_populates="roles")


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id_user = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    id_role = Column(Integer, ForeignKey("roles.id_role"))
    role = relationship("Role", back_populates="utilisateurs")


class Permission(Base):
    __tablename__ = "permissions"
    id_permission = Column(Integer, primary_key=True)
    nom = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    roles = relationship("Role", secondary="roles_permissions", back_populates="permissions")


class RolePermission(Base):
    __tablename__ = "roles_permissions"
    id_role = Column(Integer, ForeignKey("roles.id_role"), primary_key=True)
    id_permission = Column(Integer, ForeignKey("permissions.id_permission"), primary_key=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id_log = Column(Integer, primary_key=True)
    id_user = Column(Integer, ForeignKey("utilisateurs.id_user"), nullable=True)
    action = Column(String(100), nullable=False)
    table_cible = Column(String(50))
    id_cible = Column(Integer)
    details = Column(JSONB)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)
