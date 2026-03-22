# Cabinet Juridique

Outil web auto-hébergé de gestion de dossiers juridiques pour avocate solo.
Référentiel de liens vers des documents stockés sur OneDrive — ne stocke pas les fichiers.

## Fonctionnalités (MVP)

| Module | Description |
|---|---|
| **Clients** | Fiche complète personne/société, SIRET, coordonnées |
| **Dossiers** | Création avec contexte, statut, référence auto (AAAA-NNN), dates audience/échéance |
| **Actes** | Lien OneDrive, type, tags libres, liaison à un ou plusieurs dossiers |
| **Types d'actes** | Liste prédéfinie, extensible par l'avocate |
| **Recherche** | Multi-critères live (HTMX), résultats groupés Dossiers/Actes |
| **Authentification** | Session cookie sécurisée (itsdangerous) |

## Stack technique

- **Backend** : FastAPI + SQLAlchemy 2.x (sync) + SQLite
- **Migrations** : Alembic
- **Frontend** : Jinja2 + HTMX (pas de JavaScript custom, pas de framework CSS)
- **Charte graphique** : identique à `legal-anonymizer` (Playfair Display, palette beige/noir)
- **Auth** : session FastAPI, cookie signé HttpOnly

## Structure du projet

```
cabinet-juridique/
├── app/
│   ├── main.py              # App FastAPI, inclusion des routers
│   ├── database.py          # Engine SQLAlchemy, SessionLocal, Base
│   ├── models.py            # ORM models (Avocat, Client, Dossier, Acte, TypeActe, Tag)
│   ├── schemas.py           # Pydantic v2 schemas
│   ├── crud.py              # Toutes les opérations CRUD
│   ├── auth.py              # Session cookie, login/logout
│   ├── search.py            # Logique recherche multi-critères
│   ├── seed.py              # Données initiales (types d'actes + avocat admin)
│   ├── routers/
│   │   ├── clients.py
│   │   ├── dossiers.py
│   │   ├── actes.py
│   │   ├── type_actes.py
│   │   └── search.py
│   ├── static/
│   │   └── style.css
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── pages/           # Pages completes
│       └── partials/        # Fragments HTMX
├── tests/                   # 72 tests pytest
├── alembic/                 # Migrations DB
├── data/                    # Volume Docker - cabinet.db ici
├── Dockerfile
├── docker-compose.yml
└── .env
```

## Modèle de données

```
Avocat
└── id, nom, prenom, email, password_hash

Client
└── id, type (personne/societe), nom, prenom, raison_sociale, siret, email, telephone, adresse

Dossier
└── id, reference (AAAA-NNN), intitule, contexte, statut, date_ouverture, date_cloture,
    date_echeance, date_audience, client_id, avocat_id

TypeActe
└── id, libelle

Acte
└── id, nom, type_acte_id, lien_onedrive, date_production
    → many-to-many Dossier (via acte_dossiers)
    → many-to-many Tag (via acte_tags)

Tag
└── id, libelle
```

La référence dossier est auto-générée au format `AAAA-NNN` (ex: `2026-001`), compteur remis a zéro chaque 1er janvier.

Un acte peut être lié à plusieurs dossiers (cas des actes transversaux).

## Installation et lancement

### Prérequis

- Docker + Docker Compose
- Accès Tailscale au VPS (ou réseau local)

### Démarrage rapide (Docker)

```bash
# 1. Cloner le repo
git clone https://github.com/ricboro/cabinet-juridique.git
cd cabinet-juridique

# 2. Créer le fichier .env
cp .env.example .env
# Editer .env : définir SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD

# 3. Lancer
docker compose up -d --build

# 4. Accéder a l'interface
# VPS : http://100.81.134.30:8092
# Local : http://localhost:8092
```

Au premier démarrage, `seed.py` crée automatiquement :
- Les 12 types d'actes par défaut
- Le compte avocat admin (email/mot de passe définis dans `.env`)

### Variables d'environnement (`.env`)

```env
DATABASE_URL=sqlite:////data/cabinet.db
SECRET_KEY=<générer avec: python3 -c "import secrets; print(secrets.token_hex(32))">
ADMIN_EMAIL=avocat@cabinet.fr
ADMIN_PASSWORD=<mot de passe initial>
PORT=8092
```

### Développement local (sans Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Lancer les migrations
alembic upgrade head

# Lancer le serveur
uvicorn app.main:app --reload --port 8092
```

### Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

72 tests couvrant : modèles, CRUD, routes, auth, recherche.

## Déploiement VPS (OVH Ubuntu 24.04)

Le service est accessible via Tailscale uniquement (`100.81.134.30:8092`).
Pas de Nginx pour le MVP - a ajouter lors de la mise en production avec domaine.

```bash
cd /home/ubuntu/cabinet-juridique
docker compose up -d --build
docker compose logs -f app
```

```bash
# Premier démarrage — création automatique du compte et des données
# Vérifier les logs pour confirmer le seed
docker compose logs app | grep SEED
```

### Backup

La base SQLite est dans `./data/cabinet.db`. Backup quotidien recommandé :

```bash
# Cron exemple — backup local quotidien avec rotation sur 7 jours
# Editer avec : crontab -e
0 2 * * * cp /home/ubuntu/cabinet-juridique/data/cabinet.db \
             /home/ubuntu/cabinet-juridique/data/cabinet.db.bak.$(date +\%Y\%m\%d) && \
             find /home/ubuntu/cabinet-juridique/data/ -name "cabinet.db.bak.*" -mtime +7 -delete
```

## Roadmap

### MVP (en cours)

- [x] Modele de données (Avocat, Client, Dossier, Acte, TypeActe, Tag)
- [x] Couche CRUD + tests unitaires (32 tests)
- [x] Couche UI/Templates (Jinja2 + HTMX)
- [x] Routes FastAPI (auth, clients, dossiers, actes, recherche)
- [x] Tests routes (40 tests)
- [x] Docker + README
- [x] Audit qualité + corrections

### Après MVP

- [ ] Nginx + Let's Encrypt (quand domaine décidé)
- [ ] Export CSV des dossiers/clients
- [ ] Suivi des événements sur un dossier (audiences, relances)
- [ ] Migration PostgreSQL si montée en charge (SQLAlchemy ORM - changement de connection string uniquement)
- [ ] Application mobile (API REST déjà en place)

## Sécurité

- Accès restreint au réseau Tailscale (pas d'exposition Internet pour le MVP)
- Session cookie signé (itsdangerous), HttpOnly, SameSite=Lax
- Mots de passe hashés avec bcrypt
- Pas de stockage de documents (liens OneDrive uniquement)
