# Cabinet Juridique

Outil web auto-hébergé de gestion de dossiers juridiques pour avocate solo.
L'outil est un **référentiel de liens** vers des documents stockés sur OneDrive — il ne stocke aucun fichier.

Accessible uniquement via Tailscale (`http://100.81.134.30:8092`) pour le MVP.

---

## Table des matières

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Architecture](#2-architecture)
3. [Modele de donnees](#3-modele-de-donnees)
4. [Fonctionnalites](#4-fonctionnalites)
5. [Flux utilisateur](#5-flux-utilisateur)
6. [Structure du projet](#6-structure-du-projet)
7. [Stack technique](#7-stack-technique)
8. [Authentification et securite](#8-authentification-et-securite)
9. [Installation et lancement](#9-installation-et-lancement)
10. [Developpement local](#10-developpement-local)
11. [Tests](#11-tests)
12. [Operations et maintenance](#12-operations-et-maintenance)
13. [Roadmap](#13-roadmap)

---

## 1. Contexte et objectif

Une avocate solo a besoin de :
- Centraliser ses clients (personnes physiques et sociétés)
- Associer des dossiers a chaque client, avec statut et contexte
- Référencer les actes produits (contrats, assignations, courriers...) avec un lien direct vers OneDrive
- Retrouver rapidement un acte ou un dossier via une recherche multi-critères

L'outil ne remplace pas OneDrive : il stocke uniquement les métadonnées et les liens. Les fichiers restent dans OneDrive Pro de l'avocate.

---

## 2. Architecture

### Vue d'ensemble

```
Navigateur (PuTTY / Chrome via Tailscale)
    |
    | HTTP (Tailscale uniquement — 100.81.134.30:8092)
    v
+--------------------------------------------------+
|  FastAPI (Python 3.12)                           |
|  - Routes HTML (Jinja2 templates)                |
|  - Routes HTMX (fragments HTML partiels)         |
|  - Session auth (itsdangerous cookie)            |
+--------------------------------------------------+
    |
    | SQLAlchemy ORM (sync)
    v
+--------------------------------------------------+
|  SQLite  (/data/cabinet.db)                      |
|  Migrations gérées par Alembic                   |
+--------------------------------------------------+
```

### Flux d'une requete classique

```
1. Navigateur envoie GET /dossiers (avec cookie session)
2. FastAPI vérifie la session via get_current_user()
   - Cookie absent ou invalide → redirect /login
   - Cookie valide → Avocat chargé depuis DB
3. Router dossiers.py appelle crud.get_dossiers()
4. CRUD retourne les données via SQLAlchemy
5. Template pages/dossiers/list.html rendu avec Jinja2
6. HTML complet envoyé au navigateur
```

### Flux HTMX (recherche live)

```
1. Utilisateur tape dans la barre de recherche (≥ 3 caractères)
2. HTMX envoie GET /search/htmx?q=... (après 300ms debounce)
3. FastAPI retourne uniquement le fragment partials/search_results.html
4. HTMX remplace le contenu du div #search-live-results en place
   (pas de rechargement de page)
```

### Organisation des couches

| Couche | Fichier(s) | Responsabilité |
|---|---|---|
| Modeles | `app/models.py` | Tables SQLAlchemy, relations ORM |
| Schemas | `app/schemas.py` | Validation Pydantic v2 (entrees/sorties) |
| CRUD | `app/crud.py` | Toute la logique metier et acces DB |
| Auth | `app/auth.py` | Session cookie, dépendances FastAPI |
| Routers | `app/routers/*.py` | Routes HTTP, parsing form, redirects |
| Templates | `app/templates/` | HTML Jinja2 (pages completes + partials HTMX) |
| Utils | `app/utils.py` | Fonctions partagées (parse_date...) |
| Seed | `app/seed.py` | Données initiales au premier démarrage |

**Règle absolue** : toute logique metier passe par `crud.py`. Les routers ne font que parser le formulaire, appeler crud, et rediriger.

---

## 3. Modele de donnees

### Diagramme

```
Avocat
├── id (PK)
├── nom, prenom, email (unique)
└── password_hash (bcrypt)
      |
      | 1..N
      v
Dossier ←────────── Client
├── id (PK)          ├── id (PK)
├── reference         ├── type (personne/societe)
│   (AAAA-NNN)       ├── nom, prenom
├── intitule          ├── raison_sociale, siret
├── contexte          ├── email, telephone, adresse
├── statut            └── date_creation
│   (en_cours/
│    cloture/
│    suspendu)
├── date_ouverture
├── date_cloture
├── client_id (FK)
└── avocat_id (FK)
      |
      | 1..N          1..N
      v                v
Echeance           Acte ─────── Tag
├── id (PK)        ├── id (PK)   ├── id (PK)
├── dossier_id(FK) ├── nom       └── libelle (unique)
├── libelle        ├── type_acte_id (FK)   ^
└── date           ├── lien_onedrive       | N..N (via acte_tags)
                   ├── date_production ────┘
                   └── dossier_id (FK)

TypeActe
├── id (PK)
└── libelle (unique)
```

### Règles metier importantes

**Référence dossier** : format `AAAA-NNN` (ex: `2026-001`). Générée automatiquement a la création, compteur repart a `001` chaque 1er janvier. Algorithme : compte les références existantes commencant par `AAAA-` et incrémente.

**Un acte = un dossier** : un acte est lié à un seul dossier (FK directe `dossier_id`). C'est une contrainte métier : un acte produit dans le cadre d'un dossier y reste rattaché.

**Échéances multiples** : un dossier peut avoir autant d'échéances que nécessaire (audiences, conciliations, délais...). Chaque échéance a un libellé libre et une date. Ajout et suppression depuis la fiche dossier ou le formulaire de modification.

**Suppression protégée** :
- `DELETE client` → bloqué si le client a des dossiers (ValueError → flash error)
- `DELETE type_acte` → bloqué si des actes utilisent ce type
- `DELETE dossier` → supprime en cascade ses actes, échéances et tags associés
- `DELETE acte` → supprime ses tags associés (cascade ORM)

**Statuts dossier** :
- `en_cours` : dossier actif
- `suspendu` : dossier mis en attente (peut reprendre)
- `cloture` : dossier terminé — la clôture positionne automatiquement `date_cloture = today`

---

## 4. Fonctionnalites

### Clients

- Fiche personne physique (nom, prénom, email, téléphone, adresse)
- Fiche société (raison sociale, SIRET, email, téléphone, adresse)
- Liste paginée (20/page) triée par nom
- Accès direct aux dossiers d'un client depuis sa fiche
- Suppression bloquée si dossiers existants

### Dossiers

- Référence auto-générée `AAAA-NNN`
- Contexte libre (notes, références externes)
- Statut : en cours / suspendu / clôturé
- Date d'ouverture (obligatoire), date de clôture (positionnée automatiquement a la clôture)
- Échéances multiples (audience, conciliation, délai...) : libellé + date, ajout/suppression depuis la fiche
- Filtres : statut, client, avocat
- Clôture en 1 clic (bouton dédié)

### Actes

- Lien OneDrive (URL validée http/https obligatoire)
- Type d'acte (liste prédéfinie extensible)
- Tags libres avec autocomplétion (créés a la volée si nouveaux)
- Liaison à un seul dossier (select)

### Types d'actes

12 types prédéfinis au démarrage :
`Contrat`, `Assignation`, `Conclusions`, `Courrier`, `Ordonnance`, `Jugement`, `Appel`, `Requête`, `Mémoire`, `Acte de procédure`, `Mise en demeure`, `Protocole d'accord`

L'avocate peut en ajouter depuis la page de gestion. Suppression impossible si des actes utilisent le type.

### Recherche

- Barre de recherche dans le header (toutes les pages)
- Résultats live via HTMX (dès 3 caractères, debounce 300ms)
- Page de recherche complète avec filtres avancés : type d'acte, tag, client, avocat, statut dossier
- Résultats groupés en 2 sections : **Dossiers** et **Actes**

---

## 5. Flux utilisateur

### Créer un nouveau dossier

```
1. Clients → fiche client → "Nouveau dossier pour ce client"
   (ou Dossiers → "Nouveau dossier" → sélectionner le client)
2. Remplir : intitulé, contexte, avocat responsable, date d'ouverture
3. La référence AAAA-NNN est générée automatiquement
4. Enregistrer → fiche dossier ouverte
```

### Ajouter un acte a un dossier

```
1. Fiche dossier → "Ajouter un acte"
   (ou Actes → Nouvel acte → sélectionner le dossier)
2. Remplir : nom du document, type, coller le lien OneDrive, date de production
3. Tags : taper pour autocomplétion, Entrée pour créer un nouveau tag
4. Sélectionner le dossier lié (pré-sélectionné si arrivé depuis la fiche dossier)
5. Enregistrer → l'acte apparait dans la fiche du dossier
```

### Clôturer un dossier

```
1. Fiche dossier → bouton "Clôturer"
2. Confirmation → statut passe a "clôturé", date_cloture = aujourd'hui
3. Le dossier reste consultable et ses actes sont accessibles
```

### Rechercher un acte

```
Option 1 (rapide) : taper dans la barre du header → résultats live
Option 2 (filtré) : page Recherche → filtres type/tag/client/statut → Rechercher
```

---

## 6. Structure du projet

```
cabinet-juridique/
├── app/
│   ├── main.py              # App FastAPI : lifespan, routes dashboard/login/logout,
│   │                        #   helper make_context(), exception handler auth
│   ├── database.py          # Engine SQLAlchemy, SessionLocal, Base, get_db(), init_db()
│   ├── models.py            # 8 modeles ORM : Avocat, Client, Dossier, Echeance,
│   │                        #   TypeActe, Acte, Tag, ActeTag
│   ├── schemas.py           # Schemas Pydantic v2 (validation entrées/sorties API)
│   ├── crud.py              # Toutes les fonctions CRUD (logique metier centralisée)
│   ├── auth.py              # Session cookie itsdangerous, get_current_user(),
│   │                        #   flash messages, _RedirectException
│   ├── utils.py             # parse_date() partagée entre routers
│   ├── seed.py              # Données initiales : 12 types d'actes + avocat admin
│   ├── routers/
│   │   ├── clients.py       # GET/POST /clients, /clients/{id}, /clients/{id}/edit...
│   │   ├── dossiers.py      # GET/POST /dossiers, /dossiers/{id}/close...
│   │   ├── actes.py         # GET/POST /actes, /actes/tags/autocomplete (HTMX)
│   │   ├── type_actes.py    # GET/POST /type-actes, /type-actes/{id}/delete
│   │   └── search.py        # GET /search (page), GET /search/htmx (fragment)
│   ├── static/
│   │   └── style.css        # CSS custom (pas de framework) — charte legal-anonymizer
│   └── templates/
│       ├── base.html        # Layout commun : header, nav, barre recherche HTMX, logout
│       ├── login.html       # Page connexion (sans layout commun)
│       ├── pages/
│       │   ├── dashboard.html           # Statistiques + derniers dossiers
│       │   ├── clients/
│       │   │   ├── list.html            # Liste paginée + recherche
│       │   │   ├── detail.html          # Fiche client + ses dossiers
│       │   │   └── form.html            # Création / modification (toggle personne/société)
│       │   ├── dossiers/
│       │   │   ├── list.html            # Liste paginée + filtres
│       │   │   ├── detail.html          # Fiche dossier + ses actes
│       │   │   └── form.html            # Création / modification
│       │   ├── actes/
│       │   │   └── form.html            # Création / modification (tags HTMX + select dossier)
│       │   ├── type_actes/
│       │   │   └── list.html            # Liste + ajout inline + suppression
│       │   └── search.html              # Page recherche complète avec filtres
│       └── partials/                    # Fragments HTMX (retournés sans layout)
│           ├── actes_list.html          # Liste des actes d'un dossier
│           ├── search_results.html      # Résultats groupés Dossiers/Actes
│           ├── client_row.html          # Ligne de tableau client
│           ├── dossier_row.html         # Ligne de tableau dossier
│           └── acte_row.html            # Ligne/carte acte
├── tests/
│   ├── conftest.py          # Fixtures pytest : db (SQLite mémoire), avocat, client_personne,
│   │                        #   client_societe, type_acte, dossier, set_auth_cookie()
│   ├── test_models.py       # Tests intégrité modele (9 tests)
│   ├── test_crud.py         # Tests CRUD complets (27 tests)
│   ├── test_routes_auth.py  # Tests auth : login, logout, protection routes (9 tests)
│   ├── test_routes_clients.py  # Tests routes clients (14 tests)
│   ├── test_routes_dossiers.py # Tests routes dossiers (14 tests)
│   ├── test_routes_actes.py    # Tests routes actes (14 tests)
│   ├── test_search.py          # Tests recherche (11 tests)
│   └── test_utils.py           # Tests parse_date() (7 tests)
├── alembic/
│   ├── env.py               # Config Alembic (lit DATABASE_URL depuis env)
│   ├── script.py.mako       # Template migration
│   └── versions/
│       ├── 0001_initial_schema.py  # Migration initiale : toutes les tables
│       ├── 0002_echeances.py       # Échéances multiples par dossier (libellé + date)
│       └── 0003_acte_dossier_fk.py # Acte → FK dossier_id directe (suppression many-to-many)
├── data/
│   └── .gitkeep             # Répertoire versionné mais cabinet.db gitignorée
├── Dockerfile               # python:3.12-slim, copie app/ + alembic/, EXPOSE 8092
├── docker-compose.yml       # Service app, bind 100.81.134.30:8092, volume ./data:/data
├── alembic.ini              # Config Alembic (sqlalchemy.url depuis DATABASE_URL)
├── requirements.txt         # Dépendances Python
├── pytest.ini               # Config pytest
├── conftest.py              # (racine) Set TESTING=1 pour désactiver le lifespan en test
├── .env.example             # Template variables d'environnement (a copier en .env)
└── .gitignore               # Exclut .env, data/*.db, __pycache__, .venv
```

---

## 7. Stack technique

| Composant | Technologie | Version | Justification |
|---|---|---|---|
| Framework web | FastAPI | 0.115 | Async, typage, doc auto |
| ORM | SQLAlchemy | 2.x (sync) | Migration PostgreSQL = changement connection string |
| Migrations | Alembic | 1.14 | Versionnage schema, rollback possible |
| Validation | Pydantic | v2 | Intégré FastAPI, performant |
| Base de données | SQLite | 3.x | Suffisant pour usage solo, backup trivial |
| Templates | Jinja2 | 3.1 | Natif FastAPI, pas de JS requis |
| Interactivité | HTMX | 1.9 | Requêtes partielles sans écrire de JS |
| Auth | itsdangerous | 2.2 | Cookie signé, simple, sans JWT |
| Hash mots de passe | bcrypt | 4.2 | Standard, résistant aux attaques |
| Serveur ASGI | Uvicorn | 0.32 | Performant, intégré FastAPI |
| Conteneurisation | Docker + Compose | - | Déploiement reproductible |

**Pas de framework CSS** : CSS custom (450 lignes) avec variables CSS, même charte que `legal-anonymizer`.

**Pas de JavaScript custom** : HTMX gère toutes les interactions dynamiques (recherche live, autocomplétion tags). Le seul JS inline est le toggle personne/société dans le formulaire client et la gestion des chips de tags.

---

## 8. Authentification et securite

### Flux d'authentification

```
POST /login (email + password)
    |
    v
crud.get_avocat_by_email() → récupère l'avocat
    |
    v
crud.verify_password() → bcrypt.checkpw()
    |
    v (si ok)
auth.create_session(response, avocat.id)
    → URLSafeSerializer(SECRET_KEY).dumps({"user_id": id})
    → Set-Cookie: session=<token>; HttpOnly; SameSite=Lax
    |
    v
Redirect → /
```

### Protection des routes

Chaque router utilise `Depends(get_current_user)`. Si le cookie est absent ou invalide :
- `_RedirectException("/login")` est levée
- L'exception handler global retourne `RedirectResponse("/login", 303)`

### Flash messages

Les messages de confirmation/erreur sont stockés dans un cookie `flash` (signé, max_age=60s) et effacés a la première lecture. Permet d'afficher un message après une redirection sans état serveur.

### Points de sécurité

| Point | Statut | Détail |
|---|---|---|
| Cookie HttpOnly | OK | Inaccessible au JS |
| Cookie SameSite=Lax | OK | Protection CSRF partielle |
| Mot de passe bcrypt | OK | Hash non réversible |
| SECRET_KEY obligatoire | OK | Warning au démarrage si absente ou valeur par défaut |
| Accès réseau | OK | Bind Tailscale uniquement (100.81.134.30) |
| Pas de CSRF token | Note | Acceptable en Tailscale-only. A implémenter si exposition publique |
| Validation URL OneDrive | OK | urlparse vérifie scheme http/https et netloc |
| Injection SQL | OK | SQLAlchemy ORM, aucune requête SQL brute |

---

## 9. Installation et lancement

### Prérequis

- Docker + Docker Compose installés
- Accès au VPS via Tailscale (ou réseau local pour usage local)

### Démarrage (Docker)

```bash
# 1. Cloner le repo
git clone https://github.com/ricboro/cabinet-juridique.git
cd cabinet-juridique

# 2. Créer le fichier .env depuis le template
cp .env.example .env

# 3. Editer .env — obligatoire avant le premier démarrage
#    - SECRET_KEY : générer avec python3 -c "import secrets; print(secrets.token_hex(32))"
#    - ADMIN_EMAIL : email du premier compte avocat
#    - ADMIN_PASSWORD : mot de passe du premier compte avocat
nano .env

# 4. Lancer
docker compose up -d --build

# 5. Vérifier le démarrage
docker compose logs -f app
# Attendu :
#   INFO  [alembic] Running upgrade  -> 0001, initial schema
#   INFO  Application startup complete.
#   INFO  Uvicorn running on http://0.0.0.0:8092

# 6. Accéder
# Via Tailscale VPS : http://100.81.134.30:8092
# En local          : http://localhost:8092
```

### Variables d'environnement (`.env`)

```env
# Clé de signature des sessions — OBLIGATOIRE en production
# Générer avec : python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=remplacer-par-une-vraie-cle-secrete

# Compte avocat créé au premier démarrage (si table avocats vide)
ADMIN_EMAIL=avocat@cabinet.fr
ADMIN_PASSWORD=remplacer-par-un-vrai-mot-de-passe

# Base de données SQLite (ne pas modifier sauf hors Docker)
DATABASE_URL=sqlite:////data/cabinet.db

# Port d'écoute du serveur
PORT=8092
```

### Premier démarrage

Au démarrage, le container exécute automatiquement :
1. `alembic upgrade head` : crée toutes les tables (ou applique les migrations manquantes)
2. `seed.py` : peuple les 12 types d'actes par défaut + crée le compte avocat depuis `.env`

Si `ADMIN_EMAIL` ou `ADMIN_PASSWORD` sont absents du `.env`, un warning est affiché dans les logs et aucun compte n'est créé — l'app démarre mais la connexion est impossible.

---

## 10. Développement local

### Sans Docker

```bash
# Créer l'environnement Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Variables d'environnement minimales
export SECRET_KEY=dev-only-not-for-prod
export ADMIN_EMAIL=dev@test.fr
export ADMIN_PASSWORD=dev123
export DATABASE_URL=sqlite:///./data/cabinet.db

# Créer les tables
alembic upgrade head

# Lancer en mode développement (rechargement automatique)
uvicorn app.main:app --reload --port 8092
```

### Ajouter une migration Alembic

Lorsqu'on modifie `app/models.py` (ajout de colonne, nouvelle table...) :

```bash
# Générer la migration automatiquement (détecte les changements vs la DB)
alembic revision --autogenerate -m "description du changement"

# Vérifier le fichier généré dans alembic/versions/
# Puis appliquer
alembic upgrade head

# Rollback si nécessaire
alembic downgrade -1
```

### Commandes utiles

```bash
# Statut du container
docker compose ps

# Logs en direct
docker compose logs -f app

# Redémarrer sans rebuild
docker compose restart app

# Rebuild complet (après modification du code)
docker compose up -d --build

# Arrêt complet
docker compose down

# Ouvrir un shell dans le container
docker compose exec app bash

# Inspecter la DB SQLite directement
docker compose exec app python3 -c "
from app.database import SessionLocal
from app.models import Avocat, Client, Dossier
db = SessionLocal()
print('Avocats:', db.query(Avocat).count())
print('Clients:', db.query(Client).count())
print('Dossiers:', db.query(Dossier).count())
"
```

---

## 11. Tests

### Lancer les tests

```bash
# Installation des dépendances
pip install -r requirements.txt

# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=app --cov-report=term-missing

# Un fichier spécifique
pytest tests/test_crud.py -v

# Un test spécifique
pytest tests/test_routes_auth.py::test_login_success_redirects -v
```

### Résultats actuels

```
102 tests — 0 failed — couverture 90%
```

| Fichier | Tests | Couverture |
|---|---|---|
| `test_models.py` | 9 | modeles, contraintes unicité, many-to-many |
| `test_crud.py` | 27 | CRUD complet, pagination, filtres, recherche |
| `test_routes_auth.py` | 9 | login, logout, protection routes, flash |
| `test_routes_clients.py` | 14 | CRUD routes, validation, pagination, tri |
| `test_routes_dossiers.py` | 14 | CRUD routes, référence auto, clôture, 404 |
| `test_routes_actes.py` | 14 | CRUD routes, tags, URL validation, dossier lié |
| `test_search.py` | 8 | recherche, filtres, HTMX partial |
| `test_utils.py` | 7 | parse_date (cas limites) |

### Architecture des tests

- **DB isolée** : chaque test utilise une DB SQLite en mémoire (`sqlite:///:memory:`) via `StaticPool` — aucune interaction avec la DB de production
- **Auth simulée** : `set_auth_cookie(client, avocat)` dans `conftest.py` crée un cookie de session valide sans passer par le login
- **Lifespan désactivé** : `conftest.py` (racine) positionne `TESTING=1` pour court-circuiter le seed au démarrage

---

## 12. Operations et maintenance

### Backup

La base de données est dans `./data/cabinet.db`. Backup quotidien recommandé avec rotation 7 jours :

```bash
# Ajouter dans crontab : crontab -e
0 2 * * * cp /home/ubuntu/cabinet-juridique/data/cabinet.db \
             /home/ubuntu/cabinet-juridique/data/cabinet.db.bak.$(date +\%Y\%m\%d) && \
             find /home/ubuntu/cabinet-juridique/data/ -name "cabinet.db.bak.*" -mtime +7 -delete
```

### Changer le mot de passe d'un avocat

```bash
docker compose exec app python3 -c "
from app.database import SessionLocal
from app.crud import get_avocat_by_email
import bcrypt

db = SessionLocal()
avocat = get_avocat_by_email(db, 'margo@cabinet.fr')
if avocat:
    nouveau_hash = bcrypt.hashpw('nouveau_mot_de_passe'.encode(), bcrypt.gensalt()).decode()
    avocat.password_hash = nouveau_hash
    db.commit()
    print('Mot de passe mis a jour.')
else:
    print('Avocat non trouvé.')
"
```

### Ajouter un deuxième compte avocat

```bash
docker compose exec app python3 -c "
from app.database import SessionLocal
from app.crud import create_avocat

db = SessionLocal()
avocat = create_avocat(db, 'Dupont', 'Marie', 'marie@cabinet.fr', 'mot_de_passe')
print(f'Avocat créé : {avocat.prenom} {avocat.nom}')
"
```

### Mettre a jour l'application

```bash
cd /home/ubuntu/cabinet-juridique
git pull
docker compose up -d --build
# Alembic applique automatiquement les nouvelles migrations au démarrage
```

### Vérifier la santé du service

```bash
# Statut Docker
docker compose ps

# Healthcheck interne (GET /login doit retourner 200)
docker compose inspect cabinet-juridique-app-1 | grep -A5 Health

# Test direct
curl -s -o /dev/null -w "%{http_code}" http://100.81.134.30:8092/login
# Attendu : 200
```

---

## 13. Roadmap

### MVP (livré)

- [x] Modele de données (Avocat, Client, Dossier, Acte, TypeActe, Tag)
- [x] Couche CRUD + tests unitaires (32 tests)
- [x] Couche UI / Templates (Jinja2 + HTMX)
- [x] Routes FastAPI (auth, clients, dossiers, actes, recherche)
- [x] Tests routes (40 tests)
- [x] Infrastructure Docker + README
- [x] Audit qualité + corrections (102 tests, couverture 90%)

### Après MVP

- [ ] Nginx + HTTPS + Let's Encrypt (quand domaine décidé)
- [ ] Export CSV (liste clients, liste dossiers par période)
- [ ] Suivi d'événements sur un dossier (audiences, relances, notes de suivi horodatées)
- [ ] Statistiques avancées sur le dashboard (dossiers par mois, types d'actes les plus produits)
- [ ] Migration PostgreSQL si montée en charge — avec SQLAlchemy ORM, c'est uniquement un changement de `DATABASE_URL` + `alembic upgrade head`
- [ ] Application mobile (l'API FastAPI est déja en place, il suffit d'ajouter des routes JSON)
