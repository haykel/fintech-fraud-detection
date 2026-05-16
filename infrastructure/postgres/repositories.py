from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import os
import json
from datetime import datetime

from domain.transaction import Transaction, Money, FraudIndicator, TransactionStatus
from domain.account import Account, RiskProfile, AccountStatus
from domain.common import DomainEvent
from infrastructure.postgres.models import (
    Base, TransactionModel, AccountModel, EventModel, AuditLogModel
)

# ==================== Database Setup ====================

# URL de connexion
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/fintech_db"
)

# Engine asynchrone
engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialise la base de données"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ==================== Repository Implementations ====================

class PostgresTransactionRepository:
    """Repository pour les Transactions"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
    
    async def find_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Trouve une transaction par ID"""
        async with self.session_local() as session:
            model = await session.get(TransactionModel, transaction_id)
            if model:
                return self._model_to_entity(model)
            return None
    
    async def find_by_account_id(self, account_id: str) -> List[Transaction]:
        """Trouve toutes les transactions d'un compte"""
        async with self.session_local() as session:
            from sqlalchemy import select
            query = select(TransactionModel).where(
                TransactionModel.account_id == account_id
            ).order_by(TransactionModel.created_at.desc())
            
            result = await session.execute(query)
            models = result.scalars().all()
            return [self._model_to_entity(m) for m in models]
    
    async def save(self, transaction: Transaction) -> None:
        """Sauvegarde une transaction"""
        async with self.session_local() as session:
            model = TransactionModel(
                id=transaction.id,
                account_id=transaction.account_id,
                amount=float(transaction.amount.amount),
                currency=transaction.amount.currency,
                merchant_id=transaction.merchant_id,
                merchant_name=transaction.merchant_name,
                merchant_category=transaction.merchant_category,
                merchant_country=transaction.merchant_country,
                status=transaction.status.value,
                is_fraud=transaction.is_fraud,
                risk_score=transaction.risk_score,
                fraud_reason=(
                    transaction.fraud_indicator.reason
                    if transaction.fraud_indicator else None
                ),
                fraud_explanation=(
                    transaction.fraud_indicator.explanation
                    if transaction.fraud_indicator else None
                ),
                metadata=transaction.metadata,
                created_at=transaction.created_at,
                updated_at=transaction.updated_at,
            )
            
            # Merge pour update ou insert
            await session.merge(model)
            await session.commit()
    
    def _model_to_entity(self, model: TransactionModel) -> Transaction:
        """Convertit un ORM model en entité domaine"""
        amount = Money(
            amount=model.amount,
            currency=model.currency
        )
        
        fraud_indicator = None
        if model.is_fraud:
            fraud_indicator = FraudIndicator(
                is_fraud=True,
                risk_score=model.risk_score or 0.0,
                reason=model.fraud_reason,
                explanation=model.fraud_explanation
            )
        
        return Transaction(
            id=model.id,
            account_id=model.account_id,
            amount=amount,
            merchant_id=model.merchant_id,
            merchant_name=model.merchant_name,
            merchant_category=model.merchant_category,
            merchant_country=model.merchant_country,
            timestamp=model.created_at,
            status=TransactionStatus(model.status),
            fraud_indicator=fraud_indicator,
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class PostgresAccountRepository:
    """Repository pour les Accounts"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
    
    async def find_by_id(self, account_id: str) -> Optional[Account]:
        """Trouve un compte par ID"""
        async with self.session_local() as session:
            model = await session.get(AccountModel, account_id)
            if model:
                return self._model_to_entity(model)
            return None
    
    async def find_by_email(self, email: str) -> Optional[Account]:
        """Trouve un compte par email"""
        async with self.session_local() as session:
            from sqlalchemy import select
            query = select(AccountModel).where(AccountModel.email == email)
            
            result = await session.execute(query)
            model = result.scalar_one_or_none()
            if model:
                return self._model_to_entity(model)
            return None
    
    async def save(self, account: Account) -> None:
        """Sauvegarde un compte"""
        async with self.session_local() as session:
            model = AccountModel(
                id=account.id,
                holder_name=account.holder_name,
                email=account.email,
                phone=account.phone,
                status=account.status.value,
                historical_risk_score=account.risk_profile.historical_risk_score,
                transaction_count=account.risk_profile.transaction_count,
                fraud_count=account.risk_profile.fraud_count,
                last_risk_update=account.risk_profile.last_risk_update,
                metadata=account.metadata,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
            
            await session.merge(model)
            await session.commit()
    
    def _model_to_entity(self, model: AccountModel) -> Account:
        """Convertit un ORM model en entité domaine"""
        risk_profile = RiskProfile(
            historical_risk_score=model.historical_risk_score,
            transaction_count=model.transaction_count,
            fraud_count=model.fraud_count,
            last_risk_update=model.last_risk_update,
        )
        
        return Account(
            id=model.id,
            holder_name=model.holder_name,
            email=model.email,
            phone=model.phone,
            status=AccountStatus(model.status),
            risk_profile=risk_profile,
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class EventStore:
    """Event Store pour les Domain Events"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
    
    async def append(self, event: DomainEvent) -> None:
        """Ajoute un événement à l'event store"""
        async with self.session_local() as session:
            model = EventModel(
                event_type=event.event_type,
                aggregate_id=event.aggregate_id,
                aggregate_type=event.aggregate_type,
                aggregate_version=event.aggregate_version,
                data=event._get_event_data(),
                metadata=event.metadata,
                timestamp=event.timestamp,
            )
            
            session.add(model)
            await session.commit()
    
    async def get_events(self, aggregate_id: str) -> List[DomainEvent]:
        """Récupère tous les événements d'un agrégat"""
        async with self.session_local() as session:
            from sqlalchemy import select
            query = select(EventModel).where(
                EventModel.aggregate_id == aggregate_id
            ).order_by(EventModel.timestamp.asc())
            
            result = await session.execute(query)
            models = result.scalars().all()
            
            # Reconvertir en événements domaine si nécessaire
            # Pour simplifier, on retourne juste les données
            return [m.data for m in models]


class AuditLog:
    """Audit Log pour la traçabilité"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
    
    async def log_action(
        self,
        entity_id: str,
        entity_type: str,
        action: str,
        actor: str,
        old_values: dict = None,
        new_values: dict = None,
        metadata: dict = None
    ) -> None:
        """Enregistre une action d'audit"""
        async with self.session_local() as session:
            model = AuditLogModel(
                entity_id=entity_id,
                entity_type=entity_type,
                action=action,
                actor=actor,
                old_values=old_values,
                new_values=new_values,
                metadata=metadata or {},
            )
            
            session.add(model)
            await session.commit()