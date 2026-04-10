import os
from sqlalchemy.orm import Session

from app import crud
from app.models import TypeActe


TYPES_ACTES_DEFAUT = [
    "Contrat", "Assignation", "Conclusions", "Courrier",
    "Ordonnance", "Jugement", "Appel", "Requête",
    "Mémoire", "Acte de procédure", "Mise en demeure", "Protocole d'accord"
]


def seed_types_actes(db: Session) -> None:
    count = db.query(TypeActe).count()
    if count == 0:
        for libelle in TYPES_ACTES_DEFAUT:
            crud.create_type_acte(db, libelle)
    # Ajout idempotent de types spéciaux (génération de documents)
    for libelle in ["Convention d'honoraires"]:
        exists = db.query(TypeActe).filter(TypeActe.libelle == libelle).first()
        if not exists:
            crud.create_type_acte(db, libelle)


def seed_avocat_admin(db: Session) -> None:
    from app.models import Avocat

    count = db.query(Avocat).count()
    if count > 0:
        return

    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        print("[SEED] ADMIN_EMAIL ou ADMIN_PASSWORD non définis — aucun compte avocat créé.")
        print("[SEED] Définissez ces variables dans .env avant le premier démarrage.")
        return

    crud.create_avocat(db, nom="Admin", prenom="Admin", email=email, password_plain=password)


def run_seed(db: Session) -> None:
    seed_types_actes(db)
    seed_avocat_admin(db)
