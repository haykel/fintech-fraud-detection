from dataclasses import dataclass
from typing import Optional, Dict, Any
from domain.transaction import Transaction, Money
from domain.account import Account
from domain.common import (
    TransactionCreatedEvent,
    FraudDetectedEvent,
    DomainEvent,
)
from domain.fraud_rule import FraudDetectionStrategy, FraudDetectionStrategyFactory


# ==================== Command ====================

@dataclass
class ProcessTransactionCommand:
    """
    Command pour traiter une nouvelle transaction
    
    C'est la requête qui demande au système de traiter une transaction.
    """
    account_id: str
    amount: float
    currency: str
    merchant_id: str
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    merchant_country: Optional[str] = None


# ==================== Command Handler ====================

class ProcessTransactionHandler:
    """
    Handler pour la commande ProcessTransaction
    
    Orchestrate le flux :
    1. Charger le compte
    2. Créer la transaction
    3. Appliquer la détection de fraude
    4. Persister
    5. Publier les événements
    """
    
    def __init__(
        self,
        account_repository,  # Port
        transaction_repository,  # Port
        fraud_detection_service,  # Service
        event_publisher,  # Port
    ):
        self.account_repo = account_repository
        self.transaction_repo = transaction_repository
        self.fraud_detection = fraud_detection_service
        self.event_publisher = event_publisher
    
    async def execute(self, command: ProcessTransactionCommand) -> Transaction:
        """Exécute la commande et retourne la transaction créée"""
        
        # 1. Charger le compte
        account = await self.account_repo.find_by_id(command.account_id)
        if account is None:
            raise ValueError(f"Account {command.account_id} not found")
        
        if not account.can_transact:
            raise ValueError(f"Account {command.account_id} cannot transact")
        
        # 2. Créer l'entité Transaction
        amount = Money(
            amount=command.amount,
            currency=command.currency
        )
        
        transaction = Transaction(
            account_id=command.account_id,
            amount=amount,
            merchant_id=command.merchant_id,
            merchant_name=command.merchant_name,
            merchant_category=command.merchant_category,
            merchant_country=command.merchant_country,
        )
        
        # 3. Appliquer la détection de fraude
        fraud_indicator = self.fraud_detection.detect_fraud(transaction)
        
        if fraud_indicator.is_fraud:
            transaction.mark_as_fraudulent(
                risk_score=fraud_indicator.risk_score,
                reason=fraud_indicator.reason
            )
        else:
            transaction.mark_as_approved()
        
        # 4. Persister la transaction
        await self.transaction_repo.save(transaction)
        
        # 5. Enregistrer dans le profil de risque du compte
        account.record_transaction()
        if fraud_indicator.is_fraud:
            account.record_fraud(fraud_indicator.risk_score)
        
        # Persister le compte mis à jour
        await self.account_repo.save(account)
        
        # 6. Publier les événements
        events = self._generate_events(transaction, account)
        for event in events:
            await self.event_publisher.publish(event)
        
        return transaction
    
    def _generate_events(
        self,
        transaction: Transaction,
        account: Account
    ) -> list:
        """Génère les événements domaine"""
        events = []
        
        # Event: Transaction créée
        events.append(TransactionCreatedEvent(
            aggregate_id=transaction.id,
            account_id=transaction.account_id,
            amount=float(transaction.amount.amount),
            currency=transaction.amount.currency,
            merchant_id=transaction.merchant_id,
            merchant_name=transaction.merchant_name,
        ))
        
        # Event: Fraude détectée
        if transaction.is_fraud:
            events.append(FraudDetectedEvent(
                aggregate_id=transaction.id,
                risk_score=transaction.fraud_indicator.risk_score,
                reason=transaction.fraud_indicator.reason,
                rules_triggered=[], # À implémenter avec historique
            ))
        
        return events