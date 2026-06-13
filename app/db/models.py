from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.db.database import Base


# ─── PLATFORM SETTINGS ──────────────────────────────────────────────────────

class PlatformSettings(Base):
    __tablename__ = "platform_settings"
    id                  = Column(Integer, primary_key=True, default=1)
    app_name            = Column(String(100), default="CyberInsurance")
    maintenance_mode    = Column(Boolean, default=False)
    allow_registrations = Column(Boolean, default=True)
    require_mfa         = Column(Boolean, default=False)
    two_factor_required = Column(Boolean, default=False)
    session_timeout     = Column(Integer, default=30)
    password_policy     = Column(String(20), default="strong")
    max_upload_size     = Column(Integer, default=100)
    backup_frequency    = Column(String(20), default="daily")
    backup_retention    = Column(Integer, default=30)
    email_notifications = Column(Boolean, default=True)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by          = Column(Integer, ForeignKey("utilisateurs.id_user"), nullable=True)


# ─── AUTH & RBAC ────────────────────────────────────────────────────────────

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
    # Dossiers gérés en tant que courtier
    dossiers = relationship("Dossier", foreign_keys="[Dossier.id_user]", back_populates="utilisateur")
    # Dossiers où l'utilisateur est le client
    dossiers_client = relationship("Dossier", foreign_keys="[Dossier.id_client]", back_populates="client_user")


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


# ─── MÉTIER : ENTREPRISES & DOSSIERS ────────────────────────────────────────

class Entreprise(Base):
    __tablename__ = "entreprises"
    id_company = Column(Integer, primary_key=True)
    nom = Column(String(255), nullable=False)
    secteur = Column(String(100))
    taille = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    dossiers = relationship("Dossier", back_populates="entreprise")


class Dossier(Base):
    __tablename__ = "dossiers"
    id_dossier = Column(Integer, primary_key=True)
    status = Column(String(50), default="draft")
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_soumission = Column(DateTime, nullable=True)
    id_company = Column(Integer, ForeignKey("entreprises.id_company"), nullable=False)
    id_user = Column(Integer, ForeignKey("utilisateurs.id_user"), nullable=False)    # courtier
    id_client = Column(Integer, ForeignKey("utilisateurs.id_user"), nullable=True)   # client

    entreprise = relationship("Entreprise", back_populates="dossiers")
    utilisateur = relationship("Utilisateur", foreign_keys=[id_user], back_populates="dossiers")
    client_user = relationship("Utilisateur", foreign_keys=[id_client], back_populates="dossiers_client")
    reponses = relationship("Reponse", back_populates="dossier", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="dossier", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="dossier", cascade="all, delete-orphan")


# ─── QUESTIONNAIRE ──────────────────────────────────────────────────────────

class Questionnaire(Base):
    __tablename__ = "questionnaires"
    id_questionnaire = Column(Integer, primary_key=True)
    nom = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    questions = relationship("Question", back_populates="questionnaire", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    id_question = Column(Integer, primary_key=True)
    texte = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)         # boolean, scale, choix_multiple, text
    categorie = Column(String(100))
    poids = Column(Integer, default=1)
    options = Column(JSONB, nullable=True)            # pour choix_multiple
    inverse = Column(Boolean, default=False)          # score inversé (ex: avez-vous subi une attaque ?)
    condition = Column(JSONB, nullable=True)          # règle d'affichage conditionnel
    ordre = Column(Integer, default=0)               # ordre d'affichage
    section = Column(String(100), default="general") # groupe : profil, infrastructure, securite, gouvernance, incidents
    id_questionnaire = Column(Integer, ForeignKey("questionnaires.id_questionnaire"), nullable=False)

    questionnaire = relationship("Questionnaire", back_populates="questions")
    reponses = relationship("Reponse", back_populates="question", cascade="all, delete-orphan")


class Reponse(Base):
    __tablename__ = "reponses"
    id_reponse = Column(Integer, primary_key=True)
    valeur = Column(Text)
    score = Column(Float, default=0)
    id_question = Column(Integer, ForeignKey("questions.id_question"), nullable=False)
    id_dossier = Column(Integer, ForeignKey("dossiers.id_dossier"), nullable=False)

    question = relationship("Question", back_populates="reponses")
    dossier = relationship("Dossier", back_populates="reponses")


# ─── DOCUMENTS & ANALYSE IA ─────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"
    id_document = Column(Integer, primary_key=True)
    nom = Column(String(255))
    type = Column(String(100))
    url = Column(Text, nullable=False)
    taille_ko = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    id_dossier = Column(Integer, ForeignKey("dossiers.id_dossier"), nullable=False)

    dossier = relationship("Dossier", back_populates="documents")
    analyses = relationship("Analyse", back_populates="document", cascade="all, delete-orphan")


class Analyse(Base):
    __tablename__ = "analyses"
    id_analyse = Column(Integer, primary_key=True)
    resultat = Column(JSONB)
    confidence = Column(Float)
    modele_utilise = Column(String(100))
    date_analyse = Column(DateTime, default=datetime.utcnow)
    id_document = Column(Integer, ForeignKey("documents.id_document"), nullable=False)

    document = relationship("Document", back_populates="analyses")


# ─── SCORING & DEVIS ────────────────────────────────────────────────────────

class Score(Base):
    __tablename__ = "scores"
    id_score = Column(Integer, primary_key=True)
    score_questionnaire = Column(Float, default=0)
    score_document = Column(Float, default=0)
    score_global = Column(Float, default=0)
    niveau_risque = Column(String(50))
    calculated_at = Column(DateTime, default=datetime.utcnow)
    id_dossier = Column(Integer, ForeignKey("dossiers.id_dossier"), nullable=False)

    dossier = relationship("Dossier", back_populates="scores")
    devis = relationship("Devis", back_populates="score", cascade="all, delete-orphan")


class Devis(Base):
    __tablename__ = "devis"
    id_devis = Column(Integer, primary_key=True)
    prime = Column(Float, nullable=False)
    status = Column(String(50), default="en_attente")   # en_attente, valide, rejete
    motif = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    id_score = Column(Integer, ForeignKey("scores.id_score"), nullable=False)

    score = relationship("Score", back_populates="devis")
