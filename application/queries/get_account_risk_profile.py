from dataclasses import dataclass
from typing import Optional, Dict, Any
from domain.account import Account


# ==================== DTO ====================

@dataclass
class RiskProfileDTO:
    """DTO pour le profil de risque d'un compte"""
    account_id: str
    historical_risk_score: float
    transaction_count: int
    fraud_count: int
    fraud_rate: float
    is_high_risk: bool
    last_updated: str


@dataclass
class AccountRiskProfileDTO:
    """DTO pour les données de risque d'un compte"""
    account_id: str
    holder_name: str
    status: str
    risk_profile: RiskProfileDTO


# ==================== Query ====================

@dataclass
class GetAccountRiskProfileQuery:
    """
    Query pour récupérer le profil de risque d'un compte
    
    Read-only. Cached en Redis pour performance.
    """
    account_id: str


# ==================== Query Handler ====================

class GetAccountRiskProfileHandler:
    """
    Handler pour GetAccountRiskProfileQuery
    
    Récupère le profil de risque avec cache Redis.
    """
    
    def __init__(
        self,
        account_repository,  # Port
        cache_service,  # Port (Redis)
    ):
        self.account_repo = account_repository
        self.cache = cache_service
    
    async def execute(
        self,
        query: GetAccountRiskProfileQuery
    ) -> AccountRiskProfileDTO:
        """Exécute la requête avec cache"""
        
        # 1. Chercher en cache
        cache_key = f"account_risk_profile:{query.account_id}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return self._deserialize_dto(cached)
        
        # 2. Chercher en base de données
        account = await self.account_repo.find_by_id(query.account_id)
        
        if account is None:
            raise ValueError(f"Account {query.account_id} not found")
        
        # 3. Convertir en DTO
        dto = self._to_dto(account)
        
        # 4. Cacher (24h de TTL)
        await self.cache.set(
            cache_key,
            self._serialize_dto(dto),
            ttl=86400  # 24 heures
        )
        
        return dto
    
    def _to_dto(self, account: Account) -> AccountRiskProfileDTO:
        """Convertit Account en DTO"""
        risk_profile = account.risk_profile
        
        return AccountRiskProfileDTO(
            account_id=account.id,
            holder_name=account.holder_name,
            status=account.status.value,
            risk_profile=RiskProfileDTO(
                account_id=account.id,
                historical_risk_score=risk_profile.historical_risk_score,
                transaction_count=risk_profile.transaction_count,
                fraud_count=risk_profile.fraud_count,
                fraud_rate=risk_profile.fraud_rate,
                is_high_risk=risk_profile.is_high_risk_account,
                last_updated=risk_profile.last_risk_update.isoformat(),
            ),
        )
    
    def _serialize_dto(self, dto: AccountRiskProfileDTO) -> str:
        """Sérialise le DTO pour le cache"""
        import json
        return json.dumps({
            "account_id": dto.account_id,
            "holder_name": dto.holder_name,
            "status": dto.status,
            "risk_profile": {
                "account_id": dto.risk_profile.account_id,
                "historical_risk_score": dto.risk_profile.historical_risk_score,
                "transaction_count": dto.risk_profile.transaction_count,
                "fraud_count": dto.risk_profile.fraud_count,
                "fraud_rate": dto.risk_profile.fraud_rate,
                "is_high_risk": dto.risk_profile.is_high_risk,
                "last_updated": dto.risk_profile.last_updated,
            },
        })
    
    def _deserialize_dto(self, json_str: str) -> AccountRiskProfileDTO:
        """Désérialise le DTO depuis le cache"""
        import json
        data = json.loads(json_str)
        
        risk_data = data["risk_profile"]
        risk_profile = RiskProfileDTO(
            account_id=risk_data["account_id"],
            historical_risk_score=risk_data["historical_risk_score"],
            transaction_count=risk_data["transaction_count"],
            fraud_count=risk_data["fraud_count"],
            fraud_rate=risk_data["fraud_rate"],
            is_high_risk=risk_data["is_high_risk"],
            last_updated=risk_data["last_updated"],
        )
        
        return AccountRiskProfileDTO(
            account_id=data["account_id"],
            holder_name=data["holder_name"],
            status=data["status"],
            risk_profile=risk_profile,
        )