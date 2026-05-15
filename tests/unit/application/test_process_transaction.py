import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from domain.transaction import Money, Transaction
from domain.account import Account
from domain.fraud_rule import FraudDetectionStrategyFactory
from domain.common import TransactionCreatedEvent, FraudDetectedEvent
from application.commands import ProcessTransactionCommand, ProcessTransactionHandler


@pytest.fixture
def fraud_detection_service():
    """Service de détection de fraude"""
    return FraudDetectionStrategyFactory.create_hybrid()


@pytest.fixture
def mock_account_repository():
    """Mock du repository Account"""
    repo = AsyncMock()
    
    # Mock account
    account = Account(
        id="acc-123",
        holder_name="John Doe",
        email="john@example.com"
    )
    repo.find_by_id = AsyncMock(return_value=account)
    repo.save = AsyncMock()
    
    return repo


@pytest.fixture
def mock_transaction_repository():
    """Mock du repository Transaction"""
    repo = AsyncMock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_event_publisher():
    """Mock du publisher d'événements"""
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def command_handler(
    mock_account_repository,
    mock_transaction_repository,
    fraud_detection_service,
    mock_event_publisher
):
    """Handler avec mocks"""
    return ProcessTransactionHandler(
        account_repository=mock_account_repository,
        transaction_repository=mock_transaction_repository,
        fraud_detection_service=fraud_detection_service,
        event_publisher=mock_event_publisher,
    )


@pytest.mark.asyncio
async def test_process_transaction_success(command_handler):
    """Test traitement réussi d'une transaction"""
    command = ProcessTransactionCommand(
        account_id="acc-123",
        amount=100.50,
        currency="EUR",
        merchant_id="merchant-456",
        merchant_name="Test Store"
    )
    
    result = await command_handler.execute(command)
    
    # Vérifications
    assert result.account_id == "acc-123"
    assert result.amount.amount == Decimal("100.50")
    assert result.merchant_id == "merchant-456"
    
    # Vérifier les appels aux repositories
    command_handler.account_repo.find_by_id.assert_called_once_with("acc-123")
    command_handler.transaction_repo.save.assert_called_once()
    command_handler.account_repo.save.assert_called_once()
    
    # Vérifier la publication d'événements
    assert command_handler.event_publisher.publish.called


@pytest.mark.asyncio
async def test_process_transaction_account_not_found(command_handler):
    """Test erreur quand compte n'existe pas"""
    command_handler.account_repo.find_by_id = AsyncMock(return_value=None)
    
    command = ProcessTransactionCommand(
        account_id="acc-999",
        amount=100.50,
        currency="EUR",
        merchant_id="merchant-456"
    )
    
    with pytest.raises(ValueError, match="not found"):
        await command_handler.execute(command)


@pytest.mark.asyncio
async def test_process_transaction_account_cannot_transact(command_handler):
    """Test erreur quand compte ne peut pas faire de transactions"""
    # Mock account gelé
    account = Account(
        id="acc-123",
        holder_name="John Doe",
        email="john@example.com"
    )
    account.freeze("Test")
    command_handler.account_repo.find_by_id = AsyncMock(return_value=account)
    
    command = ProcessTransactionCommand(
        account_id="acc-123",
        amount=100.50,
        currency="EUR",
        merchant_id="merchant-456"
    )
    
    with pytest.raises(ValueError, match="cannot transact"):
        await command_handler.execute(command)


@pytest.mark.asyncio
async def test_process_transaction_fraud_detected(command_handler, mock_account_repository):
    """Test détection de fraude"""
    command = ProcessTransactionCommand(
        account_id="acc-123",
        amount=10000.00,  # Montant élevé = fraude
        currency="EUR",
        merchant_id="merchant-456"
    )
    
    result = await command_handler.execute(command)
    
    # La transaction devrait être bloquée
    assert result.is_fraud is True
    assert result.status.value == "BLOCKED"
    
    # Un événement FraudDetected devrait être publié
    assert command_handler.event_publisher.publish.called