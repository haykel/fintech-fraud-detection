from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
import logging
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
from infrastructure.redis.cache_adapter import RedisCache
from infrastructure.opensearch.search_adapter import OpenSearchAdapter
from infrastructure.kafka.event_publisher import KafkaEventPublisher
from domain.fraud_rule import FraudDetectionStrategyFactory

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== Dependencies ====================

async def get_command_handler() -> ProcessTransactionHandler:
    """Dependency injection pour ProcessTransactionHandler"""
    # En production, utiliser une DI container (e.g., FastAPI's Depends)
    account_repo = PostgresAccountRepository()
    transaction_repo = PostgresTransactionRepository()
    fraud_detection = FraudDetectionStrategyFactory.create_hybrid()
    event_publisher = KafkaEventPublisher()
    
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
    Process une transaction :
    1. Crée la transaction
    2. Applique la détection de fraude
    3. Calcule le score de risque
    4. Publie les événements
    
    Returns 202 Accepted (traitement asynchrone)
    """
    try:
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
        
        return {
            "status": "accepted",
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
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/transactions/{transaction_id}",
    response_model=dict,
    summary="Get Transaction Details",
    description="Récupère les détails d'une transaction"
)
async def get_transaction(transaction_id: str):
    """
    Récupère une transaction par ID
    """
    try:
        # TODO: Implémenter GetTransactionByIdQuery
        repo = PostgresTransactionRepository()
        transaction = await repo.find_by_id(transaction_id)
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {
            "id": transaction.id,
            "account_id": transaction.account_id,
            "amount": float(transaction.amount.amount),
            "currency": transaction.amount.currency,
            "merchant_id": transaction.merchant_id,
            "merchant_name": transaction.merchant_name,
            "status": transaction.status.value,
            "is_fraud": transaction.is_fraud,
            "risk_score": transaction.risk_score,
            "fraud_reason": (
                transaction.fraud_indicator.reason
                if transaction.fraud_indicator else None
            ),
            "timestamp": transaction.timestamp.isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error fetching transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=dict,
    summary="Get Transaction History",
    description="Récupère l'historique des transactions d'un compte"
)
async def get_transaction_history(
    account_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    status: Optional[str] = Query(None),
    is_fraud: Optional[bool] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    handler: GetTransactionHistoryHandler = Depends(get_query_handler)
):
    """
    Récupère l'historique des transactions avec filtres optionnels
    """
    try:
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
        
        return result
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching transaction history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")