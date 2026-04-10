from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import require_api_key
from app import crud
from app.schemas import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientResponse], dependencies=[Depends(require_api_key)])
def list_clients(skip: int = 0, limit: int = 20, search: str | None = None, db: Session = Depends(get_db)):
    clients, _ = crud.get_clients(db, skip=skip, limit=limit, search=search)
    return clients


@router.get("/{client_id}", response_model=ClientResponse, dependencies=[Depends(require_api_key)])
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable")
    return client


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    return crud.create_client(db, data)


@router.put("/{client_id}", response_model=ClientResponse, dependencies=[Depends(require_api_key)])
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db)):
    client = crud.update_client(db, client_id, data)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_client(client_id: int, db: Session = Depends(get_db)):
    try:
        deleted = crud.delete_client(db, client_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable")
