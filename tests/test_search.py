import datetime
import pytest
from fastapi.testclient import TestClient
from tests.conftest import set_auth_cookie


def auth_client(client, avocat):
    return set_auth_cookie(client, avocat)


def test_search_page(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/search")
    assert resp.status_code == 200


def test_search_with_query(client, avocat, dossier):
    auth_client(client, avocat)
    resp = client.get("/search?q=litige")
    assert resp.status_code == 200


def test_search_htmx(client, avocat, dossier):
    auth_client(client, avocat)
    resp = client.get(
        "/search/htmx?q=litige",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200


def test_search_no_results(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/search?q=xyzinexistant")
    assert resp.status_code == 200


def test_search_short_query(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/search?q=ab")
    assert resp.status_code == 200


def test_type_actes_list(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/type-actes")
    assert resp.status_code == 200


def test_type_acte_create(client, avocat):
    auth_client(client, avocat)
    resp = client.post(
        "/type-actes",
        data={"libelle": "Attestation"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_type_acte_delete_unused(client, avocat, db):
    auth_client(client, avocat)
    from app import crud
    new_type = crud.create_type_acte(db, "TypeSansUsage")
    resp = client.post(
        f"/type-actes/{new_type.id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 303
