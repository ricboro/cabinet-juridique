import datetime
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Client, Dossier, Acte, ActeDossier, Tag, TypeActe
from app.schemas import ClientCreate, DossierCreate, ActeCreate
from app import crud


def make_dossier(db, avocat, client, date_ouverture=None):
    if date_ouverture is None:
        date_ouverture = datetime.date.today()
    data = DossierCreate(
        intitule="Test dossier",
        statut="en_cours",
        date_ouverture=date_ouverture,
        client_id=client.id,
    )
    return crud.create_dossier(db, data, avocat_id=avocat.id)


def test_client_personne_creation(db):
    data = ClientCreate(type="personne", nom="Martin", prenom="Alice")
    client = crud.create_client(db, data)
    assert client.nom == "Martin"
    assert client.prenom == "Alice"
    assert client.type == "personne"


def test_client_societe_creation(db):
    data = ClientCreate(type="societe", raison_sociale="TechCorp SAS")
    client = crud.create_client(db, data)
    assert client.raison_sociale == "TechCorp SAS"
    assert client.type == "societe"


def test_dossier_reference_format_AAAA_NNN(db, avocat, client_personne):
    dossier = make_dossier(db, avocat, client_personne, datetime.date(2026, 3, 1))
    assert dossier.reference == "2026-001"


def test_dossier_reference_auto_increment_same_year(db, avocat, client_personne):
    d1 = make_dossier(db, avocat, client_personne, datetime.date(2026, 1, 1))
    d2 = make_dossier(db, avocat, client_personne, datetime.date(2026, 6, 1))
    assert d1.reference == "2026-001"
    assert d2.reference == "2026-002"


def test_dossier_reference_reset_new_year(db, avocat, client_personne):
    d_old = make_dossier(db, avocat, client_personne, datetime.date(2025, 12, 31))
    d_new = make_dossier(db, avocat, client_personne, datetime.date(2026, 1, 1))
    assert d_old.reference == "2025-001"
    assert d_new.reference == "2026-001"


def test_acte_linked_to_multiple_dossiers(db, avocat, client_personne, type_acte):
    d1 = make_dossier(db, avocat, client_personne)
    d2 = make_dossier(db, avocat, client_personne)
    data = ActeCreate(
        nom="Convention",
        type_acte_id=type_acte.id,
        lien_onedrive="https://onedrive.example.com/file1",
        date_production=datetime.date.today(),
        dossier_ids=[d1.id, d2.id],
    )
    acte = crud.create_acte(db, data)
    linked_dossier_ids = [ad.dossier_id for ad in acte.acte_dossiers]
    assert d1.id in linked_dossier_ids
    assert d2.id in linked_dossier_ids


def test_acte_link_removed_not_deleted(db, avocat, client_personne, type_acte):
    dossier = make_dossier(db, avocat, client_personne)
    data = ActeCreate(
        nom="Acte test",
        type_acte_id=type_acte.id,
        lien_onedrive="https://onedrive.example.com/file2",
        date_production=datetime.date.today(),
        dossier_ids=[dossier.id],
    )
    acte = crud.create_acte(db, data)
    acte_id = acte.id

    crud.delete_dossier(db, dossier.id)

    acte_still_exists = crud.get_acte(db, acte_id)
    assert acte_still_exists is not None


def test_tag_unique_constraint(db):
    tag1 = crud.get_or_create_tag(db, "urgent")
    with pytest.raises(IntegrityError):
        tag2 = Tag(libelle="urgent")
        db.add(tag2)
        db.commit()


def test_type_acte_unique_constraint(db):
    ta1 = crud.create_type_acte(db, "Contrat")
    with pytest.raises(IntegrityError):
        ta2 = TypeActe(libelle="Contrat")
        db.add(ta2)
        db.commit()
