import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.auth import (
    get_current_user, get_optional_user,
    get_flash, set_flash, create_session, clear_session,
    _RedirectException,
)
from app import crud

APP_NAME = "Cabinet Juridique"

# CSRF : non implémenté — l'outil est restreint au réseau Tailscale (accès interne uniquement).
# A implémenter (ex: starlette-csrf) si l'outil est un jour exposé sur internet.


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    from app.database import SessionLocal
    from app.seed import run_seed
    import os

    logger = logging.getLogger(__name__)

    # En test, la BDD est gérée par le conftest — on évite d'initialiser la vraie BDD
    testing = os.environ.get("TESTING", "0") == "1"
    if not testing:
        db = SessionLocal()
        try:
            init_db()
            run_seed(db)
        finally:
            db.close()

    secret = os.environ.get("SECRET_KEY", "")
    if not secret or secret == "dev-secret-key-change-me":
        logger.warning(
            "SECRET_KEY non définie ou valeur par défaut détectée. "
            "Les sessions peuvent être forgées. Définissez SECRET_KEY dans .env."
        )
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)

# Gestion de la redirection auth
@app.exception_handler(_RedirectException)
async def redirect_exception_handler(request: Request, exc: _RedirectException):
    return RedirectResponse(url=exc.url, status_code=303)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers de contexte
# ---------------------------------------------------------------------------

def get_flash_context(request: Request) -> dict:
    message, flash_type = get_flash(request)
    return {"flash_message": message, "flash_type": flash_type}


def make_context(request: Request, current_user, response: Response = None, **kwargs) -> dict:
    flash_msg, flash_type = get_flash(request)
    ctx = {
        "request": request,
        "current_user": current_user,
        "app_name": APP_NAME,
        "flash_message": flash_msg,
        "flash_type": flash_type,
        **kwargs,
    }
    # Efface le cookie flash dès la première lecture
    if flash_msg and response is not None:
        response.delete_cookie("flash")
    return ctx


# ---------------------------------------------------------------------------
# Inclure les routers
# ---------------------------------------------------------------------------

from app.routers import clients, dossiers, actes, type_actes
from app.routers import search as search_router

app.include_router(clients.router)
app.include_router(dossiers.router)
app.include_router(actes.router)
app.include_router(type_actes.router)
app.include_router(search_router.router)


# ---------------------------------------------------------------------------
# Routes principales
# ---------------------------------------------------------------------------

@app.get("/", name="dashboard")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _, clients_count = crud.get_clients(db, limit=1)
    _, dossiers_en_cours = crud.get_dossiers(db, statut="en_cours", limit=1)
    from app.models import Acte
    actes_count = db.query(Acte).count()

    stats = {
        "clients_count": clients_count,
        "dossiers_en_cours": dossiers_en_cours,
        "actes_count": actes_count,
    }
    derniers_dossiers, _ = crud.get_dossiers(db, limit=5)

    return templates.TemplateResponse(
        "pages/dashboard.html",
        make_context(request, current_user,
                     stats=stats, derniers_dossiers=derniers_dossiers),
    )


@app.get("/login", name="login_get")
async def login_get(request: Request):
    flash_message, flash_type = get_flash(request)
    response = templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "app_name": APP_NAME,
            "current_user": None,
            "flash_message": flash_message,
            "flash_type": flash_type,
            "error": None,
        },
    )
    # Effacer le cookie flash après lecture
    if flash_message:
        response.delete_cookie("flash")
    return response


@app.post("/login", name="login_post")
async def login_post(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    email = form.get("email", "").strip()
    password = form.get("password", "").strip()

    avocat = crud.get_avocat_by_email(db, email)
    if not avocat or not crud.verify_password(password, avocat.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "app_name": APP_NAME,
                "current_user": None,
                "flash_message": None,
                "flash_type": "error",
                "error": "Email ou mot de passe incorrect",
            },
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    create_session(response, avocat.id)
    return response


@app.post("/logout", name="logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    clear_session(response)
    return response
