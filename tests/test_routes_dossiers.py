import datetime
import re
import pytest
from fastapi.testclient import TestClient
from tests.conftest import set_auth_cookie


def auth_client(client, avocat):
    return set_auth_cookie(client, avocat)


def test_dossier_list(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/dossiers")
    assert resp.status_code == 200


def test_dossier_create(client, avocat, client_personne):
    auth_client(client, avocat)
    resp = client.post(
        "/dossiers",
        data={
            "intitule": "Nouveau litige",
            "statut": "en_cours",
            "date_ouverture": str(datetime.date.today()),
            "client_id": str(client_personne.id),
            "avocat_id": str(avocat.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_dossier_create_generates_reference(client, avocat, client_personne, db):
    auth_client(client, avocat)
    year = datetime.date.today().year
    client.post(
        "/dossiers",
        data={
            "intitule": "Dossier référence test",
            "statut": "en_cours",
            "date_ouverture": str(datetime.date.today()),
            "client_id": str(client_personne.id),
            "avocat_id": str(avocat.id),
        },
        follow_redirects=False,
    )
    from app.models import Dossier
    dossiers = db.query(Dossier).filter(Dossier.intitule == "Dossier référence test").all()
    assert len(dossiers) >= 1
    ref = dossiers[0].reference
    # Format attendu : AAAA-NNN
    assert re.match(r"^\d{4}-\d{3}$", ref), f"Référence invalide : {ref}"
    assert ref.startswith(str(year))


def test_dossier_detail(client, avocat, dossier):
    auth_client(client, avocat)
    resp = client.get(f"/dossiers/{dossier.id}")
    assert resp.status_code == 200


def test_dossier_edit(client, avocat, dossier):
    auth_client(client, avocat)
    resp = client.get(f"/dossiers/{dossier.id}/edit")
    assert resp.status_code == 200


def test_dossier_update(client, avocat, dossier, client_personne):
    auth_client(client, avocat)
    resp = client.post(
        f"/dossiers/{dossier.id}",
        data={
            "intitule": "Litige commercial modifié",
            "statut": "en_cours",
            "date_ouverture": str(datetime.date.today()),
            "client_id": str(client_personne.id),
            "avocat_id": str(avocat.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_dossier_close(client, avocat, dossier, db):
    auth_client(client, avocat)
    resp = client.post(f"/dossiers/{dossier.id}/close", follow_redirects=False)
    assert resp.status_code == 303
    db.refresh(dossier)
    assert dossier.statut == "cloture"


def test_dossier_delete(client, avocat, dossier):
    auth_client(client, avocat)
    resp = client.post(f"/dossiers/{dossier.id}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_dossier_close_not_found(client, avocat):
    """Clôturer un dossier inexistant doit rediriger avec flash error (fix M4)."""
    auth_client(client, avocat)
    resp = client.post("/dossiers/99999/close", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_dossier_delete_not_found(client, avocat):
    """Supprimer un dossier inexistant doit rediriger avec flash error (fix M4)."""
    auth_client(client, avocat)
    resp = client.post("/dossiers/99999/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_get_dossiers_sorted_by_date_ouverture_desc(db, avocat, client_personne):
    """Vérifie que get_dossiers retourne les dossiers triés par date_ouverture desc (fix M2)."""
    from app import crud
    d1 = crud.create_dossier(db, __import__('app.schemas', fromlist=['DossierCreate']).DossierCreate(
        intitule="Dossier ancien",
        statut="en_cours",
        date_ouverture=datetime.date(2024, 1, 1),
        client_id=client_personne.id,
    ), avocat_id=avocat.id)
    d2 = crud.create_dossier(db, __import__('app.schemas', fromlist=['DossierCreate']).DossierCreate(
        intitule="Dossier recent",
        statut="en_cours",
        date_ouverture=datetime.date(2026, 3, 22),
        client_id=client_personne.id,
    ), avocat_id=avocat.id)
    d3 = crud.create_dossier(db, __import__('app.schemas', fromlist=['DossierCreate']).DossierCreate(
        intitule="Dossier milieu",
        statut="en_cours",
        date_ouverture=datetime.date(2025, 6, 15),
        client_id=client_personne.id,
    ), avocat_id=avocat.id)

    dossiers, total = crud.get_dossiers(db)
    dates = [d.date_ouverture for d in dossiers]
    assert dates == sorted(dates, reverse=True)


def test_dossier_detail_not_found(client, avocat):
    """Accéder au détail d'un dossier inexistant redirige vers la liste."""
    auth_client(client, avocat)
    resp = client.get("/dossiers/99999", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_dossier_edit_not_found(client, avocat):
    """Accéder à l'édition d'un dossier inexistant redirige vers la liste."""
    auth_client(client, avocat)
    resp = client.get("/dossiers/99999/edit", follow_redirects=False)
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]


def test_dossier_update_not_found(client, avocat, client_personne):
    """Mettre à jour un dossier inexistant redirige vers la liste."""
    auth_client(client, avocat)
    resp = client.post(
        "/dossiers/99999",
        data={
            "intitule": "Test",
            "statut": "en_cours",
            "date_ouverture": str(datetime.date.today()),
            "client_id": str(client_personne.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/dossiers" in resp.headers["location"]
