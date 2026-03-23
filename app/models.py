from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Avocat(Base):
    __tablename__ = "avocats"

    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    dossiers = relationship("Dossier", back_populates="avocat")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    type = Column(Enum("personne", "societe", name="client_type"), nullable=False)
    nom = Column(String(100), nullable=True)
    prenom = Column(String(100), nullable=True)
    raison_sociale = Column(String(200), nullable=True)
    siret = Column(String(14), nullable=True)
    email = Column(String(200), nullable=True)
    telephone = Column(String(20), nullable=True)
    adresse = Column(Text, nullable=True)
    date_creation = Column(DateTime, default=func.now())
    source_type = Column(String(50), nullable=True)
    source_detail = Column(String(50), nullable=True)
    source_client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    dossiers = relationship("Dossier", back_populates="client")
    source_client = relationship("Client", foreign_keys=[source_client_id], remote_side="Client.id")


class Dossier(Base):
    __tablename__ = "dossiers"

    id = Column(Integer, primary_key=True)
    reference = Column(String(20), unique=True, nullable=False)
    intitule = Column(String(300), nullable=False)
    contexte = Column(Text, nullable=True)
    statut = Column(Enum("en_cours", "cloture", "transfere", name="dossier_statut"), default="en_cours")
    date_ouverture = Column(Date, nullable=False)
    date_cloture = Column(Date, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    avocat_id = Column(Integer, ForeignKey("avocats.id"), nullable=False)

    client = relationship("Client", back_populates="dossiers")
    avocat = relationship("Avocat", back_populates="dossiers")
    actes = relationship("Acte", back_populates="dossier", cascade="all, delete-orphan")
    echeances = relationship("Echeance", back_populates="dossier", cascade="all, delete-orphan", order_by="Echeance.date")


class TypeActe(Base):
    __tablename__ = "type_actes"

    id = Column(Integer, primary_key=True)
    libelle = Column(String(100), unique=True, nullable=False)

    actes = relationship("Acte", back_populates="type_acte")


class Acte(Base):
    __tablename__ = "actes"

    id = Column(Integer, primary_key=True)
    nom = Column(String(300), nullable=False)
    type_acte_id = Column(Integer, ForeignKey("type_actes.id"), nullable=False)
    lien_onedrive = Column(String(2000), nullable=False)
    date_production = Column(Date, nullable=False)
    dossier_id = Column(Integer, ForeignKey("dossiers.id"), nullable=True)

    type_acte = relationship("TypeActe", back_populates="actes")
    dossier = relationship("Dossier", back_populates="actes")
    acte_tags = relationship("ActeTag", back_populates="acte", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    libelle = Column(String(100), unique=True, nullable=False)

    acte_tags = relationship("ActeTag", back_populates="tag", cascade="all, delete-orphan")


class Echeance(Base):
    __tablename__ = "echeances"

    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey("dossiers.id"), nullable=False)
    libelle = Column(String(200), nullable=False)
    date = Column(Date, nullable=False)

    dossier = relationship("Dossier", back_populates="echeances")


class ActeTag(Base):
    __tablename__ = "acte_tags"

    acte_id = Column(Integer, ForeignKey("actes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    acte = relationship("Acte", back_populates="acte_tags")
    tag = relationship("Tag", back_populates="acte_tags")
