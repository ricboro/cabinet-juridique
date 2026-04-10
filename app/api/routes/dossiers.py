import datetime
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import require_api_key
from app import crud
from app.schemas import DossierCreate, DossierUpdate, EcheanceCreate, ClientSimple, AvocatSimple

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


# ---------------------------------------------------------------------------
# Schémas de réponse locaux
# ---------------------------------------------------------------------------

class EcheanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dossier_id: int
    libelle: str
    date: datetime.date


class ActeSimpleApi(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    lien_onedrive: Optional[str] = None
    date_production: datetime.date
    is_generated: bool


class DossierApiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    intitule: str
    contexte: Optional[str] = None
    statut: str
    date_ouverture: datetime.date
    date_cloture: Optional[datetime.date] = None
    honoraire_horaire: Optional[float] = None
    estimation_heures: Optional[float] = None
    client_id: int
    avocat_id: int
    client: Optional[ClientSimple] = None
    avocat: Optional[AvocatSimple] = None
    actes: list[ActeSimpleApi] = []
    echeances: list[EcheanceResponse] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DossierApiResponse], dependencies=[Depends(require_api_key)])
def list_dossiers(
    skip: int = 0,
    limit: int = 20,
    statut: str | None = None,
    client_id: int | None = None,
    avocat_id: int | None = None,
    db: Session = Depends(get_db),
):
    dossiers, _ = crud.get_dossiers(db, skip=skip, limit=limit, statut=statut, client_id=client_id, avocat_id=avocat_id)
    return dossiers


@router.get("/{dossier_id}", response_model=DossierApiResponse, dependencies=[Depends(require_api_key)])
def get_dossier(dossier_id: int, db: Session = Depends(get_db)):
    dossier = crud.get_dossier(db, dossier_id)
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    return dossier


@router.post("", response_model=DossierApiResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_dossier(data: DossierCreate, avocat_id: int, db: Session = Depends(get_db)):
    return crud.create_dossier(db, data, avocat_id=avocat_id)


@router.put("/{dossier_id}", response_model=DossierApiResponse, dependencies=[Depends(require_api_key)])
def update_dossier(dossier_id: int, data: DossierUpdate, db: Session = Depends(get_db)):
    dossier = crud.update_dossier(db, dossier_id, data)
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    return dossier


@router.post("/{dossier_id}/close", response_model=DossierApiResponse, dependencies=[Depends(require_api_key)])
def close_dossier(dossier_id: int, db: Session = Depends(get_db)):
    dossier = crud.close_dossier(db, dossier_id)
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    return dossier


@router.delete("/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_dossier(dossier_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_dossier(db, dossier_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")


@router.post("/{dossier_id}/echeances", response_model=EcheanceResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_echeance(dossier_id: int, data: EcheanceCreate, db: Session = Depends(get_db)):
    dossier = crud.get_dossier(db, dossier_id)
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    return crud.create_echeance(db, dossier_id, data)


@router.delete("/{dossier_id}/echeances/{echeance_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_echeance(dossier_id: int, echeance_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_echeance(db, echeance_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Échéance introuvable")


@router.get("/{dossier_id}/generate", dependencies=[Depends(require_api_key)])
def generate_document(dossier_id: int, template_key: str = "convention_honoraires", db: Session = Depends(get_db)):
    from app.routers.generate import DOCUMENT_TEMPLATES, _render_docx

    dossier = crud.get_dossier(db, dossier_id)
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")

    if template_key not in DOCUMENT_TEMPLATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template inconnu")

    if dossier.honoraire_horaire is None or dossier.estimation_heures is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le taux horaire et l'estimation en heures doivent être renseignés",
        )

    client = dossier.client
    if not client:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Client introuvable sur ce dossier")

    docx_bytes = _render_docx(template_key, dossier, client)

    tmpl_meta = DOCUMENT_TEMPLATES[template_key]
    client_slug = (
        f"{client.prenom}_{client.nom}" if client.type == "personne"
        else (client.raison_sociale or "").replace(" ", "_")
    )
    date_str = datetime.date.today().strftime("%Y%m%d")
    filename = f"{tmpl_meta['filename_prefix']}_{client_slug}_{date_str}.docx"

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
