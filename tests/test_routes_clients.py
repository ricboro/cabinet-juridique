import pytest
from fastapi.testclient import TestClient
from tests.conftest import set_auth_cookie


def auth_client(client, avocat):
    return set_auth_cookie(client, avocat)


def test_client_list_page(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/clients")
    assert resp.status_code == 200


def test_client_create_personne(client, avocat):
    auth_client(client, avocat)
    resp = client.post(
        "/clients",
        data={
            "type": "personne",
            "nom": "Martin",
            "prenom": "Sophie",
            "email": "sophie@example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_client_create_societe(client, avocat):
    auth_client(client, avocat)
    resp = client.post(
        "/clients",
        data={
            "type": "societe",
            "raison_sociale": "Tech Corp SAS",
            "siret": "98765432101234",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_client_create_missing_field(client, avocat):
    auth_client(client, avocat)
    resp = client.post(
        "/clients",
        data={"type": "personne", "prenom": "Jean"},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_client_detail(client, avocat, client_personne):
    auth_client(client, avocat)
    resp = client.get(f"/clients/{client_personne.id}")
    assert resp.status_code == 200


def test_client_edit(client, avocat, client_personne):
    auth_client(client, avocat)
    resp = client.get(f"/clients/{client_personne.id}/edit")
    assert resp.status_code == 200


def test_client_update(client, avocat, client_personne):
    auth_client(client, avocat)
    resp = client.post(
        f"/clients/{client_personne.id}",
        data={
            "type": "personne",
            "nom": "Dupont",
            "prenom": "Jean-Paul",
            "email": "jeanpaul@example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_client_delete_no_dossiers(client, avocat, client_societe):
    auth_client(client, avocat)
    resp = client.post(
        f"/clients/{client_societe.id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/clients" in resp.headers["location"]


def test_client_delete_with_dossiers(client, avocat, dossier, client_personne):
    auth_client(client, avocat)
    resp = client.post(
        f"/clients/{client_personne.id}/delete",
        follow_redirects=False,
    )
    # Doit rediriger vers le detail avec flash erreur (car le client a des dossiers)
    assert resp.status_code == 303
    assert str(client_personne.id) in resp.headers["location"]


def test_get_clients_sorted_by_nom(client, avocat, db):
    """Vérifie que get_clients retourne les clients triés par nom (fix M2)."""
    from app.schemas import ClientCreate
    from app import crud
    auth_client(client, avocat)
    crud.create_client(db, ClientCreate(type="personne", nom="Zola", prenom="Emile"))
    crud.create_client(db, ClientCreate(type="personne", nom="Aurelio", prenom="Jean"))
    crud.create_client(db, ClientCreate(type="personne", nom="Martin", prenom="Sophie"))

    clients, total = crud.get_clients(db)
    noms = [c.nom for c in clients if c.nom is not None]
    assert noms == sorted(noms)


def test_client_create_with_empty_url(client, avocat):
    """Test que la création d'un client avec URL vide passe (url non obligatoire)."""
    auth_client(client, avocat)
    resp = client.post(
        "/clients",
        data={
            "type": "personne",
            "nom": "Leclerc",
            "prenom": "Marie",
            "email": "",
        },
        follow_redirects=False,
    )
    # Doit passer car l'email est optionnel
    assert resp.status_code == 303


def test_client_not_found_detail(client, avocat):
    """Accéder au détail d'un client inexistant doit rediriger vers la liste."""
    auth_client(client, avocat)
    resp = client.get("/clients/99999", follow_redirects=False)
    assert resp.status_code == 303
    assert "/clients" in resp.headers["location"]


def test_client_not_found_edit(client, avocat):
    """Accéder à l'édition d'un client inexistant doit rediriger vers la liste."""
    auth_client(client, avocat)
    resp = client.get("/clients/99999/edit", follow_redirects=False)
    assert resp.status_code == 303
    assert "/clients" in resp.headers["location"]


def test_client_update_not_found(client, avocat):
    """Mettre à jour un client inexistant doit rediriger vers la liste."""
    auth_client(client, avocat)
    resp = client.post(
        "/clients/99999",
        data={"type": "personne", "nom": "Fantome", "prenom": "X"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/clients" in resp.headers["location"]
