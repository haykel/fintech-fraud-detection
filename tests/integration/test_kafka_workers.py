import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from interfaces.workers import (
    TransactionEventConsumer,
    FraudDetectionConsumer,
)


@pytest.mark.asyncio
async def test_transaction_event_consumer():
    """Test le consumer des événements de transaction"""
    consumer = TransactionEventConsumer()
    
    # Mock du consumer Kafka
    event_data = {
        "event_type": "TransactionCreatedEvent",
        "aggregate_id": "txn-123",
        "data": {
            "account_id": "acc-456",
            "amount": 100.50,
            "currency": "EUR",
        }
    }
    
    # Vérifier que le handler fonctionne
    await consumer.handle_transaction_event(event_data)
    # Devrait logger l'événement sans erreur


@pytest.mark.asyncio
async def test_fraud_detection_consumer():
    """Test le consumer des événements de fraude"""
    consumer = FraudDetectionConsumer()
    
    event_data = {
        "event_type": "FraudDetectedEvent",
        "aggregate_id": "txn-123",
        "data": {
            "risk_score": 0.95,
            "reason": "Unusual location",
        }
    }
    
    # Vérifier que le handler fonctionne
    await consumer.handle_fraud_event(event_data)
    # Devrait logger la fraude sans erreur


@pytest.mark.asyncio
async def test_fraud_explanation_worker():
    """Test le worker d'explication de fraude"""
    # TODO: Implémenter les tests avec mock Mistral API
    pass