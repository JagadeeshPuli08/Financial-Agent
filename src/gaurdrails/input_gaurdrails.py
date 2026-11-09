import os
import json

from src.llm.client import chat_completion
from src.tracing.tracing import record_current_error
from dotenv import load_dotenv


from src.gaurdrails.prompts import INPUT_GAURDRAIL_INSTRUCTION
from src.gaurdrails.schemas import GuardrailResponse


load_dotenv()


class InputGuardrailClass:

    def __init__(self):
        self.model = os.getenv("GUARDRAIL_MODEL")
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY missing")
        if not self.model:
            raise ValueError("GUARDRAIL_MODEL missing")

    def validate(self, user_prompt: str) -> GuardrailResponse:
        # Deterministic checks first
        if not user_prompt or not user_prompt.strip():
            return GuardrailResponse(
                approved=False,
                category="ambiguous_request",
                reason="Empty prompt",
                risk_flags=["ambiguous_request"],
                rejection_message="Please provide a question."
            )
        if len(user_prompt) > 4000:
            return GuardrailResponse(
                approved=False,
                category="ambiguous_request",
                reason="Prompt exceeds maximum length",
                risk_flags=["ambiguous_request"],
                rejection_message="Your question is too long."
            )
        try:
            response = chat_completion(
                model = self.model,
                messages=[
                    {
                        "role": "system",
                        "content": INPUT_GAURDRAIL_INSTRUCTION
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                generation_name="input-guardrail",
            )
            content = response.choices[0].message.content
            result = GuardrailResponse.model_validate_json(
                content
            )
            return result

        except Exception as exc:
            # Fail closed: never approve when validation fails
            record_current_error(exc)
            return GuardrailResponse(
                approved=False,
                category="ambiguous_request",
                reason=f"Guardrail validation failed: {type(exc).__name__}",
                risk_flags=["validation_failure"],
                rejection_message=(
                    "Unable to validate your request. Please contact support"
                )
            )

input_gaurdrail = InputGuardrailClass()