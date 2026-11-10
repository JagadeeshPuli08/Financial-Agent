import json
import os

from src.prompts.instructions import RESPONSE_REWRITER_INSTRUCTION
from src.llm.client import chat_completion


def rewrite_response(
    user_prompt: str,
    user_name: str,
    assistant_draft: str,
    visualization_paths: list[str],
) -> str:
    model = os.getenv("GUARDRAIL_MODEL")
    if not model:
        raise ValueError("GUARDRAIL_MODEL missing")

    response = chat_completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": RESPONSE_REWRITER_INSTRUCTION,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_request": user_prompt,
                        "user_name": user_name,
                        "assistant_draft": assistant_draft,
                        "visualization_paths": visualization_paths,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        max_tokens=4000,
        generation_name="response-rewriter",
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Response rewriter returned an empty response.")
    return content.strip()
