from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


# ==================== ORM Models ====================

class TransactionModel(Base):
    """ORM Model pour Transaction"""
    __tablename__ = "transactions"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Données
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    merchant_id = Column(String(36), nullable=False, index=True)
    merchant_name = Column(String(255), nullable=True)
    merchant_category = Column(String(100), nullable=True)
    merchant_country = Column(String(2), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, APPROVED, REJECTED, BLOCKED
    
    # Fraude
    is_fraud = Column(Boolean, default=False, index=True)
    risk_score = Column(Float, nullable=True)
    fraud_reason = Column(String(500), nullable=True)
    fraud_explanation = Column(String(1000), nullable=True)
    
    # Métadonnées (metadata_ car metadata est réservé)
    metadata_ = Column(JSON, nullable=True, default={})
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("AccountModel", back_populates="transactions")
    
    def __repr__(self):
        return f"<TransactionModel {self.id}>"


class AccountModel(Base):
    """ORM Model pour Account"""
    __tablename__ = "accounts"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Données
    holder_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED, FROZEN, CLOSED
    
    # Risk Profile
    historical_risk_score = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    fraud_count = Column(Integer, default=0)
    last_risk_update = Column(DateTime, default=datetime.utcnow)
    
    # Métadonnées
    metadata_ = Column(JSON, nullable=True, default={})
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("TransactionModel", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AccountModel {self.id}>"


class EventModel(Base):
    """ORM Model pour Domain Events (Event Store)"""
    __tablename__ = "events"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Event Metadata
    event_type = Column(String(100), nullable=False, index=True)
    aggregate_id = Column(String(36), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False, index=True)
    aggregate_version = Column(Integer, nullable=False)
    
    # Event Data
    data = Column(JSON, nullable=False)
    metadata_ = Column(JSON, nullable=True, default={})
    
    # Audit
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<EventModel {self.event_type}:{self.aggregate_id}>"


class AuditLogModel(Base):
    """ORM Model pour Audit Log"""
    __tablename__ = "audit_logs"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Audit Data
    entity_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    action = Column(String(20), nullable=False)  # CREATE, UPDATE, DELETE
    actor = Column(String(255), nullable=True)
    
    # Change Data
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Metadata
    metadata_ = Column(JSON, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLogModel {self.action}:{self.entity_type}>"