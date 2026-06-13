from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class QuestionItem(BaseModel):
    id_question: int
    texte: str
    type: str
    categorie: Optional[str] = None
    poids: int = 1
    options: Optional[List[str]] = None
    inverse: bool = False
    # Adaptive questionnaire fields
    condition: Optional[Dict[str, Any]] = None
    ordre: int = 0
    section: str = "general"
    visible: bool = True
    contexte_hint: Optional[str] = None


class QuestionnaireResponse(BaseModel):
    id_questionnaire: int
    nom: str
    version: str
    questions: List[QuestionItem]
    reponses_existantes: Dict[int, str] = {}
    secteur: Optional[str] = None
    taille: Optional[str] = None


class ReponseItem(BaseModel):
    id_question: int
    valeur: str


class SoumettreReponses(BaseModel):
    reponses: List[ReponseItem]


class EvaluateRequest(BaseModel):
    reponses: Dict[str, str]  # JSON keys are always strings


class EvaluateResponse(BaseModel):
    visibility: Dict[str, bool]
    maturity: str
    visible_count: int


class ScoreResult(BaseModel):
    score_questionnaire: float
    score_global: float
    niveau_risque: str
    message: str


class DocumentItem(BaseModel):
    id_document: int
    nom: Optional[str] = None
    type: Optional[str] = None
    taille_ko: Optional[int] = None
    uploaded_at: Optional[str] = None


class DossierOverview(BaseModel):
    id: int
    company: str
    secteur: Optional[str] = None
    taille: Optional[str] = None
    status: str
    score: Optional[float] = None
    niveau_risque: Optional[str] = None
    date_creation: Optional[str] = None
    date_soumission: Optional[str] = None
    questionnaire_complete: bool
    documents_count: int
    devis: Optional[dict] = None
