import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from domain.transaction import Transaction, Money, TransactionStatus
from application.queries import (
    GetTransactionHistoryQuery,
    GetTransactionHistoryHandler,
    TransactionDTO,
)


@pytest.fixture
def mock_search_service():
    """Mock du service de recherche"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_transaction_repository():
    """Mock du repository Transaction"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def query_handler(mock_search_service, mock_transaction_repository):
    """Handler avec mocks"""
    return GetTransactionHistoryHandler(
        search_service=mock_search_service,
        transaction_repository=mock_transaction_repository,
    )


@pytest.mark.asyncio
async def test_get_transaction_history_success(query_handler, mock_search_service):
    """Test récupération réussie de l'historique"""
    
    # Mock du service de recherche
    mock_search_service.search_transactions = AsyncMock(return_value={
        "transactions": [
            Transaction(
                id="txn-1",
                account_id="acc-123",
                amount=Money(Decimal("100"), "EUR"),
                merchant_id="merchant-456",
                merchant_name="Store 1",
                status=TransactionStatus.APPROVED,
            )
        ],
        "total": 1,
    })
    
    query = GetTransactionHistoryQuery(
        account_id="acc-123",
        limit=50,
        offset=0
    )
    
    result = await query_handler.execute(query)
    
    assert result["total"] == 1
    assert len(result["transactions"]) == 1
    assert result["transactions"][0].merchant_name == "Store 1"


@pytest.mark.asyncio
async def test_get_transaction_history_with_filters(query_handler, mock_search_service):
    """Test avec filtres"""
    
    mock_search_service.search_transactions = AsyncMock(return_value={
        "transactions": [],
        "total": 0,
    })
    
    query = GetTransactionHistoryQuery(
        account_id="acc-123",
        limit=50,
        offset=0,
        filters={
            "min_amount": 100,
            "max_amount": 500,
        }
    )
    
    result = await query_handler.execute(query)
    
    # Vérifier que le service de recherche a été appelé avec les filtres
    mock_search_service.search_transactions.assert_called_once()
    call_args = mock_search_service.search_transactions.call_args
    assert call_args.kwargs["criteria"]["account_id"] == "acc-123"


@pytest.mark.asyncio
async def test_get_transaction_history_fallback_to_db(
    query_handler,
    mock_search_service,
    mock_transaction_repository
):
    """Test fallback à la base de données"""
    
    # Service de recherche échoue
    mock_search_service.search_transactions = AsyncMock(
        side_effect=Exception("Search service down")
    )
    
    # DB retourne des transactions
    txn = Transaction(
        id="txn-1",
        account_id="acc-123",
        amount=Money(Decimal("100"), "EUR"),
        merchant_id="merchant-456",
    )
    mock_transaction_repository.find_by_account_id = AsyncMock(
        return_value=[txn]
    )
    
    query = GetTransactionHistoryQuery(account_id="acc-123")
    
    result = await query_handler.execute(query)
    
    assert result["total"] == 1
    assert len(result["transactions"]) == 1