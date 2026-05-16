from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
import logging
import os
from datetime import datetime

from application.commands import ProcessTransactionCommand, ProcessTransactionHandler
from application.queries import (
    GetTransactionHistoryQuery,
    GetTransactionHistoryHandler,
    TransactionDTO,
)
from interfaces.api.schemas.request_schemas import ProcessTransactionRequest
from infrastructure.postgres.repositories import (
    PostgresTransactionRepository,
    PostgresAccountRepository,
)
from infrastructure.redis.cache_adapter import get_cache
from infrastructure.opensearch.search_adapter import OpenSearchAdapter
from infrastructure.kafka.event_publisher import get_event_publisher
from domain.fraud_rule import FraudDetectionStrategyFactory

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== Dependency Injection ====================

async def get_command_handler() -> ProcessTransactionHandler:
    """Dependency injection pour ProcessTransactionHandler"""
    account_repo = PostgresAccountRepository()
    transaction_repo = PostgresTransactionRepository()
    fraud_detection = FraudDetectionStrategyFactory.create_hybrid()
    event_publisher = await get_event_publisher()
    
    return ProcessTransactionHandler(
        account_repository=account_repo,
        transaction_repository=transaction_repo,
        fraud_detection_service=fraud_detection,
        event_publisher=event_publisher,
    )


async def get_query_handler() -> GetTransactionHistoryHandler:
    """Dependency injection pour GetTransactionHistoryHandler"""
    search_service = OpenSearchAdapter()
    transaction_repo = PostgresTransactionRepository()
    
    return GetTransactionHistoryHandler(
        search_service=search_service,
        transaction_repository=transaction_repo,
    )


# ==================== Routes ====================

@router.post(
    "/transactions",
    response_model=dict,
    status_code=202,
    summary="Process Transaction",
    description="Crée et traite une nouvelle transaction avec détection de fraude"
)
async def process_transaction(
    request: ProcessTransactionRequest,
    handler: ProcessTransactionHandler = Depends(get_command_handler)
):
    """
    Traite une transaction :
    1. Crée la transaction en base de données
    2. Applique la détection de fraude (Rule + Anomaly + Hybrid)
    3. Calcule le score de risque
    4. Publie les événements domaine sur Kafka
    5. Les workers consomment les événements de manière asynchrone
    
    Returns 202 Accepted (traitement asynchrone)
    
    **Détection de fraude :**
    - RuleBasedStrategy: montants élevés (>5000€), pays à risque, catégories suspectes
    - AnomalyDetectionStrategy: détection statistique (z-score), heures anormales
    - HybridStrategy: combinaison des deux avec poids configurables
    
    **Événements publiés :**
    - TransactionCreatedEvent
    - FraudDetectedEvent (si fraude)
    """
    try:
        logger.info(f"Processing transaction for account {request.account_id}")
        
        # Créer la commande
        command = ProcessTransactionCommand(
            account_id=request.account_id,
            amount=request.amount,
            currency=request.currency,
            merchant_id=request.merchant_id,
            merchant_name=request.merchant_name,
            merchant_category=request.merchant_category,
            merchant_country=request.merchant_country,
        )
        
        # Exécuter la commande
        transaction = await handler.execute(command)
        
        logger.info(f"Transaction {transaction.id} processed successfully")
        logger.info(f"Fraud detected: {transaction.is_fraud}, Risk score: {transaction.risk_score}")
        
        return {
            "status": "accepted",
            "message": "Transaction processing started",
            "transaction_id": transaction.id,
            "account_id": transaction.account_id,
            "amount": float(transaction.amount.amount),
            "currency": transaction.amount.currency,
            "fraud_detected": transaction.is_fraud,
            "risk_score": transaction.risk_score,
            "fraud_reason": (
                transaction.fraud_indicator.reason
                if transaction.fraud_indicator else None
            ),
            "timestamp": transaction.timestamp.isoformat(),
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/transactions/{transaction_id}",
    response_model=dict,
    summary="Get Transaction Details",
    description="Récupère les détails d'une transaction"
)
async def get_transaction(transaction_id: str):
    """
    Récupère une transaction par ID depuis PostgreSQL
    
    **Retourne :**
    - Détails complets de la transaction
    - Status (PENDING, APPROVED, REJECTED, BLOCKED)
    - Indicateur de fraude avec score et raison
    - Métadonnées et timestamps
    """
    try:
        logger.info(f"Fetching transaction {transaction_id}")
        
        repo = PostgresTransactionRepository()
        transaction = await repo.find_by_id(transaction_id)
        
        if not transaction:
            logger.warning(f"Transaction not found: {transaction_id}")
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {
            "id": transaction.id,
            "account_id": transaction.account_id,
            "amount": float(transaction.amount.amount),
            "currency": transaction.amount.currency,
            "merchant_id": transaction.merchant_id,
            "merchant_name": transaction.merchant_name,
            "merchant_category": transaction.merchant_category,
            "merchant_country": transaction.merchant_country,
            "status": transaction.status.value,
            "is_fraud": transaction.is_fraud,
            "risk_score": transaction.risk_score,
            "fraud_reason": (
                transaction.fraud_indicator.reason
                if transaction.fraud_indicator else None
            ),
            "fraud_explanation": (
                transaction.fraud_indicator.explanation
                if transaction.fraud_indicator else None
            ),
            "timestamp": transaction.timestamp.isoformat(),
            "created_at": transaction.created_at.isoformat(),
            "updated_at": transaction.updated_at.isoformat(),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=dict,
    summary="Get Transaction History",
    description="Récupère l'historique des transactions d'un compte avec filtres optionnels"
)
async def get_transaction_history(
    account_id: str,
    limit: int = Query(50, ge=1, le=1000, description="Nombre de résultats"),
    offset: int = Query(0, ge=0, description="Décalage de pagination"),
    min_amount: Optional[float] = Query(None, ge=0, description="Montant minimum"),
    max_amount: Optional[float] = Query(None, ge=0, description="Montant maximum"),
    status: Optional[str] = Query(None, description="Status: PENDING, APPROVED, REJECTED, BLOCKED"),
    is_fraud: Optional[bool] = Query(None, description="Filtrer par fraude détectée"),
    start_date: Optional[str] = Query(None, description="Date de début (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Date de fin (ISO 8601)"),
    handler: GetTransactionHistoryHandler = Depends(get_query_handler)
):
    """
    Récupère l'historique des transactions avec filtres optionnels
    
    **Filtres disponibles :**
    - min_amount / max_amount: intervalle de montant
    - status: PENDING, APPROVED, REJECTED, BLOCKED
    - is_fraud: true/false
    - start_date / end_date: plage de dates (ISO 8601)
    
    **Recherche :**
    - Utilise OpenSearch pour performance (index par jour)
    - Fallback à PostgreSQL si OpenSearch indisponible
    
    **Pagination :**
    - limit: 1-1000 résultats par page (défaut 50)
    - offset: position de départ (défaut 0)
    
    **Exemple :**
    ```
    GET /api/accounts/acc-123/transactions?limit=20&status=APPROVED&is_fraud=false
    ```
    """
    try:
        logger.info(f"Fetching transaction history for account {account_id}")
        
        # Construire les filtres
        filters = {}
        if min_amount is not None:
            filters["min_amount"] = min_amount
        if max_amount is not None:
            filters["max_amount"] = max_amount
        if status is not None:
            filters["status"] = status
        if is_fraud is not None:
            filters["is_fraud"] = is_fraud
        if start_date is not None:
            filters["start_date"] = start_date
        if end_date is not None:
            filters["end_date"] = end_date
        
        # Exécuter la query
        query = GetTransactionHistoryQuery(
            account_id=account_id,
            limit=limit,
            offset=offset,
            filters=filters if filters else None,
        )
        
        result = await handler.execute(query)
        
        logger.info(f"Retrieved {len(result['transactions'])} transactions for account {account_id}")
        
        return {
            "account_id": account_id,
            "transactions": result["transactions"],
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < result["total"],
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching transaction history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/accounts/{account_id}/transactions/fraud",
    response_model=dict,
    summary="Get Fraudulent Transactions",
    description="Récupère les transactions frauduleuses d'un compte"
)
async def get_fraudulent_transactions(
    account_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_risk_score: Optional[float] = Query(None, ge=0, le=1),
):
    """
    Récupère les transactions frauduleuses avec scores de risque
    
    **Filtres :**
    - min_risk_score: filtre par score de risque minimum (0-1)
    - limit/offset: pagination
    
    **Retourne :**
    - Liste des transactions marquées comme fraude
    - Scores de risque et raisons détectées
    - Explications IA (si disponibles via Mistral)
    """
    try:
        logger.info(f"Fetching fraudulent transactions for account {account_id}")
        
        filters = {"is_fraud": True}
        if min_risk_score is not None:
            filters["min_risk_score"] = min_risk_score
        
        query = GetTransactionHistoryQuery(
            account_id=account_id,
            limit=limit,
            offset=offset,
            filters=filters,
        )
        
        handler = await get_query_handler()
        result = await handler.execute(query)
        
        logger.info(f"Found {len(result['transactions'])} fraudulent transactions")
        
        return {
            "account_id": account_id,
            "fraud_transactions": result["transactions"],
            "total_fraud": result["total"],
            "fraud_rate": (
                result["total"] / (result["total"] + (limit - result["total"]))
                if result["total"] > 0 else 0
            ),
            "limit": limit,
            "offset": offset,
        }
    
    except Exception as e:
        logger.error(f"Error fetching fraudulent transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")