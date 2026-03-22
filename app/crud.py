import datetime
import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models import Avocat, Client, Dossier, TypeActe, Acte, ActeDossier, Tag, ActeTag
from app.schemas import ClientCreate, ClientUpdate, DossierCreate, DossierUpdate, ActeCreate, ActeUpdate


# ---------------------------------------------------------------------------
# Avocats
# ---------------------------------------------------------------------------

def get_avocat_by_email(db: Session, email: str) -> Avocat | None:
    return db.query(Avocat).filter(Avocat.email == email).first()


def get_avocats(db: Session) -> list[Avocat]:
    """Retourne tous les avocats triés par nom."""
    return db.query(Avocat).order_by(Avocat.nom, Avocat.prenom).all()


def create_avocat(db: Session, nom: str, prenom: str, email: str, password_plain: str) -> Avocat:
    password_hash = bcrypt.hashpw(password_plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    avocat = Avocat(nom=nom, prenom=prenom, email=email, password_hash=password_hash)
    db.add(avocat)
    db.commit()
    db.refresh(avocat)
    return avocat


def verify_password(password_plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password_plain.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def get_client(db: Session, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id == client_id).first()


def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> tuple[list[Client], int]:
    query = db.query(Client)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Client.nom.ilike(pattern),
                Client.prenom.ilike(pattern),
                Client.raison_sociale.ilike(pattern),
                Client.email.ilike(pattern),
            )
        )
    total = query.count()
    clients = query.order_by(Client.nom, Client.prenom, Client.raison_sociale).offset(skip).limit(limit).all()
    return clients, total


def create_client(db: Session, data: ClientCreate) -> Client:
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_client(db: Session, client_id: int, data: ClientUpdate) -> Client | None:
    client = get_client(db, client_id)
    if not client:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client_id: int) -> bool:
    client = get_client(db, client_id)
    if not client:
        return False
    if client.dossiers:
        raise ValueError(f"Le client {client_id} possède des dossiers existants.")
    db.delete(client)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

def generate_reference(db: Session, year: int) -> str:
    """
    Génère une référence unique pour un dossier au format AAAA-NNN.
    Le compteur est séquentiel par année et repart de 001 chaque 1er janvier.

    Utilise un LIKE sur la colonne 'reference' pour compter les dossiers de l'année,
    ce qui évite une colonne séquentielle dédiée. En environnement mono-process
    (SQLite), le risque de collision concurrent est négligeable.

    Exemple : pour 2026 avec 3 dossiers existants -> retourne "2026-004"
    """
    count = db.query(func.count(Dossier.id)).filter(
        Dossier.reference.like(f"{year}-%")
    ).scalar()
    return f"{year}-{(count or 0) + 1:03d}"


def get_dossier(db: Session, dossier_id: int) -> Dossier | None:
    return db.query(Dossier).filter(Dossier.id == dossier_id).first()


def get_dossiers(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    statut: str | None = None,
    client_id: int | None = None,
    avocat_id: int | None = None,
) -> tuple[list[Dossier], int]:
    query = db.query(Dossier)
    if statut:
        query = query.filter(Dossier.statut == statut)
    if client_id:
        query = query.filter(Dossier.client_id == client_id)
    if avocat_id:
        query = query.filter(Dossier.avocat_id == avocat_id)
    total = query.count()
    dossiers = query.order_by(Dossier.date_ouverture.desc()).offset(skip).limit(limit).all()
    return dossiers, total


def create_dossier(db: Session, data: DossierCreate, avocat_id: int) -> Dossier:
    year = data.date_ouverture.year
    reference = generate_reference(db, year)
    dossier = Dossier(
        **data.model_dump(),
        reference=reference,
        avocat_id=avocat_id,
    )
    db.add(dossier)
    db.commit()
    db.refresh(dossier)
    return dossier


def update_dossier(db: Session, dossier_id: int, data: DossierUpdate) -> Dossier | None:
    dossier = get_dossier(db, dossier_id)
    if not dossier:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dossier, field, value)
    db.commit()
    db.refresh(dossier)
    return dossier


def close_dossier(db: Session, dossier_id: int) -> Dossier | None:
    dossier = get_dossier(db, dossier_id)
    if not dossier:
        return None
    dossier.statut = "cloture"
    dossier.date_cloture = datetime.date.today()
    db.commit()
    db.refresh(dossier)
    return dossier


def delete_dossier(db: Session, dossier_id: int) -> bool:
    dossier = get_dossier(db, dossier_id)
    if not dossier:
        return False
    db.query(ActeDossier).filter(ActeDossier.dossier_id == dossier_id).delete()
    db.delete(dossier)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# TypeActes
# ---------------------------------------------------------------------------

def get_type_actes(db: Session) -> list[TypeActe]:
    return db.query(TypeActe).order_by(TypeActe.libelle).all()


def get_type_actes_with_count(db: Session) -> list[tuple]:
    """Retourne les types d'actes avec leur nombre d'actes associés (requête SQL efficace)."""
    return (
        db.query(TypeActe, func.count(Acte.id).label("usage_count"))
        .outerjoin(Acte, Acte.type_acte_id == TypeActe.id)
        .group_by(TypeActe.id)
        .order_by(TypeActe.libelle)
        .all()
    )


def get_type_acte(db: Session, type_acte_id: int) -> TypeActe | None:
    return db.query(TypeActe).filter(TypeActe.id == type_acte_id).first()


def create_type_acte(db: Session, libelle: str) -> TypeActe:
    type_acte = TypeActe(libelle=libelle)
    db.add(type_acte)
    db.commit()
    db.refresh(type_acte)
    return type_acte


def delete_type_acte(db: Session, type_acte_id: int) -> bool:
    type_acte = get_type_acte(db, type_acte_id)
    if not type_acte:
        return False
    if type_acte.actes:
        raise ValueError(f"Le type d'acte {type_acte_id} est utilisé par des actes existants.")
    db.delete(type_acte)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def get_or_create_tag(db: Session, libelle: str) -> Tag:
    tag = db.query(Tag).filter(Tag.libelle == libelle).first()
    if not tag:
        tag = Tag(libelle=libelle)
        db.add(tag)
        db.commit()
        db.refresh(tag)
    return tag


def get_tags_autocomplete(db: Session, q: str) -> list[Tag]:
    return db.query(Tag).filter(Tag.libelle.ilike(f"%{q}%")).limit(20).all()


# ---------------------------------------------------------------------------
# Actes
# ---------------------------------------------------------------------------

def _resolve_tags(db: Session, tag_ids: list[int], tag_libelles: list[str]) -> list[Tag]:
    """
    Résout une liste de tags depuis des IDs et/ou des libellés.
    Crée les tags inexistants à la volée (get_or_create).
    Déduplique le résultat final pour éviter les doublons si un libellé
    correspond à un ID déjà présent dans tag_ids.
    """
    tags: list[Tag] = []
    seen_ids: set[int] = set()
    for tag_id in tag_ids:
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
        if tag and tag.id not in seen_ids:
            tags.append(tag)
            seen_ids.add(tag.id)
    for libelle in tag_libelles:
        tag = get_or_create_tag(db, libelle)
        if tag.id not in seen_ids:
            tags.append(tag)
            seen_ids.add(tag.id)
    return tags


def get_acte(db: Session, acte_id: int) -> Acte | None:
    return db.query(Acte).filter(Acte.id == acte_id).first()


def create_acte(db: Session, data: ActeCreate) -> Acte:
    acte = Acte(
        nom=data.nom,
        type_acte_id=data.type_acte_id,
        lien_onedrive=data.lien_onedrive,
        date_production=data.date_production,
    )
    db.add(acte)
    db.flush()

    for dossier_id in data.dossier_ids:
        db.add(ActeDossier(acte_id=acte.id, dossier_id=dossier_id))

    tags = _resolve_tags(db, data.tag_ids, data.tag_libelles)
    for tag in tags:
        db.add(ActeTag(acte_id=acte.id, tag_id=tag.id))

    db.commit()
    db.refresh(acte)
    return acte


def update_acte(db: Session, acte_id: int, data: ActeUpdate) -> Acte | None:
    acte = get_acte(db, acte_id)
    if not acte:
        return None

    scalar_fields = {"nom", "type_acte_id", "lien_onedrive", "date_production"}
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in scalar_fields:
            setattr(acte, field, value)

    if data.dossier_ids is not None:
        db.query(ActeDossier).filter(ActeDossier.acte_id == acte_id).delete()
        for dossier_id in data.dossier_ids:
            db.add(ActeDossier(acte_id=acte_id, dossier_id=dossier_id))

    if data.tag_ids is not None or data.tag_libelles is not None:
        db.query(ActeTag).filter(ActeTag.acte_id == acte_id).delete()
        tags = _resolve_tags(
            db,
            data.tag_ids or [],
            data.tag_libelles or [],
        )
        for tag in tags:
            db.add(ActeTag(acte_id=acte_id, tag_id=tag.id))

    db.commit()
    db.refresh(acte)
    return acte


def delete_acte(db: Session, acte_id: int) -> bool:
    acte = get_acte(db, acte_id)
    if not acte:
        return False
    db.delete(acte)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

def search(
    db: Session,
    q: str = "",
    type_acte_id: int | None = None,
    tag: str | None = None,
    client_id: int | None = None,
    avocat_id: int | None = None,
    statut: str | None = None,
) -> dict:
    """
    Recherche multi-critères. Exige soit q >= 3 caractères, soit au moins un filtre actif.
    Le filtre tag est une recherche textuelle sur le libellé (pas un ID).
    """
    has_filters = any([type_acte_id, tag, client_id, avocat_id, statut])
    if len(q) < 3 and not has_filters:
        return {"dossiers": [], "actes": []}

    # ── Dossiers ──────────────────────────────────────────────────
    dossier_query = db.query(Dossier)
    if len(q) >= 3:
        pattern = f"%{q}%"
        dossier_query = dossier_query.filter(
            or_(
                Dossier.intitule.ilike(pattern),
                Dossier.reference.ilike(pattern),
                Dossier.contexte.ilike(pattern),
            )
        )
    if client_id:
        dossier_query = dossier_query.filter(Dossier.client_id == client_id)
    if avocat_id:
        dossier_query = dossier_query.filter(Dossier.avocat_id == avocat_id)
    if statut:
        dossier_query = dossier_query.filter(Dossier.statut == statut)

    # ── Actes ─────────────────────────────────────────────────────
    acte_query = db.query(Acte)
    if len(q) >= 3:
        acte_query = acte_query.filter(Acte.nom.ilike(f"%{q}%"))
    if type_acte_id:
        acte_query = acte_query.filter(Acte.type_acte_id == type_acte_id)
    if tag:
        acte_query = (
            acte_query.join(ActeTag).join(Tag)
            .filter(Tag.libelle.ilike(f"%{tag}%"))
        )

    return {
        "dossiers": dossier_query.all(),
        "actes": acte_query.all(),
    }
