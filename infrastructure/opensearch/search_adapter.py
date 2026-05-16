from opensearchpy import OpenSearch
import os
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenSearchAdapter:
    """Search adapter pour OpenSearch"""
    
    def __init__(self):
        self.host = os.getenv("OPENSEARCH_HOST", "localhost")
        self.port = int(os.getenv("OPENSEARCH_PORT", 9200))
        self.client = None
    
    async def connect(self):
        """Connecte à OpenSearch"""
        try:
            self.client = OpenSearch(
                hosts=[{'host': self.host, 'port': self.port}],
                http_auth=('admin', 'AdminPass123!'),
                use_ssl=False,
                verify_certs=False,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
            )
            
            # Test la connexion
            info = self.client.info()
            logger.info("Connected to OpenSearch")
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            raise
    
    async def search_transactions(
        self,
        criteria: Dict[str, Any],
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "timestamp",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Recherche les transactions"""
        try:
            if not self.client:
                await self.connect()
            
            # Construire la requête
            query = {"bool": {"must": []}}
            
            if "account_id" in criteria:
                query["bool"]["must"].append({
                    "match": {"account_id": criteria["account_id"]}
                })
            
            if "is_fraud" in criteria:
                query["bool"]["must"].append({
                    "match": {"is_fraud": criteria["is_fraud"]}
                })
            
            if "status" in criteria:
                query["bool"]["must"].append({
                    "match": {"status": criteria["status"]}
                })
            
            # Requête
            search_body = {
                "query": query if query["bool"]["must"] else {"match_all": {}},
                "sort": [{sort_by: {"order": sort_order}}],
                "from": offset,
                "size": limit,
            }
            
            # Exécuter
            index_name = f"transactions-{datetime.now().strftime('%Y.%m.%d')}"
            
            try:
                response = self.client.search(
                    body=search_body,
                    index=index_name
                )
            except:
                # Si l'index n'existe pas, retourner vide
                return {"transactions": [], "total": 0}
            
            # Parser les résultats
            hits = response.get("hits", {})
            total = hits.get("total", {}).get("value", 0)
            transactions = [hit["_source"] for hit in hits.get("hits", [])]
            
            return {
                "transactions": transactions,
                "total": total,
            }
        
        except Exception as e:
            logger.error(f"Error searching transactions: {e}")
            return {"transactions": [], "total": 0}
    
    async def index_transaction(self, transaction_data: Dict[str, Any]) -> bool:
        """Indexe une transaction"""
        try:
            if not self.client:
                await self.connect()
            
            index_name = f"transactions-{datetime.now().strftime('%Y.%m.%d')}"
            transaction_id = transaction_data.get("id")
            
            # Créer l'index s'il n'existe pas
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(
                    index=index_name,
                    body={
                        "mappings": {
                            "properties": {
                                "id": {"type": "keyword"},
                                "account_id": {"type": "keyword"},
                                "amount": {"type": "float"},
                                "currency": {"type": "keyword"},
                                "merchant_id": {"type": "keyword"},
                                "status": {"type": "keyword"},
                                "is_fraud": {"type": "boolean"},
                                "risk_score": {"type": "float"},
                                "timestamp": {"type": "date"},
                            }
                        }
                    }
                )
            
            # Indexer le document
            self.client.index(
                index=index_name,
                id=transaction_id,
                body=transaction_data
            )
            
            logger.info(f"Transaction indexed: {transaction_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error indexing transaction: {e}")
            return False