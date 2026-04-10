import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import require_api_key
from app import crud
from app.schemas import ActeCreate, ActeUpdate, TypeActeSimple, DossierSimple, TagResponse

router = APIRouter(prefix="/actes", tags=["actes"])


class ActeApiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    type_acte_id: int
    lien_onedrive: Optional[str] = None
    date_production: datetime.date
    is_generated: bool
    dossier_id: Optional[int] = None
    type_acte: Optional[TypeActeSimple] = None
    dossier: Optional[DossierSimple] = None
    tags: list[TagResponse] = []


def _serialize(acte) -> ActeApiResponse:
    tags = [TagResponse.model_validate(at.tag) for at in acte.acte_tags]
    data = ActeApiResponse.model_validate(acte)
    data.tags = tags
    return data


@router.get("/{acte_id}", response_model=ActeApiResponse, dependencies=[Depends(require_api_key)])
def get_acte(acte_id: int, db: Session = Depends(get_db)):
    acte = crud.get_acte(db, acte_id)
    if not acte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acte introuvable")
    return _serialize(acte)


@router.post("", response_model=ActeApiResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_acte(data: ActeCreate, db: Session = Depends(get_db)):
    acte = crud.create_acte(db, data)
    return _serialize(acte)


@router.put("/{acte_id}", response_model=ActeApiResponse, dependencies=[Depends(require_api_key)])
def update_acte(acte_id: int, data: ActeUpdate, db: Session = Depends(get_db)):
    acte = crud.update_acte(db, acte_id, data)
    if not acte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acte introuvable")
    return _serialize(acte)


@router.delete("/{acte_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_acte(acte_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_acte(db, acte_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acte introuvable")
