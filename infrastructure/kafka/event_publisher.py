from aiokafka import AIOKafkaProducer
import json
import os
import logging
from domain.common import DomainEvent

logger = logging.getLogger(__name__)


class KafkaEventPublisher:
    """Event Publisher pour Kafka"""
    
    def __init__(self):
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:29092"
        )
        self.producer = None
    
    async def connect(self):
        """Connecte au broker Kafka"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            )
            await self.producer.start()
            logger.info("Connected to Kafka")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    async def disconnect(self):
        """Déconnecte de Kafka"""
        if self.producer:
            await self.producer.stop()
    
    async def publish(self, event: DomainEvent) -> None:
        """Publie un événement"""
        try:
            if not self.producer:
                await self.connect()
            
            # Déterminer le topic
            topic = f"{event.aggregate_type.lower()}.{event.event_type}"
            
            # Sérialiser l'événement
            message = event.to_dict()
            
            # Publier
            await self.producer.send_and_wait(topic, message)
            
            logger.info(f"Event published: {event.event_type} to topic {topic}")
        
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            raise
    
    async def publish_many(self, events: list) -> None:
        """Publie plusieurs événements"""
        for event in events:
            await self.publish(event)


# Singleton instance
_publisher_instance = None


async def get_event_publisher() -> KafkaEventPublisher:
    """Récupère l'instance du publisher (singleton)"""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = KafkaEventPublisher()
        await _publisher_instance.connect()
    return _publisher_instance