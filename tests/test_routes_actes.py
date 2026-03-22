import datetime
import pytest
from fastapi.testclient import TestClient
from tests.conftest import set_auth_cookie


def auth_client(client, avocat):
    return set_auth_cookie(client, avocat)


@pytest.fixture
def acte(db, dossier, type_acte):
    from app.schemas import ActeCreate
    from app import crud
    data = ActeCreate(
        nom="Contrat de bail",
        type_acte_id=type_acte.id,
        lien_onedrive="https://onedrive.example.com/bail",
        date_production=datetime.date.today(),
        dossier_ids=[dossier.id],
        tag_libelles=["bail"],
    )
    return crud.create_acte(db, data)


def test_acte_new_form(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/actes/new")
    assert resp.status_code == 200


def test_acte_create_single_dossier(client, avocat, dossier, type_acte):
    auth_client(client, avocat)
    resp = client.post(
        "/actes",
        data={
            "nom": "Assignation civile",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "https://onedrive.example.com/assignation",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_create_multiple_dossiers(client, avocat, dossier, type_acte, client_personne, db):
    auth_client(client, avocat)
    # Créer un second dossier
    from app.schemas import DossierCreate
    from app import crud
    dossier2 = crud.create_dossier(db, DossierCreate(
        intitule="Second dossier",
        statut="en_cours",
        date_ouverture=datetime.date.today(),
        client_id=client_personne.id,
    ), avocat_id=avocat.id)

    # httpx multi-value form data : encoder manuellement en application/x-www-form-urlencoded
    from urllib.parse import urlencode
    form_data = [
        ("nom", "Acte multi-dossiers"),
        ("type_acte_id", str(type_acte.id)),
        ("lien_onedrive", "https://onedrive.example.com/multi"),
        ("date_production", str(datetime.date.today())),
        ("dossier_ids", str(dossier.id)),
        ("dossier_ids", str(dossier2.id)),
    ]
    resp = client.post(
        "/actes",
        content=urlencode(form_data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_create_with_tag(client, avocat, dossier, type_acte):
    auth_client(client, avocat)
    from urllib.parse import urlencode
    form_data = [
        ("nom", "Acte avec tag"),
        ("type_acte_id", str(type_acte.id)),
        ("lien_onedrive", "https://onedrive.example.com/tag"),
        ("date_production", str(datetime.date.today())),
        ("dossier_ids", str(dossier.id)),
        ("tag_libelles", "urgent"),
        ("tag_libelles", "important"),
    ]
    resp = client.post(
        "/actes",
        content=urlencode(form_data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_edit(client, avocat, acte):
    auth_client(client, avocat)
    resp = client.get(f"/actes/{acte.id}/edit")
    assert resp.status_code == 200


def test_acte_update(client, avocat, acte, type_acte, dossier):
    auth_client(client, avocat)
    resp = client.post(
        f"/actes/{acte.id}",
        data={
            "nom": "Contrat de bail modifié",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "https://onedrive.example.com/bail-modifie",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_delete(client, avocat, acte):
    auth_client(client, avocat)
    resp = client.post(f"/actes/{acte.id}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_tags_autocomplete(client, avocat, db):
    auth_client(client, avocat)
    # Créer quelques tags
    from app import crud
    crud.get_or_create_tag(db, "contrat")
    crud.get_or_create_tag(db, "convention")
    crud.get_or_create_tag(db, "contradiction")

    resp = client.get("/actes/tags/autocomplete?q=con")
    assert resp.status_code == 200
    assert "tag-suggestion-item" in resp.text


def test_acte_tags_saved_via_tag_libelles(client, avocat, dossier, type_acte, db):
    """Vérifie que les tags soumis via tag_libelles sont bien enregistrés en BDD (fix B1)."""
    auth_client(client, avocat)
    from urllib.parse import urlencode
    from app.models import Tag
    form_data = [
        ("nom", "Acte tags libelles"),
        ("type_acte_id", str(type_acte.id)),
        ("lien_onedrive", "https://onedrive.example.com/tagtest"),
        ("date_production", str(datetime.date.today())),
        ("dossier_ids", str(dossier.id)),
        ("tag_libelles", "bail-commercial"),
        ("tag_libelles", "urgent-2026"),
    ]
    resp = client.post(
        "/actes",
        content=urlencode(form_data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Vérifier que les tags existent en BDD
    tag1 = db.query(Tag).filter(Tag.libelle == "bail-commercial").first()
    tag2 = db.query(Tag).filter(Tag.libelle == "urgent-2026").first()
    assert tag1 is not None
    assert tag2 is not None


def test_acte_create_url_invalide_no_scheme(client, avocat, dossier, type_acte):
    """Une URL sans scheme doit être rejetée (fix M3)."""
    auth_client(client, avocat)
    resp = client.post(
        "/actes",
        data={
            "nom": "Acte URL invalide",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "onedrive.example.com/fichier",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_acte_create_url_http_accepted(client, avocat, dossier, type_acte):
    """Une URL avec http:// doit être acceptée."""
    auth_client(client, avocat)
    resp = client.post(
        "/actes",
        data={
            "nom": "Acte URL http",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "http://onedrive.example.com/fichier",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_create_url_https_accepted(client, avocat, dossier, type_acte):
    """Une URL avec https:// doit être acceptée."""
    auth_client(client, avocat)
    resp = client.post(
        "/actes",
        data={
            "nom": "Acte URL https",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "https://onedrive.example.com/fichier",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_acte_edit_not_found(client, avocat):
    """Accéder à l'édition d'un acte inexistant doit rediriger vers la liste des dossiers."""
    auth_client(client, avocat)
    resp = client.get("/actes/99999/edit", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_acte_update_not_found(client, avocat, dossier, type_acte):
    """Mettre à jour un acte inexistant doit rediriger vers la liste des dossiers."""
    auth_client(client, avocat)
    resp = client.post(
        "/actes/99999",
        data={
            "nom": "Acte fantome",
            "type_acte_id": str(type_acte.id),
            "lien_onedrive": "https://onedrive.example.com/fantome",
            "date_production": str(datetime.date.today()),
            "dossier_ids": str(dossier.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]
