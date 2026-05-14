import pytest
from decimal import Decimal
from datetime import datetime
from domain.transaction import Transaction, Money, FraudIndicator, TransactionStatus


class TestMoney:
    """Tests pour le Value Object Money"""
    
    def test_money_creation_valid(self):
        """Test création valide"""
        money = Money(Decimal("100.50"), "EUR")
        assert money.amount == Decimal("100.50")
        assert money.currency == "EUR"
    
    def test_money_negative_amount_raises_error(self):
        """Test que le montant négatif lève une erreur"""
        with pytest.raises(ValueError, match="Amount cannot be negative"):
            Money(Decimal("-100"), "EUR")
    
    def test_money_invalid_currency_raises_error(self):
        """Test que la devise invalide lève une erreur"""
        with pytest.raises(ValueError, match="Currency must be a 3-letter code"):
            Money(Decimal("100"), "US")  # Invalide (2 lettres)
    
    def test_money_addition(self):
        """Test l'addition de deux Money"""
        m1 = Money(Decimal("100"), "EUR")
        m2 = Money(Decimal("50"), "EUR")
        result = m1 + m2
        assert result.amount == Decimal("150")
        assert result.currency == "EUR"
    
    def test_money_addition_different_currency_raises_error(self):
        """Test que l'addition avec devises différentes lève une erreur"""
        m1 = Money(Decimal("100"), "EUR")
        m2 = Money(Decimal("50"), "USD")
        with pytest.raises(ValueError, match="Cannot add different currencies"):
            m1 + m2


class TestFraudIndicator:
    """Tests pour le Value Object FraudIndicator"""
    
    def test_fraud_indicator_valid(self):
        """Test création valide"""
        indicator = FraudIndicator(
            is_fraud=True,
            risk_score=0.85,
            reason="Suspicious amount",
            explanation="High amount transaction detected"
        )
        assert indicator.is_fraud is True
        assert indicator.risk_score == 0.85
    
    def test_fraud_indicator_invalid_risk_score_raises_error(self):
        """Test que risk_score hors limites lève une erreur"""
        with pytest.raises(ValueError, match="Risk score must be between 0 and 1"):
            FraudIndicator(
                is_fraud=True,
                risk_score=1.5,  # Invalide
                reason="Test"
            )
    
    def test_fraud_indicator_fraud_without_reason_raises_error(self):
        """Test que fraude sans raison lève une erreur"""
        with pytest.raises(ValueError, match="Reason is required"):
            FraudIndicator(
                is_fraud=True,
                risk_score=0.8,
                reason=None  # Invalide
            )


class TestTransaction:
    """Tests pour l'Aggregate Root Transaction"""
    
    def test_transaction_creation_valid(self):
        """Test création valide"""
        amount = Money(Decimal("150.00"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456",
            merchant_name="Test Store"
        )
        
        assert txn.account_id == "acc-123"
        assert txn.amount == amount
        assert txn.status == TransactionStatus.PENDING
        assert txn.id is not None
        assert txn.created_at is not None
    
    def test_transaction_mark_as_fraudulent(self):
        """Test marquage comme frauduleuse"""
        amount = Money(Decimal("100"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        
        txn.mark_as_fraudulent(
            risk_score=0.95,
            reason="Unusual location",
            explanation="Transaction from unknown country"
        )
        
        assert txn.is_fraud is True
        assert txn.risk_score == 0.95
        assert txn.status == TransactionStatus.BLOCKED
    
    def test_transaction_mark_as_approved(self):
        """Test approbation"""
        amount = Money(Decimal("100"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        
        txn.mark_as_approved()
        
        assert txn.status == TransactionStatus.APPROVED
    
    def test_transaction_mark_as_rejected(self):
        """Test rejet"""
        amount = Money(Decimal("100"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        
        txn.mark_as_rejected("Insufficient funds")
        
        assert txn.status == TransactionStatus.REJECTED
    
    def test_transaction_cannot_approve_blocked(self):
        """Test qu'on ne peut pas approuver une transaction bloquée"""
        amount = Money(Decimal("100"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        
        txn.mark_as_fraudulent(0.9, "Fraud detected")
        
        with pytest.raises(ValueError, match="Cannot approve a blocked"):
            txn.mark_as_approved()
    
    def test_transaction_equality_by_id(self):
        """Test que deux transactions avec même ID sont égales"""
        amount = Money(Decimal("100"), "EUR")
        txn1 = Transaction(
            id="same-id",
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        txn2 = Transaction(
            id="same-id",
            account_id="acc-789",
            amount=amount,
            merchant_id="merchant-999"
        )
        
        assert txn1 == txn2
    
    def test_transaction_is_high_risk(self):
        """Test la property is_high_risk"""
        amount = Money(Decimal("100"), "EUR")
        txn = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        
        txn.mark_as_fraudulent(0.75, "High risk")
        assert txn.is_high_risk is True
        
        txn2 = Transaction(
            account_id="acc-123",
            amount=amount,
            merchant_id="merchant-456"
        )
        txn2.mark_as_fraudulent(0.5, "Medium risk")
        assert txn2.is_high_risk is False