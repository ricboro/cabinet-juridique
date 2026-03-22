"""Utilitaires partagés entre les routers."""
from datetime import date


def parse_date(value: str | None) -> date | None:
    """
    Parse une date au format YYYY-MM-DD depuis un champ de formulaire HTML.
    Retourne None si la valeur est absente ou vide.
    """
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
