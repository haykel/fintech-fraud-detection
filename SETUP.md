# Setup Local Development Environment

## Prérequis
- Docker & Docker Compose
- Python 3.10+
- Git

## Installation

1. Clone le repository
```bash
git clone [URL]
cd fintech-fraud-detection
```

2. Crée un fichier `.env.local`
```bash
cp .env.example .env.local
```

3. Lance Docker Compose
```bash
docker-compose up
```

4. Vérifie que les services sont up
```bash
curl http://localhost:5432  # PostgreSQL
curl http://localhost:6379  # Redis
curl http://localhost:9092  # Kafka
curl http://localhost:9200  # OpenSearch
curl http://localhost:9000  # MinIO
```

## Services et ports

| Service | Port | Credentials |
|---------|------|-------------|
| PostgreSQL | 5432 | postgres/postgres |
| Redis | 6379 | - |
| Kafka | 9092 | - |
| OpenSearch | 9200 | admin/admin |
| MinIO | 9000 | minioadmin/minioadmin |
| Jenkins | 8080 | admin/admin |

## Prochains pas

Voir la [Roadmap](https://confluenceurl) pour les phases suivantes.

## Database Setup

### Initialize PostgreSQL

```bash
# Les tables se créent automatiquement via SQLAlchemy
# Mais tu peux aussi utiliser Alembic pour les migrations

# Setup initial
python -c "from infrastructure.postgres.repositories import init_db; import asyncio; asyncio.run(init_db())"
```

### Créer un test account

```bash
# Via psql
psql -h localhost -U postgres -d fintech_db -c \
  "INSERT INTO accounts (id, holder_name, email, status) VALUES ('acc-test-1', 'Test User', 'test@example.com', 'ACTIVE');"
```