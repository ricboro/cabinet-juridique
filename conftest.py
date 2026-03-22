import os

# Marquer l'environnement comme "test" avant tout import de l'app
# Cela permet au lifespan de ne pas tenter d'ouvrir la vraie BDD SQLite
os.environ.setdefault("TESTING", "1")

# Forcer l'import des modèles pour que Base.metadata soit peuplé
# avant que les fixtures ne créent les tables
import app.models  # noqa: F401, E402
