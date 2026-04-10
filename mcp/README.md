# MCP Server — Cabinet Juridique

Serveur MCP Python qui expose l'API REST du cabinet comme outils utilisables directement par Claude Code.

## Prérequis

- Python 3.12+
- Accès au réseau Tailscale (l'API n'est pas accessible depuis Internet)

## Installation

```bash
pip install -r /home/ubuntu/cabinet-juridique/mcp/requirements.txt
```

## Variables d'environnement

| Variable | Obligatoire | Description | Exemple |
|---|---|---|---|
| `CABINET_API_KEY` | Oui | Clé d'authentification API (header `X-API-Key`) | `c0d14f15...` |
| `CABINET_API_URL` | Non | Base URL de l'API (défaut : Tailscale) | `http://100.81.134.30:8092/api/v1` |

> **Sécurité** : ne jamais committer la clé API. Le `.gitignore` du projet exclut `.env`.

## Enregistrement dans Claude Code

### Option A — Via CLI (recommandé, scope utilisateur)

```bash
claude mcp add --scope user cabinet-juridique \
  -- python3 /home/ubuntu/cabinet-juridique/mcp/cabinet_mcp_server.py
```

Puis ajouter les variables d'environnement dans `~/.claude.json` :

```json
{
  "mcpServers": {
    "cabinet-juridique": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/ubuntu/cabinet-juridique/mcp/cabinet_mcp_server.py"],
      "env": {
        "CABINET_API_KEY": "votre-clé-ici",
        "CABINET_API_URL": "http://100.81.134.30:8092/api/v1"
      }
    }
  }
}
```

### Option B — Via `.mcp.json` dans le repo (scope projet, partageable)

Créer `.mcp.json` à la racine du repo :

```json
{
  "mcpServers": {
    "cabinet-juridique": {
      "type": "stdio",
      "command": "python3",
      "args": ["mcp/cabinet_mcp_server.py"],
      "env": {
        "CABINET_API_KEY": "${CABINET_API_KEY}",
        "CABINET_API_URL": "${CABINET_API_URL}"
      }
    }
  }
}
```

Chaque développeur exporte ses variables dans son shell avant de lancer Claude Code :

```bash
export CABINET_API_KEY=votre-clé-ici
export CABINET_API_URL=http://100.81.134.30:8092/api/v1
```

## Vérification

Dans une session Claude Code :

```
/mcp
# → cabinet-juridique: connected ✓
```

## Tools disponibles (21)

| Domaine | Tool | Description |
|---|---|---|
| Clients | `list_clients` | Recherche et liste les clients |
| | `get_client` | Détail d'un client avec ses dossiers |
| | `create_client` | Crée un client (personne ou société) |
| | `update_client` | Mise à jour partielle d'un client |
| | `delete_client` | Supprime un client (si sans dossiers) |
| Dossiers | `list_dossiers` | Liste avec filtres statut/client/avocat |
| | `get_dossier` | Détail avec actes et échéances |
| | `create_dossier` | Ouvre un nouveau dossier |
| | `update_dossier` | Mise à jour partielle d'un dossier |
| | `close_dossier` | Clôture formelle avec date du jour |
| | `delete_dossier` | Suppression en cascade |
| Échéances | `add_echeance` | Ajoute une date limite à un dossier |
| | `delete_echeance` | Supprime une échéance |
| Actes | `get_acte` | Détail d'un acte avec tags |
| | `create_acte` | Enregistre un acte produit |
| | `update_acte` | Mise à jour d'un acte |
| | `delete_acte` | Supprime un acte |
| Types d'actes | `list_type_actes` | Liste avec usage_count |
| | `create_type_acte` | Crée un type d'acte |
| | `delete_type_acte` | Supprime un type (si inutilisé) |
| Documents | `generate_convention_honoraires` | Génère le DOCX encodé en base64 |
