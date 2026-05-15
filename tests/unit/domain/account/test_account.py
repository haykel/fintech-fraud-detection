import pytest
from datetime import datetime
from domain.account import Account, RiskProfile, AccountStatus


class TestRiskProfile:
    """Tests pour le Value Object RiskProfile"""
    
    def test_risk_profile_creation_valid(self):
        """Test création valide"""
        profile = RiskProfile(
            historical_risk_score=0.5,
            transaction_count=10,
            fraud_count=1,
            last_risk_update=datetime.utcnow()
        )
        assert profile.historical_risk_score == 0.5
        assert profile.transaction_count == 10
        assert profile.fraud_count == 1
    
    def test_risk_profile_invalid_score_raises_error(self):
        """Test que score invalide lève une erreur"""
        with pytest.raises(ValueError, match="Risk score must be between 0 and 1"):
            RiskProfile(
                historical_risk_score=1.5,
                transaction_count=10,
                fraud_count=1,
                last_risk_update=datetime.utcnow()
            )
    
    def test_risk_profile_fraud_rate(self):
        """Test calcul du taux de fraude"""
        profile = RiskProfile(
            historical_risk_score=0.5,
            transaction_count=10,
            fraud_count=2,
            last_risk_update=datetime.utcnow()
        )
        assert profile.fraud_rate == 0.2  # 2/10
    
    def test_risk_profile_fraud_rate_zero_transactions(self):
        """Test taux de fraude avec zéro transactions"""
        profile = RiskProfile(
            historical_risk_score=0.0,
            transaction_count=0,
            fraud_count=0,
            last_risk_update=datetime.utcnow()
        )
        assert profile.fraud_rate == 0.0
    
    def test_risk_profile_is_high_risk_by_score(self):
        """Test détection haut risque par score"""
        profile = RiskProfile(
            historical_risk_score=0.7,
            transaction_count=10,
            fraud_count=0,
            last_risk_update=datetime.utcnow()
        )
        assert profile.is_high_risk_account is True
    
    def test_risk_profile_is_high_risk_by_fraud_rate(self):
        """Test détection haut risque par taux de fraude"""
        profile = RiskProfile(
            historical_risk_score=0.3,
            transaction_count=100,
            fraud_count=6,  # 6% > 5%
            last_risk_update=datetime.utcnow()
        )
        assert profile.is_high_risk_account is True


class TestAccount:
    """Tests pour l'Aggregate Root Account"""
    
    def test_account_creation_valid(self):
        """Test création valide"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com",
            phone="+33612345678"
        )
        
        assert account.holder_name == "John Doe"
        assert account.email == "john@example.com"
        assert account.status == AccountStatus.ACTIVE
        assert account.id is not None
        assert account.risk_profile is not None
    
    def test_account_missing_holder_name_raises_error(self):
        """Test que holder_name manquant lève une erreur"""
        with pytest.raises(ValueError, match="Holder name is required"):
            Account(
                holder_name="",
                email="john@example.com"
            )
    
    def test_account_missing_email_raises_error(self):
        """Test que email manquant lève une erreur"""
        with pytest.raises(ValueError, match="Email is required"):
            Account(
                holder_name="John Doe",
                email=""
            )
    
    def test_account_suspend(self):
        """Test suspension du compte"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.suspend("Suspicious activity")
        
        assert account.status == AccountStatus.SUSPENDED
        assert account.metadata["suspension_reason"] == "Suspicious activity"
    
    def test_account_freeze(self):
        """Test gel du compte"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.freeze("Fraud detected")
        
        assert account.status == AccountStatus.FROZEN
        assert account.metadata["freeze_reason"] == "Fraud detected"
    
    def test_account_unfreeze(self):
        """Test déverrouillage"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.freeze("Test freeze")
        account.unfreeze()
        
        assert account.status == AccountStatus.ACTIVE
    
    def test_account_unfreeze_not_frozen_raises_error(self):
        """Test que dégel d'un compte non gelé lève une erreur"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        with pytest.raises(ValueError, match="Account is not frozen"):
            account.unfreeze()
    
    def test_account_close(self):
        """Test fermeture du compte"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.close("User requested closure")
        
        assert account.status == AccountStatus.CLOSED
        assert account.metadata["closure_reason"] == "User requested closure"
    
    def test_account_record_transaction(self):
        """Test enregistrement d'une transaction"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        assert account.risk_profile.transaction_count == 0
        
        account.record_transaction()
        
        assert account.risk_profile.transaction_count == 1
    
    def test_account_record_fraud(self):
        """Test enregistrement d'une fraude"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.record_fraud(risk_score=0.9)
        
        assert account.risk_profile.fraud_count == 1
        assert account.risk_profile.transaction_count == 1
        # Score moyen = 0.9
        assert abs(account.risk_profile.historical_risk_score - 0.9) < 0.01
    
    def test_account_update_risk_profile(self):
        """Test mise à jour du profil de risque"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.update_risk_profile(
            historical_risk_score=0.6,
            transaction_count=50,
            fraud_count=3
        )
        
        assert account.risk_profile.historical_risk_score == 0.6
        assert account.risk_profile.transaction_count == 50
        assert account.risk_profile.fraud_count == 3
    
    def test_account_is_high_risk(self):
        """Test détection compte haut risque"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        account.update_risk_profile(
            historical_risk_score=0.75,
            transaction_count=20,
            fraud_count=2
        )
        
        assert account.is_high_risk is True
    
    def test_account_can_transact(self):
        """Test si le compte peut faire des transactions"""
        account = Account(
            holder_name="John Doe",
            email="john@example.com"
        )
        
        assert account.can_transact is True
        
        account.freeze("Test")
        assert account.can_transact is False
        
        account.unfreeze()
        assert account.can_transact is True
    
    def test_account_equality_by_id(self):
        """Test égalité par ID"""
        account1 = Account(
            id="same-id",
            holder_name="John Doe",
            email="john@example.com"
        )
        account2 = Account(
            id="same-id",
            holder_name="Jane Doe",
            email="jane@example.com"
        )
        
        assert account1 == account2