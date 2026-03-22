import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        SQLALCHEMY_TEST_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    try:
        from app.main import app
        from fastapi.testclient import TestClient

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()
    except ImportError:
        yield None


@pytest.fixture
def avocat(db):
    from app import crud
    return crud.create_avocat(db, "Boisson", "Margo", "margo@cabinet.fr", "password123")


@pytest.fixture
def client_personne(db):
    from app.schemas import ClientCreate
    from app import crud
    data = ClientCreate(type="personne", nom="Dupont", prenom="Jean", email="jean@example.com")
    return crud.create_client(db, data)


@pytest.fixture
def client_societe(db):
    from app.schemas import ClientCreate
    from app import crud
    data = ClientCreate(type="societe", raison_sociale="ACME SAS", siret="12345678901234")
    return crud.create_client(db, data)


@pytest.fixture
def type_acte(db):
    from app import crud
    return crud.create_type_acte(db, "Contrat")


@pytest.fixture
def dossier(db, avocat, client_personne, type_acte):
    from app.schemas import DossierCreate
    from app import crud
    import datetime
    data = DossierCreate(
        intitule="Litige commercial",
        statut="en_cours",
        date_ouverture=datetime.date.today(),
        client_id=client_personne.id,
    )
    return crud.create_dossier(db, data, avocat_id=avocat.id)


def set_auth_cookie(test_client, avocat):
    """Helper pour authentifier un TestClient FastAPI."""
    from itsdangerous import URLSafeSerializer
    s = URLSafeSerializer(os.environ.get("SECRET_KEY", "dev-secret-key-change-me"), salt="session")
    token = s.dumps({"user_id": avocat.id})
    test_client.cookies.set("session", token)
    return test_client
