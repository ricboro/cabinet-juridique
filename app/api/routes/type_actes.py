from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import require_api_key
from app import crud
from app.schemas import TypeActeResponse

router = APIRouter(prefix="/type-actes", tags=["type-actes"])


class TypeActeCreate(BaseModel):
    libelle: str


@router.get("", response_model=list[TypeActeResponse], dependencies=[Depends(require_api_key)])
def list_type_actes(db: Session = Depends(get_db)):
    rows = crud.get_type_actes_with_count(db)
    result = []
    for type_acte, usage_count in rows:
        item = TypeActeResponse.model_validate(type_acte)
        item.usage_count = usage_count
        result.append(item)
    return result


@router.post("", response_model=TypeActeResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_type_acte(data: TypeActeCreate, db: Session = Depends(get_db)):
    type_acte = crud.create_type_acte(db, data.libelle)
    item = TypeActeResponse.model_validate(type_acte)
    item.usage_count = 0
    return item


@router.delete("/{type_acte_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_type_acte(type_acte_id: int, db: Session = Depends(get_db)):
    try:
        deleted = crud.delete_type_acte(db, type_acte_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Type d'acte introuvable")
