from domain.common import DomainEvent


class KafkaEventPublisher:
    """
    Event Publisher adapter pour Kafka
    """
    
    def __init__(self):
        # Kafka producer à initialiser
        self.producer = None
    
    async def publish(self, event: DomainEvent) -> None:
        """Publishes a domain event to Kafka"""
        # TODO: Implémenter avec aiokafka
        topic = f"{event.aggregate_type.lower()}.{event.event_type}"
        message = event.to_json()
        # producer.send(topic, message)
        pass