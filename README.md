# Cabinet Juridique

Outil web auto-hébergé de gestion de dossiers juridiques pour avocate solo.
L'outil est un **référentiel de liens** vers des documents stockés sur OneDrive — il ne stocke aucun fichier.

Accès public sécurisé : `https://92.222.243.19:9444` (certificat auto-signé — domaine à venir)
Accès Tailscale direct : `http://100.81.134.30:8092`

---

## Table des matières

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Architecture](#2-architecture)
3. [Modele de donnees](#3-modele-de-donnees)
4. [Fonctionnalites](#4-fonctionnalites)
5. [Flux utilisateur](#5-flux-utilisateur)
6. [Structure du projet](#6-structure-du-projet)
7. [Stack technique](#7-stack-technique)
8. [Securite](#8-securite)
9. [Installation et lancement](#9-installation-et-lancement)
10. [Développement local](#10-développement-local)
11. [Tests](#11-tests)
12. [API REST](#12-api-rest)
13. [Operations et maintenance](#13-operations-et-maintenance)
14. [Roadmap](#14-roadmap)

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
Navigateur (Internet)
    |
    | HTTPS TLS 1.3 (port 9444)
    v
+--------------------------------------------------+
|  Nginx (Docker) — Reverse proxy                  |
|  - Terminaison TLS (certificat auto-signé)       |
|  - Rate limiting (30 req/min / 10 req/min login) |
|  - Headers sécurité (HSTS, X-Frame, CSP...)      |
+--------------------------------------------------+
    |
    | HTTP interne (Docker network)
    v
+--------------------------------------------------+
|  FastAPI (Python 3.12) — port 8092               |
|  - Routes HTML (Jinja2 templates)                |
|  - Routes HTMX (fragments HTML partiels)         |
|  - Session auth (itsdangerous cookie)            |
+--------------------------------------------------+
    |
    | SQLAlchemy ORM (sync)
    v
+--------------------------------------------------+
|  SQLite  (/data/cabinet.db)                      |
|  Propriétaire : svcadmincabinet (mode 600)       |
|  Migrations gérées par Alembic                   |
+--------------------------------------------------+
```

### Flux d'une requete classique

```
1. Navigateur envoie GET /dossiers via HTTPS (nginx)
2. Nginx vérifie le rate limit, forward à FastAPI avec X-Forwarded-For
3. FastAPI vérifie la session via get_current_user()
   - Cookie absent ou invalide → redirect /login
   - Cookie valide → Avocat chargé depuis DB
4. Router dossiers.py appelle crud.get_dossiers()
5. CRUD retourne les données via SQLAlchemy
6. Template pages/dossiers/list.html rendu avec Jinja2
7. HTML complet retourné via nginx au navigateur
```

### Flux HTMX (recherche live)

```
1. Utilisateur tape dans la barre de recherche (>= 3 caractères)
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
| Auth web | `app/auth.py` | Session cookie, dépendances FastAPI |
| Auth API | `app/api/auth.py` | Dépendance `require_api_key` (header X-API-Key) |
| Routers web | `app/routers/*.py` | Routes HTTP, parsing form, redirects |
| Routers API | `app/api/routes/*.py` | Endpoints JSON REST (prefix `/api/v1`) |
| Templates | `app/templates/` | HTML Jinja2 (pages completes + partials HTMX) |
| Utils | `app/utils.py` | Fonctions partagées (parse_date...) |
| Seed | `app/seed.py` | Données initiales au premier démarrage |

**Règle absolue** : toute logique metier passe par `crud.py`. Les routers (web et API) ne font qu'appeler crud et formater la réponse.

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
Dossier <────────── Client ──────────────┐ (référent)
├── id (PK)          ├── id (PK)         │
├── reference         ├── type (personne/societe)      │
│   (AAAA-NNN)       ├── nom, prenom     │
├── intitule          ├── raison_sociale, siret         │
├── contexte          ├── email, telephone, adresse     │
├── statut            ├── date_creation   │
│   (en_cours/        ├── source_type     │
│    cloture/          ├── source_detail   │
│    transfere)        ├── source_client_id (FK) ───────┘
├── date_ouverture   ├── titre (ex: Docteur)
├── date_cloture     ├── profession (santé)
├── honoraire_horaire └── specialite (médicale)
├── estimation_heures
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
- `transfere` : dossier transféré à un autre confrère
- `cloture` : dossier terminé — la clôture positionne automatiquement `date_cloture = today`

---

## 4. Fonctionnalites

### Clients

- Fiche personne physique (nom, prénom, email, téléphone, adresse)
- Fiche société (raison sociale, SIRET, email, téléphone, adresse)
- Validation email et téléphone (format français 06 00 00 00 00)
- Liste paginée (20/page) triée par nom
- Accès direct aux dossiers d'un client depuis sa fiche
- Suppression bloquée si dossiers existants
- **Provenance client** : comment le client a connu le cabinet (bouche à oreille via client existant ou confrère, internet, assureur, réseaux sociaux — LinkedIn / Instagram / TikTok / Facebook). Pour les recommandations clients, le référent est optionnel (peut être inconnu). Affiché sur la fiche client avec lien vers le client référent si renseigné.
- **Profil professionnel** (personne physique uniquement) : titre (texte libre, auto-renseigné "Docteur" si la profession sélectionnée est Médecin), profession (autocomplétion sur 24 professions de santé), spécialité médicale (autocomplétion sur 49 spécialités, visible uniquement si Médecin). Le titre s'affiche devant le nom dans la liste clients et la fiche client.

### Dossiers

- Référence auto-générée `AAAA-NNN`
- Contexte libre (notes, références externes)
- Statut : en cours / clôturé / transféré
- Date d'ouverture (obligatoire), date de clôture (positionnée automatiquement a la clôture)
- Échéances multiples (audience, conciliation, délai...) : libellé + date, ajout/suppression depuis la fiche
- Filtres : statut, client, avocat
- Clôture en 1 clic (bouton dédié)
- **Honoraires** : taux horaire (€/h, défaut 300 €) et estimation en heures, tous deux éditables. Total estimé calculé et affiché en temps réel dans le formulaire et sur la fiche dossier.

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
│   ├── schemas.py           # Schemas Pydantic v2 (validation entrées/sorties)
│   ├── crud.py              # Toutes les fonctions CRUD (logique metier centralisée)
│   ├── auth.py              # Session cookie itsdangerous, get_current_user(),
│   │                        #   flash messages, _RedirectException
│   ├── utils.py             # parse_date() partagée entre routers
│   ├── seed.py              # Données initiales : 12 types d'actes + avocat admin
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py          # Dépendance require_api_key (header X-API-Key)
│   │   ├── router.py        # Router principal monté sous /api/v1
│   │   └── routes/
│   │       ├── clients.py   # GET/POST/PUT/DELETE /api/v1/clients
│   │       ├── dossiers.py  # CRUD + close + echeances + generate
│   │       ├── actes.py     # GET/POST/PUT/DELETE /api/v1/actes
│   │       └── type_actes.py # GET/POST/DELETE /api/v1/type-actes
│   ├── routers/
│   │   ├── clients.py       # GET/POST /clients, /clients/{id}, /clients/{id}/edit...
│   │   ├── dossiers.py      # GET/POST /dossiers, /dossiers/{id}/close...
│   │   ├── actes.py         # GET/POST /actes, /actes/tags/autocomplete (HTMX)
│   │   ├── type_actes.py    # GET/POST /type-actes, /type-actes/{id}/delete
│   │   └── search.py        # GET /search (page), GET /search/htmx (fragment)
│   ├── static/
│   │   ├── style.css        # CSS custom (pas de framework) — charte legal-anonymizer
│   │   ├── fonts/           # Polices auto-hébergées (Playfair Display SC + Display)
│   │   └── js/
│   │       └── htmx.min.js  # HTMX auto-hébergé (pas de CDN externe)
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
│           ├── guide_modal.html         # Modal guide d'utilisation (bouton ?)
│           ├── client_row.html          # Ligne de tableau client
│           ├── dossier_row.html         # Ligne de tableau dossier
│           └── acte_row.html            # Ligne/carte acte
├── nginx/
│   ├── nginx.conf           # Reverse proxy HTTPS, rate limiting, headers sécurité
│   └── certs/               # Certificat auto-signé (gitignored — à générer au setup)
│       ├── server.crt
│       └── server.key
├── logs/
│   └── nginx/               # Logs nginx (access.log, error.log) — montés depuis Docker
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
│       ├── 0003_acte_dossier_fk.py # Acte → FK dossier_id directe (suppression many-to-many)
│       ├── 0004_statut_transfere.py # Statut dossier "suspendu" → "transféré"
│       ├── 0005_client_source.py   # Provenance client (source_type, source_detail, source_client_id)
│       ├── 0006_client_profession.py # Profil professionnel (titre, profession, specialite)
│       └── 0007_dossier_honoraires.py # Honoraires par dossier (honoraire_horaire, estimation_heures)
├── data/
│   └── .gitkeep             # Répertoire versionné mais cabinet.db gitignorée
├── Dockerfile               # python:3.12-slim, copie app/ + alembic/, EXPOSE 8092
├── docker-compose.yml       # Services : nginx (port 9444 public) + app (Tailscale only)
├── alembic.ini              # Config Alembic (sqlalchemy.url depuis DATABASE_URL)
├── requirements.txt         # Dépendances Python
├── pytest.ini               # Config pytest
├── conftest.py              # (racine) Set TESTING=1 pour désactiver le lifespan en test
├── .env.example             # Template variables d'environnement (a copier en .env)
└── .gitignore               # Exclut .env, data/*.db, nginx/certs/, logs/, __pycache__
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
| Interactivité | HTMX | 1.9 | Requêtes partielles sans écrire de JS (auto-hébergé) |
| Auth | itsdangerous | 2.2 | Cookie signé, simple, sans JWT |
| Hash mots de passe | bcrypt | 4.2 | Standard, résistant aux attaques |
| Serveur ASGI | Uvicorn | 0.32 | Performant, intégré FastAPI |
| Reverse proxy | Nginx (Alpine) | 1.29 | TLS, rate limiting, headers sécurité |
| Conteneurisation | Docker + Compose | - | Déploiement reproductible |

**Pas de framework CSS** : CSS custom avec variables CSS, même charte que `legal-anonymizer`.
**Pas de CDN externe** : HTMX et polices (Playfair Display SC + Display) sont auto-hébergés — conformité RGPD, pas de fuite d'IP vers Google Fonts.

---

## 8. Securite

### Architecture de sécurité

```
Internet → Nginx (TLS 1.3, port 9444) → FastAPI (HTTP interne) → SQLite (chmod 600)
                                                                    propriétaire : svcadmincabinet
fail2ban surveille les logs Nginx → ban automatique après 5 tentatives de login échouées
```

### Mesures en place

| Couche | Mesure | Détail |
|---|---|---|
| Réseau | HTTPS TLS 1.3 | Certificat auto-signé (Let's Encrypt quand domaine disponible) |
| Réseau | Port 8092 non exposé | App FastAPI liée à Tailscale uniquement (`100.81.134.30`) |
| Réseau | Port 80 fermé | Aucun accès HTTP non chiffré depuis internet |
| Nginx | Rate limiting | 30 req/min global, 10 req/min sur `/login` |
| Nginx | Headers sécurité | HSTS, X-Frame-Options DENY, X-Content-Type nosniff, Referrer-Policy, X-XSS-Protection |
| Nginx | Logs structurés | Accès au format standard, lus par fail2ban |
| Auth | bcrypt | Mots de passe hashés, non réversibles |
| Auth | Cookie HttpOnly | Inaccessible au JavaScript |
| Auth | Cookie SameSite=Lax | Protection CSRF |
| Auth | Session max_age=8h | Expiration automatique des sessions (28 800 secondes) |
| Auth | HTTP 401 sur échec login | Permettre la détection fail2ban |
| fail2ban | Jail cabinet-juridique-auth | Ban 1h après 5 tentatives échouées en 5 min, progressif jusqu'à 1 semaine |
| Système | Utilisateur svcadmincabinet | Container app tourne sous uid 997, sans shell, sans sudo |
| Système | DB chmod 600 | Fichier cabinet.db lisible uniquement par svcadmincabinet |
| Code | Aucun CDN externe | HTMX + polices auto-hébergés (pas de fuite d'IP visiteurs) |
| Code | Validation email + téléphone | Format vérifié côté serveur |
| Code | Validation URL OneDrive | urlparse vérifie scheme http/https et netloc |
| Code | ORM SQLAlchemy | Aucune requête SQL brute, injection SQL impossible |
| Secrets | .env gitignored | Clé secrète et credentials hors du repo |
| API | X-API-Key | Clé 64 hex (256 bits), passée en header — aucun endpoint API sans clé valide |
| Nginx | `/api/` bloqué port public | `return 403` sur toute requête `/api/*` via port 9444 — API accessible Tailscale :8092 uniquement |

### Ce qui reste à faire

| Priorité | Action |
|---|---|
| P1 | Changer le mot de passe admin (voir section 12) |
| P2 | Let's Encrypt quand domaine décidé (remplacer le certificat auto-signé) |

### Flux d'authentification

```
POST /login (identifiant + password)
    |
    v
crud.get_avocat_by_email() → récupère l'avocat par identifiant
    |
    v
crud.verify_password() → bcrypt.checkpw()
    |
    v (si ok)
auth.create_session(response, avocat.id)
    → URLSafeSerializer(SECRET_KEY).dumps({"user_id": id})
    → Set-Cookie: session=<token>; HttpOnly; SameSite=Lax; Max-Age=28800
    |
    v
Redirect → /

    v (si echec)
HTTP 401 → page login avec message d'erreur
→ fail2ban incrémente le compteur pour cette IP
→ ban si >= 5 tentatives en 5 min
```

---

## 9. Installation et lancement

### Prérequis

- Docker + Docker Compose installés
- Utilisateur système `svcadmincabinet` créé (voir ci-dessous)

### Setup initial (une seule fois)

```bash
# 1. Créer l'utilisateur système dédié
sudo useradd -r -s /usr/sbin/nologin -d /nonexistent \
  -c "Cabinet Juridique service account" svcadmincabinet

# 2. Cloner le repo
git clone https://github.com/ricboro/cabinet-juridique.git
cd cabinet-juridique

# 3. Créer le .env depuis le template
cp .env.example .env
# Editer .env : SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD (voir variables ci-dessous)
nano .env

# 4. Générer le certificat auto-signé (10 ans — à remplacer par Let's Encrypt plus tard)
mkdir -p nginx/certs
openssl req -x509 -newkey rsa:4096 \
  -keyout nginx/certs/server.key \
  -out nginx/certs/server.crt \
  -days 3650 -nodes \
  -subj "/C=FR/ST=France/L=Paris/O=Cabinet Juridique/CN=cabinet.local"

# 5. Créer les répertoires de logs
mkdir -p logs/nginx

# 6. Corriger les permissions de la DB (après premier démarrage ou sur DB existante)
UID_SVC=$(id -u svcadmincabinet)
GID_SVC=$(id -g svcadmincabinet)
# Mettre à jour docker-compose.yml si les UID/GID diffèrent de 997:986
sudo chown svcadmincabinet:svcadmincabinet data/
sudo chmod 750 data/

# 7. Ouvrir le port 9444 dans iptables
sudo iptables -I INPUT -p tcp --dport 9444 -j ACCEPT
sudo netfilter-persistent save

# 8. Configurer fail2ban
sudo cp /path/to/fail2ban-configs/cabinet-juridique-auth.conf /etc/fail2ban/filter.d/
sudo cp /path/to/fail2ban-configs/cabinet-juridique.conf /etc/fail2ban/jail.d/
sudo fail2ban-client reload

# 9. Lancer
docker compose up -d --build
```

### Démarrage standard (après setup)

```bash
docker compose up -d --build
```

### Variables d'environnement (`.env`)

```env
# Clé de signature des sessions — OBLIGATOIRE en production
# Générer avec : python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=remplacer-par-une-vraie-cle-secrete

# Compte avocat créé au premier démarrage (si table avocats vide)
ADMIN_EMAIL=avocat@cabinet.fr
ADMIN_PASSWORD=remplacer-par-un-mot-de-passe-robuste

# Base de données SQLite (ne pas modifier sauf hors Docker)
DATABASE_URL=sqlite:////data/cabinet.db

# Port d'écoute du serveur
PORT=8092

# Clé d'authentification API REST (header X-API-Key)
# Générer avec : python3 -c "import secrets; print(secrets.token_hex(32))"
API_KEY=remplacer-par-une-cle-api-secrete
```

### Premier démarrage

Au démarrage, le container exécute automatiquement :
1. `alembic upgrade head` : crée toutes les tables (ou applique les migrations manquantes)
2. `seed.py` : peuple les 12 types d'actes par défaut + crée le compte avocat depuis `.env`

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
docker compose logs -f nginx

# Redémarrer sans rebuild
docker compose restart app

# Rebuild complet (après modification du code)
docker compose up -d --build

# Arrêt complet
docker compose down

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

## 12. API REST

L'application expose une API REST JSON accessible uniquement via Tailscale (`http://100.81.134.30:8092/api/v1`).
Le port public 9444 (nginx) bloque toutes les requêtes `/api/*` avec un `403`.

**Documentation complète : [`docs/api.md`](docs/api.md)**

### Authentification rapide

```bash
# Toutes les requêtes doivent inclure le header :
X-API-Key: <valeur de API_KEY dans .env>

# Sans clé ou clé invalide → 401
```

### Endpoints disponibles

| Ressource | Méthodes |
|---|---|
| Clients | `GET /clients` `GET /clients/{id}` `POST /clients` `PUT /clients/{id}` `DELETE /clients/{id}` |
| Dossiers | `GET /dossiers` `GET /dossiers/{id}` `POST /dossiers` `PUT /dossiers/{id}` `POST /dossiers/{id}/close` `DELETE /dossiers/{id}` |
| Echéances | `POST /dossiers/{id}/echeances` `DELETE /dossiers/{id}/echeances/{eid}` |
| Actes | `GET /actes/{id}` `POST /actes` `PUT /actes/{id}` `DELETE /actes/{id}` |
| Type-actes | `GET /type-actes` `POST /type-actes` `DELETE /type-actes/{id}` |
| Documents | `GET /dossiers/{id}/generate` (retourne le DOCX) |

### Test rapide

```bash
API_KEY=<votre clé>

# Liste des clients
curl http://100.81.134.30:8092/api/v1/clients -H "X-API-Key: $API_KEY"

# Sans clé → 401
curl http://100.81.134.30:8092/api/v1/clients

# Via port public → 403
curl -k https://92.222.243.19:9444/api/v1/clients
```

---

## 13. Operations et maintenance

### Backup

Le backup est automatisé via `backup.sh`. Il tourne chaque **samedi à 1h du matin** (cron utilisateur `ubuntu`).

**Fonctionnement :**
- Copie cohérente de `cabinet.db` depuis le conteneur (`docker exec` pour éviter les locks SQLite)
- Compression gzip : fichier résultant `backups/cabinet_AAAAMMJJ_HHMM.db.gz`
- Rotation automatique : les 8 derniers backups sont conservés (8 semaines)
- Log dans `backups/backup.log`

**Lancer un backup manuel :**
```bash
cd /home/ubuntu/cabinet-juridique
bash backup.sh
```

**Consulter les backups :**
```bash
ls -lh backups/
cat backups/backup.log
```

**Restaurer un backup :**
```bash
docker compose down
gunzip -c backups/cabinet_AAAAMMJJ_HHMM.db.gz | sudo tee /home/ubuntu/cabinet-juridique/data/cabinet.db > /dev/null
sudo chown svcadmincabinet:svcadmincabinet /home/ubuntu/cabinet-juridique/data/cabinet.db
sudo chmod 600 /home/ubuntu/cabinet-juridique/data/cabinet.db
docker compose up -d
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

### Gérer fail2ban

```bash
# Statut du jail
sudo fail2ban-client status cabinet-juridique-auth

# Débannir une IP (ex: si verrouillé par erreur)
sudo fail2ban-client set cabinet-juridique-auth unbanip <ip>

# Voir les logs
sudo journalctl -u fail2ban -f
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

# Test HTTPS public
curl -sk https://92.222.243.19:9444/login -o /dev/null -w "%{http_code}"
# Attendu : 200

# Test accès Tailscale direct
curl -s http://100.81.134.30:8092/login -o /dev/null -w "%{http_code}"
# Attendu : 200
```

### Remplacer le certificat auto-signé (Let's Encrypt)

Quand un nom de domaine est disponible :

```bash
# Arrêter nginx temporairement
docker compose stop nginx

# Obtenir le certificat (certbot doit être installé sur le host)
sudo certbot certonly --standalone -d votre-domaine.fr

# Copier dans nginx/certs/
sudo cp /etc/letsencrypt/live/votre-domaine.fr/fullchain.pem nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/votre-domaine.fr/privkey.pem nginx/certs/server.key

# Redémarrer
docker compose start nginx
```

---

## 14. Roadmap

### MVP (livré)

- [x] Modele de données (Avocat, Client, Dossier, Acte, TypeActe, Tag)
- [x] Couche CRUD + tests unitaires (32 tests)
- [x] Couche UI / Templates (Jinja2 + HTMX)
- [x] Routes FastAPI (auth, clients, dossiers, actes, recherche)
- [x] Tests routes (70 tests)
- [x] Infrastructure Docker + README
- [x] Audit qualité + corrections (102 tests, couverture 90%)

### Sécurité (livré)

- [x] Nginx reverse proxy + HTTPS auto-signé
- [x] TLS 1.2/1.3, headers de sécurité (HSTS, X-Frame, CSP...)
- [x] Rate limiting Nginx (global + login)
- [x] fail2ban sur les tentatives de login échouées
- [x] Utilisateur système dédié `svcadmincabinet`
- [x] DB chmod 600, propriétaire svcadmincabinet
- [x] Session avec expiration 8h
- [x] Auto-hébergement HTMX + polices (RGPD, pas de CDN tiers)
- [x] Validation email et téléphone côté serveur

### Evolutions livrées post-MVP

- [x] Statut dossier "suspendu" renommé en "transféré" (migration 0004)
- [x] Provenance client : comment le client a connu le cabinet (migration 0005)
  - Bouche à oreille (client existant optionnel / confrère), internet, assureur, réseaux sociaux (LinkedIn / Instagram / TikTok / Facebook)
- [x] Profil professionnel client (migration 0006) : titre auto (Docteur si Médecin), profession avec autocomplétion (24 professions de santé), spécialité médicale (49 options, conditionnel)
- [x] Honoraires par dossier (migration 0007) : taux horaire (défaut 300 €/h), estimation en heures, total estimé calculé en temps réel

### Evolutions livrées (suite)

- [x] API REST JSON Tailscale-only avec authentification par API Key (issue #4)
  - `app/api/` : auth, router, routes clients/dossiers/actes/type-actes
  - Nginx bloque `/api/` sur port public (403)
  - Documentation complète dans `docs/api.md`

### Après MVP

- [ ] Let's Encrypt quand domaine décidé
- [ ] Changer le mot de passe admin initial (voir section 12)
- [ ] Backup automatisé quotidien (crontab)
- [ ] Export CSV (liste clients, liste dossiers par période)
- [ ] Suivi d'événements sur un dossier (audiences, relances, notes de suivi horodatées)
- [ ] Statistiques avancées sur le dashboard (dossiers par mois, types d'actes les plus produits, sources d'acquisition clients)
- [ ] Migration PostgreSQL si montée en charge
