from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from domain.transaction import Transaction, FraudIndicator


# ==================== Strategy Base ====================

class FraudDetectionStrategy(ABC):
    """
    Interface Strategy pour la détection de fraude
    
    Différentes implémentations peuvent être utilisées pour détecter
    la fraude selon différentes approches (règles, statistiques, ML, etc.)
    """
    
    @abstractmethod
    def detect_fraud(self, transaction: Transaction) -> FraudIndicator:
        """
        Analyse une transaction et retourne un indicateur de fraude
        
        Args:
            transaction: La transaction à analyser
            
        Returns:
            FraudIndicator avec le score de risque et la raison
        """
        pass
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Retourne le nom de la stratégie"""
        pass


# ==================== Rule-Based Strategy ====================

@dataclass
class FraudRule:
    """Une règle de fraude avec ses critères"""
    id: str
    name: str
    description: str
    min_risk_score: float  # Score de risque si la règle est déclenchée
    enabled: bool = True
    
    def __post_init__(self):
        if not 0 <= self.min_risk_score <= 1:
            raise ValueError("min_risk_score must be between 0 and 1")


class RuleBasedFraudDetectionStrategy(FraudDetectionStrategy):
    """
    Stratégie basée sur des règles métier.
    
    Chaque règle peut être activée selon certains critères
    (montant, localisation, fréquence, etc.)
    """
    
    def __init__(self, rules: List[FraudRule] = None):
        self.rules = rules or self._default_rules()
    
    @staticmethod
    def _default_rules() -> List[FraudRule]:
        """Crée un ensemble de règles par défaut"""
        return [
            FraudRule(
                id="rule_high_amount",
                name="High Amount",
                description="Transaction avec montant très élevé",
                min_risk_score=0.6
            ),
            FraudRule(
                id="rule_velocity",
                name="Velocity Check",
                description="Trop de transactions en peu de temps",
                min_risk_score=0.5
            ),
            FraudRule(
                id="rule_unusual_merchant",
                name="Unusual Merchant",
                description="Catégorie de commerçant inhabituelle",
                min_risk_score=0.55
            ),
            FraudRule(
                id="rule_geolocation",
                name="Geolocation Anomaly",
                description="Transaction depuis un pays inhabituel",
                min_risk_score=0.75
            ),
        ]
    
    def detect_fraud(self, transaction: Transaction) -> FraudIndicator:
        """Exécute toutes les règles et combine les scores"""
        triggered_rules = []
        scores = []
        
        # Exécute chaque règle
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            if self._rule_matches(transaction, rule):
                triggered_rules.append(rule.id)
                scores.append(rule.min_risk_score)
        
        # Calcule le score final
        if not scores:
            # Aucune règle déclenchée = pas de fraude
            return FraudIndicator(
                is_fraud=False,
                risk_score=0.0,
                reason="No fraud rules triggered"
            )
        
        # Score final = maximum des scores (approche prudente)
        final_score = max(scores)
        
        # Fraude si score >= 0.7
        is_fraud = final_score >= 0.7
        
        reason = f"Rules triggered: {', '.join(triggered_rules)}"
        
        return FraudIndicator(
            is_fraud=is_fraud,
            risk_score=final_score,
            reason=reason
        )
    
    def _rule_matches(self, transaction: Transaction, rule: FraudRule) -> bool:
        """Vérifie si une règle s'applique à la transaction"""
        
        if rule.id == "rule_high_amount":
            # Montant > 5000 EUR = risqué
            return float(transaction.amount.amount) > 5000
        
        elif rule.id == "rule_velocity":
            # Cette règle nécessiterait historique (simulé ici)
            # En production, vérifier le nombre de txns dans la dernière heure
            return False  # Impossible à vérifier sans context historique
        
        elif rule.id == "rule_unusual_merchant":
            # Catégories à risque
            high_risk_categories = ["gambling", "crypto", "money_transfer"]
            if transaction.merchant_category:
                return transaction.merchant_category.lower() in high_risk_categories
            return False
        
        elif rule.id == "rule_geolocation":
            # Pays à risque ou différent du pays habituel
            high_risk_countries = ["KP", "IR", "SY"]  # North Korea, Iran, Syria
            if transaction.transaction_country:
                return transaction.transaction_country in high_risk_countries
            return False
        
        return False
    
    def add_rule(self, rule: FraudRule) -> None:
        """Ajoute une nouvelle règle"""
        self.rules.append(rule)
    
    def remove_rule(self, rule_id: str) -> None:
        """Supprime une règle"""
        self.rules = [r for r in self.rules if r.id != rule_id]
    
    def enable_rule(self, rule_id: str) -> None:
        """Active une règle"""
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = True
    
    def disable_rule(self, rule_id: str) -> None:
        """Désactive une règle"""
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = False
    
    @property
    def strategy_name(self) -> str:
        return "RuleBasedFraudDetection"


# ==================== Anomaly Detection Strategy ====================

class AnomalyDetectionStrategy(FraudDetectionStrategy):
    """
    Stratégie basée sur la détection d'anomalies statistiques.
    
    Détecte les transactions qui s'écartent significativement du profil normal.
    """
    
    def __init__(self):
        # En production, ces valeurs viendraient d'un modèle ML
        self.average_transaction_amount = 500.0
        self.std_deviation = 200.0
        self.average_transactions_per_day = 3
    
    def detect_fraud(self, transaction: Transaction) -> FraudIndicator:
        """Détecte les anomalies statistiques"""
        
        anomalies = []
        scores = []
        
        # Check 1: Montant anormal
        amount_score = self._check_amount_anomaly(transaction)
        if amount_score > 0:
            anomalies.append("amount_anomaly")
            scores.append(amount_score)
        
        # Check 2: Heure inhabituelle
        time_score = self._check_time_anomaly(transaction)
        if time_score > 0:
            anomalies.append("time_anomaly")
            scores.append(time_score)
        
        if not scores:
            return FraudIndicator(
                is_fraud=False,
                risk_score=0.0,
                reason="No statistical anomalies detected"
            )
        
        # Score final = moyenne des anomalies
        final_score = sum(scores) / len(scores)
        is_fraud = final_score >= 0.6
        
        reason = f"Anomalies: {', '.join(anomalies)}"
        
        return FraudIndicator(
            is_fraud=is_fraud,
            risk_score=final_score,
            reason=reason
        )
    
    def _check_amount_anomaly(self, transaction: Transaction) -> float:
        """Détecte les montants anormaux"""
        amount = float(transaction.amount.amount)
        
        # Calcule le nombre de std deviations
        z_score = abs(amount - self.average_transaction_amount) / self.std_deviation
        
        # Z-score > 3 = très anormal (>0.7 risk)
        # Z-score > 2 = anormal (>0.5 risk)
        if z_score > 3:
            return 0.8
        elif z_score > 2:
            return 0.6
        elif z_score > 1.5:
            return 0.4
        
        return 0.0
    
    def _check_time_anomaly(self, transaction: Transaction) -> float:
        """Détecte les heures anormales"""
        hour = transaction.timestamp.hour
        
        # Transactions entre 2h et 5h du matin = inhabituelles
        if 2 <= hour <= 5:
            return 0.5
        
        # Transactions le weekend = moins anormal mais notable
        if transaction.timestamp.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return 0.2
        
        return 0.0
    
    @property
    def strategy_name(self) -> str:
        return "AnomalyDetectionStrategy"


# ==================== Hybrid Strategy ====================

class HybridFraudDetectionStrategy(FraudDetectionStrategy):
    """
    Stratégie hybride qui combine plusieurs approches.
    
    Utilise à la fois les règles et la détection d'anomalies
    pour une meilleure précision.
    """
    
    def __init__(
        self,
        rule_strategy: FraudDetectionStrategy = None,
        anomaly_strategy: FraudDetectionStrategy = None,
        rule_weight: float = 0.6,
        anomaly_weight: float = 0.4
    ):
        self.rule_strategy = rule_strategy or RuleBasedFraudDetectionStrategy()
        self.anomaly_strategy = anomaly_strategy or AnomalyDetectionStrategy()
        
        # Poids pour combiner les scores
        self.rule_weight = rule_weight
        self.anomaly_weight = anomaly_weight
        
        if abs(self.rule_weight + self.anomaly_weight - 1.0) > 0.01:
            raise ValueError("Weights must sum to approximately 1.0")
    
    def detect_fraud(self, transaction: Transaction) -> FraudIndicator:
        """Combine les résultats des deux stratégies"""
        
        # Exécute les deux stratégies
        rule_result = self.rule_strategy.detect_fraud(transaction)
        anomaly_result = self.anomaly_strategy.detect_fraud(transaction)
        
        # Combine les scores
        final_score = (
            rule_result.risk_score * self.rule_weight +
            anomaly_result.risk_score * self.anomaly_weight
        )
        
        # Fraude si l'une des stratégies le dit ET score > 0.6
        is_fraud = (rule_result.is_fraud or anomaly_result.is_fraud) and final_score >= 0.6
        
        # Raison combinée
        reasons = [rule_result.reason]
        if anomaly_result.risk_score > 0:
            reasons.append(anomaly_result.reason)
        reason = " | ".join(reasons)
        
        return FraudIndicator(
            is_fraud=is_fraud,
            risk_score=final_score,
            reason=reason
        )
    
    @property
    def strategy_name(self) -> str:
        return "HybridFraudDetectionStrategy"


# ==================== Strategy Factory ====================

class FraudDetectionStrategyFactory:
    """Factory pour créer les stratégies"""
    
    @staticmethod
    def create_rule_based() -> FraudDetectionStrategy:
        return RuleBasedFraudDetectionStrategy()
    
    @staticmethod
    def create_anomaly_based() -> FraudDetectionStrategy:
        return AnomalyDetectionStrategy()
    
    @staticmethod
    def create_hybrid() -> FraudDetectionStrategy:
        return HybridFraudDetectionStrategy()
    
    @staticmethod
    def create_custom(
        strategy_type: str,
        **kwargs
    ) -> FraudDetectionStrategy:
        """Crée une stratégie personnalisée"""
        if strategy_type == "rule_based":
            return RuleBasedFraudDetectionStrategy(**kwargs)
        elif strategy_type == "anomaly":
            return AnomalyDetectionStrategy()
        elif strategy_type == "hybrid":
            return HybridFraudDetectionStrategy(**kwargs)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")