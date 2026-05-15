import pytest
from datetime import datetime
from decimal import Decimal
from domain.transaction import Transaction, Money
from domain.fraud_rule import (
    FraudDetectionStrategy,
    FraudRule,
    RuleBasedFraudDetectionStrategy,
    AnomalyDetectionStrategy,
    HybridFraudDetectionStrategy,
    FraudDetectionStrategyFactory,
)


class TestRuleBasedStrategy:
    """Tests pour RuleBasedFraudDetectionStrategy"""
    
    def test_no_fraud_when_no_rules_triggered(self):
        """Test aucune fraude quand pas de règles"""
        strategy = RuleBasedFraudDetectionStrategy()
        
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("100"), "EUR"),
            merchant_id="merchant-456",
            merchant_category="retail"
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.is_fraud is False
        assert result.risk_score == 0.0
    
    def test_high_amount_triggers_rule(self):
        """Test que montant élevé déclenche la règle"""
        strategy = RuleBasedFraudDetectionStrategy()
        
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("10000"), "EUR"),  # > 5000
            merchant_id="merchant-456"
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.risk_score >= 0.6
        assert "rule_high_amount" in result.reason
    
    def test_geolocation_rule(self):
        """Test détection par géolocalisation"""
        strategy = RuleBasedFraudDetectionStrategy()
        
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("100"), "EUR"),
            merchant_id="merchant-456",
            transaction_country="KP"  # North Korea
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.is_fraud is True
        assert result.risk_score >= 0.7
    
    def test_add_custom_rule(self):
        """Test ajout d'une règle personnalisée"""
        strategy = RuleBasedFraudDetectionStrategy()
        
        custom_rule = FraudRule(
            id="custom_rule",
            name="Custom",
            description="Test rule",
            min_risk_score=0.5
        )
        
        strategy.add_rule(custom_rule)
        
        assert len(strategy.rules) > 4  # 4 par défaut + 1 custom
    
    def test_disable_rule(self):
        """Test désactivation d'une règle"""
        strategy = RuleBasedFraudDetectionStrategy()
        
        strategy.disable_rule("rule_high_amount")
        
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("10000"), "EUR"),
            merchant_id="merchant-456"
        )
        
        result = strategy.detect_fraud(transaction)
        
        # La règle est désactivée, donc pas de fraude
        assert "rule_high_amount" not in result.reason


class TestAnomalyDetectionStrategy:
    """Tests pour AnomalyDetectionStrategy"""
    
    def test_normal_transaction(self):
        """Test transaction normale"""
        strategy = AnomalyDetectionStrategy()
        
        # Montant proche de la moyenne
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("550"), "EUR"),
            merchant_id="merchant-456"
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.is_fraud is False
        assert result.risk_score < 0.6
    
    def test_unusual_amount_detected(self):
        """Test détection de montant anormal"""
        strategy = AnomalyDetectionStrategy()
        
        # Montant très élevé (> 3 std deviations)
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("2000"), "EUR"),
            merchant_id="merchant-456"
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.risk_score > 0.4
        assert "amount_anomaly" in result.reason
    
    def test_unusual_time_detected(self):
        """Test détection d'heure anormale"""
        strategy = AnomalyDetectionStrategy()
        
        # Transaction à 3h du matin
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("100"), "EUR"),
            merchant_id="merchant-456",
            timestamp=datetime(2026, 5, 15, 3, 0, 0)  # 3 AM
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.risk_score > 0


class TestHybridStrategy:
    """Tests pour HybridFraudDetectionStrategy"""
    
    def test_hybrid_combines_scores(self):
        """Test que stratégie hybride combine les scores"""
        strategy = HybridFraudDetectionStrategy()
        
        # Transaction qui déclenche des règles ET anomalies
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("10000"), "EUR"),  # Haut montant
            merchant_id="merchant-456",
            transaction_country="KP",  # Pays à risque
            timestamp=datetime(2026, 5, 15, 3, 0, 0)  # Heure anormale
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert result.is_fraud is True
        assert result.risk_score > 0.6
    
    def test_custom_weights(self):
        """Test avec poids personnalisés"""
        strategy = HybridFraudDetectionStrategy(
            rule_weight=0.8,
            anomaly_weight=0.2
        )
        
        transaction = Transaction(
            account_id="acc-123",
            amount=Money(Decimal("600"), "EUR"),
            merchant_id="merchant-456"
        )
        
        result = strategy.detect_fraud(transaction)
        
        assert isinstance(result.risk_score, float)
        assert 0 <= result.risk_score <= 1


class TestFraudDetectionStrategyFactory:
    """Tests pour le Factory"""
    
    def test_factory_creates_rule_based(self):
        """Test création strategy basée sur règles"""
        strategy = FraudDetectionStrategyFactory.create_rule_based()
        assert isinstance(strategy, RuleBasedFraudDetectionStrategy)
    
    def test_factory_creates_anomaly_based(self):
        """Test création strategy anomalie"""
        strategy = FraudDetectionStrategyFactory.create_anomaly_based()
        assert isinstance(strategy, AnomalyDetectionStrategy)
    
    def test_factory_creates_hybrid(self):
        """Test création strategy hybride"""
        strategy = FraudDetectionStrategyFactory.create_hybrid()
        assert isinstance(strategy, HybridFraudDetectionStrategy)
    
    def test_factory_invalid_type_raises_error(self):
        """Test erreur avec type invalide"""
        with pytest.raises(ValueError, match="Unknown strategy type"):
            FraudDetectionStrategyFactory.create_custom("invalid_type")


class TestFraudRule:
    """Tests pour FraudRule"""
    
    def test_fraud_rule_creation(self):
        """Test création d'une règle"""
        rule = FraudRule(
            id="test_rule",
            name="Test Rule",
            description="Test",
            min_risk_score=0.7
        )
        
        assert rule.id == "test_rule"
        assert rule.enabled is True
    
    def test_fraud_rule_invalid_score(self):
        """Test score invalide"""
        with pytest.raises(ValueError):
            FraudRule(
                id="test",
                name="Test",
                description="Test",
                min_risk_score=1.5  # > 1
            )