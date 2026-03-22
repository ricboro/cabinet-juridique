import os
from typing import Optional

from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Avocat

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

_session_serializer = URLSafeSerializer(SECRET_KEY, salt="session")
_flash_serializer = URLSafeSerializer(SECRET_KEY, salt="flash")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def create_session(response, avocat_id: int) -> None:
    token = _session_serializer.dumps({"user_id": avocat_id})
    response.set_cookie("session", token, httponly=True, samesite="lax")


def get_session_user_id(request: Request) -> Optional[int]:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = _session_serializer.loads(token)
        return data.get("user_id")
    except (BadSignature, Exception):
        return None


def clear_session(response) -> None:
    response.delete_cookie("session")


# ---------------------------------------------------------------------------
# Flash messages
# ---------------------------------------------------------------------------

def set_flash(response, message: str, type: str = "success") -> None:
    token = _flash_serializer.dumps({"message": message, "type": type})
    response.set_cookie("flash", token, httponly=True, samesite="lax", max_age=60)


def get_flash(request: Request) -> tuple[Optional[str], str]:
    token = request.cookies.get("flash")
    if not token:
        return None, "success"
    try:
        data = _flash_serializer.loads(token)
        return data.get("message"), data.get("type", "success")
    except (BadSignature, Exception):
        return None, "success"


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[Avocat]:
    user_id = get_session_user_id(request)
    if not user_id:
        return None
    return db.query(Avocat).filter(Avocat.id == user_id).first()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = get_session_user_id(request)
    if not user_id:
        raise _RedirectException("/login")
    avocat = db.query(Avocat).filter(Avocat.id == user_id).first()
    if not avocat:
        raise _RedirectException("/login")
    return avocat


class _RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url
