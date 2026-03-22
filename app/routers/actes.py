import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, set_flash
from app import crud
from app.schemas import ActeCreate, ActeUpdate
from app.utils import parse_date

router = APIRouter()


def _validate_acte_form(form_data: dict) -> dict:
    errors = {}
    if not (form_data.get("nom") or "").strip():
        errors["nom"] = "Le nom est obligatoire"
    if not form_data.get("type_acte_id"):
        errors["type_acte_id"] = "Le type d'acte est obligatoire"
    if not (form_data.get("lien_onedrive") or "").strip():
        errors["lien_onedrive"] = "Le lien OneDrive est obligatoire"
    else:
        lien = (form_data.get("lien_onedrive") or "").strip()
        parsed = urlparse(lien)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors["lien_onedrive"] = "L'URL doit commencer par http:// ou https://"
    if not form_data.get("date_production"):
        errors["date_production"] = "La date de production est obligatoire"
    return errors


@router.get("/actes/new", name="acte_new")
async def acte_new(
    request: Request,
    dossier_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    type_actes = crud.get_type_actes(db)
    dossiers, _ = crud.get_dossiers(db, limit=1000)
    return templates.TemplateResponse(
        "pages/actes/form.html",
        make_context(request, current_user,
                     acte=None, is_edit=False,
                     type_actes=type_actes, dossiers=dossiers,
                     preselect_dossier_id=dossier_id, errors={}),
    )


@router.post("/actes", name="acte_create")
async def acte_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    form = await request.form()

    nom = (form.get("nom") or "").strip()
    type_acte_id_raw = form.get("type_acte_id", "")
    lien_onedrive = (form.get("lien_onedrive") or "").strip()
    date_production = parse_date(form.get("date_production", ""))
    dossier_id_raw = form.get("dossier_id", "")
    dossier_id = int(dossier_id_raw) if dossier_id_raw else None
    tag_libelles = [t.strip() for t in form.getlist("tag_libelles") if t.strip()]

    form_data = {
        "nom": nom,
        "type_acte_id": int(type_acte_id_raw) if type_acte_id_raw else None,
        "lien_onedrive": lien_onedrive,
        "date_production": date_production,
    }
    errors = _validate_acte_form(form_data)

    if errors:
        type_actes = crud.get_type_actes(db)
        dossiers, _ = crud.get_dossiers(db, limit=1000)
        return templates.TemplateResponse(
            "pages/actes/form.html",
            make_context(request, current_user,
                         acte=form_data, is_edit=False,
                         type_actes=type_actes, dossiers=dossiers,
                         preselect_dossier_id=dossier_id,
                         errors=errors),
            status_code=422,
        )

    data = ActeCreate(
        nom=nom,
        type_acte_id=int(type_acte_id_raw),
        lien_onedrive=lien_onedrive,
        date_production=date_production,
        dossier_id=dossier_id,
        tag_libelles=tag_libelles,
    )
    acte = crud.create_acte(db, data)

    if dossier_id:
        redirect_url = request.url_for("dossier_detail", id=dossier_id)
    else:
        redirect_url = request.url_for("dossiers_list")

    response = RedirectResponse(url=redirect_url, status_code=303)
    set_flash(response, "Acte créé avec succès", "success")
    return response


@router.get("/actes/tags/autocomplete", name="tags_autocomplete")
async def tags_autocomplete(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not q or len(q) < 1:
        return HTMLResponse("")
    tags = crud.get_tags_autocomplete(db, q)[:8]
    html = "".join(
        f'<div class="tag-suggestion-item">{tag.libelle}</div>'
        for tag in tags
    )
    return HTMLResponse(html)


@router.get("/actes/{id}/edit", name="acte_edit")
async def acte_edit(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    acte = crud.get_acte(db, id)
    if not acte:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Acte introuvable", "error")
        return response
    type_actes = crud.get_type_actes(db)
    dossiers, _ = crud.get_dossiers(db, limit=1000)
    return templates.TemplateResponse(
        "pages/actes/form.html",
        make_context(request, current_user,
                     acte=acte, is_edit=True,
                     type_actes=type_actes, dossiers=dossiers,
                     errors={}),
    )


@router.post("/actes/{id}", name="acte_update")
async def acte_update(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    acte = crud.get_acte(db, id)
    if not acte:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Acte introuvable", "error")
        return response

    form = await request.form()
    nom = (form.get("nom") or "").strip()
    type_acte_id_raw = form.get("type_acte_id", "")
    lien_onedrive = (form.get("lien_onedrive") or "").strip()
    date_production = parse_date(form.get("date_production", ""))
    dossier_id_raw = form.get("dossier_id", "")
    dossier_id = int(dossier_id_raw) if dossier_id_raw else None
    tag_libelles = [t.strip() for t in form.getlist("tag_libelles") if t.strip()]

    form_data = {
        "nom": nom,
        "type_acte_id": int(type_acte_id_raw) if type_acte_id_raw else None,
        "lien_onedrive": lien_onedrive,
        "date_production": date_production,
    }
    errors = _validate_acte_form(form_data)

    if errors:
        type_actes = crud.get_type_actes(db)
        dossiers, _ = crud.get_dossiers(db, limit=1000)
        return templates.TemplateResponse(
            "pages/actes/form.html",
            make_context(request, current_user,
                         acte=form_data, is_edit=True,
                         type_actes=type_actes, dossiers=dossiers,
                         errors=errors),
            status_code=422,
        )

    update_data = ActeUpdate(
        nom=nom,
        type_acte_id=int(type_acte_id_raw) if type_acte_id_raw else None,
        lien_onedrive=lien_onedrive,
        date_production=date_production,
        dossier_id=dossier_id,
        tag_libelles=tag_libelles,
    )
    crud.update_acte(db, id, update_data)

    updated_acte = crud.get_acte(db, id)
    if updated_acte and updated_acte.dossier_id:
        redirect_url = request.url_for("dossier_detail", id=updated_acte.dossier_id)
    else:
        redirect_url = request.url_for("dossiers_list")

    response = RedirectResponse(url=redirect_url, status_code=303)
    set_flash(response, "Acte mis à jour", "success")
    return response


@router.post("/actes/{id}/delete", name="acte_delete")
async def acte_delete(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    crud.delete_acte(db, id)
    response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
    set_flash(response, "Acte supprimé", "success")
    return response
