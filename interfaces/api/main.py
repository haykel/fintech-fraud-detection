from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from interfaces.api.routes import accounts, explanations, transactions

# ==================== Logging ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Lifespan Events ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le startup et shutdown de l'app"""
    # Startup
    logger.info("Application starting...")
    yield
    # Shutdown
    logger.info("Application shutting down...")


# ==================== FastAPI App ====================

app = FastAPI(
    title="FinTech Fraud Detection Platform",
    description="Plateforme de détection de fraude avec scoring de risque et explainabilité IA",
    version="1.0.0",
    lifespan=lifespan,
)

# ==================== CORS ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Routes ====================

app.include_router(transactions.router, prefix="/api", tags=["transactions"])
app.include_router(accounts.router, prefix="/api", tags=["accounts"])
app.include_router(explanations.router, prefix="/api", tags=["explanations"])

# ==================== Health Check ====================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "fintech-fraud-detection",
        "version": "1.0.0",
    }

# ==================== Root ====================

@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "FinTech Fraud Detection Platform",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)