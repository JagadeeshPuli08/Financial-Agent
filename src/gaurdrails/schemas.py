from pydantic import BaseModel, Field
from typing import Literal


class GuardrailResponse(BaseModel):

    approved: bool

    category: Literal[
        "greeting",
        "invalid_request",
        "ambiguous_request",
        "financial_analysis",
        "transaction_lookup",
        "spending_analysis",
        "income_analysis",
        "visualization_request",
        "out_of_scope",
        "prompt_injection",
        "unauthorized_data_access",
        "unsafe_execution",
    ]
    reason: str
    risk_flags: list[str] = Field(default_factory=list)
    response_message: str | None = None
    rejection_message: str | None = None