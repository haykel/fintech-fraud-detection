from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import uuid


# ==================== Enums ====================

class AccountStatus(str, Enum):
    """Status d'un compte"""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


# ==================== Value Objects ====================

@dataclass(frozen=True)
class RiskProfile:
    """Value Object pour le profil de risque d'un compte"""
    historical_risk_score: float  # Score moyen historique (0-1)
    transaction_count: int  # Nombre total de transactions
    fraud_count: int  # Nombre de fraudes détectées
    last_risk_update: datetime  # Dernière mise à jour du score
    
    def __post_init__(self):
        if not 0 <= self.historical_risk_score <= 1:
            raise ValueError("Risk score must be between 0 and 1")
        if self.transaction_count < 0:
            raise ValueError("Transaction count cannot be negative")
        if self.fraud_count < 0:
            raise ValueError("Fraud count cannot be negative")
    
    @property
    def fraud_rate(self) -> float:
        """Retourne le taux de fraude (fraud_count / transaction_count)"""
        if self.transaction_count == 0:
            return 0.0
        return self.fraud_count / self.transaction_count
    
    @property
    def is_high_risk_account(self) -> bool:
        """Retourne True si le compte est à haut risque"""
        # Haut risque si: score moyen > 0.6 OU taux de fraude > 5%
        return self.historical_risk_score > 0.6 or self.fraud_rate > 0.05


# ==================== Aggregate Root ====================

@dataclass
class Account:
    """
    Account Aggregate Root
    
    Représente un compte bancaire avec toutes ses informations,
    son statut, et son profil de risque.
    """
    
    # Identité
    id: str = None  # UUID
    
    # Informations du titulaire
    holder_name: str = None
    email: str = None
    phone: Optional[str] = None
    
    # Status et profil
    status: AccountStatus = AccountStatus.ACTIVE
    risk_profile: Optional[RiskProfile] = None
    
    # Métadonnées
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Audit
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        """Valide l'entité lors de la création"""
        if self.id is None:
            self.id = str(uuid.uuid4())
        
        if self.holder_name is None or not self.holder_name.strip():
            raise ValueError("Holder name is required")
        
        if self.email is None or not self.email.strip():
            raise ValueError("Email is required")
        
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        
        # Crée un profil de risque par défaut si absent
        if self.risk_profile is None:
            self.risk_profile = RiskProfile(
                historical_risk_score=0.0,
                transaction_count=0,
                fraud_count=0,
                last_risk_update=datetime.utcnow()
            )
    
    # ==================== Méthodes métier ====================
    
    def suspend(self, reason: str) -> None:
        """Suspend le compte"""
        if self.status == AccountStatus.CLOSED:
            raise ValueError("Cannot suspend a closed account")
        
        self.status = AccountStatus.SUSPENDED
        self.add_metadata("suspension_reason", reason)
        self.updated_at = datetime.utcnow()
    
    def unfreeze(self) -> None:
        """Déverrouille un compte gelé"""
        if self.status != AccountStatus.FROZEN:
            raise ValueError("Account is not frozen")
        
        self.status = AccountStatus.ACTIVE
        self.updated_at = datetime.utcnow()
    
    def freeze(self, reason: str) -> None:
        """Gèle le compte (mesure plus sévère que suspension)"""
        if self.status == AccountStatus.CLOSED:
            raise ValueError("Cannot freeze a closed account")
        
        self.status = AccountStatus.FROZEN
        self.add_metadata("freeze_reason", reason)
        self.updated_at = datetime.utcnow()
    
    def close(self, reason: str) -> None:
        """Ferme le compte de manière permanente"""
        self.status = AccountStatus.CLOSED
        self.add_metadata("closure_reason", reason)
        self.add_metadata("closed_at", datetime.utcnow().isoformat())
        self.updated_at = datetime.utcnow()
    
    def update_risk_profile(
        self,
        historical_risk_score: float,
        transaction_count: int,
        fraud_count: int
    ) -> None:
        """Met à jour le profil de risque du compte"""
        self.risk_profile = RiskProfile(
            historical_risk_score=historical_risk_score,
            transaction_count=transaction_count,
            fraud_count=fraud_count,
            last_risk_update=datetime.utcnow()
        )
        self.updated_at = datetime.utcnow()
    
    def record_transaction(self) -> None:
        """Enregistre qu'une transaction a été effectuée"""
        if self.risk_profile is None:
            raise ValueError("Account must have risk profile")
        
        self.update_risk_profile(
            historical_risk_score=self.risk_profile.historical_risk_score,
            transaction_count=self.risk_profile.transaction_count + 1,
            fraud_count=self.risk_profile.fraud_count
        )
    
    def record_fraud(self, risk_score: float) -> None:
        """Enregistre une fraude détectée"""
        if self.risk_profile is None:
            raise ValueError("Account must have risk profile")
        
        # Recalcule le score moyen avec la nouvelle fraude
        old_sum = self.risk_profile.historical_risk_score * self.risk_profile.transaction_count
        new_sum = old_sum + risk_score
        new_count = self.risk_profile.transaction_count + 1
        new_avg = new_sum / new_count if new_count > 0 else 0
        
        self.update_risk_profile(
            historical_risk_score=new_avg,
            transaction_count=new_count,
            fraud_count=self.risk_profile.fraud_count + 1
        )
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Ajoute une métadonnée"""
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()
    
    # ==================== Properties ====================
    
    @property
    def is_active(self) -> bool:
        """Retourne True si le compte est actif"""
        return self.status == AccountStatus.ACTIVE
    
    @property
    def is_suspended(self) -> bool:
        """Retourne True si le compte est suspendu"""
        return self.status == AccountStatus.SUSPENDED
    
    @property
    def is_frozen(self) -> bool:
        """Retourne True si le compte est gelé"""
        return self.status == AccountStatus.FROZEN
    
    @property
    def is_closed(self) -> bool:
        """Retourne True si le compte est fermé"""
        return self.status == AccountStatus.CLOSED
    
    @property
    def is_high_risk(self) -> bool:
        """Retourne True si le compte est à haut risque"""
        if self.risk_profile is None:
            return False
        return self.risk_profile.is_high_risk_account
    
    @property
    def can_transact(self) -> bool:
        """Retourne True si le compte peut faire des transactions"""
        return self.is_active and not self.is_frozen
    
    # ==================== Equality ====================
    
    def __eq__(self, other: 'Account') -> bool:
        """Deux comptes sont égaux si ils ont le même ID"""
        if not isinstance(other, Account):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash basé sur l'ID"""
        return hash(self.id)