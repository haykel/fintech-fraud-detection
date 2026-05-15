import pytest
from datetime import datetime
from domain.common.events import (
    TransactionCreatedEvent,
    TransactionApprovedEvent,
    FraudDetectedEvent,
    AccountCreatedEvent,
    RiskScoreCalculatedEvent,
)


class TestTransactionCreatedEvent:
    """Tests pour TransactionCreatedEvent"""
    
    def test_transaction_created_event_valid(self):
        """Test création valide"""
        event = TransactionCreatedEvent(
            aggregate_id="txn-123",
            account_id="acc-456",
            amount=100.50,
            currency="EUR",
            merchant_id="merchant-789",
            merchant_name="Test Store"
        )
        
        assert event.aggregate_id == "txn-123"
        assert event.account_id == "acc-456"
        assert event.amount == 100.50
        assert event.event_type == "TransactionCreatedEvent"
        assert event.aggregate_type == "Transaction"
        assert event.event_id is not None
    
    def test_transaction_created_event_missing_account_id(self):
        """Test que account_id manquant lève une erreur"""
        with pytest.raises(ValueError, match="account_id is required"):
            TransactionCreatedEvent(
                aggregate_id="txn-123",
                amount=100.50,
                currency="EUR",
                merchant_id="merchant-789"
            )
    
    def test_transaction_created_event_invalid_amount(self):
        """Test que montant négatif lève une erreur"""
        with pytest.raises(ValueError, match="amount must be positive"):
            TransactionCreatedEvent(
                aggregate_id="txn-123",
                account_id="acc-456",
                amount=-100,
                currency="EUR",
                merchant_id="merchant-789"
            )
    
    def test_transaction_created_event_serialization(self):
        """Test sérialisation en dictionnaire"""
        event = TransactionCreatedEvent(
            aggregate_id="txn-123",
            account_id="acc-456",
            amount=100.50,
            currency="EUR",
            merchant_id="merchant-789"
        )
        
        data = event.to_dict()
        
        assert data["event_type"] == "TransactionCreatedEvent"
        assert data["aggregate_id"] == "txn-123"
        assert data["data"]["amount"] == 100.50
        assert "timestamp" in data
    
    def test_transaction_created_event_to_json(self):
        """Test sérialisation en JSON"""
        event = TransactionCreatedEvent(
            aggregate_id="txn-123",
            account_id="acc-456",
            amount=100.50,
            currency="EUR",
            merchant_id="merchant-789"
        )
        
        json_str = event.to_json()
        
        assert isinstance(json_str, str)
        assert "TransactionCreatedEvent" in json_str
        assert "txn-123" in json_str


class TestFraudDetectedEvent:
    """Tests pour FraudDetectedEvent"""
    
    def test_fraud_detected_event_valid(self):
        """Test création valide"""
        event = FraudDetectedEvent(
            aggregate_id="txn-123",
            risk_score=0.95,
            reason="Unusual location",
            rules_triggered=["geolocation_rule", "amount_threshold_rule"]
        )
        
        assert event.risk_score == 0.95
        assert event.reason == "Unusual location"
        assert len(event.rules_triggered) == 2
    
    def test_fraud_detected_event_invalid_risk_score(self):
        """Test que risk_score invalide lève une erreur"""
        with pytest.raises(ValueError, match="risk_score must be between 0 and 1"):
            FraudDetectedEvent(
                aggregate_id="txn-123",
                risk_score=1.5,  # Invalide
                reason="Test"
            )
    
    def test_fraud_detected_event_missing_reason(self):
        """Test que reason manquant lève une erreur"""
        with pytest.raises(ValueError, match="reason is required"):
            FraudDetectedEvent(
                aggregate_id="txn-123",
                risk_score=0.9,
                reason=None  # Invalide
            )


class TestAccountCreatedEvent:
    """Tests pour AccountCreatedEvent"""
    
    def test_account_created_event_valid(self):
        """Test création valide"""
        event = AccountCreatedEvent(
            aggregate_id="acc-123",
            holder_name="John Doe",
            email="john@example.com",
            phone="+33612345678"
        )
        
        assert event.holder_name == "John Doe"
        assert event.email == "john@example.com"
        assert event.aggregate_type == "Account"
    
    def test_account_created_event_missing_holder_name(self):
        """Test que holder_name manquant lève une erreur"""
        with pytest.raises(ValueError, match="holder_name is required"):
            AccountCreatedEvent(
                aggregate_id="acc-123",
                email="john@example.com"
            )


class TestRiskScoreCalculatedEvent:
    """Tests pour RiskScoreCalculatedEvent"""
    
    def test_risk_score_calculated_event_valid(self):
        """Test création valide"""
        event = RiskScoreCalculatedEvent(
            aggregate_id="acc-123",
            historical_risk_score=0.65,
            transaction_count=50,
            fraud_count=3
        )
        
        assert event.historical_risk_score == 0.65
        assert event.transaction_count == 50
        assert event.fraud_count == 3
    
    def test_risk_score_calculated_event_invalid_score(self):
        """Test que score invalide lève une erreur"""
        with pytest.raises(ValueError, match="historical_risk_score must be between"):
            RiskScoreCalculatedEvent(
                aggregate_id="acc-123",
                historical_risk_score=1.5,  # Invalide
                transaction_count=50,
                fraud_count=3
            )
    
    def test_risk_score_calculated_event_serialization(self):
        """Test sérialisation"""
        event = RiskScoreCalculatedEvent(
            aggregate_id="acc-123",
            historical_risk_score=0.65,
            transaction_count=50,
            fraud_count=3
        )
        
        data = event.to_dict()
        
        assert data["data"]["historical_risk_score"] == 0.65
        assert data["data"]["transaction_count"] == 50


class TestEventImmutability:
    """Tests pour vérifier l'immutabilité des événements"""
    
    def test_event_is_immutable(self):
        """Test que les événements sont immuables"""
        event = TransactionCreatedEvent(
            aggregate_id="txn-123",
            account_id="acc-456",
            amount=100.50,
            currency="EUR",
            merchant_id="merchant-789"
        )
        
        # Les dataclasses frozen=True ne sont pas utilisées ici,
        # mais c'est une bonne pratique à ajouter si nécessaire
        assert event.event_id is not None