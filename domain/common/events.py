from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import uuid
import json


# ==================== Base Classes ====================

@dataclass
class DomainEvent(ABC):
    """
    Classe de base pour tous les événements du domaine
    
    Un événement représente quelque chose qui s'est passé dans le domaine.
    Immutable et sérialisable pour Event Sourcing.
    """
    
    # Identité de l'événement
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Identité de l'agrégat concerné
    aggregate_id: str = None
    aggregate_type: str = None
    
    # Timestamp et version
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_version: int = 1
    
    # Métadonnées
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Valide l'événement"""
        if self.aggregate_id is None:
            raise ValueError("aggregate_id is required")
        if self.aggregate_type is None:
            raise ValueError("aggregate_type is required")
    
    @property
    def event_type(self) -> str:
        """Retourne le type d'événement (nom de la classe)"""
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'événement en dictionnaire"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "timestamp": self.timestamp.isoformat(),
            "aggregate_version": self.aggregate_version,
            "data": self._get_event_data(),
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """Sérialise l'événement en JSON"""
        data = self.to_dict()
        # Convertir les objets non sérialisables
        return json.dumps(data, default=str)
    
    @abstractmethod
    def _get_event_data(self) -> Dict[str, Any]:
        """Retourne les données spécifiques de l'événement"""
        pass


# ==================== Transaction Events ====================

@dataclass
class TransactionCreatedEvent(DomainEvent):
    """Événement: Une transaction a été créée"""
    
    account_id: str = None
    amount: float = None
    currency: str = None
    merchant_id: str = None
    merchant_name: Optional[str] = None
    
    def __post_init__(self):
        self.aggregate_type = "Transaction"
        super().__post_init__()
        
        if self.account_id is None:
            raise ValueError("account_id is required")
        if self.amount is None or self.amount <= 0:
            raise ValueError("amount must be positive")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "amount": self.amount,
            "currency": self.currency,
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant_name,
        }


@dataclass
class TransactionApprovedEvent(DomainEvent):
    """Événement: Une transaction a été approuvée"""
    
    approved_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Transaction"
        super().__post_init__()
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "approved_at": self.approved_at.isoformat(),
        }


@dataclass
class TransactionRejectedEvent(DomainEvent):
    """Événement: Une transaction a été rejetée"""
    
    reason: str = None
    rejected_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Transaction"
        super().__post_init__()
        
        if self.reason is None:
            raise ValueError("reason is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "rejected_at": self.rejected_at.isoformat(),
        }


@dataclass
class FraudDetectedEvent(DomainEvent):
    """Événement: Une fraude a été détectée"""
    
    risk_score: float = None
    reason: str = None
    rules_triggered: list = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Transaction"
        super().__post_init__()
        
        if self.risk_score is None or not 0 <= self.risk_score <= 1:
            raise ValueError("risk_score must be between 0 and 1")
        if self.reason is None:
            raise ValueError("reason is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "reason": self.reason,
            "rules_triggered": self.rules_triggered,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class FraudExplainedEvent(DomainEvent):
    """Événement: Une fraude a été expliquée via Mistral"""
    
    explanation: str = None
    explained_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Transaction"
        super().__post_init__()
        
        if self.explanation is None:
            raise ValueError("explanation is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "explanation": self.explanation,
            "explained_at": self.explained_at.isoformat(),
        }


# ==================== Account Events ====================

@dataclass
class AccountCreatedEvent(DomainEvent):
    """Événement: Un compte a été créé"""
    
    holder_name: str = None
    email: str = None
    phone: Optional[str] = None
    
    def __post_init__(self):
        self.aggregate_type = "Account"
        super().__post_init__()
        
        if self.holder_name is None:
            raise ValueError("holder_name is required")
        if self.email is None:
            raise ValueError("email is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "holder_name": self.holder_name,
            "email": self.email,
            "phone": self.phone,
        }


@dataclass
class AccountSuspendedEvent(DomainEvent):
    """Événement: Un compte a été suspendu"""
    
    reason: str = None
    suspended_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Account"
        super().__post_init__()
        
        if self.reason is None:
            raise ValueError("reason is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "suspended_at": self.suspended_at.isoformat(),
        }


@dataclass
class AccountFrozenEvent(DomainEvent):
    """Événement: Un compte a été gelé"""
    
    reason: str = None
    frozen_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Account"
        super().__post_init__()
        
        if self.reason is None:
            raise ValueError("reason is required")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "frozen_at": self.frozen_at.isoformat(),
        }


@dataclass
class AccountUnfrozenEvent(DomainEvent):
    """Événement: Un compte a été déverrouillé"""
    
    unfrozen_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Account"
        super().__post_init__()
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "unfrozen_at": self.unfrozen_at.isoformat(),
        }


@dataclass
class RiskScoreCalculatedEvent(DomainEvent):
    """Événement: Un score de risque a été calculé"""
    
    historical_risk_score: float = None
    transaction_count: int = None
    fraud_count: int = None
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.aggregate_type = "Account"
        super().__post_init__()
        
        if self.historical_risk_score is None or not 0 <= self.historical_risk_score <= 1:
            raise ValueError("historical_risk_score must be between 0 and 1")
        if self.transaction_count is None or self.transaction_count < 0:
            raise ValueError("transaction_count must be >= 0")
        if self.fraud_count is None or self.fraud_count < 0:
            raise ValueError("fraud_count must be >= 0")
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "historical_risk_score": self.historical_risk_score,
            "transaction_count": self.transaction_count,
            "fraud_count": self.fraud_count,
            "calculated_at": self.calculated_at.isoformat(),
        }


# ==================== Event Publisher Port ====================

class EventPublisher:
    """Interface pour la publication des événements"""
    
    async def publish(self, event: DomainEvent) -> None:
        """Publie un événement"""
        raise NotImplementedError
    
    async def publish_many(self, events: list) -> None:
        """Publie plusieurs événements"""
        raise NotImplementedError


# ==================== Event Store ====================

class EventStore:
    """Interface pour le stockage des événements"""
    
    async def append(self, event: DomainEvent) -> None:
        """Ajoute un événement au store"""
        raise NotImplementedError
    
    async def get_events(self, aggregate_id: str) -> list:
        """Récupère tous les événements d'un agrégat"""
        raise NotImplementedError
    
    async def get_events_after(self, timestamp: datetime) -> list:
        """Récupère les événements après une date"""
        raise NotImplementedError