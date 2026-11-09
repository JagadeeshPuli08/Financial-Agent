"""LiteLLM client for completions, with retries and model fallback."""

import logging
import os
import time
from typing import Any, Literal

from dotenv import load_dotenv
from litellm import completion

from src.tracing.tracing import litellm_trace_metadata, record_current_error

load_dotenv()
GUARDRAIL_MODEL = os.getenv("GUARDRAIL_MODEL")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 1))
MAX_GAURDRAILS_TOKENS = int(os.getenv("MAX_GAURDRAILS_TOKENS", 50000))
logger = logging.getLogger(__name__)

def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = GUARDRAIL_MODEL,
    temperature: float | None = None,
    stream: bool | None = None,
    max_tokens: int | None = MAX_GAURDRAILS_TOKENS,
    reasoning_effort: Literal[
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
        "default",
    ]
    | None = None,
    generation_name: str = "guardrail",
) -> Any:
    
    models = [model, FALLBACK_MODEL]

    last_error: Exception | None = None
    for selected_model in models:
        for attempt in range(MAX_RETRIES + 1):
            try:
                return completion(
                    model = selected_model,
                    messages = messages,
                    temperature = temperature,
                    stream = stream,
                    reasoning_effort = reasoning_effort,
                    max_tokens = max_tokens,
                    metadata = litellm_trace_metadata(generation_name),
                )
            except Exception as exc:
                logger.warning(
                    "LiteLLM request failed (model=%s, attempt=%d/%d): %s",
                    selected_model,
                    attempt + 1,
                    MAX_RETRIES + 1,
                    type(exc).__name__,
                )
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(MAX_RETRIES * (2 ** attempt))
        # Move to the fallback model only after all primary attempts fail.

    assert last_error is not None
    record_current_error(last_error)
    raise last_error


if __name__ == "__main__":
    messages = [{
        "role": "user",
        "content" : "Hi"
    }]
    print(chat_completion(model = "openrouter/openai/gpt-6-luna", messages=messages))