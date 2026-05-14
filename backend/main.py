"""FastAPI bootstrap with basic Supabase connectivity checks."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

try:
    from .db import get_supabase
except ImportError:  # pragma: no cover - supports running with `uvicorn main:app`
    from db import get_supabase

try:
    from .agent import reset_session, run_agent_turn
except ImportError:  # pragma: no cover - supports running with `uvicorn main:app`
    from agent import reset_session, run_agent_turn

try:
    from .admin import get_ticket_detail, get_ticket_summary, list_tickets
except ImportError:  # pragma: no cover - supports running with `uvicorn main:app`
    from admin import get_ticket_detail, get_ticket_summary, list_tickets

try:
    from .tools import (
        apply_rules_and_summarize,
        cancel_chargeback_request,
        create_chargeback_ticket,
        get_transaction_context,
        search_transactions,
    )
except ImportError:  # pragma: no cover - supports running with `uvicorn main:app`
    from tools import (
        apply_rules_and_summarize,
        cancel_chargeback_request,
        create_chargeback_ticket,
        get_transaction_context,
        search_transactions,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

logger = logging.getLogger("backend.main")

app = FastAPI(title="BROU Chargeback Demo API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def validate_env_vars_on_startup() -> None:
    """Log missing critical environment variables at startup."""
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DEMO_USER_ID"]
    missing_vars = [var_name for var_name in required_vars if not os.getenv(var_name)]

    if missing_vars:
        logger.error("Missing critical env vars: %s", ", ".join(missing_vars))
    else:
        logger.info("Critical env vars loaded.")


@app.get("/health")
def health() -> dict[str, Any]:
    """Check API liveness and basic Supabase connectivity."""
    supabase_ok = False
    try:
        client = get_supabase()
        client.table("transactions").select("id", count="exact").limit(1).execute()
        supabase_ok = True
    except Exception:
        logger.exception("Supabase connectivity check failed in /health.")

    return {
        "status": "ok" if supabase_ok else "degraded",
        "supabase": supabase_ok,
    }


@app.get("/transactions/sample")
def transactions_sample() -> list[dict[str, Any]]:
    """Return latest 5 transactions for the demo user."""
    demo_user_id = os.getenv("DEMO_USER_ID")
    if not demo_user_id:
        raise HTTPException(status_code=500, detail="Missing DEMO_USER_ID in environment.")

    try:
        client = get_supabase()
        response = (
            client.table("transactions")
            .select("*")
            .eq("user_id", demo_user_id)
            .order("transaction_at", desc=True)
            .limit(5)
            .execute()
        )
        return response.data or []
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch sample transactions.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {exc}") from exc


@app.get("/admin/tickets/summary")
def admin_tickets_summary() -> dict[str, Any]:
    """Return aggregate counters for admin panel."""
    try:
        return get_ticket_summary()
    except Exception as exc:
        logger.exception("Failed to fetch admin ticket summary.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch ticket summary: {exc}") from exc


@app.get("/admin/tickets")
def admin_tickets_list(limit: int = 100) -> dict[str, Any]:
    """Return recent chargeback tickets for admin listing."""
    try:
        return {"items": list_tickets(limit=limit)}
    except Exception as exc:
        logger.exception("Failed to fetch admin ticket list.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch ticket list: {exc}") from exc


@app.get("/admin/tickets/{ticket_id}")
def admin_ticket_detail(ticket_id: str) -> dict[str, Any]:
    """Return one ticket with summary, recommendation, and logs."""
    try:
        ticket = get_ticket_detail(ticket_id=ticket_id)
    except Exception as exc:
        logger.exception("Failed to fetch admin ticket detail.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch ticket detail: {exc}") from exc

    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return ticket


@app.post("/tools/search_transactions")
def search_transactions_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Testing endpoint for the search_transactions tool."""
    try:
        return search_transactions(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("search_transactions tool endpoint failed.")
        raise HTTPException(status_code=500, detail=f"search_transactions failed: {exc}") from exc


@app.post("/tools/get_transaction_context")
def get_transaction_context_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Testing endpoint for the get_transaction_context tool."""
    transaction_id = payload.get("transaction_id")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="transaction_id is required.")

    try:
        return get_transaction_context(transaction_id=transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("get_transaction_context tool endpoint failed.")
        raise HTTPException(status_code=500, detail=f"get_transaction_context failed: {exc}") from exc


@app.post("/tools/create_chargeback_ticket")
def create_chargeback_ticket_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Testing endpoint for the create_chargeback_ticket tool."""
    try:
        return create_chargeback_ticket(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("create_chargeback_ticket tool endpoint failed.")
        raise HTTPException(status_code=500, detail=f"create_chargeback_ticket failed: {exc}") from exc


@app.post("/tools/cancel_chargeback_request")
def cancel_chargeback_request_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Testing endpoint for the cancel_chargeback_request tool."""
    try:
        return cancel_chargeback_request(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("cancel_chargeback_request tool endpoint failed.")
        raise HTTPException(status_code=500, detail=f"cancel_chargeback_request failed: {exc}") from exc


@app.post("/tools/apply_rules_and_summarize")
def apply_rules_and_summarize_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Testing endpoint for apply_rules_and_summarize."""
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required.")
    try:
        return apply_rules_and_summarize(ticket_id=ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("apply_rules_and_summarize tool endpoint failed.")
        raise HTTPException(status_code=500, detail=f"apply_rules_and_summarize failed: {exc}") from exc


@app.post("/chat/stream")
async def chat_stream(payload: dict[str, Any]) -> EventSourceResponse:
    """Stream one chat turn over SSE."""
    session_id = payload.get("session_id")
    message = payload.get("message")
    if not isinstance(session_id, str) or not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required.")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="message is required.")

    async def event_generator():
        try:
            async for event in run_agent_turn(session_id=session_id, user_message=message):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        except Exception as exc:
            logger.exception("chat_stream failed.")
            yield {
                "event": "token",
                "data": json.dumps(
                    {"text": "Ocurrió un error interno al procesar el turno."},
                    ensure_ascii=False,
                ),
            }
            yield {
                "event": "done",
                "data": json.dumps({}, ensure_ascii=False),
            }

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/chat/reset")
async def chat_reset(payload: dict[str, Any]) -> dict[str, Any]:
    """Reset in-memory chat history for a session."""
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required.")

    reset_session(session_id)
    return {"status": "ok", "session_id": session_id}
