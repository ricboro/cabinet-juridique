import pytest
from fastapi.testclient import TestClient
from tests.conftest import set_auth_cookie


def auth_client(client, avocat):
    return set_auth_cookie(client, avocat)


def test_login_page_accessible(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_success_redirects(client, avocat):
    resp = client.post(
        "/login",
        data={"email": "margo@cabinet.fr", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_wrong_password(client, avocat):
    resp = client.post(
        "/login",
        data={"email": "margo@cabinet.fr", "password": "mauvais"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.text.lower() or "error" in resp.text.lower()


def test_login_unknown_email(client, avocat):
    resp = client.post(
        "/login",
        data={"email": "inconnu@cabinet.fr", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.text.lower() or "error" in resp.text.lower()


def test_logout(client, avocat):
    auth_client(client, avocat)
    resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]


def test_protected_route_redirects(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]


def test_authenticated_route_accessible(client, avocat):
    auth_client(client, avocat)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200


def test_flash_cookie_cleared_after_read(client, avocat):
    """Vérifie que le header Set-Cookie de suppression du flash est bien émis (fix O1).

    Le code login_get appelle response.delete_cookie("flash") lorsqu'un message
    flash est présent. Ce test vérifie que la réponse contient bien un header
    Set-Cookie pour effacer le cookie flash (max-age=0 ou expires passé).

    Note : le template login.html n'affiche pas flash_message (seule la variable
    `error` est affichée) — bug séparé signalé dans le rapport.
    """
    from itsdangerous import URLSafeSerializer
    import os
    auth_client(client, avocat)

    # Poser un cookie flash manuellement
    s = URLSafeSerializer(os.environ.get("SECRET_KEY", "dev-secret-key-change-me"), salt="flash")
    token = s.dumps({"message": "test flash", "type": "success"})
    client.cookies.set("flash", token)

    # La page de login doit émettre un Set-Cookie pour effacer le flash
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 200
    # Vérifier que la réponse contient un Set-Cookie pour "flash" avec max-age=0
    set_cookie_headers = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [
        v for k, v in resp.headers.items() if k.lower() == "set-cookie"
    ]
    flash_delete = any(
        "flash" in h and ("max-age=0" in h.lower() or 'expires=thu, 01 jan 1970' in h.lower())
        for h in set_cookie_headers
    )
    assert flash_delete, f"Le cookie flash n'est pas supprimé dans les headers. Set-Cookie: {set_cookie_headers}"


def test_login_without_admin_env_vars(client):
    """Teste le comportement login quand ADMIN_EMAIL/ADMIN_PASSWORD ne sont pas définis.
    Le système utilise la BDD uniquement — sans avocat en BDD, login doit échouer avec 401."""
    # Pas d'avocat créé en BDD, pas de variables d'environnement ADMIN_EMAIL/ADMIN_PASSWORD
    resp = client.post(
        "/login",
        data={"email": "admin@cabinet.fr", "password": "somepassword"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
