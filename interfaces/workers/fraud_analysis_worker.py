"""Worker Kafka qui consomme `fraud.detected` et déclenche l'agent Mistral.

Pour chaque événement :
    1. Récupère le transaction_id depuis l'événement.
    2. Lance MistralAgent.analyze_fraud(transaction_id).
    3. Publie un FraudExplainedEvent avec l'analyse sérialisée en JSON.
"""

import asyncio
import json
import logging
import os
from typing import Optional

from aiokafka import AIOKafkaConsumer

from domain.common import FraudExplainedEvent
from infrastructure.kafka.event_publisher import KafkaEventPublisher
from infrastructure.mistral import (
    AGENT_TIMEOUT,
    FraudAnalysisTools,
    MistralAgent,
    MistralAgentError,
)
from infrastructure.postgres.repositories import (
    PostgresAccountRepository,
    PostgresTransactionRepository,
)

logger = logging.getLogger(__name__)


class FraudAnalysisWorker:
    """Worker async : `fraud.detected` -> MistralAgent -> `FraudExplainedEvent`."""

    TOPIC = "fraud.detected"
    GROUP_ID = "fintech-fraud-analysis-worker"

    def __init__(
        self,
        agent: Optional[MistralAgent] = None,
        event_publisher: Optional[KafkaEventPublisher] = None,
        bootstrap_servers: Optional[str] = None,
    ):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
        )
        self.agent = agent or self._build_default_agent()
        self.event_publisher = event_publisher or KafkaEventPublisher()
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False

    @staticmethod
    def _build_default_agent() -> MistralAgent:
        return MistralAgent(
            tools=FraudAnalysisTools(
                transaction_repo=PostgresTransactionRepository(),
                account_repo=PostgresAccountRepository(),
            )
        )

    # ==================== Lifecycle ====================

    async def start(self) -> None:
        """Démarre le consumer Kafka et la boucle de consommation."""
        logger.info(
            "FraudAnalysisWorker starting topic=%s group=%s servers=%s",
            self.TOPIC,
            self.GROUP_ID,
            self.bootstrap_servers,
        )
        try:
            self.consumer = AIOKafkaConsumer(
                self.TOPIC,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.GROUP_ID,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await self.consumer.start()
            self.running = True
            logger.info("FraudAnalysisWorker started")
            await self._consume_loop()
        except Exception:
            logger.exception("FraudAnalysisWorker failed to start")
            raise

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("FraudAnalysisWorker stopped")

    # ==================== Consumption ====================

    async def _consume_loop(self) -> None:
        assert self.consumer is not None
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                try:
                    await self._process_event(message.value)
                except Exception:
                    logger.exception(
                        "Erreur lors du traitement d'un événement fraud.detected (offset=%s)",
                        message.offset,
                    )
        except Exception:
            logger.exception("Erreur dans la boucle de consommation")

    async def _process_event(self, event_data: dict) -> None:
        """Lance l'agent et publie le FraudExplainedEvent résultant."""
        event_type = event_data.get("event_type")
        if event_type != "FraudDetectedEvent":
            logger.debug("Ignored event_type=%s", event_type)
            return

        transaction_id = event_data.get("aggregate_id")
        if not transaction_id:
            logger.warning("FraudDetectedEvent sans aggregate_id : %s", event_data)
            return

        logger.info("Mistral analysis requested transaction_id=%s", transaction_id)

        try:
            analysis = await self.agent.analyze_fraud(transaction_id)
        except MistralAgentError as e:
            logger.error("MistralAgent failed transaction_id=%s err=%s", transaction_id, e)
            return
        except asyncio.TimeoutError:
            logger.error(
                "MistralAgent timeout (%ss) transaction_id=%s",
                AGENT_TIMEOUT,
                transaction_id,
            )
            return

        explanation_payload = json.dumps(analysis, ensure_ascii=False)

        explained_event = FraudExplainedEvent(
            aggregate_id=transaction_id,
            explanation=explanation_payload,
        )

        try:
            await self.event_publisher.publish(explained_event)
            logger.info(
                "FraudExplainedEvent published transaction_id=%s risk_level=%s",
                transaction_id,
                analysis.get("risk_level"),
            )
        except Exception:
            logger.exception(
                "Échec de publication de FraudExplainedEvent transaction_id=%s",
                transaction_id,
            )
