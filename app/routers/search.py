from typing import Optional

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app import crud
from app.models import Avocat

router = APIRouter()


@router.get("/search", name="search_page")
async def search_page(
    request: Request,
    q: Optional[str] = None,
    type_acte_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    client_id: Optional[int] = None,
    avocat_id: Optional[int] = None,
    statut: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    q = q or ""
    if q and len(q) >= 3:
        results = crud.search(
            db, q,
            type_acte_id=type_acte_id,
            tag_id=tag_id,
            client_id=client_id,
            avocat_id=avocat_id,
            statut=statut,
        )
    else:
        results = {"dossiers": [], "actes": []}

    type_actes = crud.get_type_actes(db)
    filters = {
        "type_acte_id": type_acte_id,
        "tag_id": tag_id,
        "client_id": client_id,
        "avocat_id": avocat_id,
        "statut": statut,
    }
    return templates.TemplateResponse(
        "pages/search.html",
        make_context(request, current_user,
                     q=q, results=results,
                     type_actes=type_actes, filters=filters),
    )


@router.get("/search/htmx", name="search_htmx")
async def search_htmx(
    request: Request,
    q: Optional[str] = None,
    type_acte_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    client_id: Optional[int] = None,
    avocat_id: Optional[int] = None,
    statut: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    q = q or ""
    if q and len(q) >= 3:
        results = crud.search(
            db, q,
            type_acte_id=type_acte_id,
            tag_id=tag_id,
            client_id=client_id,
            avocat_id=avocat_id,
            statut=statut,
        )
    else:
        results = {"dossiers": [], "actes": []}

    return templates.TemplateResponse(
        "partials/search_results.html",
        make_context(request, current_user,
                     q=q, results=results, filters={}),
    )
