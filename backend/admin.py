"""Read-only admin queries for chargeback tickets."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

try:
    from .db import get_supabase
except ImportError:  # pragma: no cover - supports running as script module
    from db import get_supabase


def _json_safe_value(value: Any) -> Any:
    """Convert non-JSON-native values recursively."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe_value(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    return value


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of a DB row."""
    return {key: _json_safe_value(value) for key, value in row.items()}


def get_ticket_summary() -> dict[str, Any]:
    """Return aggregate counters for admin dashboard cards."""
    client = get_supabase()
    statuses = [
        "open",
        "cancelled_by_user",
        "in_review",
        "resolved_favorable",
        "resolved_unfavorable",
    ]

    total_response = client.table("chargeback_tickets").select("id", count="exact").limit(1).execute()
    total = int(total_response.count or 0)

    by_status: dict[str, int] = {}
    for status in statuses:
        status_response = (
            client.table("chargeback_tickets")
            .select("id", count="exact")
            .eq("status", status)
            .limit(1)
            .execute()
        )
        by_status[status] = int(status_response.count or 0)

    return {
        "total": total,
        "open": by_status.get("open", 0),
        "cancelled_by_user": by_status.get("cancelled_by_user", 0),
        "by_status": by_status,
    }


def list_tickets(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent tickets with compact transaction preview."""
    safe_limit = max(1, min(int(limit), 200))
    response = (
        get_supabase()
        .table("chargeback_tickets")
        .select(
            ",".join(
                [
                    "id",
                    "ticket_number",
                    "status",
                    "reason_code",
                    "reason_label_es",
                    "created_at",
                    "updated_at",
                    "transaction_id",
                    "transaction:transactions(id,transaction_at,merchant_name,total_amount,currency,card_last4)",
                ]
            )
        )
        .order("created_at", desc=True)
        .limit(safe_limit)
        .execute()
    )
    rows = response.data or []
    return [_json_safe_row(row) for row in rows]


def get_ticket_detail(ticket_id: str) -> dict[str, Any] | None:
    """Return one ticket with all admin-facing details."""
    response = (
        get_supabase()
        .table("chargeback_tickets")
        .select(
            ",".join(
                [
                    "id",
                    "ticket_number",
                    "user_id",
                    "transaction_id",
                    "reason_code",
                    "reason_label_es",
                    "user_additional_info",
                    "status",
                    "resolved_by",
                    "agent_summary",
                    "agent_recommendation",
                    "conversation_log",
                    "created_at",
                    "updated_at",
                    "transaction:transactions(*)",
                ]
            )
        )
        .eq("id", ticket_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return None
    return _json_safe_row(rows[0])
