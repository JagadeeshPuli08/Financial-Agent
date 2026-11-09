import json
import os

from dotenv import load_dotenv

from src.gaurdrails.prompts import OUTPUT_GAURDRAIL_INSTRUCTION
from src.gaurdrails.schemas import GuardrailResponse
from src.llm.client import chat_completion
from src.tracing.tracing import record_current_error

load_dotenv()


class OutputGuardrailClass:
    def __init__(self) -> None:
        self.model = os.getenv("GUARDRAIL_MODEL")
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY missing")
        if not self.model:
            raise ValueError("GUARDRAIL_MODEL missing")

    def validate(
        self,
        user_prompt: str,
        assistant_response: str,
    ) -> GuardrailResponse:
        try:
            response = chat_completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": OUTPUT_GAURDRAIL_INSTRUCTION,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_request": user_prompt,
                                "assistant_response": assistant_response,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                generation_name="output-guardrail",
            )
            content = response.choices[0].message.content
            return GuardrailResponse.model_validate_json(content)
        except Exception as exc:
            record_current_error(exc)
            return GuardrailResponse(
                approved=False,
                category="invalid_request",
                reason=f"Output guardrail validation failed: {type(exc).__name__}",
                risk_flags=["output_guardrail_failure"],
                rejection_message="Sorry, I couldn't retrieve that information.",
            )


output_gaurdrail = OutputGuardrailClass()
