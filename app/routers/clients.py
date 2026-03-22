import math
import re
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, set_flash
from app import crud
from app.schemas import ClientCreate, ClientUpdate

router = APIRouter()


def _validate_client_form(form_data: dict) -> dict:
    errors = {}
    client_type = form_data.get("type", "")
    if client_type == "personne":
        if not (form_data.get("nom") or "").strip():
            errors["nom"] = "Le nom est obligatoire"
        if not (form_data.get("prenom") or "").strip():
            errors["prenom"] = "Le prénom est obligatoire"
    elif client_type == "societe":
        if not (form_data.get("raison_sociale") or "").strip():
            errors["raison_sociale"] = "La raison sociale est obligatoire"
    else:
        errors["type"] = "Le type de client est obligatoire"

    email = (form_data.get("email") or "").strip()
    if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        errors["email"] = "Format d'email invalide"

    return errors


def _parse_client_form(form) -> dict:
    return {
        "type": form.get("type", "").strip(),
        "nom": form.get("nom", "").strip() or None,
        "prenom": form.get("prenom", "").strip() or None,
        "raison_sociale": form.get("raison_sociale", "").strip() or None,
        "siret": form.get("siret", "").strip() or None,
        "email": form.get("email", "").strip() or None,
        "telephone": form.get("telephone", "").strip() or None,
        "adresse": form.get("adresse", "").strip() or None,
    }


@router.get("/clients", name="clients_list")
async def clients_list(
    request: Request,
    page: int = 1,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    limit = 20
    skip = (page - 1) * limit
    clients, total = crud.get_clients(db, skip=skip, limit=limit, search=search)
    pages = math.ceil(total / limit) if total > 0 else 1
    return templates.TemplateResponse(
        "pages/clients/list.html",
        make_context(request, current_user,
                     clients=clients, total=total, page=page,
                     pages=pages, search=search or ""),
    )


@router.get("/clients/new", name="client_new")
async def client_new(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    return templates.TemplateResponse(
        "pages/clients/form.html",
        make_context(request, current_user, client=None, is_edit=False, errors={}),
    )


@router.post("/clients", name="client_create")
async def client_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    form = await request.form()
    form_data = _parse_client_form(form)
    errors = _validate_client_form(form_data)

    if errors:
        return templates.TemplateResponse(
            "pages/clients/form.html",
            make_context(request, current_user, client=form_data,
                         is_edit=False, errors=errors),
            status_code=422,
        )

    client = crud.create_client(db, ClientCreate(**form_data))
    response = RedirectResponse(
        url=request.url_for("client_detail", id=client.id),
        status_code=303,
    )
    set_flash(response, "Client créé avec succès", "success")
    return response


@router.get("/clients/{id}", name="client_detail")
async def client_detail(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    client = crud.get_client(db, id)
    if not client:
        response = RedirectResponse(url=request.url_for("clients_list"), status_code=303)
        set_flash(response, "Client introuvable", "error")
        return response
    dossiers, _ = crud.get_dossiers(db, client_id=id, limit=100)
    return templates.TemplateResponse(
        "pages/clients/detail.html",
        make_context(request, current_user, client=client, dossiers=dossiers),
    )


@router.get("/clients/{id}/edit", name="client_edit")
async def client_edit(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    client = crud.get_client(db, id)
    if not client:
        response = RedirectResponse(url=request.url_for("clients_list"), status_code=303)
        set_flash(response, "Client introuvable", "error")
        return response
    return templates.TemplateResponse(
        "pages/clients/form.html",
        make_context(request, current_user, client=client, is_edit=True, errors={}),
    )


@router.post("/clients/{id}", name="client_update")
async def client_update(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    client = crud.get_client(db, id)
    if not client:
        response = RedirectResponse(url=request.url_for("clients_list"), status_code=303)
        set_flash(response, "Client introuvable", "error")
        return response

    form = await request.form()
    form_data = _parse_client_form(form)
    errors = _validate_client_form(form_data)

    if errors:
        return templates.TemplateResponse(
            "pages/clients/form.html",
            make_context(request, current_user, client=form_data,
                         is_edit=True, errors=errors),
            status_code=422,
        )

    crud.update_client(db, id, ClientUpdate(**form_data))
    response = RedirectResponse(
        url=request.url_for("client_detail", id=id),
        status_code=303,
    )
    set_flash(response, "Client mis à jour", "success")
    return response


@router.post("/clients/{id}/delete", name="client_delete")
async def client_delete(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    client = crud.get_client(db, id)
    if not client:
        response = RedirectResponse(url=request.url_for("clients_list"), status_code=303)
        set_flash(response, "Client introuvable", "error")
        return response
    try:
        crud.delete_client(db, id)
        response = RedirectResponse(url=request.url_for("clients_list"), status_code=303)
        set_flash(response, "Client supprimé", "success")
        return response
    except ValueError as e:
        response = RedirectResponse(
            url=request.url_for("client_detail", id=id),
            status_code=303,
        )
        set_flash(response, str(e), "error")
        return response
