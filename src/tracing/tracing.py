import hashlib
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import litellm
from langfuse import get_client, propagate_attributes

from src.app.settings import APP_NAME

logger = logging.getLogger(__name__)

_client: Any = None
_enabled = False
_active_trace: ContextVar[dict[str, str] | None] = ContextVar(
    "langfuse_trace_context",
    default=None,
)
_active_observation: ContextVar["_TracedObservation | None"] = ContextVar(
    "langfuse_active_observation",
    default=None,
)


class _TracedObservation:
    def __init__(self, observation: Any, *, is_trace: bool) -> None:
        self._observation = observation
        self._is_trace = is_trace
        self._has_output = False

    def update(self, **kwargs: Any) -> None:
        try:
            self._observation.update(**kwargs)
            self._has_output = self._has_output or "output" in kwargs
        except Exception:
            logger.exception("Failed to update Langfuse observation")

    def set_trace_io(self, *, input: Any, output: Any) -> None:
        if not self._is_trace:
            self.update(input=input, output=output)
            return

        try:
            self._observation.update(input=input, output=output)
            self._observation.set_trace_io(input=input, output=output)
            self._has_output = True
        except Exception:
            logger.exception("Failed to update Langfuse trace input/output")


def _error_output(exc: Exception) -> dict[str, str]:
    message = str(exc)[:500]
    message = re.sub(
        r"(?i)(api[_ -]?key|authorization|bearer|secret|token)(\s*[=:]\s*|\s+)[^\s,;]+",
        r"\1\2[REDACTED]",
        message,
    )
    message = re.sub(r"\b(?:sk|pk)-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", message)
    return {"error_type": type(exc).__name__, "error": message}


def initialize_tracing() -> None:
    global _client, _enabled

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        logger.info("Langfuse tracing disabled: credentials are not configured")
        return

    _client = get_client()
    _enabled = True

    if "langfuse" not in litellm.success_callback:
        litellm.success_callback.append("langfuse")
    if "langfuse" not in litellm.failure_callback:
        litellm.failure_callback.append("langfuse")


@contextmanager
def observe_span(
    name: str,
    *,
    input: Any | None = None,
    trace_user_id: str | None = None,
) -> Iterator[_TracedObservation | None]:
    if not _enabled or _client is None:
        yield None
        return

    with _client.start_as_current_observation(
        as_type="span",
        name=name,
        input={} if input is None else input,
        output={"status": "started"},
    ) as observation:
        inherited_context = _active_trace.get() or {}
        trace_context = {
            **inherited_context,
            "trace_id": observation.trace_id,
            "parent_observation_id": observation.id,
        }
        if trace_user_id is not None:
            trace_context["trace_user_id"] = trace_user_id

        token = _active_trace.set(trace_context)
        traced_observation = _TracedObservation(
            observation,
            is_trace=trace_user_id is not None,
        )
        observation_token = _active_observation.set(traced_observation)
        try:
            if trace_user_id is not None:
                with propagate_attributes(
                    user_id=trace_user_id,
                    trace_name=APP_NAME,
                ):
                    yield traced_observation
            else:
                yield traced_observation
        except Exception as exc:
            details = _error_output(exc)
            traced_observation.update(
                level="ERROR",
                status_message=f"{details['error_type']}: {details['error']}",
                output={"status": "error", **details},
            )
            raise
        else:
            if not traced_observation._has_output:
                traced_observation.update(output={"status": "completed"})
        finally:
            _active_observation.reset(observation_token)
            _active_trace.reset(token)


def litellm_trace_metadata(generation_name: str) -> dict[str, Any] | None:
    trace_context = _active_trace.get()
    if trace_context is None:
        return None

    return {
        **trace_context,
        "generation_name": generation_name,
        "trace_name": APP_NAME,
    }


def trace_user_identifier(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def trace_error_details(exc: Exception) -> dict[str, str]:
    return _error_output(exc)


def record_current_error(exc: Exception) -> None:
    observation = _active_observation.get()
    details = _error_output(exc)
    if observation is None:
        logger.error(
            "LLM processing failed outside a traced observation: %s: %s",
            details["error_type"],
            details["error"],
        )
        return

    observation.update(
        level="ERROR",
        status_message=f"{details['error_type']}: {details['error']}",
        metadata={"error": details},
    )


def shutdown_tracing() -> None:
    if _client is not None:
        _client.shutdown()
