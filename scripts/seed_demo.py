"""
Jeu de données de démonstration — Cabinet Juridique
Usage : python3 scripts/seed_demo.py

Crée directement dans la base SQLite (./data/cabinet.db via DATABASE_URL).
Idempotent : ne recrée pas ce qui existe déjà (vérifie par email/raison sociale/référence).
"""

import os
import sys
from datetime import date

# Permet d'importer app/ sans être dans le conteneur
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/cabinet.db")
os.environ.setdefault("SECRET_KEY", "demo")
os.environ.setdefault("TESTING", "1")  # désactive le lifespan FastAPI

from app.database import engine, Base, SessionLocal
from app.models import Avocat, Client, Dossier, TypeActe, Acte, Tag, ActeDossier, ActeTag
import bcrypt

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Récupérer l'avocat existant ───────────────────────────────────────────────
avocat = db.query(Avocat).first()
if not avocat:
    print("❌  Aucun avocat trouvé — lancez d'abord le conteneur pour exécuter seed.py.")
    sys.exit(1)

print(f"✔  Avocat : {avocat.prenom} {avocat.nom}")

# ── Helper ────────────────────────────────────────────────────────────────────
def get_or_create_type(libelle: str) -> TypeActe:
    ta = db.query(TypeActe).filter_by(libelle=libelle).first()
    if not ta:
        ta = TypeActe(libelle=libelle)
        db.add(ta)
        db.flush()
    return ta

def get_or_create_tag(libelle: str) -> Tag:
    tag = db.query(Tag).filter_by(libelle=libelle).first()
    if not tag:
        tag = Tag(libelle=libelle)
        db.add(tag)
        db.flush()
    return tag

# ── Clients ───────────────────────────────────────────────────────────────────
clients_data = [
    dict(type="personne", nom="Leclerc", prenom="Thomas",
         email="t.leclerc@gmail.com", telephone="06 12 34 56 78",
         adresse="14 rue des Acacias, 75017 Paris"),
    dict(type="personne", nom="Fontaine", prenom="Marie-Claire",
         email="mc.fontaine@outlook.fr", telephone="06 98 76 54 32",
         adresse="8 avenue Victor Hugo, 69006 Lyon"),
    dict(type="personne", nom="Girard", prenom="Sophie",
         email="sophie.girard@free.fr", telephone="07 45 23 67 89",
         adresse="3 impasse des Lilas, 33000 Bordeaux"),
    dict(type="societe", raison_sociale="Dupont & Fils SARL",
         siret="44306184000047",
         email="contact@dupont-fils.fr", telephone="01 42 58 96 30",
         adresse="22 boulevard Haussmann, 75009 Paris"),
    dict(type="societe", raison_sociale="SCI Les Pins",
         siret="81234567800012",
         email="sci.lespins@notaires.fr", telephone="04 93 12 45 67",
         adresse="Résidence Les Pins, 06400 Cannes"),
]

clients = {}
for data in clients_data:
    key = data.get("email") or data.get("raison_sociale")
    existing = db.query(Client).filter_by(email=data.get("email")).first() if data.get("email") else \
               db.query(Client).filter_by(raison_sociale=data.get("raison_sociale")).first()
    if existing:
        print(f"  (existe déjà) Client : {key}")
        clients[key] = existing
    else:
        c = Client(**data)
        db.add(c)
        db.flush()
        print(f"  ✔  Client créé : {key}")
        clients[key] = c

# ── Dossiers ──────────────────────────────────────────────────────────────────
def get_next_ref(year: int) -> str:
    count = db.query(Dossier).filter(Dossier.reference.like(f"{year}-%")).count()
    return f"{year}-{count + 1:03d}"

dossiers_data = [
    dict(
        ref_key="divorce_leclerc",
        client_key="t.leclerc@gmail.com",
        intitule="Divorce contentieux Leclerc / Renard",
        contexte="Procédure de divorce contentieux initiée par M. Leclerc. "
                 "Désaccord sur la garde des enfants et la prestation compensatoire. "
                 "Audience de conciliation fixée.",
        statut="en_cours",
        date_ouverture=date(2026, 1, 15),
        date_echeance=date(2026, 6, 30),
        date_audience=date(2026, 4, 10),
    ),
    dict(
        ref_key="licenciement_fontaine",
        client_key="mc.fontaine@outlook.fr",
        intitule="Licenciement abusif — Fontaine c/ Entreprise Renova",
        contexte="Licenciement pour faute grave contesté. Mme Fontaine conteste les "
                 "motifs invoqués par l'employeur. Saisine du conseil de prud'hommes.",
        statut="en_cours",
        date_ouverture=date(2026, 2, 3),
        date_echeance=date(2026, 9, 15),
        date_audience=date(2026, 5, 22),
    ),
    dict(
        ref_key="bail_girard",
        client_key="sophie.girard@free.fr",
        intitule="Litige locatif — expulsion Girard",
        contexte="Bailleur souhaitant récupérer son bien occupé par une locataire "
                 "en situation d'impayés depuis 4 mois. Mise en demeure envoyée.",
        statut="en_cours",
        date_ouverture=date(2026, 3, 1),
        date_echeance=date(2026, 7, 1),
    ),
    dict(
        ref_key="cession_dupont",
        client_key="contact@dupont-fils.fr",
        intitule="Cession de parts sociales — Dupont & Fils SARL",
        contexte="Cession de 40% des parts de M. Dupont père à son fils. "
                 "Protocole d'accord rédigé et signé. Opération finalisée.",
        statut="cloture",
        date_ouverture=date(2025, 9, 10),
        date_cloture=date(2025, 12, 20),
    ),
    dict(
        ref_key="sci_pins",
        client_key="sci.lespins@notaires.fr",
        intitule="Constitution SCI Les Pins",
        contexte="Rédaction des statuts et enregistrement d'une SCI familiale pour "
                 "acquisition d'un bien immobilier sur la Côte d'Azur.",
        statut="cloture",
        date_ouverture=date(2025, 11, 5),
        date_cloture=date(2026, 1, 28),
    ),
    dict(
        ref_key="contrat_girard",
        client_key="sophie.girard@free.fr",
        intitule="Rédaction contrat de prestation — Girard Conseil",
        contexte="Mme Girard exerce en freelance et souhaite sécuriser ses contrats "
                 "clients. Rédaction d'un modèle de contrat de prestation de services.",
        statut="suspendu",
        date_ouverture=date(2026, 1, 20),
    ),
]

dossiers = {}
for d in dossiers_data:
    key = d.pop("ref_key")
    client_key = d.pop("client_key")
    client = clients[client_key]
    year = d["date_ouverture"].year

    existing = db.query(Dossier).filter_by(intitule=d["intitule"]).first()
    if existing:
        print(f"  (existe déjà) Dossier : {d['intitule'][:45]}")
        dossiers[key] = existing
    else:
        ref = get_next_ref(year)
        dos = Dossier(reference=ref, client_id=client.id, avocat_id=avocat.id, **d)
        db.add(dos)
        db.flush()
        print(f"  ✔  Dossier créé : {ref} — {d['intitule'][:45]}")
        dossiers[key] = dos

# ── Actes ─────────────────────────────────────────────────────────────────────
ta_assignation   = get_or_create_type("assignation")
ta_conclusions   = get_or_create_type("conclusions")
ta_courrier      = get_or_create_type("courrier")
ta_ordonnance    = get_or_create_type("ordonnance")
ta_mise_en_dem   = get_or_create_type("mise en demeure")
ta_protocole     = get_or_create_type("protocole d'accord")
ta_contrat       = get_or_create_type("contrat")

tag_urgent    = get_or_create_tag("urgent")
tag_signature = get_or_create_tag("à signer")
tag_transmis  = get_or_create_tag("transmis client")
tag_prud      = get_or_create_tag("prud'hommes")
tag_famille   = get_or_create_tag("droit de la famille")

actes_data = [
    dict(
        nom="Assignation en divorce contentieux",
        type_acte=ta_assignation,
        lien_onedrive="https://onedrive.live.com/personal/demo/assignation-divorce-leclerc.docx",
        date_production=date(2026, 1, 20),
        dossier_keys=["divorce_leclerc"],
        tag_keys=["droit de la famille"],
    ),
    dict(
        nom="Conclusions en réponse — audience conciliation",
        type_acte=ta_conclusions,
        lien_onedrive="https://onedrive.live.com/personal/demo/conclusions-conciliation-leclerc.docx",
        date_production=date(2026, 3, 5),
        dossier_keys=["divorce_leclerc"],
        tag_keys=["droit de la famille", "à signer"],
    ),
    dict(
        nom="Courrier de mise en demeure — loyers impayés",
        type_acte=ta_mise_en_dem,
        lien_onedrive="https://onedrive.live.com/personal/demo/miseendemeure-girard.docx",
        date_production=date(2026, 3, 8),
        dossier_keys=["bail_girard"],
        tag_keys=["transmis client", "urgent"],
    ),
    dict(
        nom="Assignation devant le conseil de prud'hommes",
        type_acte=ta_assignation,
        lien_onedrive="https://onedrive.live.com/personal/demo/assignation-prudhommes-fontaine.docx",
        date_production=date(2026, 2, 15),
        dossier_keys=["licenciement_fontaine"],
        tag_keys=["prud'hommes", "urgent"],
    ),
    dict(
        nom="Conclusions récapitulatives — licenciement",
        type_acte=ta_conclusions,
        lien_onedrive="https://onedrive.live.com/personal/demo/conclusions-fontaine-v2.docx",
        date_production=date(2026, 3, 18),
        dossier_keys=["licenciement_fontaine"],
        tag_keys=["prud'hommes"],
    ),
    dict(
        nom="Protocole d'accord de cession de parts",
        type_acte=ta_protocole,
        lien_onedrive="https://onedrive.live.com/personal/demo/protocole-cession-dupont.docx",
        date_production=date(2025, 11, 30),
        dossier_keys=["cession_dupont"],
        tag_keys=["transmis client"],
    ),
    dict(
        nom="Statuts SCI Les Pins — version finale",
        type_acte=ta_contrat,
        lien_onedrive="https://onedrive.live.com/personal/demo/statuts-sci-lespins-final.docx",
        date_production=date(2025, 12, 10),
        dossier_keys=["sci_pins"],
        tag_keys=["à signer", "transmis client"],
    ),
    dict(
        nom="Modèle contrat prestation de services",
        type_acte=ta_contrat,
        lien_onedrive="https://onedrive.live.com/personal/demo/contrat-prestation-girard.docx",
        date_production=date(2026, 2, 1),
        dossier_keys=["contrat_girard"],
        tag_keys=[],
    ),
    dict(
        nom="Courrier récapitulatif procédure divorce",
        type_acte=ta_courrier,
        lien_onedrive="https://onedrive.live.com/personal/demo/courrier-recapitulatif-leclerc.docx",
        date_production=date(2026, 2, 28),
        dossier_keys=["divorce_leclerc"],
        tag_keys=["transmis client"],
    ),
]

for a_data in actes_data:
    existing = db.query(Acte).filter_by(nom=a_data["nom"]).first()
    if existing:
        print(f"  (existe déjà) Acte : {a_data['nom'][:50]}")
        continue

    acte = Acte(
        nom=a_data["nom"],
        type_acte_id=a_data["type_acte"].id,
        lien_onedrive=a_data["lien_onedrive"],
        date_production=a_data["date_production"],
    )
    db.add(acte)
    db.flush()

    for dk in a_data["dossier_keys"]:
        db.add(ActeDossier(acte_id=acte.id, dossier_id=dossiers[dk].id))

    for tk in a_data["tag_keys"]:
        tag = get_or_create_tag(tk)
        db.add(ActeTag(acte_id=acte.id, tag_id=tag.id))

    print(f"  ✔  Acte créé : {a_data['nom'][:50]}")

db.commit()
db.close()
print("\n✅  Données de démonstration chargées avec succès.")
