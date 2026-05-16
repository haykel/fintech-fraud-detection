# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Bring up the full stack (Postgres, Redis, Kafka/Zookeeper, OpenSearch, MinIO, pgAdmin, workers)
docker-compose up

# Build/refresh just the workers image after a code change
docker-compose build workers
docker-compose up -d workers

# Run the FastAPI app locally (no Docker; expects services reachable on localhost or via .env)
uvicorn interfaces.api.main:app --reload --port 8000

# Run the Kafka workers locally
python -m interfaces.workers.main

# Tests (conftest.py at repo root puts the project on sys.path; run from repo root)
pytest                                       # everything
pytest tests/unit                            # unit tests only
pytest tests/integration                     # integration tests
pytest tests/unit/domain/transaction/test_transaction.py::test_name -v   # single test
```

Async tests use `pytest-asyncio` and are marked with `@pytest.mark.asyncio`.

## Architecture

The codebase follows **Clean Architecture / DDD with CQRS**, organised into four layers under the repo root. Dependencies only point inward: `domain` → `application` → `infrastructure`/`interfaces`. The outer layers wire concrete adapters into the application via constructor injection.

### Layer responsibilities

- **`domain/`** — pure business logic, no I/O, no framework imports.
  - Aggregates: `Transaction` (`domain/transaction/transaction.py`), `Account` (`domain/account/account.py`). Each owns its invariants and state transitions (e.g. `Transaction.mark_as_fraudulent`, `Account.record_fraud`).
  - Value objects: `Money`, `FraudIndicator`, `RiskProfile` (frozen dataclasses with validation in `__post_init__`).
  - Domain events in `domain/common/events.py` — `DomainEvent` base + concrete events (`TransactionCreatedEvent`, `FraudDetectedEvent`, `FraudExplainedEvent`, account lifecycle events). Each event implements `_get_event_data()` and is JSON-serialisable.
  - **Strategy pattern** for fraud detection in `domain/fraud_rule/fraud_detection_strategy.py`: `RuleBasedFraudDetectionStrategy`, `AnomalyDetectionStrategy`, `HybridFraudDetectionStrategy`, plus `FraudDetectionStrategyFactory`. The API currently wires the hybrid strategy.

- **`application/`** — orchestration via CQRS.
  - `commands/` — write side. `ProcessTransactionHandler` loads account → builds `Transaction` → runs fraud strategy → persists → emits domain events through the injected `event_publisher`.
  - `queries/` — read side, returns DTOs. `GetTransactionHistoryHandler` reads from OpenSearch with a Postgres fallback on exception. `GetAccountRiskProfileHandler` is cache-aside on Redis (24h TTL).
  - Ports (repositories, cache, search, event publisher) are passed in as duck-typed dependencies — there are no explicit ABCs for them yet.

- **`infrastructure/`** — adapters for Postgres, Redis, Kafka, OpenSearch, Mistral. **Most adapters are currently stubs** (`# TODO: Implémenter avec ...`) returning `None`/empty results. When implementing a feature end-to-end, expect to fill these in (e.g. `PostgresTransactionRepository.save` does nothing today).

- **`interfaces/`** — entry points.
  - `interfaces/api/main.py` — FastAPI app, mounts `routes/transactions.py` and `routes/accounts.py` under `/api`. Dependencies are constructed per-request inside `get_*_handler()` functions; there is no DI container.
  - `interfaces/workers/main.py` — entry point that starts `TransactionEventConsumer`, `FraudDetectionConsumer`, `SearchIndexingConsumer` (and optionally `FraudExplanationWorker`, currently commented out) concurrently via `asyncio.gather`. Each consumer subclasses `KafkaConsumerWorker` and binds to a topic / consumer group.

### Event flow

1. HTTP `POST /api/transactions` → `ProcessTransactionHandler.execute` runs the fraud strategy synchronously and persists.
2. The handler then publishes `TransactionCreatedEvent` (always) and `FraudDetectedEvent` (if flagged) through `KafkaEventPublisher`. Topic naming convention: `{aggregate_type.lower()}.{event_type}` (see `infrastructure/kafka/event_publisher.py`).
3. Workers consume those topics asynchronously. `FraudExplanationWorker` listens on `fraud.detected`, calls the Mistral API, and is intended to emit a `FraudExplainedEvent` back (TODO).

When adding a new event, register it in `domain/common/__init__.py`'s `__all__` so it can be imported as `from domain.common import ...`.

### Service hostnames

Inside Docker, services reach each other by container hostname (`kafka:9092`, `postgres:5432`, `redis:6379`, `opensearch:9200`). The recent fix `e7d2f70` switched workers from `localhost` to these hostnames — keep that convention for any new adapter defaults. Host-side access to Kafka uses port `29092` (see `KAFKA_ADVERTISED_LISTENERS` in `docker-compose.yml`).

## Conventions specific to this repo

- Docstrings and inline comments are mixed French/English — match the surrounding style of the file you're editing.
- Dataclasses are used for aggregates, value objects, commands, queries, and events. Value objects use `frozen=True`; aggregates do not.
- Domain validation lives in `__post_init__`. Raise `ValueError` for invariant violations; FastAPI routes translate these to HTTP 400.
- No SQLAlchemy models yet — the Postgres adapters are placeholders. If you add models, wire them up so existing dataclass aggregates remain the in-memory representation (map at the adapter boundary).
