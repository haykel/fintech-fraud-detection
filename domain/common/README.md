# Domain - Common

Contient les éléments partagés et transversaux du domaine :

- **events.py** : Domain Events pour Event Sourcing
  - TransactionCreatedEvent
  - FraudDetectedEvent
  - AccountCreatedEvent
  - RiskScoreCalculatedEvent
  - etc.

- EventPublisher : Port interface pour publier les événements
- EventStore : Port interface pour stocker les événements