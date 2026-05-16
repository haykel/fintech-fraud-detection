import asyncio
import logging
import os
from typing import List

from interfaces.workers import (
    TransactionEventConsumer,
    FraudDetectionConsumer,
    SearchIndexingConsumer,
    FraudExplanationWorker,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_workers():
    """Lance tous les workers"""
    
    workers: List = [
        TransactionEventConsumer(),
        FraudDetectionConsumer(),
        SearchIndexingConsumer(),
        # FraudExplanationWorker(mistral_api_key=os.getenv("MISTRAL_API_KEY")),
    ]
    
    logger.info(f"Starting {len(workers)} workers...")
    
    try:
        # Démarrer tous les workers en parallèle
        tasks = [worker.start() for worker in workers]
        await asyncio.gather(*tasks)
    
    except KeyboardInterrupt:
        logger.info("Shutting down workers...")
        stop_tasks = [worker.stop() for worker in workers]
        await asyncio.gather(*stop_tasks)
    
    except Exception as e:
        logger.error(f"Error running workers: {e}")
        # Arrêter les workers en cas d'erreur
        stop_tasks = [worker.stop() for worker in workers]
        await asyncio.gather(*stop_tasks)


if __name__ == "__main__":
    asyncio.run(run_workers())