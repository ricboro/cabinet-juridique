from __future__ import annotations
import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


# ---------------------------------------------------------------------------
# Avocat
# ---------------------------------------------------------------------------

class AvocatBase(BaseModel):
    nom: str
    prenom: str
    email: EmailStr


class AvocatCreate(AvocatBase):
    password: str


class AvocatResponse(AvocatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ClientBase(BaseModel):
    type: str
    nom: Optional[str] = None
    prenom: Optional[str] = None
    raison_sociale: Optional[str] = None
    siret: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    type: Optional[str] = None
    nom: Optional[str] = None
    prenom: Optional[str] = None
    raison_sociale: Optional[str] = None
    siret: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None


class DossierSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    intitule: str
    statut: str


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_creation: Optional[datetime.datetime] = None
    dossiers: list[DossierSimple] = []


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------

class DossierBase(BaseModel):
    intitule: str
    contexte: Optional[str] = None
    statut: Optional[str] = "en_cours"
    date_ouverture: datetime.date
    date_cloture: Optional[datetime.date] = None
    client_id: int


class DossierCreate(DossierBase):
    pass


class DossierUpdate(BaseModel):
    intitule: Optional[str] = None
    contexte: Optional[str] = None
    statut: Optional[str] = None
    date_ouverture: Optional[datetime.date] = None
    date_cloture: Optional[datetime.date] = None
    client_id: Optional[int] = None


class EcheanceCreate(BaseModel):
    libelle: str
    date: datetime.date


class AvocatSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str


class ActeSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    lien_onedrive: str
    date_production: datetime.date


class DossierResponse(DossierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    avocat_id: int
    client: Optional[ClientBase] = None
    avocat: Optional[AvocatSimple] = None
    actes: list[ActeSimple] = []


# ---------------------------------------------------------------------------
# TypeActe
# ---------------------------------------------------------------------------

class TypeActeBase(BaseModel):
    libelle: str


class TypeActeCreate(TypeActeBase):
    pass


class TypeActeResponse(TypeActeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usage_count: int = 0


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------

class TagBase(BaseModel):
    libelle: str


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Acte
# ---------------------------------------------------------------------------

class ActeBase(BaseModel):
    nom: str
    type_acte_id: int
    lien_onedrive: str
    date_production: datetime.date


class ActeCreate(ActeBase):
    dossier_id: Optional[int] = None
    tag_ids: list[int] = []
    tag_libelles: list[str] = []


class ActeUpdate(BaseModel):
    nom: Optional[str] = None
    type_acte_id: Optional[int] = None
    lien_onedrive: Optional[str] = None
    date_production: Optional[datetime.date] = None
    dossier_id: Optional[int] = None
    tag_ids: Optional[list[int]] = None
    tag_libelles: Optional[list[str]] = None


class TypeActeSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    libelle: str


class ActeResponse(ActeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_acte: Optional[TypeActeSimple] = None
    dossier: Optional[DossierSimple] = None
    tags: list[TagResponse] = []


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    dossiers: list[DossierResponse]
    actes: list[ActeResponse]
