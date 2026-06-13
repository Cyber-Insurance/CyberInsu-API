from pydantic import BaseModel, EmailStr
from typing import Optional, List


class EntrepriseCreate(BaseModel):
    nom: str
    secteur: Optional[str] = None
    taille: Optional[str] = None


class DossierCreate(BaseModel):
    entreprise: EntrepriseCreate
    client_email: Optional[EmailStr] = None


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
    client_email: Optional[str] = None
    questionnaire_complete: bool = False
    documents_count: int = 0


class DossierListResponse(BaseModel):
    total: int
    dossiers: List[DossierItem]


class ClientItem(BaseModel):
    id_user: int
    email: str
    dossier_id: Optional[int] = None
    company: Optional[str] = None
    dossier_status: Optional[str] = None
    created_at: Optional[str] = None


class ClientListResponse(BaseModel):
    total: int
    clients: List[ClientItem]


class InviteClientRequest(BaseModel):
    email: EmailStr
    password: str
    dossier_id: int


class StatsResponse(BaseModel):
    total_dossiers: int
    dossiers_actifs: int
    devis_envoyes: int
    clients_actifs: int
    score_moyen: float
    repartition: dict
    recent_dossiers: List[dict]
