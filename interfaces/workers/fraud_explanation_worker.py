import asyncio
import json
import logging
from typing import Optional
from aiokafka import AIOKafkaConsumer
import httpx

logger = logging.getLogger(__name__)


class FraudExplanationWorker:
    """
    Worker pour générer les explications de fraude via Mistral
    
    Consomme les événements FraudDetected et appelle Mistral
    """
    
    def __init__(
        self,
        mistral_api_key: str,
        bootstrap_servers: str = "localhost:9092",
    ):
        self.mistral_api_key = mistral_api_key
        self.bootstrap_servers = bootstrap_servers
        self.consumer = None
        self.running = False
        self.mistral_client = httpx.AsyncClient()
    
    async def start(self) -> None:
        """Démarre le worker"""
        try:
            self.consumer = AIOKafkaConsumer(
                "fraud.detected",
                bootstrap_servers=self.bootstrap_servers,
                group_id="fintech-fraud-explanation-worker",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            )
            
            await self.consumer.start()
            self.running = True
            logger.info("Fraud explanation worker started")
            
            await self._consume_messages()
        
        except Exception as e:
            logger.error(f"Error starting fraud explanation worker: {e}")
            raise
    
    async def stop(self) -> None:
        """Arrête le worker"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        await self.mistral_client.aclose()
        logger.info("Fraud explanation worker stopped")
    
    async def _consume_messages(self) -> None:
        """Boucle de consommation"""
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    await self._process_fraud_event(message.value)
                except Exception as e:
                    logger.error(f"Error processing fraud event: {e}")
        
        except Exception as e:
            logger.error(f"Error in consumption loop: {e}")
    
    async def _process_fraud_event(self, event_data: dict) -> None:
        """Traite un événement de fraude et appelle Mistral"""
        transaction_id = event_data.get("aggregate_id")
        risk_score = event_data.get("data", {}).get("risk_score")
        reason = event_data.get("data", {}).get("reason")
        
        logger.info(f"Generating explanation for fraud: {transaction_id}")
        
        # Construire le prompt pour Mistral
        prompt = self._build_explanation_prompt(transaction_id, risk_score, reason)
        
        # Appeler Mistral
        explanation = await self._call_mistral(prompt)
        
        if explanation:
            logger.info(f"Generated explanation: {explanation[:100]}...")
            # TODO: Sauvegarder l'explication dans la DB
            # TODO: Publier un FraudExplainedEvent
        else:
            logger.warning(f"Failed to generate explanation for {transaction_id}")
    
    def _build_explanation_prompt(
        self,
        transaction_id: str,
        risk_score: float,
        reason: str
    ) -> str:
        """Construit le prompt pour Mistral"""
        return f"""
        Générez une explication courte et claire pour une fraude détectée.
        
        Transaction ID: {transaction_id}
        Risk Score: {risk_score}/1.0
        Raison détectée: {reason}
        
        Expliquez en langage naturel pourquoi cette transaction a été marquée comme fraude.
        Soyez concis (max 150 caractères).
        """
    
    async def _call_mistral(self, prompt: str) -> Optional[str]:
        """Appelle l'API Mistral"""
        try:
            response = await self.mistral_client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.mistral_api_key}",
                },
                json={
                    "model": "mistral-small",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 200,
                },
                timeout=10.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                return content
            else:
                logger.error(f"Mistral API error: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error calling Mistral: {e}")
            return None