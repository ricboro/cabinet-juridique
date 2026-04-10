"""
MCP Server — Cabinet Juridique
Wrappe l'API REST FastAPI du cabinet pour permettre à Claude Code
de manipuler les données en langage naturel.

Variables d'environnement requises :
    CABINET_API_KEY  : clé d'authentification API (header X-API-Key)
    CABINET_API_URL  : base URL de l'API (défaut : http://100.81.134.30:8092/api/v1)
"""

import base64
import os
import re
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("CABINET_API_URL", "http://100.81.134.30:8092/api/v1")
API_KEY = os.getenv("CABINET_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Variable d'environnement CABINET_API_KEY manquante. "
        "Définissez-la avant de lancer le serveur MCP."
    )

mcp = FastMCP("cabinet-juridique")


def _headers() -> dict:
    return {"X-API-Key": API_KEY}


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code == 409:
        detail = r.json().get("detail", "Conflit : cette ressource est utilisée par d'autres données.")
        raise ValueError(detail)
    if r.status_code == 422:
        raise ValueError(f"Données invalides : {r.json()}")
    if r.status_code == 404:
        detail = r.json().get("detail", "Ressource introuvable.")
        raise ValueError(detail)
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@mcp.tool()
def list_clients(search: str = "", skip: int = 0, limit: int = 50) -> dict:
    """
    Recherche et liste les clients du cabinet.

    Utiliser 'search' pour filtrer par nom, prénom, raison sociale ou email.
    Retourne la liste paginée des clients avec leur type (personne ou société).
    Augmenter 'limit' si le résultat semble tronqué.
    """
    params = {"skip": skip, "limit": limit}
    if search:
        params["search"] = search
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/clients", headers=_headers(), params=params)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def get_client(client_id: int) -> dict:
    """
    Récupère le détail complet d'un client, incluant la liste de ses dossiers.

    Utiliser list_clients avec un critère de recherche pour trouver l'ID du client
    si vous ne le connaissez pas.
    """
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/clients/{client_id}", headers=_headers())
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def create_client(
    type: str,
    nom: Optional[str] = None,
    prenom: Optional[str] = None,
    raison_sociale: Optional[str] = None,
    siret: Optional[str] = None,
    email: Optional[str] = None,
    telephone: Optional[str] = None,
    adresse: Optional[str] = None,
    source_type: Optional[str] = None,
    source_detail: Optional[str] = None,
    titre: Optional[str] = None,
    profession: Optional[str] = None,
    representant_nom: Optional[str] = None,
    representant_prenom: Optional[str] = None,
) -> dict:
    """
    Crée un nouveau client dans le cabinet.

    'type' doit être 'personne' ou 'societe'.
    - Pour une personne : fournir 'nom' et 'prenom'.
    - Pour une société : fournir 'raison_sociale' (et éventuellement 'siret').

    Valeurs valides pour 'source_type' :
    bouche_a_oreille | internet | assureur | linkedin | instagram | tiktok | facebook

    Retourne le client créé avec son ID.
    """
    payload = {"type": type}
    for field, value in [
        ("nom", nom), ("prenom", prenom), ("raison_sociale", raison_sociale),
        ("siret", siret), ("email", email), ("telephone", telephone),
        ("adresse", adresse), ("source_type", source_type), ("source_detail", source_detail),
        ("titre", titre), ("profession", profession),
        ("representant_nom", representant_nom), ("representant_prenom", representant_prenom),
    ]:
        if value is not None:
            payload[field] = value
    with httpx.Client() as client:
        r = client.post(f"{BASE_URL}/clients", headers=_headers(), json=payload)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def update_client(
    client_id: int,
    nom: Optional[str] = None,
    prenom: Optional[str] = None,
    raison_sociale: Optional[str] = None,
    siret: Optional[str] = None,
    email: Optional[str] = None,
    telephone: Optional[str] = None,
    adresse: Optional[str] = None,
    source_type: Optional[str] = None,
    source_detail: Optional[str] = None,
    titre: Optional[str] = None,
    profession: Optional[str] = None,
    representant_nom: Optional[str] = None,
    representant_prenom: Optional[str] = None,
) -> dict:
    """
    Met à jour les informations d'un client existant.

    Seuls les champs fournis sont modifiés — les autres restent inchangés.
    Retourne le client mis à jour.
    """
    payload = {}
    for field, value in [
        ("nom", nom), ("prenom", prenom), ("raison_sociale", raison_sociale),
        ("siret", siret), ("email", email), ("telephone", telephone),
        ("adresse", adresse), ("source_type", source_type), ("source_detail", source_detail),
        ("titre", titre), ("profession", profession),
        ("representant_nom", representant_nom), ("representant_prenom", representant_prenom),
    ]:
        if value is not None:
            payload[field] = value
    with httpx.Client() as client:
        r = client.put(f"{BASE_URL}/clients/{client_id}", headers=_headers(), json=payload)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def delete_client(client_id: int) -> dict:
    """
    Supprime un client du cabinet.

    Attention : la suppression est impossible si le client possède des dossiers.
    Dans ce cas, clôturer ou supprimer les dossiers associés en premier.
    """
    with httpx.Client() as client:
        r = client.delete(f"{BASE_URL}/clients/{client_id}", headers=_headers())
    _raise_for_status(r)
    return {"success": True, "message": f"Client {client_id} supprimé."}


# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

@mcp.tool()
def list_dossiers(
    statut: Optional[str] = None,
    client_id: Optional[int] = None,
    avocat_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> list:
    """
    Liste les dossiers du cabinet avec filtres optionnels.

    Filtres disponibles :
    - 'statut' : en_cours | cloture | transfere
    - 'client_id' : dossiers d'un client spécifique
    - 'avocat_id' : dossiers d'un avocat spécifique

    Retourne les dossiers avec leurs actes et échéances.
    """
    params: dict = {"skip": skip, "limit": limit}
    if statut:
        params["statut"] = statut
    if client_id is not None:
        params["client_id"] = client_id
    if avocat_id is not None:
        params["avocat_id"] = avocat_id
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/dossiers", headers=_headers(), params=params)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def get_dossier(dossier_id: int) -> dict:
    """
    Récupère le détail complet d'un dossier : informations générales,
    liste des actes produits et liste des échéances.
    """
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/dossiers/{dossier_id}", headers=_headers())
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def create_dossier(
    intitule: str,
    client_id: int,
    avocat_id: int,
    contexte: Optional[str] = None,
    honoraire_horaire: Optional[float] = None,
    estimation_heures: Optional[float] = None,
) -> dict:
    """
    Ouvre un nouveau dossier pour un client.

    La référence (ex. 2026-007) est générée automatiquement.
    'avocat_id' est obligatoire — utiliser list_dossiers pour trouver l'ID de l'avocat
    si inconnu (il apparaît dans les dossiers existants).
    Renseigner 'honoraire_horaire' et 'estimation_heures' pour permettre
    la génération de la convention d'honoraires.
    """
    payload: dict = {"intitule": intitule, "client_id": client_id}
    if contexte is not None:
        payload["contexte"] = contexte
    if honoraire_horaire is not None:
        payload["honoraire_horaire"] = honoraire_horaire
    if estimation_heures is not None:
        payload["estimation_heures"] = estimation_heures
    with httpx.Client() as client:
        r = client.post(
            f"{BASE_URL}/dossiers",
            headers=_headers(),
            json=payload,
            params={"avocat_id": avocat_id},
        )
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def update_dossier(
    dossier_id: int,
    intitule: Optional[str] = None,
    contexte: Optional[str] = None,
    statut: Optional[str] = None,
    honoraire_horaire: Optional[float] = None,
    estimation_heures: Optional[float] = None,
) -> dict:
    """
    Met à jour les informations d'un dossier existant.

    Seuls les champs fournis sont modifiés.
    Valeurs valides pour 'statut' : en_cours | cloture | transfere
    (préférer close_dossier pour une clôture formelle avec date automatique).
    """
    payload = {}
    for field, value in [
        ("intitule", intitule), ("contexte", contexte), ("statut", statut),
        ("honoraire_horaire", honoraire_horaire), ("estimation_heures", estimation_heures),
    ]:
        if value is not None:
            payload[field] = value
    with httpx.Client() as client:
        r = client.put(f"{BASE_URL}/dossiers/{dossier_id}", headers=_headers(), json=payload)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def close_dossier(dossier_id: int) -> dict:
    """
    Clôture formellement un dossier.

    Passe le statut à 'cloture' et enregistre la date de clôture au jour d'aujourd'hui.
    Cette action est préférable à update_dossier pour une clôture officielle.
    """
    with httpx.Client() as client:
        r = client.post(f"{BASE_URL}/dossiers/{dossier_id}/close", headers=_headers())
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def delete_dossier(dossier_id: int) -> dict:
    """
    Supprime définitivement un dossier et toutes ses données associées.

    Attention : suppression en cascade — tous les actes et échéances du dossier
    seront également supprimés. Cette action est irréversible.
    """
    with httpx.Client() as client:
        r = client.delete(f"{BASE_URL}/dossiers/{dossier_id}", headers=_headers())
    _raise_for_status(r)
    return {"success": True, "message": f"Dossier {dossier_id} supprimé avec ses actes et échéances."}


# ---------------------------------------------------------------------------
# Échéances
# ---------------------------------------------------------------------------

@mcp.tool()
def add_echeance(dossier_id: int, libelle: str, date: str) -> dict:
    """
    Ajoute une échéance (date limite) à un dossier.

    'date' doit être au format YYYY-MM-DD (ex. 2026-06-30).
    'libelle' décrit la nature de l'échéance (ex. "Dépôt des conclusions").
    """
    with httpx.Client() as client:
        r = client.post(
            f"{BASE_URL}/dossiers/{dossier_id}/echeances",
            headers=_headers(),
            json={"libelle": libelle, "date": date},
        )
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def delete_echeance(dossier_id: int, echeance_id: int) -> dict:
    """
    Supprime une échéance d'un dossier.

    Les deux identifiants sont nécessaires : celui du dossier et celui de l'échéance.
    Utiliser get_dossier pour consulter les échéances et leurs IDs.
    """
    with httpx.Client() as client:
        r = client.delete(
            f"{BASE_URL}/dossiers/{dossier_id}/echeances/{echeance_id}",
            headers=_headers(),
        )
    _raise_for_status(r)
    return {"success": True, "message": f"Échéance {echeance_id} supprimée."}


# ---------------------------------------------------------------------------
# Actes
# ---------------------------------------------------------------------------

@mcp.tool()
def get_acte(acte_id: int) -> dict:
    """
    Récupère le détail d'un acte : type, dossier associé, lien OneDrive et tags.
    """
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/actes/{acte_id}", headers=_headers())
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def create_acte(
    nom: str,
    dossier_id: int,
    date_production: str,
    type_acte_id: Optional[int] = None,
    lien_onedrive: Optional[str] = None,
    tag_libelles: Optional[list[str]] = None,
) -> dict:
    """
    Enregistre un acte produit dans un dossier.

    'date_production' au format YYYY-MM-DD.
    'tag_libelles' : liste de labels texte (ex. ["assignation", "urgence"]).
    Les tags inexistants sont créés automatiquement.
    'type_acte_id' : ID du type d'acte — utiliser list_type_actes pour le trouver.
    'lien_onedrive' : URL du document sur OneDrive (stockage externe).
    """
    payload: dict = {"nom": nom, "dossier_id": dossier_id, "date_production": date_production}
    if type_acte_id is not None:
        payload["type_acte_id"] = type_acte_id
    if lien_onedrive is not None:
        payload["lien_onedrive"] = lien_onedrive
    if tag_libelles:
        payload["tag_libelles"] = tag_libelles
    with httpx.Client() as client:
        r = client.post(f"{BASE_URL}/actes", headers=_headers(), json=payload)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def update_acte(
    acte_id: int,
    nom: Optional[str] = None,
    lien_onedrive: Optional[str] = None,
    date_production: Optional[str] = None,
    type_acte_id: Optional[int] = None,
    tag_libelles: Optional[list[str]] = None,
) -> dict:
    """
    Met à jour un acte existant.

    Seuls les champs fournis sont modifiés.
    Attention : si 'tag_libelles' est fourni, il remplace intégralement
    les tags existants (pas d'ajout incrémental).
    """
    payload = {}
    for field, value in [
        ("nom", nom), ("lien_onedrive", lien_onedrive),
        ("date_production", date_production), ("type_acte_id", type_acte_id),
    ]:
        if value is not None:
            payload[field] = value
    if tag_libelles is not None:
        payload["tag_libelles"] = tag_libelles
    with httpx.Client() as client:
        r = client.put(f"{BASE_URL}/actes/{acte_id}", headers=_headers(), json=payload)
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def delete_acte(acte_id: int) -> dict:
    """
    Supprime un acte du dossier.
    """
    with httpx.Client() as client:
        r = client.delete(f"{BASE_URL}/actes/{acte_id}", headers=_headers())
    _raise_for_status(r)
    return {"success": True, "message": f"Acte {acte_id} supprimé."}


# ---------------------------------------------------------------------------
# Types d'actes
# ---------------------------------------------------------------------------

@mcp.tool()
def list_type_actes() -> list:
    """
    Liste tous les types d'actes disponibles dans le cabinet,
    avec le nombre d'actes utilisant chaque type ('usage_count').

    Utiliser cette liste pour connaître les IDs à passer lors de la création d'actes.
    """
    with httpx.Client() as client:
        r = client.get(f"{BASE_URL}/type-actes", headers=_headers())
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def create_type_acte(libelle: str) -> dict:
    """
    Crée un nouveau type d'acte (ex. "Assignation", "Contrat de prestation").

    Le libellé doit être unique. Vérifier list_type_actes avant de créer
    pour éviter les doublons.
    """
    with httpx.Client() as client:
        r = client.post(f"{BASE_URL}/type-actes", headers=_headers(), json={"libelle": libelle})
    _raise_for_status(r)
    return r.json()


@mcp.tool()
def delete_type_acte(type_acte_id: int) -> dict:
    """
    Supprime un type d'acte.

    Impossible si des actes utilisent encore ce type — dans ce cas,
    mettre à jour les actes concernés avant de supprimer le type.
    """
    with httpx.Client() as client:
        r = client.delete(f"{BASE_URL}/type-actes/{type_acte_id}", headers=_headers())
    _raise_for_status(r)
    return {"success": True, "message": f"Type d'acte {type_acte_id} supprimé."}


# ---------------------------------------------------------------------------
# Génération de documents
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_convention_honoraires(dossier_id: int) -> dict:
    """
    Génère la convention d'honoraires (DOCX) pour un dossier.

    Prérequis : les champs 'honoraire_horaire' et 'estimation_heures'
    doivent être renseignés sur le dossier (via update_dossier si besoin).

    Retourne :
    - 'filename' : nom de fichier suggéré (ex. convention_honoraires_Dupont_20260410.docx)
    - 'content_base64' : contenu du fichier encodé en base64
    - 'instructions' : commande Python pour sauvegarder le fichier localement

    Pour sauvegarder le fichier :
        import base64
        data = base64.b64decode(result['content_base64'])
        open(result['filename'], 'wb').write(data)
    """
    with httpx.Client() as client:
        r = client.get(
            f"{BASE_URL}/dossiers/{dossier_id}/generate",
            headers=_headers(),
            params={"template_key": "convention_honoraires"},
        )
    _raise_for_status(r)

    # Extraire le nom de fichier depuis le header Content-Disposition
    content_disposition = r.headers.get("content-disposition", "")
    match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
    filename = match.group(1) if match else f"convention_honoraires_{dossier_id}.docx"

    return {
        "filename": filename,
        "content_base64": base64.b64encode(r.content).decode("utf-8"),
        "instructions": (
            f"Pour sauvegarder : "
            f"import base64; open('{filename}', 'wb').write(base64.b64decode(content_base64))"
        ),
    }


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
