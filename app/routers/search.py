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
    type_acte_id: Optional[str] = None,
    tag: Optional[str] = None,
    client_id: Optional[str] = None,
    avocat_id: Optional[str] = None,
    statut: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    q = q or ""
    type_acte_id = int(type_acte_id) if type_acte_id else None
    client_id    = int(client_id)    if client_id    else None
    avocat_id    = int(avocat_id)    if avocat_id    else None
    tag          = tag.strip()       if tag          else None
    statut       = statut            if statut       else None
    has_filters = any([type_acte_id, tag, client_id, avocat_id, statut])
    if len(q) >= 3 or has_filters:
        results = crud.search(
            db, q,
            type_acte_id=type_acte_id,
            tag=tag,
            client_id=client_id,
            avocat_id=avocat_id,
            statut=statut,
        )
    else:
        results = None  # None = pas encore lancé (différent de "0 résultats")

    type_actes = crud.get_type_actes(db)
    filters = {
        "type_acte_id": type_acte_id,
        "tag": tag,
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
    type_acte_id: Optional[str] = None,
    tag: Optional[str] = None,
    client_id: Optional[str] = None,
    avocat_id: Optional[str] = None,
    statut: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    q = q or ""
    type_acte_id = int(type_acte_id) if type_acte_id else None
    client_id    = int(client_id)    if client_id    else None
    avocat_id    = int(avocat_id)    if avocat_id    else None
    tag          = tag.strip()       if tag          else None
    statut       = statut            if statut       else None
    has_filters = any([type_acte_id, tag, client_id, avocat_id, statut])
    if len(q) >= 3 or has_filters:
        results = crud.search(
            db, q,
            type_acte_id=type_acte_id,
            tag=tag,
            client_id=client_id,
            avocat_id=avocat_id,
            statut=statut,
        )
    else:
        results = None

    filters = {
        "type_acte_id": type_acte_id,
        "tag": tag,
        "statut": statut,
    }
    return templates.TemplateResponse(
        "partials/search_results.html",
        make_context(request, current_user,
                     q=q, results=results, filters=filters),
    )
