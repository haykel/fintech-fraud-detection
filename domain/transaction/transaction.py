from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal
from enum import Enum
import uuid

# ==================== Enums ====================

class TransactionStatus(str, Enum):
    """Status d'une transaction"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


# ==================== Value Objects ====================

@dataclass(frozen=True)
class Money:
    """Value Object pour représenter une somme d'argent"""
    amount: Decimal
    currency: str
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter code (ISO 4217)")
    
    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot subtract different currencies")
        return Money(self.amount - other.amount, self.currency)


@dataclass(frozen=True)
class FraudIndicator:
    """Value Object pour l'indicateur de fraude"""
    is_fraud: bool
    risk_score: float  # 0-1
    reason: Optional[str] = None
    explanation: Optional[str] = None  # Explication IA via Mistral
    
    def __post_init__(self):
        if not 0 <= self.risk_score <= 1:
            raise ValueError("Risk score must be between 0 and 1")
        if self.is_fraud and not self.reason:
            raise ValueError("Reason is required when is_fraud is True")


# ==================== Aggregate Root ====================

@dataclass
class Transaction:
    """
    Transaction Aggregate Root
    
    Représente une transaction bancaire avec tous ses détails,
    son statut, et son indicateur de fraude.
    """
    
    # Identité
    id: str = None  # UUID
    account_id: str = None  # UUID du compte
    
    # Données métier
    amount: Money = None
    merchant_id: str = None  # UUID du commerçant
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    
    # Localisation
    merchant_country: Optional[str] = None
    transaction_country: Optional[str] = None
    
    # Temps
    timestamp: datetime = None
    
    # Status
    status: TransactionStatus = TransactionStatus.PENDING
    
    # Fraude
    fraud_indicator: Optional[FraudIndicator] = None
    
    # Métadonnées
    metadata: Dict[str, Any] = None
    
    # Audit
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        """Valide l'entité lors de la création"""
        if self.id is None:
            self.id = str(uuid.uuid4())
        
        if self.amount is None:
            raise ValueError("Amount is required")
        
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        
        if self.metadata is None:
            self.metadata = {}
    
    # ==================== Méthodes métier ====================
    
    def mark_as_fraudulent(
        self,
        risk_score: float,
        reason: str,
        explanation: Optional[str] = None
    ) -> None:
        """Marque la transaction comme frauduleuse"""
        if self.status == TransactionStatus.BLOCKED:
            raise ValueError("Cannot mark blocked transaction as fraudulent")
        
        self.fraud_indicator = FraudIndicator(
            is_fraud=True,
            risk_score=risk_score,
            reason=reason,
            explanation=explanation
        )
        self.status = TransactionStatus.BLOCKED
        self.updated_at = datetime.utcnow()
    
    def mark_as_approved(self) -> None:
        """Approuve la transaction"""
        if self.status == TransactionStatus.BLOCKED:
            raise ValueError("Cannot approve a blocked transaction")
        
        self.status = TransactionStatus.APPROVED
        self.updated_at = datetime.utcnow()
    
    def mark_as_rejected(self, reason: str) -> None:
        """Rejette la transaction"""
        self.status = TransactionStatus.REJECTED
        self.fraud_indicator = FraudIndicator(
            is_fraud=False,
            risk_score=0.0,
            reason=reason
        )
        self.updated_at = datetime.utcnow()
    
    def set_fraud_explanation(self, explanation: str) -> None:
        """Ajoute une explication IA à l'indicateur de fraude"""
        if self.fraud_indicator is None:
            raise ValueError("Transaction must have fraud indicator first")
        
        # Crée un nouvel indicateur avec l'explication
        self.fraud_indicator = FraudIndicator(
            is_fraud=self.fraud_indicator.is_fraud,
            risk_score=self.fraud_indicator.risk_score,
            reason=self.fraud_indicator.reason,
            explanation=explanation
        )
        self.updated_at = datetime.utcnow()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Ajoute une métadonnée"""
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()
    
    # ==================== Properties ====================
    
    @property
    def is_fraud(self) -> bool:
        """Retourne True si la transaction est marquée comme fraude"""
        return self.fraud_indicator is not None and self.fraud_indicator.is_fraud
    
    @property
    def risk_score(self) -> float:
        """Retourne le score de risque (0 si pas d'indicateur)"""
        if self.fraud_indicator is None:
            return 0.0
        return self.fraud_indicator.risk_score
    
    @property
    def is_high_risk(self) -> bool:
        """Retourne True si le risque est > 0.7"""
        return self.risk_score > 0.7
    
    @property
    def is_approved_or_blocked(self) -> bool:
        """Retourne True si la transaction est approuvée ou bloquée"""
        return self.status in [TransactionStatus.APPROVED, TransactionStatus.BLOCKED]
    
    # ==================== Equality ====================
    
    def __eq__(self, other: 'Transaction') -> bool:
        """Deux transactions sont égales si elles ont le même ID"""
        if not isinstance(other, Transaction):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash basé sur l'ID"""
        return hash(self.id)