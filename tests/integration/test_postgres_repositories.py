import pytest
import asyncio
from decimal import Decimal
from domain.transaction import Transaction, Money
from domain.account import Account
from infrastructure.postgres.repositories import (
    PostgresTransactionRepository,
    PostgresAccountRepository,
    init_db,
)


@pytest.fixture
async def setup_db():
    """Setup base de données pour les tests"""
    await init_db()
    yield
    # Cleanup si besoin


@pytest.mark.asyncio
async def test_save_and_find_transaction(setup_db):
    """Test sauvegarde et récupération d'une transaction"""
    repo = PostgresTransactionRepository()
    
    # Créer une transaction
    amount = Money(Decimal("150.50"), "EUR")
    txn = Transaction(
        account_id="acc-123",
        amount=amount,
        merchant_id="merchant-456",
        merchant_name="Test Store"
    )
    
    # Sauvegarder
    await repo.save(txn)
    
    # Récupérer
    found = await repo.find_by_id(txn.id)
    
    assert found is not None
    assert found.id == txn.id
    assert found.account_id == "acc-123"
    assert float(found.amount.amount) == 150.50


@pytest.mark.asyncio
async def test_save_and_find_account(setup_db):
    """Test sauvegarde et récupération d'un compte"""
    repo = PostgresAccountRepository()
    
    # Créer un compte
    account = Account(
        holder_name="John Doe",
        email="john@example.com"
    )
    
    # Sauvegarder
    await repo.save(account)
    
    # Récupérer par ID
    found = await repo.find_by_id(account.id)
    
    assert found is not None
    assert found.id == account.id
    assert found.holder_name == "John Doe"
    assert found.email == "john@example.com"


@pytest.mark.asyncio
async def test_find_account_by_email(setup_db):
    """Test recherche de compte par email"""
    repo = PostgresAccountRepository()
    
    account = Account(
        holder_name="Jane Doe",
        email="jane@example.com"
    )
    
    await repo.save(account)
    
    # Rechercher par email
    found = await repo.find_by_email("jane@example.com")
    
    assert found is not None
    assert found.email == "jane@example.com"