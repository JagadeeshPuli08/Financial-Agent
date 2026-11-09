from datetime import date
from typing import Any

from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    user_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class QueryResponse(BaseModel):
    response: str
    data_summary: dict[str, Any]
    visualizations: list[str]
    cache_hit: bool
    latency_ms: float = Field(ge=0)
    guardrail_flags: list[str]


class UserProfileDateRange(BaseModel):
    start: date
    end: date


class UserProfile(BaseModel):
    user_name: str
    transaction_count: int = Field(ge=0)
    date_range: UserProfileDateRange
    top_categories: list[str]
    top_merchants: list[str]
    average_monthly_spend: float
    dataset_version: str
