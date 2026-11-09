import os
import json
import inspect
from time import perf_counter
from typing import Any
from functools import wraps

import pandas as pd
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.app.cache import cache, cache_manager
from src.app.modals import QueryResponse
from src.gaurdrails.input_gaurdrails import input_gaurdrail
from src.gaurdrails.output_gaurdrails import output_gaurdrail
from src.pipeline.query_generator import build_query_generation_prompt
from src.tools.pandas_executor import execute_pandas_code
from src.tools.visualization_tools import bar, barh, imshow, pie, plot, stackplot

load_dotenv()

APP_NAME = "transaction_agent"
BASE_MODEL = os.getenv("BASE_MODEL")
MAX_TOKENS = int(os.getenv("MAX_GAURDRAILS_TOKENS", "50000"))


class UserNotFoundError(Exception):
    """Raised when a user has no transactions in the loaded dataset."""


def _make_user_visualization_tool(
    user_id: str,
    user_name: str,
    tool: Any,
    image_paths: list[str],
):
    @wraps(tool)
    def save_visualization(*args: Any, **kwargs: Any) -> str:
        bound_arguments = inspect.signature(tool).bind_partial(*args, **kwargs)
        title = bound_arguments.arguments.get("title", "")
        if user_name and not title.startswith(f"{user_name} - "):
            bound_arguments.arguments["title"] = (
                f"{user_name} - {title}" if title else user_name
            )

        image_path = tool(*bound_arguments.args, **bound_arguments.kwargs)
        image_paths.append(image_path)
        viz_state = cache_manager.get_viz_state(user_id) or []
        cache_manager.set_viz_state(user_id, [*viz_state, image_path])
        return image_path

    return save_visualization


def _make_user_pandas_tool(user_df: pd.DataFrame):
    def execute_user_pandas_code(code: str) -> dict[str, Any]:
        return execute_pandas_code(code, user_df)

    execute_user_pandas_code.__name__ = "execute_pandas_code"
    execute_user_pandas_code.__doc__ = (
        "Execute Pandas analysis code against only the current user's transactions."
    )
    return execute_user_pandas_code


async def TransactionRAGPipeline(
    user_id: str,
    query: str,
    df: pd.DataFrame,
) -> QueryResponse:
    started_at = perf_counter()
    profile_cache_hit = (
        user_id in cache.store and cache.store[user_id].get("profile") is not None
    )
    guardrail_response = input_gaurdrail.validate(user_prompt=query)
    if not guardrail_response.approved:
        if guardrail_response.category == "unauthorized_data_access":
            response_text = "Sorry, I can only help with your own transactions."
        else:
            response_text = (
                guardrail_response.rejection_message
                or "Sorry, I couldn't help with that request."
            )
        cache_manager.add_query_history(
            user_id,
            {
                "query": query,
                "response": response_text,
                "visualizations": [],
            },
        )
        return QueryResponse(
            response=response_text,
            data_summary={},
            visualizations=[],
            cache_hit=profile_cache_hit,
            latency_ms=(perf_counter() - started_at) * 1000,
            guardrail_flags=[
                guardrail_response.category,
                guardrail_response.reason,
            ],
        )

    user_profile = cache_manager.get_user_profile(user_id, df)

    if user_profile is None:
        raise UserNotFoundError("User not found in the transaction dataset.")

    user_df = df.loc[df["user_id"].astype(str) == user_id].copy()
    image_paths: list[str] = []
    query_history = cache_manager.get_query_history(user_id)
    viz_state = cache_manager.get_viz_state(user_id)
    if not BASE_MODEL:
        raise RuntimeError(
            "BASE_MODEL is not configured. Set BASE_MODEL in the environment or .env file."
        )

    instruction = (
        f"{build_query_generation_prompt(user_profile)}"
        f"\n\nRelevant conversation history:\n{json.dumps(query_history, default=str)}"
        f"\n\nPrevious visualization paths:\n{json.dumps(viz_state, default=str)}"
    )
    agent = Agent(
        name=APP_NAME,
        model=LiteLlm(model=BASE_MODEL, max_tokens=MAX_TOKENS),
        instruction=instruction,
        tools=[
            _make_user_pandas_tool(user_df),
            *(
                _make_user_visualization_tool(
                    user_id,
                    user_profile.user_name,
                    tool,
                    image_paths,
                )
                for tool in (plot, pie, bar, barh, stackplot, imshow)
            ),
        ],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
    )
    events = runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=query)],
        ),
    )

    final_event = None
    async for event in events:
        if event.is_final_response():
            final_event = event
    if final_event is None or final_event.content is None:
        raise RuntimeError("The transaction agent did not return a final response.")

    response_text = "\n".join(
        part.text for part in final_event.content.parts if part.text
    )
    output_guardrail_response = output_gaurdrail.validate(
        user_prompt=query,
        assistant_response=response_text,
        visualizations=image_paths,
    )
    guardrail_flags: list[str] = []
    response_visualizations = image_paths
    # if not output_guardrail_response.approved:
    #     if (
    #         output_guardrail_response.category == "unauthorized_data_access"
    #         or "unauthorized_data_access" in output_guardrail_response.risk_flags
    #     ):
    #         response_text = "Sorry, I can only help with your own transactions."
    #     else:
    #         response_text = "Sorry, I couldn't retrieve that information."
    #     response_visualizations = []
    #     guardrail_flags = [
    #         output_guardrail_response.category,
    #         output_guardrail_response.reason,
    #     ]

    cache_manager.add_query_history(
        user_id,
        {
            "query": query,
            "response": response_text,
            "visualizations": response_visualizations.copy(),
        },
    )
    return QueryResponse(
        response=response_text,
        data_summary=user_profile.model_dump(mode="json"),
        visualizations=response_visualizations,
        cache_hit=profile_cache_hit,
        latency_ms=(perf_counter() - started_at) * 1000,
        guardrail_flags=guardrail_flags,
    )
