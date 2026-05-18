"""Agent LLM pour la détection de fraude (provider-agnostique).

Utilise le SDK `openai` (AsyncOpenAI) pour parler à n'importe quel endpoint
compatible OpenAI : Mistral cloud, Ollama local, vLLM, LM Studio, etc.

Configuration via variables d'environnement :
    LLM_BASE_URL  ex: http://localhost:11434/v1 (Ollama)
                  ex: https://api.mistral.ai/v1 (Mistral cloud)
    LLM_API_KEY   clé du provider (placeholder accepté par Ollama : "ollama")
    LLM_MODEL     nom du modèle exposé par le provider
                  ex: "mistral:latest" (Ollama), "mistral-small-latest" (cloud)
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from infrastructure.mistral.prompts import (
    ANALYZE_FRAUD_TRANSACTION_PROMPT,
    GENERATE_ACCOUNT_RISK_REPORT_PROMPT,
    SYSTEM_PROMPT_FRAUD_ANALYST,
)
from infrastructure.mistral.tools import TOOL_SCHEMAS, FraudAnalysisTools

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", "ollama")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "mistral:latest")
AGENT_TIMEOUT = float(os.getenv("LLM_AGENT_TIMEOUT", "300"))
TOOL_TIMEOUT = float(os.getenv("LLM_TOOL_TIMEOUT", "5"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
MAX_ITERATIONS = int(os.getenv("LLM_MAX_ITERATIONS", "8"))


class MistralAgentError(Exception):
    """Erreur de haut niveau de l'agent (timeout, max iterations, etc.)."""


class MistralAgent:
    """Agent LLM avec tool calling pour l'analyse de fraude.

    Le nom est conservé pour rétro-compat, mais le client est désormais
    OpenAI-compatible et peut viser n'importe quel backend.

    Usage minimal :
        tools = FraudAnalysisTools(transaction_repo=..., account_repo=...)
        agent = MistralAgent(tools=tools)
        result = await agent.analyze_fraud("txn-uuid")
    """

    def __init__(
        self,
        tools: FraudAnalysisTools,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = base_url or DEFAULT_BASE_URL
        self.api_key = api_key or DEFAULT_API_KEY
        self.model = model or DEFAULT_MODEL
        self.tools = tools
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info(
            "LLM agent ready provider_url=%s model=%s",
            self.base_url,
            self.model,
        )

    # ==================== Entry points ====================

    async def analyze_fraud(self, transaction_id: str) -> Dict[str, Any]:
        """Analyse complète d'une transaction suspecte.

        Retourne un dict conforme au schéma de réponse défini dans le system prompt
        (risk_level, risk_score, analysis, factors, recommendation, confidence).
        """
        logger.info("analyze_fraud start transaction_id=%s", transaction_id)
        prompt = ANALYZE_FRAUD_TRANSACTION_PROMPT.format(transaction_id=transaction_id)
        messages = self._initial_messages(prompt)

        try:
            content = await asyncio.wait_for(
                self._run_agent_loop(messages),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError as e:
            logger.error(
                "analyze_fraud timeout (%ss) transaction_id=%s",
                AGENT_TIMEOUT,
                transaction_id,
            )
            raise MistralAgentError(
                f"Agent timeout après {AGENT_TIMEOUT}s pour transaction {transaction_id}"
            ) from e

        parsed = self._parse_final_response(content)
        logger.info(
            "analyze_fraud done transaction_id=%s risk_level=%s recommendation=%s",
            transaction_id,
            parsed.get("risk_level"),
            parsed.get("recommendation"),
        )
        return parsed

    async def generate_account_report(self, account_id: str) -> Dict[str, Any]:
        """Génère un rapport de risque global pour un compte."""
        logger.info("generate_account_report start account_id=%s", account_id)
        prompt = GENERATE_ACCOUNT_RISK_REPORT_PROMPT.format(account_id=account_id)
        messages = self._initial_messages(prompt)

        try:
            content = await asyncio.wait_for(
                self._run_agent_loop(messages),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError as e:
            raise MistralAgentError(
                f"Agent timeout après {AGENT_TIMEOUT}s pour compte {account_id}"
            ) from e

        parsed = self._parse_final_response(content)
        logger.info(
            "generate_account_report done account_id=%s risk_level=%s",
            account_id,
            parsed.get("risk_level"),
        )
        return parsed

    # ==================== Agent loop ====================

    async def _run_agent_loop(self, messages: List[Dict[str, Any]]) -> str:
        """Boucle agent : tant que le modèle veut appeler des tools, exécute-les
        et renvoie les résultats. Sort dès qu'il produit un message sans tool_calls.
        """
        for iteration in range(MAX_ITERATIONS):
            logger.debug("agent_loop iteration=%s n_messages=%s", iteration, len(messages))
            response = await self._call_llm_with_retry(messages)
            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None) or []

            if not tool_calls:
                content = msg.content or ""
                if isinstance(content, list):
                    content = "".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                return content

            messages.append(self._assistant_message_with_tools(msg, tool_calls))

            for tc in tool_calls:
                tool_name = tc.function.name
                raw_args = tc.function.arguments
                args = _safe_json_loads(raw_args)
                logger.info("agent_loop tool_call name=%s args=%s", tool_name, args)

                try:
                    result = await asyncio.wait_for(
                        self.tools.dispatch(tool_name, args),
                        timeout=TOOL_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("tool timeout name=%s", tool_name)
                    result = {"error": f"Tool {tool_name} a dépassé {TOOL_TIMEOUT}s"}
                except Exception as e:
                    logger.exception("tool error name=%s", tool_name)
                    result = {"error": f"Tool {tool_name} a échoué : {e}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        raise MistralAgentError(
            f"Agent loop a dépassé {MAX_ITERATIONS} itérations sans conclure"
        )

    # ==================== LLM call w/ retry ====================

    async def _call_llm_with_retry(self, messages: List[Dict[str, Any]]):
        """Appelle chat.completions.create avec retry exponentiel."""
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )
            except Exception as e:
                last_exc = e
                wait = 2 ** attempt
                logger.warning(
                    "LLM call failed (attempt %s/%s): %s — retry in %ss",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                    wait,
                )
                if attempt == MAX_RETRIES - 1:
                    break
                await asyncio.sleep(wait)
        raise MistralAgentError(
            f"LLM API a échoué après {MAX_RETRIES} tentatives"
        ) from last_exc

    # ==================== Helpers ====================

    @staticmethod
    def _initial_messages(user_prompt: str) -> List[Dict[str, Any]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT_FRAUD_ANALYST},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _assistant_message_with_tools(msg, tool_calls) -> Dict[str, Any]:
        """Convertit la réponse SDK en dict compatible avec l'historique chat."""
        return {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                        if isinstance(tc.function.arguments, str)
                        else json.dumps(tc.function.arguments, ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ],
        }

    @staticmethod
    def _parse_final_response(content: str) -> Dict[str, Any]:
        """Parse la réponse finale en JSON. Tolère le markdown autour."""
        if not content:
            return _fallback_response("Réponse vide du modèle")

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return _fallback_response(content)


def _safe_json_loads(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Arguments de tool non parsables : %r", raw)
        return {}


def _fallback_response(content: str) -> Dict[str, Any]:
    """Réponse de secours si le modèle n'a pas produit de JSON exploitable."""
    return {
        "risk_level": "UNKNOWN",
        "risk_score": 0.0,
        "analysis": content[:1000] if isinstance(content, str) else str(content),
        "factors": {"high_risk": [], "low_risk": []},
        "recommendation": "REVIEW",
        "confidence": 0.0,
    }
