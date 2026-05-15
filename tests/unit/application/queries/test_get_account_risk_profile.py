import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from domain.account import Account, RiskProfile
from application.queries import (
    GetAccountRiskProfileQuery,
    GetAccountRiskProfileHandler,
)


@pytest.fixture
def mock_account_repository():
    """Mock du repository Account"""
    repo = AsyncMock()
    
    account = Account(
        id="acc-123",
        holder_name="John Doe",
        email="john@example.com"
    )
    account.update_risk_profile(
        historical_risk_score=0.5,
        transaction_count=10,
        fraud_count=1
    )
    
    repo.find_by_id = AsyncMock(return_value=account)
    return repo


@pytest.fixture
def mock_cache_service():
    """Mock du service de cache"""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def query_handler(mock_account_repository, mock_cache_service):
    """Handler avec mocks"""
    return GetAccountRiskProfileHandler(
        account_repository=mock_account_repository,
        cache_service=mock_cache_service,
    )


@pytest.mark.asyncio
async def test_get_account_risk_profile_success(query_handler):
    """Test récupération réussie du profil"""
    
    query = GetAccountRiskProfileQuery(account_id="acc-123")
    result = await query_handler.execute(query)
    
    assert result.account_id == "acc-123"
    assert result.holder_name == "John Doe"
    assert result.risk_profile.transaction_count == 10
    assert result.risk_profile.fraud_count == 1


@pytest.mark.asyncio
async def test_get_account_risk_profile_from_cache(query_handler, mock_cache_service):
    """Test récupération depuis le cache"""
    
    # Mock cache retourne les données
    mock_cache_service.get = AsyncMock(return_value='{"account_id": "acc-123", "holder_name": "John Doe", "status": "ACTIVE", "risk_profile": {"account_id": "acc-123", "historical_risk_score": 0.5, "transaction_count": 10, "fraud_count": 1, "fraud_rate": 0.1, "is_high_risk": false, "last_updated": "2026-05-15T00:00:00"}}')
    
    query = GetAccountRiskProfileQuery(account_id="acc-123")
    result = await query_handler.execute(query)
    
    # Vérifier que le cache a été consulté
    mock_cache_service.get.assert_called_once()
    
    # Vérifier que le repo n'a pas été appelé
    query_handler.account_repo.find_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_get_account_risk_profile_account_not_found(query_handler, mock_cache_service):
    """Test erreur quand compte n'existe pas"""
    
    query_handler.account_repo.find_by_id = AsyncMock(return_value=None)
    
    query = GetAccountRiskProfileQuery(account_id="acc-999")
    
    with pytest.raises(ValueError, match="not found"):
        await query_handler.execute(query)