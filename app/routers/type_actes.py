from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, set_flash
from app import crud

router = APIRouter()


@router.get("/type-actes", name="type_actes_list")
async def type_actes_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.main import templates, make_context

    rows = crud.get_type_actes_with_count(db)
    # Construire des objets hybrides pour garder la compatibilité du template (ta.libelle, ta.id, ta.usage_count)
    type_actes = []
    for ta, count in rows:
        ta.usage_count = count
        type_actes.append(ta)

    return templates.TemplateResponse(
        "pages/type_actes/list.html",
        make_context(request, current_user, type_actes=type_actes, error=None),
    )


@router.post("/type-actes", name="type_acte_create")
async def type_acte_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    form = await request.form()
    libelle = (form.get("libelle") or "").strip()

    if not libelle:
        response = RedirectResponse(url=request.url_for("type_actes_list"), status_code=303)
        set_flash(response, "Le libellé est obligatoire", "error")
        return response

    # Vérifier existence
    existing = crud.get_type_actes(db)
    if any(ta.libelle.lower() == libelle.lower() for ta in existing):
        response = RedirectResponse(url=request.url_for("type_actes_list"), status_code=303)
        set_flash(response, f"Le type '{libelle}' existe déjà", "error")
        return response

    crud.create_type_acte(db, libelle)
    response = RedirectResponse(url=request.url_for("type_actes_list"), status_code=303)
    set_flash(response, f"Type d'acte '{libelle}' créé", "success")
    return response


@router.post("/type-actes/{id}/delete", name="type_acte_delete")
async def type_acte_delete(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        crud.delete_type_acte(db, id)
        response = RedirectResponse(url=request.url_for("type_actes_list"), status_code=303)
        set_flash(response, "Type d'acte supprimé", "success")
        return response
    except ValueError as e:
        response = RedirectResponse(url=request.url_for("type_actes_list"), status_code=303)
        set_flash(response, str(e), "error")
        return response
