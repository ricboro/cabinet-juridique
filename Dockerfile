FROM python:3.12-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY app/ ./app/

# Alembic (migrations)
COPY alembic/ ./alembic/
COPY alembic.ini .

# Répertoire de données (monté en volume en prod)
RUN mkdir -p /data

EXPOSE 8092

# Démarrage : migrations Alembic puis serveur
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8092
