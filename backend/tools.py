"""Tools module for backend agent functions."""

from __future__ import annotations

import os
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

try:
    from .db import get_supabase
except ImportError:  # pragma: no cover - supports running as script module
    from db import get_supabase

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

RESULT_FIELDS = (
    "id",
    "transaction_at",
    "merchant_name",
    "total_amount",
    "currency",
    "card_last4",
    "entry_mode",
)
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COUNTRY_LABELS = {
    "UY": "Uruguay",
    "US": "Estados Unidos",
    "AR": "Argentina",
    "BR": "Brasil",
    "CL": "Chile",
    "PY": "Paraguay",
    "CN": "China",
}
_MCC_BUSINESS_TYPE_LABELS = {
    "5411": "supermercado",
    "5812": "restaurante o delivery",
    "5814": "restaurante o delivery",
    "5815": "servicio digital o streaming",
    "4899": "servicio digital o suscripcion",
    "4121": "transporte o movilidad",
    "4814": "telecomunicaciones",
    "5942": "ecommerce o retail",
    "5999": "ecommerce o retail",
    "5541": "estacion de servicio",
    "5912": "farmacia",
}

_GEMINI_CLIENT: genai.Client | None = None


class RulesSummaryResponse(BaseModel):
    """Schema for rules summary output."""

    summary: str = Field(description="Resumen del caso en 3-5 lineas.")
    recommendation: str = Field(description="Accion concreta recomendada segun reglas.")


def _coerce_amount(value: Any) -> float:
    """Convert DB numeric values into plain float for JSON responses."""
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _amounts_match_money_precision(left: float, right: float) -> bool:
    """Compare amounts using 2-decimal money precision."""
    return round(left, 2) == round(right, 2)


def _get_gemini_client() -> genai.Client:
    """Create/cached Gemini client from environment."""
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is not None:
        return _GEMINI_CLIENT

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")
    _GEMINI_CLIENT = genai.Client(api_key=gemini_api_key)
    return _GEMINI_CLIENT


def _get_gemini_model() -> str:
    """Read Gemini model from environment."""
    gemini_model = os.getenv("GEMINI_MODEL")
    if not gemini_model:
        raise RuntimeError("Missing GEMINI_MODEL in environment.")
    return gemini_model


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy converting Decimal values to float."""
    safe_row: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            safe_row[key] = float(value)
        else:
            safe_row[key] = value
    return safe_row


def _clean_string(value: Any) -> str | None:
    """Normalize string-like values and return None when empty."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _friendly_country(country_code: str | None) -> str | None:
    """Map a country code to a user-friendly Spanish label."""
    if not country_code:
        return None
    normalized_code = country_code.strip().upper()
    if not normalized_code:
        return None
    return _COUNTRY_LABELS.get(normalized_code, normalized_code)


def _resolve_purchase_channel_label(transaction: dict[str, Any]) -> str | None:
    """Resolve channel as online or physical for customer-facing copy."""
    entry_mode = _clean_string(transaction.get("entry_mode"))
    card_present = transaction.get("card_present")

    if entry_mode == "online" or card_present is False:
        return "online"
    if entry_mode in {"chip", "contactless", "manual"} or card_present is True:
        return "presencial (tarjeta física)"
    return None


def _build_user_friendly_transaction_context(transaction: dict[str, Any]) -> dict[str, Any]:
    """Build sanitized transaction context for customer confirmation copy."""
    merchant_name = _clean_string(transaction.get("merchant_name")) or "comercio no identificado"
    merchant_dba = _clean_string(transaction.get("merchant_dba"))
    city = _clean_string(transaction.get("merchant_city"))
    country_label = _friendly_country(_clean_string(transaction.get("merchant_country")))

    location_hint_parts = [part for part in (city, country_label) if part]
    location_hint = ", ".join(location_hint_parts) if location_hint_parts else None

    mcc = _clean_string(transaction.get("mcc"))
    business_type = _MCC_BUSINESS_TYPE_LABELS.get(mcc) if mcc else None

    card_last4 = _clean_string(transaction.get("card_last4"))
    card_used = f"tarjeta terminada en {card_last4}" if card_last4 else None

    return {
        "id": transaction.get("id"),
        "transaction_at": transaction.get("transaction_at"),
        "merchant_name": merchant_name,
        "merchant_display_name": merchant_dba or merchant_name,
        "total_amount": transaction.get("total_amount"),
        "currency": transaction.get("currency"),
        "location_hint": location_hint,
        "business_type": business_type,
        "card_used": card_used,
        "purchase_channel": _resolve_purchase_channel_label(transaction),
    }


def _query_transactions(
    *,
    user_id: str,
    date_from: str | None,
    date_to: str | None,
    min_amount: float | None,
    max_amount: float | None,
    currency: str | None,
    merchant_query: str | None,
) -> list[dict[str, Any]]:
    """Run a single select over transactions with dynamic filters."""
    normalized_date_from = date_from
    normalized_date_to = date_to
    if isinstance(normalized_date_from, str) and _DATE_ONLY_RE.fullmatch(normalized_date_from.strip()):
        normalized_date_from = f"{normalized_date_from.strip()}T00:00:00+00:00"
    if isinstance(normalized_date_to, str) and _DATE_ONLY_RE.fullmatch(normalized_date_to.strip()):
        normalized_date_to = f"{normalized_date_to.strip()}T23:59:59.999999+00:00"

    query = (
        get_supabase()
        .table("transactions")
        .select(",".join(RESULT_FIELDS))
        .eq("user_id", user_id)
    )

    if normalized_date_from:
        query = query.gte("transaction_at", normalized_date_from)
    if normalized_date_to:
        query = query.lte("transaction_at", normalized_date_to)
    if min_amount is not None:
        query = query.gte("total_amount", min_amount)
    if max_amount is not None:
        query = query.lte("total_amount", max_amount)
    if currency:
        query = query.eq("currency", currency)
    if merchant_query:
        merchant_like = merchant_query.strip().replace(",", " ")
        query = query.or_(f"merchant_name.ilike.%{merchant_like}%,merchant_dba.ilike.%{merchant_like}%")

    response = query.order("transaction_at", desc=True).limit(50).execute()
    return response.data or []


def _parse_transaction_dt(value: str) -> datetime:
    """Parse ISO datetime for tie-break sorting."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def search_transactions(
    *,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    approximate_amount: float | None = None,
    amount_tolerance_pct: float = 20.0,
    min_amount: float | None = None,
    max_amount: float | None = None,
    currency: str | None = None,
    merchant_query: str | None = None,
    last_n: int = 10,
) -> dict[str, Any]:
    """Search transactions by optional filters.

    Args:
        user_id: User UUID to scope the search. Defaults to `DEMO_USER_ID` from env.
        date_from: Inclusive lower bound for `transaction_at` (ISO date/datetime string).
        date_to: Inclusive upper bound for `transaction_at` (ISO date/datetime string).
        approximate_amount: Approximate transaction amount referenced by the user.
        amount_tolerance_pct: Percentage tolerance around `approximate_amount`.
            Defaults to 20.0 and is clamped to a minimum of 10.0.
        min_amount: Explicit minimum amount filter. If provided, overrides approximate
            amount lower bound logic.
        max_amount: Explicit maximum amount filter. If provided, overrides approximate
            amount upper bound logic.
        currency: Optional currency filter (`UYU` or `USD`).
        merchant_query: Case-insensitive substring query against merchant name/DBA.
        last_n: Maximum number of rows to return. Defaults to 10 and is capped at 20.

    Returns:
        A dictionary with:
            - `results`: list of filtered transactions with required fields.
            - `total_results`: number of matching items before `last_n` truncation.
            - `amount_tolerance_used_pct`: effective tolerance used when searching by
              `approximate_amount`.
    """
    effective_user_id = user_id or os.getenv("DEMO_USER_ID")
    if not effective_user_id:
        raise ValueError("Missing user_id and DEMO_USER_ID is not configured.")

    if currency and currency not in {"UYU", "USD"}:
        raise ValueError("currency must be 'UYU' or 'USD'.")

    safe_last_n = max(1, min(int(last_n), 20))
    safe_tolerance_pct = max(float(amount_tolerance_pct), 10.0)

    amount_tolerance_used_pct: float | None = None
    resolved_min_amount = min_amount
    resolved_max_amount = max_amount

    using_approximate_band = (
        approximate_amount is not None and min_amount is None and max_amount is None
    )
    if using_approximate_band:
        resolved_min_amount = approximate_amount * (1 - safe_tolerance_pct / 100.0)
        resolved_max_amount = approximate_amount * (1 + safe_tolerance_pct / 100.0)
        amount_tolerance_used_pct = safe_tolerance_pct

    rows = _query_transactions(
        user_id=effective_user_id,
        date_from=date_from,
        date_to=date_to,
        min_amount=resolved_min_amount,
        max_amount=resolved_max_amount,
        currency=currency,
        merchant_query=merchant_query,
    )

    if using_approximate_band and not rows and safe_tolerance_pct < 35.0:
        fallback_tolerance = 35.0
        rows = _query_transactions(
            user_id=effective_user_id,
            date_from=date_from,
            date_to=date_to,
            min_amount=approximate_amount * (1 - fallback_tolerance / 100.0),
            max_amount=approximate_amount * (1 + fallback_tolerance / 100.0),
            currency=currency,
            merchant_query=merchant_query,
        )
        amount_tolerance_used_pct = fallback_tolerance

    if approximate_amount is not None:
        rows.sort(
            key=lambda row: (
                abs(_coerce_amount(row["total_amount"]) - float(approximate_amount)),
                -_parse_transaction_dt(row["transaction_at"]).timestamp(),
            )
        )
        exact_amount_rows = [
            row
            for row in rows
            if _amounts_match_money_precision(_coerce_amount(row["total_amount"]), float(approximate_amount))
        ]
        if exact_amount_rows:
            rows = exact_amount_rows
    else:
        rows.sort(key=lambda row: _parse_transaction_dt(row["transaction_at"]), reverse=True)

    total_results = len(rows)
    serialized_results: list[dict[str, Any]] = []
    for row in rows[:safe_last_n]:
        serialized_results.append(
            {
                "id": row["id"],
                "transaction_at": row["transaction_at"],
                "merchant_name": row["merchant_name"],
                "total_amount": _coerce_amount(row["total_amount"]),
                "currency": row["currency"],
                "card_last4": row["card_last4"],
                "entry_mode": row["entry_mode"],
            }
        )

    payload: dict[str, Any] = {
        "results": serialized_results,
        "total_results": total_results,
    }
    if approximate_amount is not None and amount_tolerance_used_pct is not None:
        payload["amount_tolerance_used_pct"] = amount_tolerance_used_pct

    return payload


def get_transaction_context(transaction_id: str) -> dict[str, Any]:
    """Get context details for a confirmed transaction.

    Args:
        transaction_id: UUID of the confirmed transaction.

    Returns:
        A dictionary containing sanitized transaction detail and same-merchant
        history metadata for user confirmation. If the transaction does not
        exist, returns `{"error": "transaction_not_found"}`.
    """
    if not transaction_id:
        raise ValueError("transaction_id is required.")

    client = get_supabase()

    tx_response = (
        client.table("transactions")
        .select("*")
        .eq("id", transaction_id)
        .limit(1)
        .execute()
    )
    tx_rows = tx_response.data or []
    if not tx_rows:
        return {"error": "transaction_not_found"}

    transaction = _json_safe_row(tx_rows[0])
    user_id = transaction["user_id"]
    merchant_name = transaction["merchant_name"]
    tx_timestamp = transaction["transaction_at"]
    user_friendly_transaction = _build_user_friendly_transaction_context(transaction)

    history_response = (
        client.table("transactions")
        .select("id,transaction_at,total_amount,currency")
        .eq("user_id", user_id)
        .eq("merchant_name", merchant_name)
        .neq("id", transaction_id)
        .lt("transaction_at", tx_timestamp)
        .order("transaction_at", desc=True)
        .limit(5)
        .execute()
    )
    history_rows = history_response.data or []
    same_merchant_history = [
        {
            "transaction_at": row["transaction_at"],
            "total_amount": _coerce_amount(row["total_amount"]),
            "currency": row["currency"],
        }
        for row in history_rows
    ]

    six_months_ago = (datetime.now(timezone.utc) - timedelta(days=183)).isoformat()
    count_response = (
        client.table("transactions")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("merchant_name", merchant_name)
        .neq("id", transaction_id)
        .gte("transaction_at", six_months_ago)
        .execute()
    )
    same_merchant_count_6m = int(count_response.count or 0)

    return {
        "transaction": user_friendly_transaction,
        "same_merchant_history": same_merchant_history,
        "same_merchant_count_6m": same_merchant_count_6m,
    }


def generate_ticket_number(sequence_offset: int = 0) -> str:
    """Generate the next chargeback ticket number for the current year."""
    current_year = datetime.now(timezone.utc).year
    prefix = f"CB-{current_year}-"

    response = (
        get_supabase()
        .table("chargeback_tickets")
        .select("id", count="exact")
        .like("ticket_number", f"{prefix}%")
        .execute()
    )
    current_count = int(response.count or 0)
    next_sequence = current_count + 1 + max(0, sequence_offset)

    return f"{prefix}{next_sequence:06d}"


def _is_unique_violation(exc: Exception) -> bool:
    """Detect unique-constraint errors from PostgREST/Supabase."""
    if not isinstance(exc, APIError):
        return False

    if str(exc.code or "") == "23505":
        return True

    details = " ".join(
        [
            str(getattr(exc, "message", "")),
            str(getattr(exc, "details", "")),
            str(getattr(exc, "hint", "")),
        ]
    ).lower()
    return "duplicate key" in details or "unique" in details


def create_chargeback_ticket(
    *,
    user_id: str,
    transaction_id: str | None,
    reason_code: str,
    reason_label_es: str,
    user_additional_info: str | None,
    conversation_log: Any,
    status: str = "open",
    resolved_by: str | None = None,
) -> dict[str, str]:
    """Create and persist a chargeback ticket with yearly sequential number.

    Args:
        user_id: UUID of the user that owns the chargeback request.
        transaction_id: UUID of the selected transaction (optional per schema).
        reason_code: Chargeback reason code.
        reason_label_es: Human-readable reason label in Spanish.
        user_additional_info: Optional additional text from the user.
        conversation_log: JSON-serializable conversation transcript.
        status: Initial ticket status. Defaults to `open`.
        resolved_by: Optional resolver label (`agent`, `human`, `system`).

    Returns:
        A dictionary with `ticket_id` and `ticket_number`.
    """
    if not user_id:
        raise ValueError("user_id is required.")
    if not reason_code:
        raise ValueError("reason_code is required.")
    if not reason_label_es:
        raise ValueError("reason_label_es is required.")

    client = get_supabase()
    last_error: Exception | None = None

    for attempt in range(3):
        ticket_number = generate_ticket_number(sequence_offset=attempt)
        payload = {
            "ticket_number": ticket_number,
            "user_id": user_id,
            "transaction_id": transaction_id,
            "reason_code": reason_code,
            "reason_label_es": reason_label_es,
            "user_additional_info": user_additional_info,
            "conversation_log": conversation_log,
            "status": status,
            "resolved_by": resolved_by,
        }

        try:
            response = (
                client.table("chargeback_tickets")
                .insert(payload)
                .select("id,ticket_number")
                .execute()
            )
            rows = response.data or []
            if not rows:
                raise RuntimeError("Ticket insert returned no data.")

            return {
                "ticket_id": rows[0]["id"],
                "ticket_number": rows[0]["ticket_number"],
            }
        except Exception as exc:  # pragma: no cover - DB error path
            if _is_unique_violation(exc):
                last_error = exc
                continue
            raise

    raise RuntimeError("Failed to create chargeback ticket after 3 attempts.") from last_error


def apply_rules_and_summarize(ticket_id: str) -> dict[str, str]:
    """Apply rules.md to a ticket and persist summary/recommendation.

    Args:
        ticket_id: UUID of the ticket to evaluate.

    Returns:
        A dictionary with `summary` and `recommendation`.
    """
    if not ticket_id:
        raise ValueError("ticket_id is required.")

    client = get_supabase()
    ticket_response = (
        client.table("chargeback_tickets")
        .select("*")
        .eq("id", ticket_id)
        .limit(1)
        .execute()
    )
    ticket_rows = ticket_response.data or []
    if not ticket_rows:
        raise ValueError("ticket_not_found")
    ticket = _json_safe_row(ticket_rows[0])

    transaction: dict[str, Any] | None = None
    transaction_id = ticket.get("transaction_id")
    if transaction_id:
        tx_response = (
            client.table("transactions")
            .select("*")
            .eq("id", transaction_id)
            .limit(1)
            .execute()
        )
        tx_rows = tx_response.data or []
        if tx_rows:
            transaction = _json_safe_row(tx_rows[0])

    rules_text = (REPO_ROOT / "rules.md").read_text(encoding="utf-8")

    system_prompt = (
        "Sos un sistema experto en gestion de contracargos de BROU. "
        "Aplica las reglas indicadas al caso y devolve estrictamente el JSON pedido."
    )
    user_prompt = "\n\n".join(
        [
            "Reglas activas:",
            rules_text,
            "Datos del ticket:",
            json.dumps(
                {
                    "id": ticket.get("id"),
                    "status": ticket.get("status"),
                    "reason_code": ticket.get("reason_code"),
                    "reason_label_es": ticket.get("reason_label_es"),
                    "user_additional_info": ticket.get("user_additional_info"),
                    "conversation_log": ticket.get("conversation_log"),
                    "created_at": ticket.get("created_at"),
                },
                ensure_ascii=False,
                default=str,
            ),
            "Datos de transaccion asociada (si existe):",
            json.dumps(transaction, ensure_ascii=False, default=str),
            "Devolve JSON valido con campos `summary` y `recommendation`.",
        ]
    )

    gemini_client = _get_gemini_client()
    response = gemini_client.models.generate_content(
        model=_get_gemini_model(),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=RulesSummaryResponse,
        ),
    )

    parsed = response.parsed
    if isinstance(parsed, RulesSummaryResponse):
        summary = parsed.summary.strip()
        recommendation = parsed.recommendation.strip()
    else:
        raw = response.text or "{}"
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid JSON returned by Gemini for rules summary.") from exc
        summary = str(loaded.get("summary", "")).strip()
        recommendation = str(loaded.get("recommendation", "")).strip()

    if not summary or not recommendation:
        raise RuntimeError("Gemini rules summary response missing required fields.")

    (
        client.table("chargeback_tickets")
        .update(
            {
                "agent_summary": summary,
                "agent_recommendation": recommendation,
            }
        )
        .eq("id", ticket_id)
        .execute()
    )

    return {"summary": summary, "recommendation": recommendation}


def cancel_chargeback_request(
    *,
    user_id: str,
    transaction_id: str | None,
    conversation_log: list[dict[str, Any]],
    cancellation_reason: str,
) -> dict[str, str]:
    """Create a cancellation ticket for a chargeback flow.

    Args:
        user_id: UUID of the user requesting cancellation.
        transaction_id: UUID of the selected transaction, or None.
        conversation_log: Conversation transcript to persist with the ticket.
        cancellation_reason: User-provided explanation for cancelling.

    Returns:
        A dictionary with `ticket_id` and `ticket_number`.
    """
    if not cancellation_reason:
        raise ValueError("cancellation_reason is required.")

    created_ticket = create_chargeback_ticket(
        user_id=user_id,
        transaction_id=transaction_id,
        reason_code="unknown_transaction",
        reason_label_es="Desconocimiento de transacciones",
        user_additional_info=cancellation_reason,
        conversation_log=conversation_log,
        status="cancelled_by_user",
        resolved_by="agent",
    )
    apply_rules_and_summarize(ticket_id=created_ticket["ticket_id"])
    return created_ticket
