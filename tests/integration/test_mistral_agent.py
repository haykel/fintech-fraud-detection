"""Tests d'intégration de l'agent Mistral, des tools, du worker et des routes.

Tous les appels externes (Mistral API, Postgres, Kafka, Redis) sont mockés —
ces tests valident la logique de l'agent loop et du câblage, pas l'infra.
"""

import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from domain.account import Account, AccountStatus, RiskProfile
from domain.transaction import Money, Transaction, TransactionStatus
from infrastructure.mistral.agent import MistralAgent, MistralAgentError
from infrastructure.mistral.tools import (
    HIGH_RISK_CATEGORIES,
    HIGH_RISK_COUNTRIES,
    TOOL_SCHEMAS,
    FraudAnalysisTools,
)


# ==================== Helpers / Fixtures ====================


def _make_transaction(**overrides) -> Transaction:
    defaults = dict(
        id="txn-1",
        account_id="acc-1",
        amount=Money(Decimal("1200.00"), "EUR"),
        merchant_id="merchant-42",
        merchant_name="Crypto Exchange",
        merchant_category="crypto",
        merchant_country="KP",
        transaction_country="KP",
        timestamp=datetime(2026, 5, 1, 3, 30),
        status=TransactionStatus.BLOCKED,
    )
    defaults.update(overrides)
    return Transaction(**defaults)


def _make_account(**overrides) -> Account:
    defaults = dict(
        id="acc-1",
        holder_name="Jane Doe",
        email="jane@example.com",
        status=AccountStatus.ACTIVE,
        risk_profile=RiskProfile(
            historical_risk_score=0.75,
            transaction_count=120,
            fraud_count=6,
            last_risk_update=datetime(2026, 5, 1),
        ),
    )
    defaults.update(overrides)
    return Account(**defaults)


@pytest.fixture
def repos():
    """Repositories mockés (find_by_id, find_by_account_id, save)."""
    txn = _make_transaction()
    account = _make_account()

    txn_repo = MagicMock()
    txn_repo.find_by_id = AsyncMock(return_value=txn)
    txn_repo.find_by_account_id = AsyncMock(return_value=[txn])
    txn_repo.save = AsyncMock(return_value=None)

    account_repo = MagicMock()
    account_repo.find_by_id = AsyncMock(return_value=account)
    account_repo.save = AsyncMock(return_value=None)

    return SimpleNamespace(txn=txn_repo, account=account_repo, txn_obj=txn, account_obj=account)


@pytest.fixture
def tools(repos):
    return FraudAnalysisTools(
        transaction_repo=repos.txn,
        account_repo=repos.account,
    )


# ==================== Tools : tests unitaires ====================


@pytest.mark.asyncio
async def test_tool_get_transaction_details(tools, repos):
    result = await tools.get_transaction_details("txn-1")
    assert result["id"] == "txn-1"
    assert result["amount"] == 1200.0
    assert result["currency"] == "EUR"
    assert result["merchant_category"] == "crypto"
    repos.txn.find_by_id.assert_awaited_once_with("txn-1")


@pytest.mark.asyncio
async def test_tool_get_transaction_details_not_found(tools, repos):
    repos.txn.find_by_id = AsyncMock(return_value=None)
    tools.transaction_repo = repos.txn
    result = await tools.get_transaction_details("unknown")
    assert "error" in result


@pytest.mark.asyncio
async def test_tool_get_account_history(tools, repos):
    result = await tools.get_account_history("acc-1", limit=5)
    assert result["account_id"] == "acc-1"
    assert result["count"] == 1
    assert len(result["transactions"]) == 1


@pytest.mark.asyncio
async def test_tool_get_account_risk_profile(tools):
    result = await tools.get_account_risk_profile("acc-1")
    assert result["account_id"] == "acc-1"
    assert result["historical_risk_score"] == 0.75
    assert result["fraud_count"] == 6
    assert result["is_high_risk"] is True


@pytest.mark.asyncio
async def test_tool_check_geolocation_risk_high(tools):
    result = await tools.check_geolocation_risk("KP")
    assert result["risk_label"] == "HIGH"
    assert result["risk_score"] == HIGH_RISK_COUNTRIES["KP"]


@pytest.mark.asyncio
async def test_tool_check_geolocation_risk_low(tools):
    result = await tools.check_geolocation_risk("FR")
    assert result["risk_label"] == "LOW"
    assert result["risk_score"] < 0.3


@pytest.mark.asyncio
async def test_tool_analyze_merchant_high_risk_category(tools):
    result = await tools.analyze_merchant("merchant-42", category="crypto")
    assert result["risk_score"] >= HIGH_RISK_CATEGORIES["crypto"]
    assert any("crypto" in s.lower() for s in result["signals"])


@pytest.mark.asyncio
async def test_tool_analyze_merchant_unknown_category(tools):
    result = await tools.analyze_merchant("merchant-42", category="retail")
    assert result["risk_label"] in {"LOW", "MEDIUM"}


@pytest.mark.asyncio
async def test_tool_get_fraud_rules_triggered(tools):
    result = await tools.get_fraud_rules_triggered("txn-1")
    # Transaction est crypto + KP + 1200 EUR : aucune règle "high_amount" mais
    # rule_unusual_merchant et rule_geolocation se déclenchent.
    assert result["transaction_id"] == "txn-1"
    assert isinstance(result["rules_triggered"], list)
    assert result["risk_score"] > 0


@pytest.mark.asyncio
async def test_tools_dispatch_routes(tools):
    result = await tools.dispatch("get_transaction_details", {"transaction_id": "txn-1"})
    assert result["id"] == "txn-1"


@pytest.mark.asyncio
async def test_tools_dispatch_unknown_tool(tools):
    result = await tools.dispatch("nonexistent_tool", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_tools_dispatch_invalid_arguments(tools):
    result = await tools.dispatch("check_geolocation_risk", {"wrong_arg": "x"})
    assert "error" in result


def test_tool_schemas_match_implementation(tools):
    """Les noms déclarés dans TOOL_SCHEMAS doivent tous être des méthodes."""
    for schema in TOOL_SCHEMAS:
        name = schema["function"]["name"]
        assert callable(getattr(tools, name, None)), f"Tool '{name}' manquant"


# ==================== Agent loop ====================


def _mistral_response(content="", tool_calls=None):
    """Construit un objet imitant la réponse de mistralai.client.chat.complete_async."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


@pytest.mark.asyncio
async def test_agent_analyze_fraud_full_loop(tools, monkeypatch):
    """L'agent doit appeler un tool, intégrer son résultat, puis produire la
    réponse JSON finale, qui est parsée correctement.
    """
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    final_json = {
        "risk_level": "HIGH",
        "risk_score": 0.92,
        "analysis": "Transaction crypto depuis pays sous sanctions.",
        "factors": {
            "high_risk": ["Pays KP", "Catégorie crypto"],
            "low_risk": [],
        },
        "recommendation": "FREEZE_ACCOUNT",
        "confidence": 0.95,
    }

    responses = [
        _mistral_response(tool_calls=[_tool_call("call_1", "get_transaction_details", {"transaction_id": "txn-1"})]),
        _mistral_response(content=json.dumps(final_json)),
    ]

    with patch("infrastructure.mistral.agent.AsyncOpenAI") as OpenAIClass:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=responses)
        OpenAIClass.return_value = client

        agent = MistralAgent(tools=tools, api_key="test-key")
        result = await agent.analyze_fraud("txn-1")

    assert result["risk_level"] == "HIGH"
    assert result["recommendation"] == "FREEZE_ACCOUNT"
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_agent_parses_json_inside_markdown(tools, monkeypatch):
    """Le parser doit extraire le JSON même s'il est entouré de texte/markdown."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    wrapped = (
        "Voici mon analyse :\n```json\n"
        '{"risk_level":"LOW","risk_score":0.1,"analysis":"ok","factors":'
        '{"high_risk":[],"low_risk":[]},"recommendation":"APPROVE","confidence":0.8}\n'
        "```"
    )
    response = _mistral_response(content=wrapped)

    with patch("infrastructure.mistral.agent.AsyncOpenAI") as OpenAIClass:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=response)
        OpenAIClass.return_value = client

        agent = MistralAgent(tools=tools, api_key="test-key")
        result = await agent.analyze_fraud("txn-1")

    assert result["risk_level"] == "LOW"
    assert result["recommendation"] == "APPROVE"


@pytest.mark.asyncio
async def test_agent_retries_on_transient_failure(tools, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    # Pour éviter d'attendre les sleeps réels du backoff (1+2+4 = 7s)
    with patch("infrastructure.mistral.agent.asyncio.sleep", new=AsyncMock()):
        with patch("infrastructure.mistral.agent.AsyncOpenAI") as OpenAIClass:
            client = MagicMock()
            client.chat.completions.create = AsyncMock(
                side_effect=[
                    RuntimeError("transient 1"),
                    RuntimeError("transient 2"),
                    _mistral_response(content='{"risk_level":"LOW","risk_score":0.1,"analysis":"x","factors":{"high_risk":[],"low_risk":[]},"recommendation":"APPROVE","confidence":0.9}'),
                ]
            )
            OpenAIClass.return_value = client

            agent = MistralAgent(tools=tools, api_key="test-key")
            result = await agent.analyze_fraud("txn-1")

    assert result["risk_level"] == "LOW"
    assert client.chat.completions.create.await_count == 3


@pytest.mark.asyncio
async def test_agent_raises_after_max_retries(tools, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    with patch("infrastructure.mistral.agent.asyncio.sleep", new=AsyncMock()):
        with patch("infrastructure.mistral.agent.AsyncOpenAI") as OpenAIClass:
            client = MagicMock()
            client.chat.completions.create = AsyncMock(side_effect=RuntimeError("nope"))
            OpenAIClass.return_value = client

            agent = MistralAgent(tools=tools, api_key="test-key")
            with pytest.raises(MistralAgentError):
                await agent.analyze_fraud("txn-1")


@pytest.mark.asyncio
async def test_agent_picks_up_env_config(tools, monkeypatch):
    """L'agent doit utiliser LLM_BASE_URL / LLM_MODEL passés explicitement."""
    with patch("infrastructure.mistral.agent.AsyncOpenAI") as OpenAIClass:
        OpenAIClass.return_value = MagicMock()
        agent = MistralAgent(
            tools=tools,
            api_key="custom-key",
            base_url="http://custom-host:1234/v1",
            model="mistral-large-latest",
        )
        assert agent.base_url == "http://custom-host:1234/v1"
        assert agent.model == "mistral-large-latest"
        OpenAIClass.assert_called_once_with(
            api_key="custom-key",
            base_url="http://custom-host:1234/v1",
        )


# ==================== Worker ====================


@pytest.mark.asyncio
async def test_fraud_analysis_worker_publishes_explained_event():
    from interfaces.workers.fraud_analysis_worker import FraudAnalysisWorker

    agent = MagicMock()
    agent.analyze_fraud = AsyncMock(
        return_value={
            "risk_level": "HIGH",
            "risk_score": 0.9,
            "analysis": "fraud probable",
            "factors": {"high_risk": ["x"], "low_risk": []},
            "recommendation": "BLOCK_TRANSACTION",
            "confidence": 0.9,
        }
    )

    publisher = MagicMock()
    publisher.publish = AsyncMock(return_value=None)

    worker = FraudAnalysisWorker(agent=agent, event_publisher=publisher)
    await worker._process_event({
        "event_type": "FraudDetectedEvent",
        "aggregate_id": "txn-99",
        "data": {"risk_score": 0.9, "reason": "rule_geolocation"},
    })

    agent.analyze_fraud.assert_awaited_once_with("txn-99")
    publisher.publish.assert_awaited_once()
    published_event = publisher.publish.call_args.args[0]
    assert published_event.aggregate_id == "txn-99"
    parsed = json.loads(published_event.explanation)
    assert parsed["risk_level"] == "HIGH"


@pytest.mark.asyncio
async def test_fraud_analysis_worker_ignores_non_fraud_events():
    from interfaces.workers.fraud_analysis_worker import FraudAnalysisWorker

    agent = MagicMock()
    agent.analyze_fraud = AsyncMock()
    publisher = MagicMock()
    publisher.publish = AsyncMock()

    worker = FraudAnalysisWorker(agent=agent, event_publisher=publisher)
    await worker._process_event({"event_type": "TransactionApprovedEvent", "aggregate_id": "txn-x"})

    agent.analyze_fraud.assert_not_awaited()
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_fraud_analysis_worker_swallows_agent_errors():
    """Une erreur de l'agent ne doit pas faire tomber le worker."""
    from interfaces.workers.fraud_analysis_worker import FraudAnalysisWorker

    agent = MagicMock()
    agent.analyze_fraud = AsyncMock(side_effect=MistralAgentError("boom"))
    publisher = MagicMock()
    publisher.publish = AsyncMock()

    worker = FraudAnalysisWorker(agent=agent, event_publisher=publisher)
    # Ne doit pas lever
    await worker._process_event({"event_type": "FraudDetectedEvent", "aggregate_id": "txn-err"})
    publisher.publish.assert_not_awaited()


# ==================== API endpoints ====================


@pytest.fixture
def api_client(monkeypatch):
    """TestClient FastAPI avec dépendances mockées."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    from interfaces.api.main import app
    from interfaces.api.routes import explanations as expl_module

    agent = MagicMock()
    agent.analyze_fraud = AsyncMock(return_value={
        "risk_level": "MEDIUM",
        "risk_score": 0.55,
        "analysis": "analysis text",
        "factors": {"high_risk": [], "low_risk": []},
        "recommendation": "REVIEW",
        "confidence": 0.7,
    })
    agent.generate_account_report = AsyncMock(return_value={
        "risk_level": "HIGH",
        "risk_score": 0.8,
        "analysis": "report text",
        "factors": {"high_risk": [], "low_risk": []},
        "recommendation": "FREEZE_ACCOUNT",
        "confidence": 0.85,
    })

    cache_store: dict = {}

    class FakeCache:
        async def get(self, key):
            return cache_store.get(key)

        async def set(self, key, value, ttl=None):
            cache_store[key] = value

        async def delete(self, key):
            cache_store.pop(key, None)

    cache = FakeCache()

    app.include_router(expl_module.router, prefix="/api", tags=["explanations"])
    app.dependency_overrides[expl_module.get_agent] = lambda: agent
    app.dependency_overrides[expl_module.get_cache] = lambda: cache

    client = TestClient(app)
    yield client, cache_store, agent

    app.dependency_overrides.clear()


def test_post_analyze_returns_202_and_runs_background(api_client):
    client, cache_store, agent = api_client

    resp = client.post("/api/transactions/txn-77/analyze")
    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] == "txn-77"
    assert body["status"] == "accepted"
    # BackgroundTasks de FastAPI s'exécute après la réponse — avec TestClient,
    # ça tourne synchroniquement avant le retour du client.
    agent.analyze_fraud.assert_awaited_once_with("txn-77")
    cached = json.loads(cache_store["fraud_explanation:txn-77"])
    assert cached["status"] == "completed"
    assert cached["result"]["risk_level"] == "MEDIUM"


def test_get_explanation_404_when_missing(api_client):
    client, *_ = api_client
    resp = client.get("/api/transactions/unknown/explanation")
    assert resp.status_code == 404


def test_get_explanation_returns_completed_result(api_client):
    client, cache_store, agent = api_client

    client.post("/api/transactions/txn-88/analyze")
    resp = client.get("/api/transactions/txn-88/explanation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["recommendation"] == "REVIEW"


def test_post_generate_account_report(api_client):
    client, cache_store, agent = api_client

    resp = client.post("/api/accounts/acc-7/generate-report")
    assert resp.status_code == 202
    assert resp.json()["job_id"] == "acc-7"
    agent.generate_account_report.assert_awaited_once_with("acc-7")
    cached = json.loads(cache_store["account_report:acc-7"])
    assert cached["status"] == "completed"
    assert cached["result"]["risk_level"] == "HIGH"
