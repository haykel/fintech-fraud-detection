import asyncio
import json
import logging
from typing import Callable, Optional
from aiokafka import AIOKafkaConsumer
from domain.common import DomainEvent

logger = logging.getLogger(__name__)


class KafkaConsumerWorker:
    """
    Worker base pour consommer les messages Kafka
    
    Gère la connexion, la consommation, et le traitement des messages
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topics: list = None,
        group_id: str = "fintech-workers",
        message_handler: Optional[Callable] = None,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics or []
        self.group_id = group_id
        self.message_handler = message_handler
        self.consumer = None
        self.running = False
    
    async def start(self) -> None:
        """Démarre le consumer"""
        try:
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
            )
            
            await self.consumer.start()
            self.running = True
            logger.info(f"Kafka consumer started for topics: {self.topics}")
            
            # Commencer à consommer les messages
            await self._consume_messages()
        
        except Exception as e:
            logger.error(f"Error starting Kafka consumer: {e}")
            raise
    
    async def stop(self) -> None:
        """Arrête le consumer"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")
    
    async def _consume_messages(self) -> None:
        """Boucle de consommation des messages"""
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    # Traiter le message
                    await self._process_message(message)
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Envoyer en DLQ (Dead Letter Queue) si besoin
                    await self._send_to_dlq(message, str(e))
        
        except Exception as e:
            logger.error(f"Error in message consumption loop: {e}")
    
    async def _process_message(self, message) -> None:
        """Traite un message"""
        if self.message_handler:
            await self.message_handler(message.value)
        else:
            logger.warning(f"No message handler defined for topic {message.topic}")
    
    async def _send_to_dlq(self, message, error: str) -> None:
        """Envoie un message échoué à la Dead Letter Queue"""
        logger.error(f"Sending message to DLQ: {error}")
        # TODO: Implémenter l'envoi en DLQ
        pass


# ==================== Event Consumers ====================

class TransactionEventConsumer(KafkaConsumerWorker):
    """Consumer pour les événements de transactions"""
    
    def __init__(self):
        super().__init__(
            topics=["transactions.created", "transactions.approved", "transactions.rejected"],
            group_id="fintech-transaction-consumer",
            message_handler=self.handle_transaction_event,
        )
    
    async def handle_transaction_event(self, event_data: dict) -> None:
        """Traite un événement de transaction"""
        event_type = event_data.get("event_type")
        
        logger.info(f"Processing transaction event: {event_type}")
        
        if event_type == "TransactionCreatedEvent":
            await self._handle_transaction_created(event_data)
        elif event_type == "TransactionApprovedEvent":
            await self._handle_transaction_approved(event_data)
        elif event_type == "TransactionRejectedEvent":
            await self._handle_transaction_rejected(event_data)
    
    async def _handle_transaction_created(self, event_data: dict) -> None:
        """Traite une transaction créée"""
        transaction_id = event_data.get("aggregate_id")
        logger.info(f"Transaction created: {transaction_id}")
        # TODO: Logique supplémentaire si besoin
    
    async def _handle_transaction_approved(self, event_data: dict) -> None:
        """Traite une transaction approuvée"""
        transaction_id = event_data.get("aggregate_id")
        logger.info(f"Transaction approved: {transaction_id}")
        # TODO: Logique supplémentaire si besoin
    
    async def _handle_transaction_rejected(self, event_data: dict) -> None:
        """Traite une transaction rejetée"""
        transaction_id = event_data.get("aggregate_id")
        logger.info(f"Transaction rejected: {transaction_id}")
        # TODO: Logique supplémentaire si besoin


class FraudDetectionConsumer(KafkaConsumerWorker):
    """Consumer pour les événements de fraude"""
    
    def __init__(self):
        super().__init__(
            topics=["fraud.detected"],
            group_id="fintech-fraud-consumer",
            message_handler=self.handle_fraud_event,
        )
    
    async def handle_fraud_event(self, event_data: dict) -> None:
        """Traite un événement de fraude"""
        event_type = event_data.get("event_type")
        
        logger.info(f"Processing fraud event: {event_type}")
        
        if event_type == "FraudDetectedEvent":
            await self._handle_fraud_detected(event_data)
    
    async def _handle_fraud_detected(self, event_data: dict) -> None:
        """Traite une fraude détectée"""
        transaction_id = event_data.get("aggregate_id")
        risk_score = event_data.get("data", {}).get("risk_score")
        reason = event_data.get("data", {}).get("reason")
        
        logger.warning(
            f"Fraud detected - Transaction: {transaction_id}, "
            f"Risk: {risk_score}, Reason: {reason}"
        )
        
        # TODO: Appeler Mistral pour explication
        # TODO: Envoyer alertes si besoin
        # TODO: Mettre à jour les métriques


class SearchIndexingConsumer(KafkaConsumerWorker):
    """Consumer pour indexer les transactions dans OpenSearch"""
    
    def __init__(self):
        super().__init__(
            topics=["transactions.created", "fraud.detected"],
            group_id="fintech-search-indexing-consumer",
            message_handler=self.handle_indexing_event,
        )
    
    async def handle_indexing_event(self, event_data: dict) -> None:
        """Indexe un événement dans OpenSearch"""
        event_type = event_data.get("event_type")
        aggregate_id = event_data.get("aggregate_id")
        
        logger.info(f"Indexing event: {event_type} for {aggregate_id}")
        
        # TODO: Indexer dans OpenSearch
        # await self.opensearch_adapter.index_transaction(event_data)