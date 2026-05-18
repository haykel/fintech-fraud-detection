"""Endpoints REST pour l'analyse de fraude via l'agent Mistral.

Le format "job" est volontairement simple : `job_id == transaction_id` (ou
`account_id` pour les rapports). Le résultat est stocké dans Redis sous la clé
`fraud_explanation:{id}` avec un statut `pending` / `completed` / `failed`.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from infrastructure.mistral import FraudAnalysisTools, MistralAgent, MistralAgentError
from infrastructure.postgres.repositories import (
    PostgresAccountRepository,
    PostgresTransactionRepository,
)
from infrastructure.redis.cache_adapter import RedisCache

logger = logging.getLogger(__name__)
router = APIRouter()


EXPLANATION_KEY_PREFIX = "fraud_explanation"
REPORT_KEY_PREFIX = "account_report"
PENDING_TTL = 600       # 10 min : durée de vie d'un job pending/failed
COMPLETED_TTL = 86400   # 24 h : durée de vie d'un résultat


# ==================== Dependencies ====================


def get_agent() -> MistralAgent:
    """Construit un agent par requête (DI simple, à factoriser en prod)."""
    tools = FraudAnalysisTools(
        transaction_repo=PostgresTransactionRepository(),
        account_repo=PostgresAccountRepository(),
    )
    return MistralAgent(tools=tools)


def get_cache() -> RedisCache:
    return RedisCache()


# ==================== Background workers ====================


async def _run_fraud_analysis(
    agent: MistralAgent,
    cache: RedisCache,
    transaction_id: str,
) -> None:
    """Tâche d'arrière-plan : analyse Mistral + persistance Redis du résultat."""
    key = f"{EXPLANATION_KEY_PREFIX}:{transaction_id}"
    await _safe_cache_set(cache, key, {"status": "pending"}, ttl=PENDING_TTL)

    try:
        analysis = await agent.analyze_fraud(transaction_id)
    except MistralAgentError as e:
        logger.error("analyze_fraud failed transaction_id=%s err=%s", transaction_id, e)
        await _safe_cache_set(
            cache, key, {"status": "failed", "error": str(e)}, ttl=PENDING_TTL
        )
        return
    except Exception as e:
        logger.exception("analyze_fraud unexpected error transaction_id=%s", transaction_id)
        await _safe_cache_set(
            cache, key, {"status": "failed", "error": str(e)}, ttl=PENDING_TTL
        )
        return

    await _safe_cache_set(
        cache,
        key,
        {"status": "completed", "result": analysis},
        ttl=COMPLETED_TTL,
    )


async def _run_account_report(
    agent: MistralAgent,
    cache: RedisCache,
    account_id: str,
) -> None:
    key = f"{REPORT_KEY_PREFIX}:{account_id}"
    await _safe_cache_set(cache, key, {"status": "pending"}, ttl=PENDING_TTL)

    try:
        report = await agent.generate_account_report(account_id)
    except MistralAgentError as e:
        logger.error("generate_account_report failed account_id=%s err=%s", account_id, e)
        await _safe_cache_set(
            cache, key, {"status": "failed", "error": str(e)}, ttl=PENDING_TTL
        )
        return
    except Exception as e:
        logger.exception("generate_account_report unexpected error account_id=%s", account_id)
        await _safe_cache_set(
            cache, key, {"status": "failed", "error": str(e)}, ttl=PENDING_TTL
        )
        return

    await _safe_cache_set(
        cache,
        key,
        {"status": "completed", "result": report},
        ttl=COMPLETED_TTL,
    )


async def _safe_cache_set(
    cache: RedisCache, key: str, value: Dict[str, Any], ttl: int
) -> None:
    """Encapsule cache.set avec serialization JSON + logging d'erreur."""
    try:
        await cache.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl=ttl)
    except Exception:
        logger.exception("cache.set failed key=%s", key)


async def _safe_cache_get(cache: RedisCache, key: str) -> Optional[Dict[str, Any]]:
    try:
        raw = await cache.get(key)
    except Exception:
        logger.exception("cache.get failed key=%s", key)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("cache value not JSON key=%s", key)
        return None


# ==================== Routes ====================


@router.post(
    "/transactions/{transaction_id}/analyze",
    status_code=202,
    summary="Lancer une analyse Mistral d'une transaction",
)
async def analyze_transaction(
    transaction_id: str,
    background_tasks: BackgroundTasks,
    agent: MistralAgent = Depends(get_agent),
    cache: RedisCache = Depends(get_cache),
):
    """Démarre une analyse Mistral en tâche d'arrière-plan.

    Retourne 202 Accepted avec un `job_id` (= `transaction_id`) que le client
    pourra utiliser sur `GET /transactions/{id}/explanation` pour récupérer
    le résultat.
    """
    logger.info("analyze_transaction queued transaction_id=%s", transaction_id)
    background_tasks.add_task(_run_fraud_analysis, agent, cache, transaction_id)
    return {
        "job_id": transaction_id,
        "status": "accepted",
        "poll_url": f"/api/transactions/{transaction_id}/explanation",
    }


@router.get(
    "/transactions/{transaction_id}/explanation",
    summary="Récupérer l'explication générée par l'agent",
)
async def get_explanation(
    transaction_id: str,
    cache: RedisCache = Depends(get_cache),
):
    """Lit le résultat de l'analyse depuis le cache.

    Réponses possibles :
        * 200 status=completed : `result` contient l'analyse JSON.
        * 200 status=pending|failed : analyse en cours ou en erreur.
        * 404 : pas d'analyse trouvée pour cette transaction.
    """
    key = f"{EXPLANATION_KEY_PREFIX}:{transaction_id}"
    cached = await _safe_cache_get(cache, key)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Aucune explication trouvée pour {transaction_id}. "
                f"Lance d'abord POST /transactions/{transaction_id}/analyze."
            ),
        )
    return cached


@router.post(
    "/accounts/{account_id}/generate-report",
    status_code=202,
    summary="Lancer la génération d'un rapport de risque pour un compte",
)
async def generate_account_report(
    account_id: str,
    background_tasks: BackgroundTasks,
    agent: MistralAgent = Depends(get_agent),
    cache: RedisCache = Depends(get_cache),
):
    logger.info("generate_account_report queued account_id=%s", account_id)
    background_tasks.add_task(_run_account_report, agent, cache, account_id)
    return {
        "job_id": account_id,
        "status": "accepted",
        "poll_url": f"/api/accounts/{account_id}/report",
    }


@router.get(
    "/accounts/{account_id}/report",
    summary="Récupérer le rapport de risque généré par l'agent",
)
async def get_account_report(
    account_id: str,
    cache: RedisCache = Depends(get_cache),
):
    key = f"{REPORT_KEY_PREFIX}:{account_id}"
    cached = await _safe_cache_get(cache, key)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Aucun rapport trouvé pour {account_id}. "
                f"Lance d'abord POST /accounts/{account_id}/generate-report."
            ),
        )
    return cached
