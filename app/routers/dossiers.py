import math
import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, set_flash
from app import crud
from app.schemas import DossierCreate, DossierUpdate, EcheanceCreate
from app.utils import parse_date

router = APIRouter()


def _parse_dossier_form(form) -> dict:
    return {
        "intitule": (form.get("intitule") or "").strip(),
        "contexte": (form.get("contexte") or "").strip() or None,
        "statut": (form.get("statut") or "en_cours").strip() or "en_cours",
        "date_ouverture": parse_date(form.get("date_ouverture", "")),
        "date_cloture": parse_date(form.get("date_cloture", "")),
        "client_id": int(form.get("client_id", 0)) if form.get("client_id") else None,
        "avocat_id": int(form.get("avocat_id", 0)) if form.get("avocat_id") else None,
    }


def _validate_dossier_form(form_data: dict) -> dict:
    errors = {}
    if not (form_data.get("intitule") or "").strip():
        errors["intitule"] = "L'intitulé est obligatoire"
    if not form_data.get("date_ouverture"):
        errors["date_ouverture"] = "La date d'ouverture est obligatoire"
    if not form_data.get("client_id"):
        errors["client_id"] = "Le client est obligatoire"
    return errors


@router.get("/dossiers", name="dossiers_list")
async def dossiers_list(
    request: Request,
    page: int = 1,
    statut: Optional[str] = None,
    client_id: Optional[str] = None,
    avocat_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    client_id_int = int(client_id) if client_id and client_id.strip() else None
    avocat_id_int = int(avocat_id) if avocat_id and avocat_id.strip() else None
    statut_val = statut if statut and statut.strip() else None
    limit = 20
    skip = (page - 1) * limit
    dossiers, total = crud.get_dossiers(
        db, skip=skip, limit=limit, statut=statut_val,
        client_id=client_id_int, avocat_id=avocat_id_int,
    )
    pages = math.ceil(total / limit) if total > 0 else 1
    clients, _ = crud.get_clients(db, limit=1000)
    avocats = crud.get_avocats(db)
    filters = {
        "statut": statut_val,
        "client_id": client_id_int,
        "avocat_id": avocat_id_int,
    }
    return templates.TemplateResponse(
        "pages/dossiers/list.html",
        make_context(request, current_user,
                     dossiers=dossiers, total=total, page=page, pages=pages,
                     clients=clients, avocats=avocats, filters=filters),
    )


@router.get("/dossiers/new", name="dossier_new")
async def dossier_new(
    request: Request,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    clients, _ = crud.get_clients(db, limit=1000)
    avocats = crud.get_avocats(db)
    return templates.TemplateResponse(
        "pages/dossiers/form.html",
        make_context(request, current_user,
                     dossier=None, is_edit=False,
                     clients=clients, avocats=avocats,
                     errors={}, preselect_client_id=client_id),
    )


@router.post("/dossiers", name="dossier_create")
async def dossier_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    form = await request.form()
    form_data = _parse_dossier_form(form)
    errors = _validate_dossier_form(form_data)

    if errors:
        clients, _ = crud.get_clients(db, limit=1000)
        avocats = crud.get_avocats(db)
        return templates.TemplateResponse(
            "pages/dossiers/form.html",
            make_context(request, current_user,
                         dossier=form_data, is_edit=False,
                         clients=clients, avocats=avocats,
                         errors=errors, preselect_client_id=None),
            status_code=422,
        )

    avocat_id = form_data.pop("avocat_id", None) or current_user.id
    data = DossierCreate(**{k: v for k, v in form_data.items()})
    dossier = crud.create_dossier(db, data, avocat_id=avocat_id)
    response = RedirectResponse(
        url=request.url_for("dossier_detail", id=dossier.id),
        status_code=303,
    )
    set_flash(response, "Dossier créé avec succès", "success")
    return response


@router.get("/dossiers/{id}", name="dossier_detail")
async def dossier_detail(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    dossier = crud.get_dossier(db, id)
    if not dossier:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier introuvable", "error")
        return response
    actes = dossier.actes
    return templates.TemplateResponse(
        "pages/dossiers/detail.html",
        make_context(request, current_user, dossier=dossier, actes=actes),
    )


@router.get("/dossiers/{id}/edit", name="dossier_edit")
async def dossier_edit(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    dossier = crud.get_dossier(db, id)
    if not dossier:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier introuvable", "error")
        return response
    clients, _ = crud.get_clients(db, limit=1000)
    avocats = crud.get_avocats(db)
    return templates.TemplateResponse(
        "pages/dossiers/form.html",
        make_context(request, current_user,
                     dossier=dossier, is_edit=True,
                     clients=clients, avocats=avocats,
                     errors={}, preselect_client_id=None),
    )


@router.post("/dossiers/{id}", name="dossier_update")
async def dossier_update(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    dossier = crud.get_dossier(db, id)
    if not dossier:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier introuvable", "error")
        return response

    form = await request.form()
    form_data = _parse_dossier_form(form)
    errors = _validate_dossier_form(form_data)

    if errors:
        clients, _ = crud.get_clients(db, limit=1000)
        avocats = crud.get_avocats(db)
        return templates.TemplateResponse(
            "pages/dossiers/form.html",
            make_context(request, current_user,
                         dossier=form_data, is_edit=True,
                         clients=clients, avocats=avocats,
                         errors=errors, preselect_client_id=None),
            status_code=422,
        )

    update_data = {k: v for k, v in form_data.items() if k != "avocat_id"}
    crud.update_dossier(db, id, DossierUpdate(**update_data))
    response = RedirectResponse(
        url=request.url_for("dossier_detail", id=id),
        status_code=303,
    )
    set_flash(response, "Dossier mis à jour", "success")
    return response


@router.post("/dossiers/{id}/close", name="dossier_close")
async def dossier_close(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dossier = crud.get_dossier(db, id)
    if not dossier:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier introuvable", "error")
        return response
    crud.close_dossier(db, id)
    response = RedirectResponse(
        url=request.url_for("dossier_detail", id=id),
        status_code=303,
    )
    set_flash(response, "Dossier clôturé", "success")
    return response


@router.post("/dossiers/{id}/echeances", name="echeance_create")
async def echeance_create(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context
    dossier = crud.get_dossier(db, id)
    if not dossier:
        return RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
    form = await request.form()
    libelle = (form.get("libelle") or "").strip()
    date = parse_date(form.get("date", ""))
    if libelle and date:
        crud.create_echeance(db, id, EcheanceCreate(libelle=libelle, date=date))
    db.refresh(dossier)
    # Si requête HTMX → renvoyer le partial ; sinon → rediriger vers la fiche
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/echeances.html",
            make_context(request, current_user, dossier=dossier),
        )
    return RedirectResponse(url=request.url_for("dossier_detail", id=id), status_code=303)


@router.post("/dossiers/{id}/echeances/{eid}/delete", name="echeance_delete")
async def echeance_delete(
    id: int,
    eid: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dossier = crud.get_dossier(db, id)
    if not dossier:
        return RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
    crud.delete_echeance(db, eid)
    # Rediriger vers la page d'édition pour rester dans le contexte de modification
    return RedirectResponse(url=request.url_for("dossier_edit", id=id), status_code=303)


@router.post("/dossiers/{id}/delete", name="dossier_delete")
async def dossier_delete(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dossier = crud.get_dossier(db, id)
    if not dossier:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier introuvable", "error")
        return response
    crud.delete_dossier(db, id)
    response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
    set_flash(response, "Dossier supprimé", "success")
    return response
