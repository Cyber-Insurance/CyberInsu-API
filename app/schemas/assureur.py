from pydantic import BaseModel
from typing import Optional, List


class RecentDossier(BaseModel):
    id: int
    company: str
    status: str
    score: Optional[float] = None
    date: Optional[str] = None


class StatsResponse(BaseModel):
    total_dossiers: int
    a_valider: int
    valides: int
    rejetes: int
    score_moyen: float
    recent_dossiers: List[RecentDossier]


class DossierItem(BaseModel):
    id: int
    company: str
    secteur: Optional[str] = None
    taille: Optional[str] = None
    status: str
    score: Optional[float] = None
    niveau_risque: Optional[str] = None
    date_creation: Optional[str] = None
    date_soumission: Optional[str] = None


class DossierListResponse(BaseModel):
    total: int
    dossiers: List[DossierItem]


class ScoreResponse(BaseModel):
    score_questionnaire: float
    score_document: float
    score_global: float
    niveau_risque: Optional[str] = None
    calculated_at: Optional[str] = None


class DevisItem(BaseModel):
    id: int
    dossier_id: Optional[int] = None
    company: str
    prime: float
    status: str
    score: Optional[float] = None
    niveau_risque: Optional[str] = None
    date: Optional[str] = None


class DevisListResponse(BaseModel):
    total: int
    devis: List[DevisItem]


class RejeterRequest(BaseModel):
    motif: Optional[str] = None
