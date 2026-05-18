import pytest
import pytest_asyncio
from decimal import Decimal
from domain.transaction import Transaction, Money
from domain.account import Account
from infrastructure.postgres.models import Base
from infrastructure.postgres.repositories import (
    PostgresTransactionRepository,
    PostgresAccountRepository,
    engine,
)


@pytest_asyncio.fixture
async def setup_db():
    """Setup base de données pour les tests.

    Recrée le schéma à chaque test pour garantir l'isolation. Utilise l'engine
    module-level partagé via le fixture `event_loop` session-scoped défini
    dans le conftest racine.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_save_and_find_transaction(setup_db):
    """Test sauvegarde et récupération d'une transaction"""
    # Une transaction nécessite un account_id existant (FK) — on persiste
    # d'abord le compte associé.
    account_repo = PostgresAccountRepository()
    account = Account(id="acc-123", holder_name="Owner", email="owner@example.com")
    await account_repo.save(account)

    repo = PostgresTransactionRepository()
    amount = Money(Decimal("150.50"), "EUR")
    txn = Transaction(
        account_id="acc-123",
        amount=amount,
        merchant_id="merchant-456",
        merchant_name="Test Store",
    )
    await repo.save(txn)

    found = await repo.find_by_id(txn.id)
    assert found is not None
    assert found.id == txn.id
    assert found.account_id == "acc-123"
    assert float(found.amount.amount) == 150.50


@pytest.mark.asyncio
async def test_save_and_find_account(setup_db):
    """Test sauvegarde et récupération d'un compte"""
    repo = PostgresAccountRepository()
    account = Account(holder_name="John Doe", email="john@example.com")
    await repo.save(account)

    found = await repo.find_by_id(account.id)
    assert found is not None
    assert found.id == account.id
    assert found.holder_name == "John Doe"
    assert found.email == "john@example.com"


@pytest.mark.asyncio
async def test_find_account_by_email(setup_db):
    """Test recherche de compte par email"""
    repo = PostgresAccountRepository()
    account = Account(holder_name="Jane Doe", email="jane@example.com")
    await repo.save(account)

    found = await repo.find_by_email("jane@example.com")
    assert found is not None
    assert found.email == "jane@example.com"
