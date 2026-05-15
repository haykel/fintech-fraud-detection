from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from domain.transaction import Transaction


# ==================== DTO (Data Transfer Object) ====================

@dataclass
class TransactionDTO:
    """DTO pour retourner les données de transaction au client"""
    id: str
    account_id: str
    amount: float
    currency: str
    merchant_id: str
    merchant_name: Optional[str]
    timestamp: str
    status: str
    is_fraud: bool
    risk_score: float
    fraud_reason: Optional[str] = None


# ==================== Query ====================

@dataclass
class GetTransactionHistoryQuery:
    """
    Query pour récupérer l'historique des transactions d'un compte
    
    C'est une requête read-only qui ne modifie aucun état.
    """
    account_id: str
    limit: int = 50
    offset: int = 0
    filters: Optional[Dict[str, Any]] = None


# ==================== Query Handler ====================

class GetTransactionHistoryHandler:
    """
    Handler pour la requête GetTransactionHistory
    
    Récupère les transactions via OpenSearch (search index)
    pour des performances optimales.
    """
    
    def __init__(
        self,
        search_service,  # Port pour OpenSearch
        transaction_repository,  # Port pour fallback DB
    ):
        self.search_service = search_service
        self.transaction_repo = transaction_repository
    
    async def execute(
        self,
        query: GetTransactionHistoryQuery
    ) -> Dict[str, Any]:
        """
        Exécute la requête et retourne les résultats paginés
        
        Returns:
            Dict avec:
            - transactions: List[TransactionDTO]
            - total: int (nombre total)
            - limit: int
            - offset: int
        """
        
        # 1. Construire les critères de recherche
        search_criteria = {
            "account_id": query.account_id,
        }
        
        # 2. Ajouter les filtres optionnels
        if query.filters:
            search_criteria.update(query.filters)
        
        # 3. Rechercher dans OpenSearch
        try:
            results = await self.search_service.search_transactions(
                criteria=search_criteria,
                limit=query.limit,
                offset=query.offset,
                sort_by="timestamp",
                sort_order="desc"
            )
        except Exception as e:
            # Fallback à la base de données
            print(f"Search service failed, using DB fallback: {e}")
            results = await self._fallback_db_search(query)
        
        # 4. Transformer en DTOs
        transaction_dtos = [
            self._to_dto(txn) for txn in results.get("transactions", [])
        ]
        
        return {
            "transactions": transaction_dtos,
            "total": results.get("total", 0),
            "limit": query.limit,
            "offset": query.offset,
        }
    
    async def _fallback_db_search(
        self,
        query: GetTransactionHistoryQuery
    ) -> Dict[str, Any]:
        """Fallback à la recherche en base de données"""
        
        transactions = await self.transaction_repo.find_by_account_id(
            query.account_id
        )
        
        # Appliquer les filtres si présents
        if query.filters:
            transactions = self._apply_filters(transactions, query.filters)
        
        # Trier et paginer
        transactions = sorted(
            transactions,
            key=lambda t: t.timestamp,
            reverse=True
        )
        
        total = len(transactions)
        transactions = transactions[query.offset:query.offset + query.limit]
        
        return {
            "transactions": transactions,
            "total": total,
        }
    
    def _apply_filters(
        self,
        transactions: List[Transaction],
        filters: Dict[str, Any]
    ) -> List[Transaction]:
        """Applique les filtres aux transactions"""
        
        result = transactions
        
        # Filtre par montant
        if "min_amount" in filters:
            result = [
                t for t in result
                if float(t.amount.amount) >= filters["min_amount"]
            ]
        
        if "max_amount" in filters:
            result = [
                t for t in result
                if float(t.amount.amount) <= filters["max_amount"]
            ]
        
        # Filtre par statut
        if "status" in filters:
            result = [
                t for t in result
                if t.status.value == filters["status"]
            ]
        
        # Filtre par fraude
        if "is_fraud" in filters:
            result = [
                t for t in result
                if t.is_fraud == filters["is_fraud"]
            ]
        
        # Filtre par date
        if "start_date" in filters:
            start = datetime.fromisoformat(filters["start_date"])
            result = [t for t in result if t.timestamp >= start]
        
        if "end_date" in filters:
            end = datetime.fromisoformat(filters["end_date"])
            result = [t for t in result if t.timestamp <= end]
        
        return result
    
    def _to_dto(self, transaction: Transaction) -> TransactionDTO:
        """Convertit une Transaction en DTO"""
        return TransactionDTO(
            id=transaction.id,
            account_id=transaction.account_id,
            amount=float(transaction.amount.amount),
            currency=transaction.amount.currency,
            merchant_id=transaction.merchant_id,
            merchant_name=transaction.merchant_name,
            timestamp=transaction.timestamp.isoformat(),
            status=transaction.status.value,
            is_fraud=transaction.is_fraud,
            risk_score=transaction.risk_score,
            fraud_reason=(
                transaction.fraud_indicator.reason
                if transaction.fraud_indicator else None
            ),
        )