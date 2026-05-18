"""Tools exposés à l'agent Mistral.

Chaque tool est une méthode async qui prend des arguments JSON-sérialisables et
retourne un dict JSON-sérialisable. `TOOL_SCHEMAS` décrit ces tools dans le
format attendu par l'API Mistral (compatible avec le schéma OpenAI function-calling).
"""

import logging
from typing import Any, Dict, Optional

from domain.fraud_rule import RuleBasedFraudDetectionStrategy
from domain.transaction import Transaction

logger = logging.getLogger(__name__)


# Tables de référence pour les heuristiques utilisées par les tools "sans I/O".
HIGH_RISK_COUNTRIES: Dict[str, float] = {
    "KP": 0.98,  # North Korea
    "IR": 0.92,  # Iran
    "SY": 0.92,  # Syria
    "AF": 0.85,  # Afghanistan
    "MM": 0.80,  # Myanmar
    "VE": 0.70,  # Venezuela
    "RU": 0.60,  # sanctions context
    "BY": 0.55,
    "CU": 0.55,
}

MEDIUM_RISK_COUNTRIES: Dict[str, float] = {
    "NG": 0.45,
    "PK": 0.45,
    "UA": 0.40,
}

HIGH_RISK_CATEGORIES: Dict[str, float] = {
    "gambling": 0.70,
    "crypto": 0.75,
    "money_transfer": 0.80,
    "adult": 0.60,
    "prepaid_cards": 0.55,
}


# ==================== Tool schemas (format Mistral / OpenAI) ====================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_transaction_details",
            "description": "Récupère tous les détails d'une transaction (montant, devise, "
                           "commerçant, localisation, statut, indicateur de fraude).",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "UUID de la transaction.",
                    }
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_history",
            "description": "Liste les transactions les plus récentes d'un compte (10 par défaut, "
                           "triées par date décroissante).",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "UUID du compte."},
                    "limit": {"type": "integer", "description": "Nombre max de transactions.", "default": 10},
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_risk_profile",
            "description": "Retourne le profil de risque d'un compte (score historique, "
                           "nombre de transactions, nombre de fraudes, taux de fraude).",
            "parameters": {
                "type": "object",
                "properties": {"account_id": {"type": "string", "description": "UUID du compte."}},
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_geolocation_risk",
            "description": "Évalue le risque géographique d'un pays par son code ISO 3166-1 alpha-2. "
                           "Retourne un score 0-1 et un libellé qualitatif.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country_code": {
                        "type": "string",
                        "description": "Code pays ISO alpha-2 (ex: 'FR', 'KP').",
                    }
                },
                "required": ["country_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_merchant",
            "description": "Évalue le risque associé à un commerçant à partir de son identifiant "
                           "et éventuellement de sa catégorie.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "string", "description": "UUID du commerçant."},
                    "category": {
                        "type": "string",
                        "description": "Catégorie du commerçant (ex: 'crypto', 'retail').",
                    },
                },
                "required": ["merchant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fraud_rules_triggered",
            "description": "Ré-exécute les règles de fraude sur une transaction et retourne "
                           "la liste des règles déclenchées avec leur score.",
            "parameters": {
                "type": "object",
                "properties": {"transaction_id": {"type": "string", "description": "UUID de la transaction."}},
                "required": ["transaction_id"],
            },
        },
    },
]


# ==================== Implémentation ====================


class FraudAnalysisTools:
    """Implémente les tools exposés à l'agent.

    Reçoit en injection les ports (repositories) nécessaires pour ne pas
    coupler les tools à une implémentation infra particulière. Cela facilite
    aussi le mocking dans les tests.
    """

    def __init__(
        self,
        transaction_repo,
        account_repo,
        fraud_strategy=None,
    ):
        self.transaction_repo = transaction_repo
        self.account_repo = account_repo
        self.fraud_strategy = fraud_strategy or RuleBasedFraudDetectionStrategy()

    # -------- Tools --------

    async def get_transaction_details(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 1 : détails d'une transaction."""
        logger.debug("tool.get_transaction_details(%s)", transaction_id)
        txn = await self.transaction_repo.find_by_id(transaction_id)
        if txn is None:
            return {"error": f"Transaction {transaction_id} introuvable"}
        return self._transaction_to_dict(txn)

    async def get_account_history(
        self, account_id: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Tool 2 : 10 dernières transactions du compte."""
        logger.debug("tool.get_account_history(%s, limit=%s)", account_id, limit)
        txns = await self.transaction_repo.find_by_account_id(account_id)
        txns_sorted = sorted(
            txns,
            key=lambda t: t.timestamp,
            reverse=True,
        )[:limit]
        return {
            "account_id": account_id,
            "count": len(txns_sorted),
            "transactions": [self._transaction_to_dict(t) for t in txns_sorted],
        }

    async def get_account_risk_profile(self, account_id: str) -> Dict[str, Any]:
        """Tool 3 : profil de risque agrégé du compte."""
        logger.debug("tool.get_account_risk_profile(%s)", account_id)
        account = await self.account_repo.find_by_id(account_id)
        if account is None:
            return {"error": f"Compte {account_id} introuvable"}
        rp = account.risk_profile
        return {
            "account_id": account.id,
            "status": account.status.value,
            "historical_risk_score": rp.historical_risk_score,
            "transaction_count": rp.transaction_count,
            "fraud_count": rp.fraud_count,
            "fraud_rate": rp.fraud_rate,
            "is_high_risk": rp.is_high_risk_account,
            "last_risk_update": rp.last_risk_update.isoformat(),
        }

    async def check_geolocation_risk(self, country_code: str) -> Dict[str, Any]:
        """Tool 4 : risque géographique d'un pays (heuristique listes)."""
        logger.debug("tool.check_geolocation_risk(%s)", country_code)
        code = (country_code or "").upper().strip()
        if not code:
            return {"error": "country_code vide"}
        if code in HIGH_RISK_COUNTRIES:
            return {
                "country_code": code,
                "risk_score": HIGH_RISK_COUNTRIES[code],
                "risk_label": "HIGH",
                "reason": "Pays sous sanctions ou à très haut risque géopolitique.",
            }
        if code in MEDIUM_RISK_COUNTRIES:
            return {
                "country_code": code,
                "risk_score": MEDIUM_RISK_COUNTRIES[code],
                "risk_label": "MEDIUM",
                "reason": "Pays avec surveillance accrue.",
            }
        return {
            "country_code": code,
            "risk_score": 0.1,
            "risk_label": "LOW",
            "reason": "Pays sans signal particulier.",
        }

    async def analyze_merchant(
        self, merchant_id: str, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool 5 : risque d'un commerçant via catégorie."""
        logger.debug("tool.analyze_merchant(%s, %s)", merchant_id, category)
        signals = []
        score = 0.1  # base

        if category:
            cat = category.lower().strip()
            if cat in HIGH_RISK_CATEGORIES:
                score = max(score, HIGH_RISK_CATEGORIES[cat])
                signals.append(f"Catégorie à risque : {cat}")

        if not merchant_id or len(merchant_id) < 4:
            score = max(score, 0.5)
            signals.append("Identifiant commerçant inhabituel/manquant.")

        return {
            "merchant_id": merchant_id,
            "category": category,
            "risk_score": score,
            "risk_label": _label_for_score(score),
            "signals": signals,
        }

    async def get_fraud_rules_triggered(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 6 : règles de fraude déclenchées par la transaction."""
        logger.debug("tool.get_fraud_rules_triggered(%s)", transaction_id)
        txn = await self.transaction_repo.find_by_id(transaction_id)
        if txn is None:
            return {"error": f"Transaction {transaction_id} introuvable"}

        indicator = self.fraud_strategy.detect_fraud(txn)
        triggered = [
            rid for rid in indicator.reason.replace("Rules triggered: ", "").split(", ")
            if rid and rid != "No fraud rules triggered"
        ] if indicator.reason else []

        return {
            "transaction_id": transaction_id,
            "is_fraud": indicator.is_fraud,
            "risk_score": indicator.risk_score,
            "reason": indicator.reason,
            "rules_triggered": triggered,
        }

    # -------- Dispatcher --------

    async def dispatch(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route un appel de tool (par nom) vers la méthode correspondante."""
        handler = getattr(self, name, None)
        if handler is None or name not in _TOOL_NAMES:
            return {"error": f"Tool inconnu : {name}"}
        try:
            return await handler(**arguments)
        except TypeError as e:
            return {"error": f"Arguments invalides pour {name} : {e}"}

    # -------- Helpers --------

    @staticmethod
    def _transaction_to_dict(txn: Transaction) -> Dict[str, Any]:
        return {
            "id": txn.id,
            "account_id": txn.account_id,
            "amount": float(txn.amount.amount),
            "currency": txn.amount.currency,
            "merchant_id": txn.merchant_id,
            "merchant_name": txn.merchant_name,
            "merchant_category": txn.merchant_category,
            "merchant_country": txn.merchant_country,
            "transaction_country": txn.transaction_country,
            "timestamp": txn.timestamp.isoformat(),
            "status": txn.status.value,
            "is_fraud": txn.is_fraud,
            "risk_score": txn.risk_score,
            "fraud_reason": (
                txn.fraud_indicator.reason if txn.fraud_indicator else None
            ),
        }


_TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}


def _label_for_score(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"
