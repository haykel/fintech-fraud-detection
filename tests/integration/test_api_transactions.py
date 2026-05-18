import os
import socket

import pytest
from fastapi.testclient import TestClient
from interfaces.api import app


def _kafka_reachable() -> bool:
    """Quick TCP probe to decide if a Kafka broker is available for the e2e test."""
    host_port = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    host, _, port = host_port.split(",")[0].partition(":")
    try:
        with socket.create_connection((host, int(port or "9092")), timeout=1):
            return True
    except OSError:
        return False


requires_kafka = pytest.mark.skipif(
    not _kafka_reachable(),
    reason="Kafka broker not reachable — skipping end-to-end transaction test",
)


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "docs_url" in response.json()


@requires_kafka
@pytest.mark.asyncio
async def test_process_transaction_success(client):
    """Test processing a valid transaction"""
    payload = {
        "account_id": "acc-123",
        "amount": 150.50,
        "currency": "EUR",
        "merchant_id": "merchant-456",
        "merchant_name": "Test Store",
    }
    
    response = client.post("/api/transactions", json=payload)
    
    # Should return 202 Accepted
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["transaction_id"] is not None


@pytest.mark.asyncio
async def test_process_transaction_validation_error(client):
    """Test validation error"""
    payload = {
        "account_id": "acc-123",
        "amount": -100,  # Invalid negative amount
        "currency": "EUR",
        "merchant_id": "merchant-456",
    }
    
    response = client.post("/api/transactions", json=payload)
    
    assert response.status_code == 422  # Validation error