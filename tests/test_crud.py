import datetime
import pytest

from app.schemas import ClientCreate, ClientUpdate, DossierCreate, DossierUpdate, ActeCreate, ActeUpdate
from app import crud
from app.models import ActeDossier, Acte


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_acte(db, type_acte, dossier_ids=None, tag_ids=None, tag_libelles=None):
    data = ActeCreate(
        nom="Acte test",
        type_acte_id=type_acte.id,
        lien_onedrive="https://onedrive.example.com/acte",
        date_production=datetime.date.today(),
        dossier_ids=dossier_ids or [],
        tag_ids=tag_ids or [],
        tag_libelles=tag_libelles or [],
    )
    return crud.create_acte(db, data)


def make_dossier(db, avocat, client, date_ouverture=None, intitule="Dossier test"):
    if date_ouverture is None:
        date_ouverture = datetime.date.today()
    data = DossierCreate(
        intitule=intitule,
        statut="en_cours",
        date_ouverture=date_ouverture,
        client_id=client.id,
    )
    return crud.create_dossier(db, data, avocat_id=avocat.id)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def test_create_client(db):
    data = ClientCreate(type="personne", nom="Durand", prenom="Paul")
    client = crud.create_client(db, data)
    assert client.id is not None
    assert client.nom == "Durand"


def test_get_client_by_id(db, client_personne):
    fetched = crud.get_client(db, client_personne.id)
    assert fetched is not None
    assert fetched.id == client_personne.id


def test_get_client_not_found(db):
    result = crud.get_client(db, 99999)
    assert result is None


def test_update_client(db, client_personne):
    update = ClientUpdate(nom="Leblanc")
    updated = crud.update_client(db, client_personne.id, update)
    assert updated.nom == "Leblanc"
    assert updated.prenom == client_personne.prenom


def test_delete_client_no_dossiers(db, client_personne):
    result = crud.delete_client(db, client_personne.id)
    assert result is True
    assert crud.get_client(db, client_personne.id) is None


def test_delete_client_with_dossiers_raises(db, client_personne, dossier):
    with pytest.raises(ValueError):
        crud.delete_client(db, client_personne.id)


# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

def test_create_dossier(db, avocat, client_personne):
    d = make_dossier(db, avocat, client_personne, datetime.date(2026, 3, 22))
    assert d.reference == "2026-001"
    assert d.intitule == "Dossier test"


def test_get_dossiers_by_client(db, avocat, client_personne, client_societe):
    make_dossier(db, avocat, client_personne)
    make_dossier(db, avocat, client_personne)
    make_dossier(db, avocat, client_societe)

    results, total = crud.get_dossiers(db, client_id=client_personne.id)
    assert total == 2
    assert all(d.client_id == client_personne.id for d in results)


def test_close_dossier_sets_date_cloture(db, dossier):
    closed = crud.close_dossier(db, dossier.id)
    assert closed.statut == "cloture"
    assert closed.date_cloture == datetime.date.today()


def test_delete_dossier_cascades_acte_links(db, avocat, client_personne, type_acte, dossier):
    acte = make_acte(db, type_acte, dossier_ids=[dossier.id])
    acte_id = acte.id

    crud.delete_dossier(db, dossier.id)

    # ActeDossier supprimé
    links = db.query(ActeDossier).filter(ActeDossier.acte_id == acte_id).all()
    assert len(links) == 0

    # L'acte lui-même subsiste
    assert crud.get_acte(db, acte_id) is not None


# ---------------------------------------------------------------------------
# Actes
# ---------------------------------------------------------------------------

def test_create_acte(db, type_acte, dossier):
    tag = crud.get_or_create_tag(db, "contrat-type")
    acte = make_acte(db, type_acte, dossier_ids=[dossier.id], tag_ids=[tag.id])
    assert acte.id is not None
    assert len(acte.acte_dossiers) == 1
    assert len(acte.acte_tags) == 1


def test_create_acte_with_multiple_dossiers(db, avocat, client_personne, type_acte):
    d1 = make_dossier(db, avocat, client_personne)
    d2 = make_dossier(db, avocat, client_personne)
    acte = make_acte(db, type_acte, dossier_ids=[d1.id, d2.id])
    assert len(acte.acte_dossiers) == 2


def test_update_acte_change_dossiers(db, avocat, client_personne, type_acte, dossier):
    acte = make_acte(db, type_acte, dossier_ids=[dossier.id])
    d2 = make_dossier(db, avocat, client_personne)

    update = ActeUpdate(dossier_ids=[d2.id])
    updated = crud.update_acte(db, acte.id, update)

    dossier_ids = [ad.dossier_id for ad in updated.acte_dossiers]
    assert dossier.id not in dossier_ids
    assert d2.id in dossier_ids


def test_delete_acte_cascades_links(db, type_acte, dossier):
    tag = crud.get_or_create_tag(db, "a-supprimer")
    acte = make_acte(db, type_acte, dossier_ids=[dossier.id], tag_ids=[tag.id])
    acte_id = acte.id

    result = crud.delete_acte(db, acte_id)
    assert result is True
    assert crud.get_acte(db, acte_id) is None


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def test_create_tag(db):
    tag = crud.get_or_create_tag(db, "nouveau-tag")
    assert tag.id is not None
    assert tag.libelle == "nouveau-tag"


def test_get_or_create_tag_existing(db):
    tag1 = crud.get_or_create_tag(db, "mon-tag")
    tag2 = crud.get_or_create_tag(db, "mon-tag")
    assert tag1.id == tag2.id


# ---------------------------------------------------------------------------
# TypeActes
# ---------------------------------------------------------------------------

def test_create_type_acte(db):
    ta = crud.create_type_acte(db, "Jugement")
    assert ta.id is not None
    assert ta.libelle == "Jugement"


def test_delete_type_acte_unused(db):
    ta = crud.create_type_acte(db, "Obsolete")
    result = crud.delete_type_acte(db, ta.id)
    assert result is True


def test_delete_type_acte_in_use_raises(db, type_acte, dossier):
    make_acte(db, type_acte, dossier_ids=[dossier.id])
    with pytest.raises(ValueError):
        crud.delete_type_acte(db, type_acte.id)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_paginate_clients(db):
    for i in range(5):
        data = ClientCreate(type="personne", nom=f"Client{i}", prenom="Test")
        crud.create_client(db, data)

    page1, total = crud.get_clients(db, skip=0, limit=3)
    assert total == 5
    assert len(page1) == 3

    page2, _ = crud.get_clients(db, skip=3, limit=3)
    assert len(page2) == 2


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------

def test_filter_dossiers_by_statut(db, avocat, client_personne):
    d1 = make_dossier(db, avocat, client_personne)
    d2 = make_dossier(db, avocat, client_personne)
    crud.close_dossier(db, d1.id)

    results, total = crud.get_dossiers(db, statut="cloture")
    assert total == 1
    assert results[0].id == d1.id


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

def test_search_keyword(db, avocat, client_personne):
    make_dossier(db, avocat, client_personne, intitule="Litige commercial urgent")

    result = crud.search(db, "litige")
    assert len(result["dossiers"]) >= 1
    assert any("litige" in d.intitule.lower() for d in result["dossiers"])


def test_search_less_than_3_chars(db):
    result = crud.search(db, "li")
    assert result["dossiers"] == []
    assert result["actes"] == []


# ---------------------------------------------------------------------------
# get_type_actes_with_count
# ---------------------------------------------------------------------------

def test_get_type_actes_with_count_empty(db):
    """Sans aucun type d'acte, la liste retournée est vide."""
    rows = crud.get_type_actes_with_count(db)
    assert rows == []


def test_get_type_actes_with_count_zero(db):
    """Un type d'acte sans acte associé doit retourner count=0 (fix O3)."""
    ta = crud.create_type_acte(db, "Type sans actes")
    rows = crud.get_type_actes_with_count(db)
    assert len(rows) == 1
    type_acte_obj, count = rows[0]
    assert type_acte_obj.id == ta.id
    assert count == 0


def test_get_type_actes_with_count_with_actes(db, avocat, client_personne):
    """Un type d'acte avec 2 actes associés doit retourner count=2 (fix O3)."""
    ta = crud.create_type_acte(db, "Type avec actes")
    d = make_dossier(db, avocat, client_personne)
    make_acte(db, ta, dossier_ids=[d.id])
    make_acte(db, ta, dossier_ids=[d.id])

    rows = crud.get_type_actes_with_count(db)
    assert len(rows) == 1
    type_acte_obj, count = rows[0]
    assert type_acte_obj.id == ta.id
    assert count == 2


def test_get_type_actes_with_count_multiple_types(db, avocat, client_personne):
    """Plusieurs types avec des counts différents, triés par libelle."""
    ta_b = crud.create_type_acte(db, "Beta")
    ta_a = crud.create_type_acte(db, "Alpha")
    d = make_dossier(db, avocat, client_personne)
    make_acte(db, ta_b, dossier_ids=[d.id])

    rows = crud.get_type_actes_with_count(db)
    libelles = [r[0].libelle for r in rows]
    assert libelles == sorted(libelles)

    counts = {r[0].libelle: r[1] for r in rows}
    assert counts["Alpha"] == 0
    assert counts["Beta"] == 1
