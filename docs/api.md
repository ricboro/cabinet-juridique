# API REST — Cabinet Juridique

API JSON exposée sur le port Tailscale `8092`, préfixe `/api/v1`.

**Accès :** `http://100.81.134.30:8092/api/v1`
**Port public 9444 :** toutes les requêtes `/api/*` sont bloquées par nginx (`403 Forbidden`).

---

## Authentification

Toutes les requêtes doivent inclure le header `X-API-Key` avec la valeur définie dans la variable d'environnement `API_KEY`.

```
X-API-Key: <votre clé>
```

| Situation | Code retourné |
|---|---|
| Header absent | `401 Unauthorized` |
| Clé incorrecte | `401 Unauthorized` |
| Clé valide | réponse normale |

**Générer une clé :**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Ajouter la valeur dans `.env` (`API_KEY=...`) puis redémarrer le container.

---

## Codes HTTP utilisés

| Code | Signification |
|---|---|
| `200` | Succès (lecture / mise à jour) |
| `201` | Ressource créée |
| `204` | Suppression réussie (corps vide) |
| `401` | Clé API absente ou invalide |
| `403` | Accès bloqué (port public nginx) |
| `404` | Ressource introuvable |
| `409` | Conflit (ex: suppression bloquée car ressource utilisée) |
| `422` | Données invalides (validation Pydantic) |

---

## Clients

### GET /api/v1/clients

Liste les clients. Supporte la pagination et la recherche.

**Paramètres query :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `skip` | int | 0 | Nombre d'éléments à sauter |
| `limit` | int | 20 | Nombre maximum d'éléments |
| `search` | string | - | Recherche sur nom, prénom, raison sociale, email |

**Exemple :**
```bash
curl http://100.81.134.30:8092/api/v1/clients?limit=10&search=martin \
  -H "X-API-Key: $API_KEY"
```

**Réponse :** `200` — tableau de `ClientResponse`

---

### GET /api/v1/clients/{id}

Récupère un client par son ID. Inclut la liste de ses dossiers.

**Réponse :** `200` — `ClientResponse` / `404`

---

### POST /api/v1/clients

Crée un nouveau client.

**Corps (JSON) :**

```json
{
  "type": "personne",
  "nom": "Dupont",
  "prenom": "Alice",
  "email": "alice@example.com",
  "telephone": "06 12 34 56 78",
  "adresse": "12 rue de la Paix, 75001 Paris",
  "titre": "Docteur",
  "profession": "Médecin",
  "specialite": "Cardiologie",
  "source_type": "bouche_a_oreille",
  "source_detail": "client",
  "source_client_id": 3
}
```

```json
{
  "type": "societe",
  "raison_sociale": "Cabinet Martin SAS",
  "siret": "82341567800012",
  "email": "contact@cabinet-martin.fr",
  "telephone": "01 23 45 67 89",
  "adresse": "45 avenue Victor Hugo, 69002 Lyon",
  "representant_nom": "Martin",
  "representant_prenom": "Paul"
}
```

**Champs `type` :** `personne` | `societe`
**Champs `source_type` :** `bouche_a_oreille` | `internet` | `assureur` | `linkedin` | `instagram` | `tiktok` | `facebook`

**Réponse :** `201` — `ClientResponse`

---

### PUT /api/v1/clients/{id}

Met à jour un client. Tous les champs sont optionnels (PATCH sémantique).

**Corps (JSON) :** mêmes champs que POST, tous optionnels.

**Réponse :** `200` — `ClientResponse` / `404`

---

### DELETE /api/v1/clients/{id}

Supprime un client.

**Réponse :** `204` / `404` / `409` (si le client a des dossiers)

---

## Dossiers

### GET /api/v1/dossiers

Liste les dossiers. Supporte la pagination et les filtres.

**Paramètres query :**

| Paramètre | Type | Description |
|---|---|---|
| `skip` | int | Offset |
| `limit` | int | Maximum (défaut 20) |
| `statut` | string | `en_cours` / `cloture` / `transfere` |
| `client_id` | int | Filtrer par client |
| `avocat_id` | int | Filtrer par avocat |

**Réponse :** `200` — tableau de `DossierApiResponse`

---

### GET /api/v1/dossiers/{id}

Récupère un dossier avec ses actes et ses échéances.

**Réponse :** `200` — `DossierApiResponse` / `404`

---

### POST /api/v1/dossiers

Crée un nouveau dossier. La référence (`AAAA-NNN`) est générée automatiquement.

**Paramètre query obligatoire :** `avocat_id` (int)

**Corps (JSON) :**

```json
{
  "intitule": "Litige commercial SCI Les Acacias",
  "contexte": "Contentieux suite à résiliation anticipée du bail commercial.",
  "statut": "en_cours",
  "date_ouverture": "2026-04-10",
  "honoraire_horaire": 350.0,
  "estimation_heures": 12.0,
  "client_id": 5
}
```

**Réponse :** `201` — `DossierApiResponse`

---

### PUT /api/v1/dossiers/{id}

Met à jour un dossier. Tous les champs sont optionnels.

**Corps (JSON) :** mêmes champs que POST, tous optionnels.

**Réponse :** `200` — `DossierApiResponse` / `404`

---

### POST /api/v1/dossiers/{id}/close

Clôture un dossier : passe le statut à `cloture` et positionne `date_cloture = today`.

**Corps :** aucun

**Réponse :** `200` — `DossierApiResponse` / `404`

---

### DELETE /api/v1/dossiers/{id}

Supprime un dossier et ses actes/échéances en cascade.

**Réponse :** `204` / `404`

---

## Echéances

### POST /api/v1/dossiers/{id}/echeances

Ajoute une échéance à un dossier.

**Corps (JSON) :**

```json
{
  "libelle": "Audience de conciliation",
  "date": "2026-05-15"
}
```

**Réponse :** `201` — `EcheanceResponse` / `404` (dossier introuvable)

---

### DELETE /api/v1/dossiers/{dossier_id}/echeances/{echeance_id}

Supprime une échéance.

**Réponse :** `204` / `404`

---

## Actes

### GET /api/v1/actes/{id}

Récupère un acte par son ID. Inclut le type d'acte, le dossier et les tags.

**Réponse :** `200` — `ActeApiResponse` / `404`

---

### POST /api/v1/actes

Crée un acte.

**Corps (JSON) :**

```json
{
  "nom": "Assignation en référé",
  "type_acte_id": 2,
  "lien_onedrive": "https://onedrive.live.com/edit/...",
  "date_production": "2026-04-10",
  "dossier_id": 7,
  "tag_ids": [1, 3],
  "tag_libelles": ["urgent", "référé"],
  "is_generated": false
}
```

`tag_ids` et `tag_libelles` peuvent être combinés. Les tags inexistants dans `tag_libelles` sont créés automatiquement.

**Réponse :** `201` — `ActeApiResponse`

---

### PUT /api/v1/actes/{id}

Met à jour un acte. Tous les champs sont optionnels.

Si `tag_ids` ou `tag_libelles` est fourni, les tags existants sont remplacés (pas ajoutés).

**Réponse :** `200` — `ActeApiResponse` / `404`

---

### DELETE /api/v1/actes/{id}

Supprime un acte.

**Réponse :** `204` / `404`

---

## Types d'actes

### GET /api/v1/type-actes

Liste tous les types d'actes avec leur nombre d'utilisations.

**Réponse :** `200` — tableau de `TypeActeResponse`

```json
[
  {"id": 1, "libelle": "Assignation", "usage_count": 5},
  {"id": 2, "libelle": "Contrat", "usage_count": 12}
]
```

---

### POST /api/v1/type-actes

Crée un nouveau type d'acte.

**Corps (JSON) :**

```json
{"libelle": "Protocole transactionnel"}
```

**Réponse :** `201` — `TypeActeResponse`

---

### DELETE /api/v1/type-actes/{id}

Supprime un type d'acte.

**Réponse :** `204` / `404` / `409` (si des actes utilisent ce type)

---

## Documents générés

### GET /api/v1/dossiers/{id}/generate

Génère et retourne un document DOCX pour le dossier.

**Paramètres query :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `template_key` | string | `convention_honoraires` | Identifiant du template |

**Templates disponibles :**

| Clé | Document |
|---|---|
| `convention_honoraires` | Convention d'honoraires |

**Prérequis :** le dossier doit avoir `honoraire_horaire` et `estimation_heures` renseignés.

**Réponse :** `200` — fichier DOCX (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)

```bash
curl "http://100.81.134.30:8092/api/v1/dossiers/7/generate" \
  -H "X-API-Key: $API_KEY" \
  --output convention.docx
```

**Erreurs :**
- `404` : dossier introuvable
- `400` : template inconnu
- `422` : honoraires manquants

---

## Schemas de réponse

### ClientResponse

```json
{
  "id": 1,
  "type": "personne",
  "nom": "Dupont",
  "prenom": "Alice",
  "raison_sociale": null,
  "siret": null,
  "email": "alice@example.com",
  "telephone": "06 12 34 56 78",
  "adresse": "12 rue de la Paix, 75001 Paris",
  "date_creation": "2026-04-10T10:00:00",
  "source_type": "bouche_a_oreille",
  "source_detail": "client",
  "source_client_id": 3,
  "titre": "Docteur",
  "profession": "Médecin",
  "specialite": "Cardiologie",
  "representant_nom": null,
  "representant_prenom": null,
  "dossiers": [
    {"id": 7, "reference": "2026-007", "intitule": "Litige SCI", "statut": "en_cours"}
  ],
  "source_client": {"id": 3, "type": "personne", "nom": "Martin", "prenom": "Paul", "raison_sociale": null}
}
```

### DossierApiResponse

```json
{
  "id": 7,
  "reference": "2026-007",
  "intitule": "Litige commercial SCI Les Acacias",
  "contexte": "Contentieux suite à résiliation anticipée du bail.",
  "statut": "en_cours",
  "date_ouverture": "2026-04-10",
  "date_cloture": null,
  "honoraire_horaire": 350.0,
  "estimation_heures": 12.0,
  "client_id": 5,
  "avocat_id": 1,
  "client": {"id": 5, "type": "personne", "nom": "Dupont", "prenom": "Alice", "raison_sociale": null},
  "avocat": {"id": 1, "nom": "Boisson", "prenom": "Margot"},
  "actes": [
    {"id": 3, "nom": "Assignation", "lien_onedrive": "https://...", "date_production": "2026-04-10", "is_generated": false}
  ],
  "echeances": [
    {"id": 1, "dossier_id": 7, "libelle": "Audience de conciliation", "date": "2026-05-15"}
  ]
}
```

### ActeApiResponse

```json
{
  "id": 3,
  "nom": "Assignation en référé",
  "type_acte_id": 2,
  "lien_onedrive": "https://onedrive.live.com/edit/...",
  "date_production": "2026-04-10",
  "is_generated": false,
  "dossier_id": 7,
  "type_acte": {"id": 2, "libelle": "Assignation"},
  "dossier": {"id": 7, "reference": "2026-007", "intitule": "Litige SCI", "statut": "en_cours"},
  "tags": [
    {"id": 1, "libelle": "urgent"},
    {"id": 3, "libelle": "référé"}
  ]
}
```

---

## Exemples curl complets

```bash
API="http://100.81.134.30:8092/api/v1"
KEY="votre-api-key"

# Créer un client
curl -X POST "$API/clients" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"personne","nom":"Leroy","prenom":"Sophie","email":"sophie@leroy.fr"}'

# Créer un dossier (avocat_id=1)
curl -X POST "$API/dossiers?avocat_id=1" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"intitule":"Divorce Leroy","date_ouverture":"2026-04-10","client_id":42,"honoraire_horaire":300,"estimation_heures":8}'

# Clôturer un dossier
curl -X POST "$API/dossiers/42/close" \
  -H "X-API-Key: $KEY"

# Ajouter une échéance
curl -X POST "$API/dossiers/42/echeances" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"libelle":"Audience","date":"2026-06-01"}'

# Créer un acte avec tags
curl -X POST "$API/actes" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"nom":"Convention","type_acte_id":1,"date_production":"2026-04-10","dossier_id":42,"tag_libelles":["convention","divorce"]}'

# Télécharger un document généré
curl "$API/dossiers/42/generate" \
  -H "X-API-Key: $KEY" \
  --output convention_honoraires.docx
```
