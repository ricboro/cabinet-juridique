"""
Router : génération de documents depuis templates DOCX (docxtpl).

Routes :
  GET  /dossiers/{id}/generate          → formulaire de génération
  POST /dossiers/{id}/generate          → crée l'acte + redirect dossier
  GET  /actes/{id}/download             → régénère et sert le DOCX
"""
import datetime
import io
from pathlib import Path
from typing import Optional

from docxtpl import DocxTemplate
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, set_flash
from app import crud
from app.schemas import ActeCreate

router = APIRouter()

# Registre des templates disponibles
# Clé = identifiant interne, valeur = métadonnées
DOCUMENT_TEMPLATES = {
    "convention_honoraires": {
        "label": "Convention d'honoraires",
        "file": Path("Template/convention_honoraires_template.docx"),
        "type_acte_libelle": "Convention d'honoraires",
        "filename_prefix": "Convention_honoraires",
    },
}


def _build_docx_context(dossier, client) -> dict:
    """Construit le dictionnaire de variables pour le template docxtpl."""
    today = datetime.date.today().strftime("%d/%m/%Y")

    if client.type == "personne":
        titre = client.titre or ""
        client_line1 = f"{titre} {client.prenom} {client.nom}".strip()
        profession = client.profession or ""
        specialite = client.specialite or ""
        client_line2 = profession
        if specialite:
            client_line2 += f" - {specialite}"
        client_line3 = ""
    else:
        client_line1 = client.raison_sociale or ""
        repr_prenom = client.representant_prenom or ""
        repr_nom = client.representant_nom or ""
        client_line2 = f"Représentée par {repr_prenom} {repr_nom}".strip()
        client_line3 = f"SIRET\xa0: {client.siret}" if client.siret else ""

    taux = dossier.honoraire_horaire or 0
    heures = dossier.estimation_heures or 0
    total = round(taux * heures, 2)

    return {
        "client_line1": client_line1,
        "client_line2": client_line2,
        "client_line3": client_line3,
        "adresse": client.adresse or "",
        "mail": client.email or "",
        "telephone": client.telephone or "",
        "taux_horaire": f"{taux:g}",
        "nb_heure_estimation": f"{heures:g}",
        "estimation_total": f"{total:g}",
        "date_creation": today,
    }


def _render_docx(template_key: str, dossier, client) -> bytes:
    """Rend le template DOCX et retourne les bytes du fichier généré."""
    tmpl_meta = DOCUMENT_TEMPLATES[template_key]
    tpl = DocxTemplate(tmpl_meta["file"])
    context = _build_docx_context(dossier, client)
    tpl.render(context)
    buf = io.BytesIO()
    tpl.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# GET : formulaire de génération
# ---------------------------------------------------------------------------

@router.get("/dossiers/{id}/generate", name="generate_form")
async def generate_form(
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

    # Vérifier que les honoraires sont renseignés
    errors = {}
    if dossier.honoraire_horaire is None:
        errors["honoraire_horaire"] = "Le taux horaire doit être renseigné sur le dossier avant de générer un document."
    if dossier.estimation_heures is None:
        errors["estimation_heures"] = "L'estimation en heures doit être renseignée sur le dossier."

    return templates.TemplateResponse(
        "pages/generate/form.html",
        make_context(request, current_user,
                     dossier=dossier,
                     document_templates=DOCUMENT_TEMPLATES,
                     errors=errors),
    )


# ---------------------------------------------------------------------------
# POST : création de l'acte + redirect
# ---------------------------------------------------------------------------

@router.post("/dossiers/{id}/generate", name="generate_doc")
async def generate_doc(
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

    form = await request.form()
    nom = (form.get("nom") or "").strip()
    template_key = (form.get("template_key") or "").strip()

    from app.main import templates, make_context

    errors = {}
    if not nom:
        errors["nom"] = "Le nom de l'acte est obligatoire"
    if not template_key or template_key not in DOCUMENT_TEMPLATES:
        errors["template_key"] = "Veuillez sélectionner un type de document"
    if dossier.honoraire_horaire is None:
        errors["honoraire_horaire"] = "Le taux horaire doit être renseigné sur le dossier."
    if dossier.estimation_heures is None:
        errors["estimation_heures"] = "L'estimation en heures doit être renseignée sur le dossier."

    if errors:
        return templates.TemplateResponse(
            "pages/generate/form.html",
            make_context(request, current_user,
                         dossier=dossier,
                         document_templates=DOCUMENT_TEMPLATES,
                         errors=errors,
                         form_nom=nom,
                         form_template_key=template_key),
            status_code=422,
        )

    # Récupérer ou créer le type d'acte
    tmpl_meta = DOCUMENT_TEMPLATES[template_key]
    type_acte = next(
        (t for t in crud.get_type_actes(db) if t.libelle == tmpl_meta["type_acte_libelle"]),
        None,
    )
    if not type_acte:
        type_acte = crud.create_type_acte(db, tmpl_meta["type_acte_libelle"])

    # Créer l'acte avec lien vide et is_generated=True
    data = ActeCreate(
        nom=nom,
        type_acte_id=type_acte.id,
        lien_onedrive=None,
        date_production=datetime.date.today(),
        dossier_id=dossier.id,
        is_generated=True,
    )
    acte = crud.create_acte(db, data)

    response = RedirectResponse(
        url=request.url_for("dossier_detail", id=dossier.id),
        status_code=303,
    )
    set_flash(
        response,
        f"Acte « {nom} » créé. Téléchargez-le depuis la fiche dossier, "
        "puis uploadez-le sur OneDrive et renseignez le lien.",
        "success",
    )
    return response


# ---------------------------------------------------------------------------
# GET : téléchargement du DOCX (régénéré à la demande)
# ---------------------------------------------------------------------------

@router.get("/actes/{id}/download", name="acte_download")
async def acte_download(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    acte = crud.get_acte(db, id)
    if not acte or not acte.is_generated:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Document introuvable", "error")
        return response

    dossier = acte.dossier
    client = dossier.client if dossier else None
    if not dossier or not client:
        response = RedirectResponse(url=request.url_for("dossiers_list"), status_code=303)
        set_flash(response, "Dossier ou client introuvable", "error")
        return response

    # Déterminer le template depuis le type d'acte
    template_key = next(
        (k for k, v in DOCUMENT_TEMPLATES.items()
         if acte.type_acte and v["type_acte_libelle"] == acte.type_acte.libelle),
        None,
    )
    if not template_key:
        response = RedirectResponse(
            url=request.url_for("dossier_detail", id=dossier.id), status_code=303
        )
        set_flash(response, "Template introuvable pour ce type d'acte", "error")
        return response

    docx_bytes = _render_docx(template_key, dossier, client)

    # Nom du fichier : préfixe + nom client + date
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
