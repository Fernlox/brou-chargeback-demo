"""Langfuse tracing helpers with no-op fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - dependency/import edge case
    Langfuse = None  # type: ignore[assignment]


@dataclass
class _NoOpTrace:
    """Minimal trace object compatible with helper calls."""

    session_id: str | None = None

    def update(self, **kwargs: Any) -> "_NoOpTrace":
        return self

    def span(self, **kwargs: Any) -> "_NoOpTrace":
        return self

    def generation(self, **kwargs: Any) -> "_NoOpTrace":
        return self

    def end(self, **kwargs: Any) -> "_NoOpTrace":
        return self


_LANGFUSE_CLIENT: Any | None = None


def _get_langfuse_client() -> Any | None:
    """Initialize and cache Langfuse client when keys are available."""
    global _LANGFUSE_CLIENT

    if _LANGFUSE_CLIENT is not None:
        return _LANGFUSE_CLIENT

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if not public_key or not secret_key or Langfuse is None:
        _LANGFUSE_CLIENT = None
        return None

    try:
        _LANGFUSE_CLIENT = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception:
        _LANGFUSE_CLIENT = None

    return _LANGFUSE_CLIENT


def start_trace(session_id: str, user_message: str) -> Any:
    """Create a new trace for one user turn."""
    client = _get_langfuse_client()
    if client is None:
        return _NoOpTrace(session_id=session_id)

    return client.trace(
        name="brou_chargeback_turn",
        session_id=session_id,
        input={"user_message": user_message},
        metadata={"channel": "chat_stream"},
    )


def log_user_turn(trace_obj: Any, message: str) -> None:
    """Log user turn text."""
    try:
        trace_obj.span(
            name="user_turn",
            input={"message": message},
            output={"recorded": True},
        ).end()
    except Exception:
        return None


def log_llm_call(
    trace_obj: Any,
    prompt: Any,
    response: Any,
    model: str,
    latency_ms: float,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    """Log a Gemini generation call."""
    usage_details: dict[str, int] = {}
    if input_tokens is not None:
        usage_details["input"] = int(input_tokens)
    if output_tokens is not None:
        usage_details["output"] = int(output_tokens)

    try:
        trace_obj.generation(
            name="gemini_generate_content",
            model=model,
            input=prompt,
            output=response,
            usage_details=usage_details or None,
            metadata={"latency_ms": latency_ms},
        ).end()
    except Exception:
        return None


def log_tool_call(
    trace_obj: Any,
    tool_name: str,
    input_args: dict[str, Any],
    output: Any,
    latency_ms: float,
) -> None:
    """Log a tool call with arguments and result."""
    try:
        trace_obj.span(
            name=f"tool:{tool_name}",
            input=input_args,
            output=output,
            metadata={"latency_ms": latency_ms},
        ).end()
    except Exception:
        return None


def log_intent_classification(
    trace_obj: Any,
    message: str,
    classified_intent: str,
) -> None:
    """Log classified user intent when available."""
    try:
        trace_obj.span(
            name="intent_classification",
            input={"message": message},
            output={"classified_intent": classified_intent},
        ).end()
    except Exception:
        return None


def flush_traces() -> None:
    """Flush buffered tracing events when Langfuse is active."""
    client = _get_langfuse_client()
    if client is None:
        return None
    try:
        client.flush()
    except Exception:
        return None
