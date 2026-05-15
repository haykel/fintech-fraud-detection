from fastapi import APIRouter, HTTPException, Depends
import logging

from application.queries import (
    GetAccountRiskProfileQuery,
    GetAccountRiskProfileHandler,
)
from infrastructure.postgres.repositories import PostgresAccountRepository
from infrastructure.redis.cache_adapter import RedisCache

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== Dependencies ====================

async def get_risk_profile_handler() -> GetAccountRiskProfileHandler:
    """Dependency injection"""
    account_repo = PostgresAccountRepository()
    cache = RedisCache()
    
    return GetAccountRiskProfileHandler(
        account_repository=account_repo,
        cache_service=cache,
    )


# ==================== Routes ====================

@router.get(
    "/accounts/{account_id}/risk-profile",
    response_model=dict,
    summary="Get Account Risk Profile",
    description="Récupère le profil de risque d'un compte (cached)"
)
async def get_account_risk_profile(
    account_id: str,
    handler: GetAccountRiskProfileHandler = Depends(get_risk_profile_handler)
):
    """
    Récupère le profil de risque d'un compte
    Cached en Redis pour performance
    """
    try:
        query = GetAccountRiskProfileQuery(account_id=account_id)
        result = await handler.execute(query)
        
        logger.info(f"Retrieved risk profile for account {account_id}")
        
        return {
            "account_id": result.account_id,
            "holder_name": result.holder_name,
            "status": result.status,
            "risk_profile": {
                "historical_risk_score": result.risk_profile.historical_risk_score,
                "transaction_count": result.risk_profile.transaction_count,
                "fraud_count": result.risk_profile.fraud_count,
                "fraud_rate": result.risk_profile.fraud_rate,
                "is_high_risk": result.risk_profile.is_high_risk,
                "last_updated": result.risk_profile.last_updated,
            },
        }
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching risk profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")