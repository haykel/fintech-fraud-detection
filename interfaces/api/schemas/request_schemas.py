from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict, Any
from decimal import Decimal


# ==================== Request Schemas ====================

class ProcessTransactionRequest(BaseModel):
    """Request body pour POST /api/transactions"""
    account_id: str = Field(..., description="UUID du compte")
    amount: float = Field(..., gt=0, description="Montant de la transaction")
    currency: str = Field(default="EUR", description="Code devise ISO 4217")
    merchant_id: str = Field(..., description="UUID du commerçant")
    merchant_name: Optional[str] = Field(None, description="Nom du commerçant")
    merchant_category: Optional[str] = Field(None, description="Catégorie du commerçant")
    merchant_country: Optional[str] = Field(None, description="Code pays du commerçant")

    @field_validator('currency')
    @classmethod
    def currency_must_be_3_chars(cls, v):
        if len(v) != 3:
            raise ValueError('Currency must be a 3-letter ISO 4217 code')
        return v.upper()

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account_id": "acc-123",
                "amount": 150.50,
                "currency": "EUR",
                "merchant_id": "merchant-456",
                "merchant_name": "Electronics Store",
                "merchant_category": "retail",
                "merchant_country": "FR",
            }
        }
    )


class GetTransactionHistoryRequest(BaseModel):
    """Query params pour GET /api/accounts/{account_id}/transactions"""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="PENDING, APPROVED, REJECTED, BLOCKED")
    is_fraud: Optional[bool] = Field(None)
    start_date: Optional[str] = Field(None, description="ISO 8601 format")
    end_date: Optional[str] = Field(None, description="ISO 8601 format")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit": 50,
                "offset": 0,
                "min_amount": 100,
                "max_amount": 500,
                "status": "APPROVED",
                "is_fraud": False,
            }
        }
    )