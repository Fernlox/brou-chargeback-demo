"""Agent runtime for console and SSE chat streaming."""

from __future__ import annotations

import json
import os
import inspect
import asyncio
import time
import re
import logging
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types

try:
    from .copy import (
        CANONICAL_REASON_LABEL_ES,
        continue_choices,
        get_system_prompt,
        msg,
        normalize_language,
        reason_choices,
    )
except ImportError:  # pragma: no cover - supports running from backend directory
    import importlib.util

    _copy_spec = importlib.util.spec_from_file_location("backend_copy", Path(__file__).with_name("copy.py"))
    if _copy_spec is None or _copy_spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Failed to load backend copy module.")
    _copy_module = importlib.util.module_from_spec(_copy_spec)
    _copy_spec.loader.exec_module(_copy_module)
    CANONICAL_REASON_LABEL_ES = _copy_module.CANONICAL_REASON_LABEL_ES
    continue_choices = _copy_module.continue_choices
    get_system_prompt = _copy_module.get_system_prompt
    msg = _copy_module.msg
    normalize_language = _copy_module.normalize_language
    reason_choices = _copy_module.reason_choices

try:
    from .tools import (
        apply_rules_and_summarize,
        cancel_chargeback_request,
        create_chargeback_ticket,
        get_transaction_context,
        search_transactions,
    )
except ImportError:  # pragma: no cover - supports running from backend directory
    from tools import (
        apply_rules_and_summarize,
        cancel_chargeback_request,
        create_chargeback_ticket,
        get_transaction_context,
        search_transactions,
    )

try:
    from .tracing import (
        flush_traces,
        log_llm_call,
        log_tool_call,
        log_user_turn,
        start_trace,
    )
except ImportError:  # pragma: no cover - supports running from backend directory
    from tracing import (
        flush_traces,
        log_llm_call,
        log_tool_call,
        log_user_turn,
        start_trace,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")
logger = logging.getLogger(__name__)

_DATE_EXPR_RE = re.compile(r"\b([0-3]?\d)[/\-]([0-1]?\d)(?:[/\-](\d{2,4}))?\b")
_NUMBER_EXPR_RE = re.compile(r"\b\d+(?:[.,]\d{1,2})?\b")
_SELECT_TX_VALUE_RE = re.compile(
    r"tx_select:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
_SELECT_TX_LEGACY_RE = re.compile(
    r"selecciono la transacci[oó]n\s+([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)

_TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "search_transactions": search_transactions,
    "get_transaction_context": get_transaction_context,
    "create_chargeback_ticket": create_chargeback_ticket,
    "cancel_chargeback_request": cancel_chargeback_request,
    "apply_rules_and_summarize": apply_rules_and_summarize,
}

_SESSION_HISTORIES: dict[str, list[types.Content]] = {}
_SESSION_TRANSCRIPTS: dict[str, list[dict[str, str]]] = {}
_SESSION_STATE: dict[str, dict[str, Any]] = {}
_GEMINI_CLIENT: genai.Client | None = None
_GEMINI_MODEL: str | None = None
_GEMINI_TOOLS: list[types.Tool] | None = None


def _build_tools_config() -> list[types.Tool]:
    """Build Gemini function declarations aligned with tool signatures."""
    tool_schemas: dict[str, dict[str, Any]] = {
        "search_transactions": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "approximate_amount": {"type": "number"},
                "amount_tolerance_pct": {"type": "number"},
                "min_amount": {"type": "number"},
                "max_amount": {"type": "number"},
                "currency": {"type": "string", "enum": ["UYU", "USD"]},
                "merchant_query": {"type": "string"},
                "last_n": {"type": "integer"},
            },
        },
        "get_transaction_context": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"},
                "language": {"type": "string", "enum": ["es", "en"]},
            },
            "required": ["transaction_id"],
        },
        "create_chargeback_ticket": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "transaction_id": {"type": "string"},
                "reason_code": {"type": "string"},
                "reason_label_es": {"type": "string"},
                "user_additional_info": {"type": "string"},
            },
            "required": ["user_id", "reason_code", "reason_label_es"],
        },
        "cancel_chargeback_request": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "transaction_id": {"type": "string"},
                "conversation_log": {"type": "array", "items": {"type": "object"}},
                "cancellation_reason": {"type": "string"},
                "language": {"type": "string", "enum": ["es", "en"]},
            },
            "required": ["user_id", "conversation_log", "cancellation_reason"],
        },
        "apply_rules_and_summarize": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "language": {"type": "string", "enum": ["es", "en"]},
            },
            "required": ["ticket_id"],
        },
    }

    declarations: list[types.FunctionDeclaration] = []
    for tool_name, fn in _TOOL_FUNCTIONS.items():
        declarations.append(
            types.FunctionDeclaration(
                name=tool_name,
                description=inspect.getdoc(fn) or "",
                parameters=types.Schema.from_json_schema(
                    json_schema=types.JSONSchema(**tool_schemas[tool_name])
                ),
            )
        )

    return [types.Tool(function_declarations=declarations)]


def _ensure_runtime_ready() -> tuple[genai.Client, str, list[types.Tool]]:
    """Lazily initialize Gemini runtime dependencies."""
    global _GEMINI_CLIENT, _GEMINI_MODEL, _GEMINI_TOOLS

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")

    if not gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")
    if not gemini_model:
        raise RuntimeError("Missing GEMINI_MODEL in environment.")

    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=gemini_api_key)
    if _GEMINI_TOOLS is None:
        _GEMINI_TOOLS = _build_tools_config()
    _GEMINI_MODEL = gemini_model
    return _GEMINI_CLIENT, _GEMINI_MODEL, _GEMINI_TOOLS


def _get_session_history(session_id: str) -> list[types.Content]:
    """Return in-memory history for session, creating it if needed."""
    history = _SESSION_HISTORIES.get(session_id)
    if history is None:
        history = []
        _SESSION_HISTORIES[session_id] = history
    return history


def _get_session_transcript(session_id: str) -> list[dict[str, str]]:
    """Return structured transcript for session, creating it if needed."""
    transcript = _SESSION_TRANSCRIPTS.get(session_id)
    if transcript is None:
        transcript = []
        _SESSION_TRANSCRIPTS[session_id] = transcript
    return transcript


def _get_session_state(session_id: str) -> dict[str, Any]:
    """Return mutable per-session state."""
    state = _SESSION_STATE.get(session_id)
    if state is None:
        state = {}
        _SESSION_STATE[session_id] = state
    return state


def _iso_now_utc() -> str:
    """Return ISO8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str) -> str:
    """Lowercase and remove diacritics for keyword matching."""
    lowered = text.lower()
    return "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )


def _extract_selected_transaction_id(text: str) -> str | None:
    """Extract selected transaction UUID from quick-reply user text."""
    normalized = _normalize_text(" ".join(text.strip().split()))
    match = _SELECT_TX_VALUE_RE.search(normalized)
    if not match:
        match = _SELECT_TX_LEGACY_RE.search(normalized)
    if not match:
        return None
    return match.group(1)


def _extract_transaction_search_slots(
    text: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Extract date/amount/currency hints from user text."""
    compact = " ".join(text.strip().split())
    if not compact:
        return {}

    normalized = _normalize_text(compact)
    extracted: dict[str, Any] = {}
    reference_now = now_utc or datetime.now(timezone.utc)

    date_match = _DATE_EXPR_RE.search(compact)
    if date_match:
        raw_day, raw_month, raw_year = date_match.groups()
        try:
            day = int(raw_day)
            month = int(raw_month)
            if raw_year is None:
                year = reference_now.year
            else:
                parsed_year = int(raw_year)
                year = parsed_year + 2000 if parsed_year < 100 else parsed_year
            parsed_date = datetime(year, month, day)
            date_iso = parsed_date.strftime("%Y-%m-%d")
            extracted["date_from"] = date_iso
            extracted["date_to"] = date_iso
        except ValueError:
            pass

    if re.search(r"\b(?:u\$s|usd|dolares?|dolar|dollars?)\b", normalized):
        extracted["currency"] = "USD"
    elif re.search(r"\b(?:uyu|pesos uruguayos?|pesos?)\b", normalized):
        extracted["currency"] = "UYU"

    text_without_dates = _DATE_EXPR_RE.sub(" ", compact)
    number_candidates = _NUMBER_EXPR_RE.findall(text_without_dates)
    if number_candidates:
        picked_candidate = number_candidates[-1]
        for candidate in number_candidates:
            if "." in candidate or "," in candidate:
                picked_candidate = candidate
                break
        try:
            amount_value = float(picked_candidate.replace(",", "."))
            if amount_value > 0:
                exact_markers = (
                    "exacto",
                    "exacta",
                    "monto exacto",
                    "monto exacta",
                    "exact",
                    "exact amount",
                )
                approximate_markers = (
                    "aprox",
                    "aproxim",
                    "unos",
                    "mas o menos",
                    "about",
                    "around",
                    "approximately",
                )
                is_exact = any(marker in normalized for marker in exact_markers)
                is_approximate = any(marker in normalized for marker in approximate_markers)
                extracted["amount_value"] = amount_value
                extracted["amount_is_approximate"] = not is_exact
                if is_approximate and not is_exact:
                    extracted["amount_is_approximate"] = True
        except ValueError:
            pass

    return extracted


def _merge_transaction_search_slots(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Merge extracted search slots into mutable session state."""
    current = state.get("search_slots")
    if not isinstance(current, dict):
        current = {}
    current.update(updates)
    state["search_slots"] = current
    return current


def _search_slots_have_amount(slots: dict[str, Any]) -> bool:
    """Return whether slots include an amount hint."""
    return isinstance(slots.get("amount_value"), (int, float))


def _build_search_transactions_args_from_slots(slots: dict[str, Any]) -> dict[str, Any]:
    """Build search_transactions args using deterministic search slots."""
    args: dict[str, Any] = {"last_n": 5}
    date_from = slots.get("date_from")
    date_to = slots.get("date_to")
    currency = slots.get("currency")
    amount_value = slots.get("amount_value")
    amount_is_approximate = bool(slots.get("amount_is_approximate", True))

    if isinstance(date_from, str) and date_from.strip():
        args["date_from"] = date_from.strip()
    if isinstance(date_to, str) and date_to.strip():
        args["date_to"] = date_to.strip()
    if isinstance(currency, str) and currency in {"UYU", "USD"}:
        args["currency"] = currency

    if isinstance(amount_value, (int, float)):
        numeric_amount = float(amount_value)
        if amount_is_approximate:
            args["approximate_amount"] = numeric_amount
            args["amount_tolerance_pct"] = 20.0
        else:
            args["min_amount"] = numeric_amount
            args["max_amount"] = numeric_amount

    return args


def _store_latest_search_candidates(state: dict[str, Any], tool_result: dict[str, Any]) -> list[str]:
    """Store latest candidate transaction IDs in session state."""
    candidate_ids: list[str] = []
    payload = tool_result.get("result")
    if isinstance(payload, dict):
        raw_results = payload.get("results")
        if isinstance(raw_results, list):
            for row in raw_results:
                if not isinstance(row, dict):
                    continue
                transaction_id = row.get("id")
                if isinstance(transaction_id, str) and transaction_id.strip():
                    candidate_ids.append(transaction_id)

    state["candidate_transaction_ids"] = candidate_ids
    state["last_search_had_results"] = bool(candidate_ids)
    return candidate_ids


def _is_latest_search_candidate(state: dict[str, Any], transaction_id: str | None) -> bool:
    """Validate transaction ID belongs to latest deterministic search candidate list."""
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        return False
    candidates = state.get("candidate_transaction_ids")
    if not isinstance(candidates, list):
        return False
    return transaction_id in candidates


def _classify_chargeback_reason_hint(text: str) -> str:
    """Return coarse reason hint: unknown_transaction, other_reason, ambiguous_chargeback, none."""
    normalized = _normalize_text(text)
    if "reason:unknown_transaction" in normalized:
        return "unknown_transaction"
    if re.search(r"reason:(not_received|duplicate|processing_error)", normalized):
        return "other_reason"

    unknown_patterns = (
        "no reconozco",
        "cargo equivocado",
        "cargo raro",
        "cargo extrano",
        "movimiento raro",
        "desconocimiento de transacciones",
        "no hice esa compra",
        "no hice ese cargo",
        "desconozco este cargo",
        "unknown transaction",
        "do not recognize",
        "dont recognize",
        "i did not make this",
        "i didnt make this",
        "i did not make that purchase",
        "unauthorized charge",
        "unrecognized charge",
    )
    other_reason_patterns = (
        "no recibi",
        "no me llego",
        "mercaderia",
        "compra duplicad",
        "retiro duplicad",
        "doble cobro",
        "me cobraron dos veces",
        "error de procesamiento",
        "dio error pero",
        "rechazada pero cobrada",
        "did not receive",
        "didnt receive",
        "duplicate purchase",
        "duplicate withdrawal",
        "double charge",
        "charged twice",
        "processing error",
        "failed but charged",
    )
    chargeback_generic_patterns = (
        "cargo",
        "tarjeta",
        "reclamo",
        "contracargo",
        "movimiento",
        "charge",
        "card",
        "chargeback",
        "claim",
        "transaction",
    )

    if any(pattern in normalized for pattern in other_reason_patterns):
        return "other_reason"
    if any(pattern in normalized for pattern in unknown_patterns):
        return "unknown_transaction"
    if any(pattern in normalized for pattern in chargeback_generic_patterns):
        return "ambiguous_chargeback"
    return "none"


def _build_routing_hint(reason_hint: str, language: str) -> str | None:
    """Build internal routing guidance for the model."""
    if reason_hint == "unknown_transaction":
        return msg(language, "routing_hint_unknown")
    if reason_hint == "other_reason":
        return msg(language, "routing_hint_other")
    return None


def _response_mentions_reason_menu(response_text: str) -> bool:
    """Detect if model answer is presenting the 4 reason options."""
    normalized = _normalize_text(response_text)
    spanish_menu = (
        "desconocimiento de transacciones" in normalized
        and "no recibi el servicio" in normalized
        and "compra o retiro duplicado" in normalized
        and "error de procesamiento" in normalized
    )
    english_menu = (
        "unknown transaction" in normalized
        and "did not receive" in normalized
        and "duplicate purchase" in normalized
        and "processing error" in normalized
    )
    return spanish_menu or english_menu


def _response_requests_continue_confirmation(response_text: str, language: str) -> bool:
    """Detect if model asks explicit continue/cancel confirmation."""
    normalized = _normalize_text(response_text)
    if _normalize_text(msg(language, "cost_warning_text")) in normalized:
        return True
    return (
        "confirmas que queres continuar" in normalized
        or "queres seguir adelante" in normalized
        or "confirm you want to continue" in normalized
        or "do you want to continue" in normalized
    )


def _looks_like_continue_confirmation(text: str) -> bool:
    """Detect user intent to continue while waiting explicit confirmation."""
    normalized = _normalize_text(" ".join(text.strip().split()))
    if not normalized:
        return False
    if normalized == "continue:yes":
        return True
    if normalized == "continue:no":
        return False

    explicit_phrases = (
        "si quiero seguir adelante",
        "quiero seguir adelante",
        "si quiero continuar",
        "quiero continuar",
        "confirmo que quiero continuar",
        "confirmo continuar",
        "dale continuar",
        "si confirma",
        "si confirmo",
        "yes i want to continue",
        "i want to continue",
        "i confirm i want to continue",
        "i confirm continue",
        "please continue",
    )
    if any(phrase in normalized for phrase in explicit_phrases):
        return True

    short_confirmations = {"si", "ok", "dale", "continuar", "confirmo", "de acuerdo", "yes", "continue"}
    return normalized in short_confirmations


def _build_quick_reply_payload(
    choices: list[dict[str, str]],
    group: str,
) -> dict[str, Any]:
    """Build SSE payload for quick replies."""
    return {"group": group, "choices": choices}


def _build_transaction_quick_replies(tool_result: dict[str, Any], language: str) -> list[dict[str, str]]:
    """Build quick replies for transaction selection from search results."""
    lang = normalize_language(language)
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return []
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []

    choices: list[dict[str, str]] = []
    for row in raw_results:
        if not isinstance(row, dict):
            continue
        transaction_id = row.get("id")
        merchant_name = row.get("merchant_name")
        transaction_at = row.get("transaction_at")
        total_amount = row.get("total_amount")
        currency = row.get("currency")
        card_last4 = row.get("card_last4")
        if not all(
            isinstance(value, str) for value in (transaction_id, merchant_name, transaction_at, currency)
        ):
            continue
        amount_repr = f"{float(total_amount):.2f}" if isinstance(total_amount, (int, float)) else "?"
        date_raw = transaction_at[:10]
        date_parts = date_raw.split("-")
        if len(date_parts) == 3:
            date_repr = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
        else:
            date_repr = date_raw
        card_suffix = (
            f" (Tarjeta terminada en {card_last4})"
            if lang == "es" and isinstance(card_last4, str) and card_last4.strip()
            else f" (Card ending in {card_last4})"
            if isinstance(card_last4, str) and card_last4.strip()
            else ""
        )
        display_text = f"{date_repr} - {merchant_name} - {currency} {amount_repr}{card_suffix}"
        choices.append(
            {
                "id": f"tx_{transaction_id}",
                "label": display_text,
                "value": f"tx_select:{transaction_id}",
                "display_text": display_text,
            }
        )
    return choices


def _append_transcript_entry(session_id: str, role: str, content: str) -> None:
    """Append a structured transcript entry for the session."""
    _get_session_transcript(session_id).append(
        {
            "role": role,
            "content": content,
            "ts": _iso_now_utc(),
        }
    )


def _snapshot_transcript(session_id: str) -> list[dict[str, str]]:
    """Return a safe copy of the session transcript."""
    return [dict(entry) for entry in _get_session_transcript(session_id)]


def _looks_like_cancellation(text: str) -> bool:
    """Detect direct cancellation intents in user message."""
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if normalized == "continue:no":
        return True

    phrase_keywords = (
        "no quiero seguir",
        "olvidate",
        "olvidate de esto",
        "no quiero continuar",
        "quiero cancelar",
        "prefiero cancelar",
        "i want to cancel",
        "prefer to cancel",
        "do not continue",
        "dont continue",
    )
    if any(keyword in normalized for keyword in phrase_keywords):
        return True

    token_keywords = {"cancelar", "cancela", "deja", "cancel", "stop"}
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return any(token in token_keywords for token in tokens)


def _infer_cancellation_reason(user_message: str, language: str) -> str:
    """Generate a short cancellation reason from the user text."""
    normalized = " ".join(user_message.strip().split())
    if not normalized:
        return msg(language, "cancellation_reason_empty")
    if len(normalized) > 140:
        normalized = normalized[:137].rstrip() + "..."
    return msg(language, "cancellation_reason_prefix", message=normalized)


def _last_agent_message(session_id: str) -> str | None:
    """Return the latest plain agent message from the transcript."""
    transcript = _get_session_transcript(session_id)
    for entry in reversed(transcript):
        if entry.get("role") == "agent":
            content = str(entry.get("content") or "").strip()
            if content:
                return content
    return None


def _is_optional_info_prompt(agent_message: str) -> bool:
    """Detect if the assistant just asked for optional free-text details."""
    normalized = _normalize_text(agent_message)
    has_optional_info_prompt = (
        "informacion" in normalized
        and "agregar" in normalized
        and ("continuar" in normalized or "no tengo nada mas para agregar" in normalized)
    )
    if has_optional_info_prompt:
        return True
    return (
        "additional detail" in normalized
        and "before creating the claim" in normalized
        and ("type 'continue'" in agent_message.lower() or "type continue" in normalized)
    )


def _extract_additional_info(user_message: str) -> str | None:
    """Convert the user's optional-info reply into free text or explicit empty info."""
    compact = " ".join(user_message.strip().split())
    if not compact:
        return None

    normalized = _normalize_text(compact)
    no_info_patterns = (
        "continue:yes",
        "continuar",
        "continua",
        "continuemos",
        "seguir",
        "sigamos",
        "no tengo nada mas para agregar",
        "no tengo nada para agregar",
        "nada mas para agregar",
        "no hay nada mas para agregar",
        "continue",
        "go on",
        "nothing else to add",
        "i have nothing else to add",
        "no additional details",
    )
    if any(pattern == normalized or pattern in normalized for pattern in no_info_patterns):
        return None

    return compact


def _is_optional_info_follow_up(session_id: str) -> bool:
    """Return whether the current user turn is answering optional-info prompt."""
    state = _get_session_state(session_id)
    if state.get("awaiting_optional_info"):
        return True
    last_agent_message = _last_agent_message(session_id)
    if not last_agent_message:
        return False
    return _is_optional_info_prompt(last_agent_message)


def _build_ticket_confirmation_text(tool_result: dict[str, Any], language: str) -> str:
    """Create the final user-facing closure message after ticket creation."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return msg(language, "ticket_confirmation_missing")

    ticket_number = payload.get("ticket_number")
    if not isinstance(ticket_number, str) or not ticket_number.strip():
        return msg(language, "ticket_confirmation_missing")

    message = msg(language, "ticket_confirmation_success", ticket_number=ticket_number)
    return f"{message}\n{msg(language, 'thanks')}"


async def _apply_rules_summary_background(ticket_id: str, language: str) -> None:
    """Run ticket summarization off the user-facing critical path."""
    try:
        await asyncio.to_thread(apply_rules_and_summarize, ticket_id=ticket_id, language=language)
    except Exception:
        logger.exception("Background apply_rules_and_summarize failed for ticket_id=%s", ticket_id)


def _schedule_rules_summary_from_tool_result(tool_result: dict[str, Any], language: str) -> None:
    """Schedule async rules summary if tool result includes a valid ticket_id."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return

    ticket_id = payload.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id.strip():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "Skipping async rules summary for ticket_id=%s because no event loop is running.",
            ticket_id,
        )
        return

    loop.create_task(_apply_rules_summary_background(ticket_id=ticket_id, language=language))


def _format_transaction_date(transaction_at: str) -> str:
    """Format ISO-like transaction timestamp into DD/MM/YYYY."""
    date_raw = transaction_at[:10]
    date_parts = date_raw.split("-")
    if len(date_parts) == 3:
        return f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
    return date_raw


def _build_transaction_confirmation_text(tool_result: dict[str, Any], language: str) -> str:
    """Build deterministic confirmation + deterrence after selected transaction context."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return msg(language, "transaction_context_missing")

    transaction = payload.get("transaction")
    if not isinstance(transaction, dict):
        return msg(language, "transaction_context_invalid")

    merchant_name = str(transaction.get("merchant_name") or msg(language, "merchant_fallback")).strip()
    merchant_display_name = str(transaction.get("merchant_display_name") or merchant_name).strip()
    currency = str(transaction.get("currency") or "USD").strip()
    transaction_at = str(transaction.get("transaction_at") or "").strip()
    total_amount = transaction.get("total_amount")
    location_hint = str(transaction.get("location_hint") or "").strip()
    business_type = str(transaction.get("business_type") or "").strip()
    card_used = str(transaction.get("card_used") or "").strip()
    purchase_channel = str(transaction.get("purchase_channel") or "").strip()

    amount_repr = "?"
    if isinstance(total_amount, (int, float)):
        amount_repr = f"{float(total_amount):.2f}"
    date_repr = _format_transaction_date(transaction_at) if transaction_at else msg(language, "date_unavailable")

    summary_lines: list[str] = [
        msg(
            language,
            "tx_confirm_intro",
            currency=currency,
            amount=amount_repr,
            merchant=merchant_name,
            date=date_repr,
        )
    ]
    if merchant_display_name and merchant_display_name.lower() != merchant_name.lower():
        summary_lines.append(msg(language, "tx_confirm_display_name", name=merchant_display_name))
    if location_hint:
        summary_lines.append(msg(language, "tx_confirm_location", location=location_hint))
    if business_type:
        summary_lines.append(msg(language, "tx_confirm_business_type", business_type=business_type))
    if card_used:
        summary_lines.append(msg(language, "tx_confirm_card", card_used=card_used))
    if purchase_channel:
        summary_lines.append(msg(language, "tx_confirm_channel", purchase_channel=purchase_channel))

    message = "\n".join(summary_lines)

    same_merchant_count_6m = payload.get("same_merchant_count_6m")
    has_prior_with_merchant = isinstance(same_merchant_count_6m, int) and same_merchant_count_6m > 0
    if has_prior_with_merchant:
        message = f"{message}\n{msg(language, 'tx_confirm_prior_count', count=same_merchant_count_6m)}"

    return f"{message}\n{msg(language, 'tx_confirm_ask_continue')}"


def _build_transaction_selection_text(tool_result: dict[str, Any], language: str) -> str:
    """Build deterministic copy for transaction quick-reply turns."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return msg(language, "tx_selection_fallback")

    raw_results = payload.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        return msg(language, "tx_selection_no_results")

    return msg(language, "tx_selection_found")


def reset_session(session_id: str) -> None:
    """Clear session history from in-memory store."""
    _SESSION_HISTORIES.pop(session_id, None)
    _SESSION_TRANSCRIPTS.pop(session_id, None)
    _SESSION_STATE.pop(session_id, None)


def _format_tool_call(name: str, args: dict[str, Any]) -> str:
    """Render tool call in the required console format."""
    args_repr = json.dumps(args, ensure_ascii=False, default=str)
    return f"[tool: {name}({args_repr})]"


def _execute_tool_call(
    tool_name: str,
    args: dict[str, Any],
    history: list[types.Content],
    session_id: str,
) -> dict[str, Any]:
    """Execute a requested tool call with minimal guardrails."""
    fn = _TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    state = _get_session_state(session_id)
    language = normalize_language(state.get("language"))

    if tool_name == "search_transactions":
        slots = state.get("search_slots")
        if isinstance(slots, dict):
            if isinstance(slots.get("date_from"), str):
                args["date_from"] = slots["date_from"]
            if isinstance(slots.get("date_to"), str):
                args["date_to"] = slots["date_to"]
            if isinstance(slots.get("currency"), str) and slots["currency"] in {"UYU", "USD"}:
                args["currency"] = slots["currency"]
            amount_value = slots.get("amount_value")
            if isinstance(amount_value, (int, float)):
                if bool(slots.get("amount_is_approximate", True)):
                    args["approximate_amount"] = float(amount_value)
                    args["amount_tolerance_pct"] = 20.0
                    args.pop("min_amount", None)
                    args.pop("max_amount", None)
                else:
                    args["min_amount"] = float(amount_value)
                    args["max_amount"] = float(amount_value)
                    args.pop("approximate_amount", None)
        # Step 9 requires showing at most 5 candidates.
        requested_last_n = args.get("last_n", 5)
        try:
            args["last_n"] = min(max(int(requested_last_n), 1), 5)
        except Exception:
            args["last_n"] = 5

    if tool_name == "create_chargeback_ticket":
        demo_user_id = os.getenv("DEMO_USER_ID")
        if not args.get("user_id") or args.get("user_id") == "DEMO_USER_ID":
            args["user_id"] = demo_user_id
        if not args.get("transaction_id"):
            transaction_id = state.get("transaction_id")
            if transaction_id:
                args["transaction_id"] = transaction_id
        if args.get("reason_code") != "unknown_transaction":
            args["reason_code"] = "unknown_transaction"
        args.setdefault("reason_label_es", CANONICAL_REASON_LABEL_ES)
        args.setdefault("user_additional_info", None)
        args.setdefault("status", "open")
        args.setdefault("resolved_by", None)

    if tool_name == "cancel_chargeback_request":
        if not args.get("user_id") or args.get("user_id") == "DEMO_USER_ID":
            args["user_id"] = os.getenv("DEMO_USER_ID")

    if tool_name in {"create_chargeback_ticket", "cancel_chargeback_request"}:
        args.setdefault("conversation_log", _snapshot_transcript(session_id))
    if tool_name in {"cancel_chargeback_request", "apply_rules_and_summarize", "get_transaction_context"}:
        args.setdefault("language", language)

    args_for_log = {key: value for key, value in args.items() if key != "conversation_log"}
    tool_call_repr = _format_tool_call(tool_name, args_for_log)
    _append_transcript_entry(session_id, "tool", f"CALL {tool_call_repr}")

    try:
        if tool_name == "create_chargeback_ticket":
            ticket_payload = fn(**args)
            if args.get("transaction_id"):
                _get_session_state(session_id)["transaction_id"] = args.get("transaction_id")
            _append_transcript_entry(
                session_id,
                "tool",
                f"RESULT {tool_name}: {json.dumps(ticket_payload, ensure_ascii=False, default=str)}",
            )
            return {"result": ticket_payload}

        tool_payload = fn(**args)
        if tool_name == "search_transactions":
            _store_latest_search_candidates(_get_session_state(session_id), {"result": tool_payload})
        if tool_name == "get_transaction_context":
            transaction = tool_payload.get("transaction") if isinstance(tool_payload, dict) else None
            if isinstance(transaction, dict) and isinstance(args.get("transaction_id"), str):
                _get_session_state(session_id)["transaction_id"] = args.get("transaction_id")
        _append_transcript_entry(
            session_id,
            "tool",
            f"RESULT {tool_name}: {json.dumps(tool_payload, ensure_ascii=False, default=str)}",
        )
        return {"result": tool_payload}
    except Exception as exc:  # pragma: no cover - runtime DB/tool errors
        _append_transcript_entry(session_id, "tool", f"ERROR {tool_name}: {exc}")
        return {"error": str(exc)}


def _extract_response_text(response: types.GenerateContentResponse) -> str:
    """Extract plain text from response without warning on non-text parts."""
    if not response.candidates or not response.candidates[0].content:
        return ""
    parts = response.candidates[0].content.parts or []
    text_parts = [part.text.strip() for part in parts if part.text and part.text.strip()]
    return "\n".join(text_parts).strip()


def _chunk_text_for_sse(text: str) -> list[str]:
    """Split text into small chunks for token streaming fallback."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    for idx, word in enumerate(words):
        suffix = " " if idx < len(words) - 1 else ""
        chunks.append(f"{word}{suffix}")
    return chunks


def _history_to_jsonable(history: list[types.Content]) -> list[dict[str, Any]]:
    """Serialize Gemini content history into JSON-safe structures."""
    serialized: list[dict[str, Any]] = []
    for content in history:
        try:
            serialized.append(content.model_dump(exclude_none=True))
        except Exception:
            serialized.append({"role": content.role or "unknown"})
    return serialized


def _response_to_jsonable(response: types.GenerateContentResponse) -> dict[str, Any]:
    """Serialize response for tracing while avoiding unserializable fields."""
    try:
        return response.model_dump(exclude_none=True)
    except Exception:
        return {"text": _extract_response_text(response)}


def _extract_token_usage(
    response: types.GenerateContentResponse,
) -> tuple[int | None, int | None]:
    """Extract input/output token counts from usage metadata when present."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None

    input_candidates = (
        "prompt_token_count",
        "input_token_count",
        "input_tokens",
    )
    output_candidates = (
        "candidates_token_count",
        "output_token_count",
        "output_tokens",
        "completion_token_count",
    )

    input_tokens = None
    for key in input_candidates:
        value = getattr(usage, key, None)
        if value is not None:
            input_tokens = int(value)
            break

    output_tokens = None
    for key in output_candidates:
        value = getattr(usage, key, None)
        if value is not None:
            output_tokens = int(value)
            break

    return input_tokens, output_tokens


async def run_agent_turn(session_id: str, user_message: str, language: str = "es"):
    """Run one agent turn and yield SSE-style events.

    Yields:
        Dicts with shape:
        - {"event": "token", "data": {"text": "..."}}
        - {"event": "tool_call", "data": {"name": "...", "args": {...}}}
        - {"event": "tool_result", "data": {"name": "...", "result": {...}}}
        - {"event": "done", "data": {}}
    """
    if not session_id:
        raise ValueError("session_id is required.")
    if not user_message or not user_message.strip():
        raise ValueError("user_message is required.")

    client, model_name, tools_config = _ensure_runtime_ready()
    history = _get_session_history(session_id)
    _get_session_transcript(session_id)
    state = _get_session_state(session_id)
    lang = normalize_language(language or state.get("language"))
    state["language"] = lang

    config = types.GenerateContentConfig(
        system_instruction=get_system_prompt(lang),
        tools=tools_config,
    )
    reason_hint = _classify_chargeback_reason_hint(user_message)
    routing_hint = _build_routing_hint(reason_hint, lang)
    user_parts = [types.Part.from_text(text=user_message)]
    if routing_hint:
        user_parts.append(types.Part.from_text(text=routing_hint))
    history.append(types.Content(role="user", parts=user_parts))
    state["last_reason_hint"] = reason_hint
    _append_transcript_entry(session_id, "user", user_message.strip())
    trace = start_trace(session_id=session_id, user_message=user_message)
    log_user_turn(trace, user_message)

    if _looks_like_cancellation(user_message):
        cancellation_text = msg(lang, "cancellation_text")
        if state.get("chargeback_flow_cancelled"):
            _append_transcript_entry(session_id, "agent", cancellation_text)
            for chunk in _chunk_text_for_sse(cancellation_text):
                yield {"event": "token", "data": {"text": chunk}}
            try:
                trace.update(output={"final_response_text": cancellation_text})
            except Exception:
                pass
            flush_traces()
            yield {"event": "done", "data": {}}
            return

        cancellation_args: dict[str, Any] = {
            "cancellation_reason": _infer_cancellation_reason(user_message, lang),
            "language": lang,
        }
        transaction_id = _get_session_state(session_id).get("transaction_id")
        if transaction_id:
            cancellation_args["transaction_id"] = transaction_id

        yield {
            "event": "tool_call",
            "data": {
                "name": "cancel_chargeback_request",
                "args": cancellation_args,
            },
        }
        tool_start = time.perf_counter()
        cancellation_result = _execute_tool_call(
            "cancel_chargeback_request",
            cancellation_args,
            history,
            session_id,
        )
        tool_latency_ms = (time.perf_counter() - tool_start) * 1000.0
        log_tool_call(
            trace_obj=trace,
            tool_name="cancel_chargeback_request",
            input_args=cancellation_args,
            output=cancellation_result,
            latency_ms=tool_latency_ms,
        )
        yield {
            "event": "tool_result",
            "data": {"name": "cancel_chargeback_request", "result": cancellation_result},
        }

        state["chargeback_flow_cancelled"] = True
        _append_transcript_entry(session_id, "agent", cancellation_text)
        for chunk in _chunk_text_for_sse(cancellation_text):
            yield {"event": "token", "data": {"text": chunk}}

        try:
            trace.update(output={"final_response_text": cancellation_text})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    if state.get("awaiting_transaction_confirmation"):
        if _looks_like_continue_confirmation(user_message):
            state["awaiting_transaction_confirmation"] = False
            state["awaiting_cost_warning_confirmation"] = True
            warning_text = msg(lang, "cost_warning_text")
            _append_transcript_entry(session_id, "agent", warning_text)
            for chunk in _chunk_text_for_sse(warning_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
            }
        else:
            reminder_text = msg(lang, "reminder_confirm_transaction")
            _append_transcript_entry(session_id, "agent", reminder_text)
            for chunk in _chunk_text_for_sse(reminder_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
            }

        try:
            trace.update(output={"final_response_text": _last_agent_message(session_id) or ""})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    if state.get("awaiting_cost_warning_confirmation"):
        if _looks_like_continue_confirmation(user_message):
            state["awaiting_cost_warning_confirmation"] = False
            state["awaiting_optional_info"] = True
            optional_info_text = msg(lang, "optional_info_prompt_text")
            _append_transcript_entry(session_id, "agent", optional_info_text)
            for chunk in _chunk_text_for_sse(optional_info_text):
                yield {"event": "token", "data": {"text": chunk}}
        else:
            reminder_text = msg(lang, "reminder_continue_or_cancel")
            _append_transcript_entry(session_id, "agent", reminder_text)
            for chunk in _chunk_text_for_sse(reminder_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
            }

        try:
            trace.update(output={"final_response_text": _last_agent_message(session_id) or ""})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    if _is_optional_info_follow_up(session_id):
        state["awaiting_optional_info"] = False
        create_ticket_args: dict[str, Any] = {
            "reason_code": "unknown_transaction",
            "reason_label_es": CANONICAL_REASON_LABEL_ES,
            "user_additional_info": _extract_additional_info(user_message),
        }
        if state.get("transaction_id"):
            create_ticket_args["transaction_id"] = state["transaction_id"]

        yield {
            "event": "tool_call",
            "data": {
                "name": "create_chargeback_ticket",
                "args": create_ticket_args,
            },
        }
        tool_start = time.perf_counter()
        create_ticket_result = _execute_tool_call(
            "create_chargeback_ticket",
            create_ticket_args,
            history,
            session_id,
        )
        tool_latency_ms = (time.perf_counter() - tool_start) * 1000.0
        log_tool_call(
            trace_obj=trace,
            tool_name="create_chargeback_ticket",
            input_args=create_ticket_args,
            output=create_ticket_result,
            latency_ms=tool_latency_ms,
        )
        yield {
            "event": "tool_result",
            "data": {"name": "create_chargeback_ticket", "result": create_ticket_result},
        }
        _schedule_rules_summary_from_tool_result(create_ticket_result, lang)

        final_text = _build_ticket_confirmation_text(create_ticket_result, lang)
        _append_transcript_entry(session_id, "agent", final_text)
        for chunk in _chunk_text_for_sse(final_text):
            yield {"event": "token", "data": {"text": chunk}}

        try:
            trace.update(output={"final_response_text": final_text})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    selected_transaction_id = _extract_selected_transaction_id(user_message)
    if selected_transaction_id:
        if not _is_latest_search_candidate(state, selected_transaction_id):
            stale_selection_text = msg(lang, "stale_selection")
            _append_transcript_entry(session_id, "agent", stale_selection_text)
            for chunk in _chunk_text_for_sse(stale_selection_text):
                yield {"event": "token", "data": {"text": chunk}}
            try:
                trace.update(output={"final_response_text": stale_selection_text})
            except Exception:
                pass
            flush_traces()
            yield {"event": "done", "data": {}}
            return

        context_args = {"transaction_id": selected_transaction_id}
        yield {
            "event": "tool_call",
            "data": {
                "name": "get_transaction_context",
                "args": context_args,
            },
        }
        tool_start = time.perf_counter()
        context_result = _execute_tool_call(
            "get_transaction_context",
            context_args,
            history,
            session_id,
        )
        tool_latency_ms = (time.perf_counter() - tool_start) * 1000.0
        log_tool_call(
            trace_obj=trace,
            tool_name="get_transaction_context",
            input_args=context_args,
            output=context_result,
            latency_ms=tool_latency_ms,
        )
        yield {
            "event": "tool_result",
            "data": {"name": "get_transaction_context", "result": context_result},
        }

        payload = context_result.get("result")
        transaction = payload.get("transaction") if isinstance(payload, dict) else None
        if not isinstance(transaction, dict):
            invalid_context_text = msg(lang, "invalid_context_after_selection")
            state["awaiting_transaction_confirmation"] = False
            state["awaiting_cost_warning_confirmation"] = False
            state["awaiting_optional_info"] = False
            _append_transcript_entry(session_id, "agent", invalid_context_text)
            for chunk in _chunk_text_for_sse(invalid_context_text):
                yield {"event": "token", "data": {"text": chunk}}
            try:
                trace.update(output={"final_response_text": invalid_context_text})
            except Exception:
                pass
            flush_traces()
            yield {"event": "done", "data": {}}
            return

        deterministic_confirmation = _build_transaction_confirmation_text(context_result, lang)
        state["awaiting_transaction_confirmation"] = True
        state["awaiting_cost_warning_confirmation"] = False
        state["awaiting_optional_info"] = False
        yield {
            "event": "quick_replies",
            "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
        }
        _append_transcript_entry(session_id, "agent", deterministic_confirmation)
        for chunk in _chunk_text_for_sse(deterministic_confirmation):
            yield {"event": "token", "data": {"text": chunk}}
        try:
            trace.update(output={"final_response_text": deterministic_confirmation})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    extracted_slots = _extract_transaction_search_slots(user_message)
    merged_slots = _merge_transaction_search_slots(state, extracted_slots) if extracted_slots else state.get(
        "search_slots", {}
    )
    has_new_amount_hint = isinstance(extracted_slots.get("amount_value"), (int, float))
    if has_new_amount_hint and isinstance(merged_slots, dict) and _search_slots_have_amount(merged_slots):
        search_args = _build_search_transactions_args_from_slots(merged_slots)
        state["awaiting_transaction_confirmation"] = False
        state["awaiting_cost_warning_confirmation"] = False
        state["awaiting_optional_info"] = False

        yield {
            "event": "tool_call",
            "data": {
                "name": "search_transactions",
                "args": search_args,
            },
        }
        tool_start = time.perf_counter()
        search_result = _execute_tool_call(
            "search_transactions",
            search_args,
            history,
            session_id,
        )
        tool_latency_ms = (time.perf_counter() - tool_start) * 1000.0
        log_tool_call(
            trace_obj=trace,
            tool_name="search_transactions",
            input_args=search_args,
            output=search_result,
            latency_ms=tool_latency_ms,
        )
        yield {
            "event": "tool_result",
            "data": {"name": "search_transactions", "result": search_result},
        }
        transaction_choices = _build_transaction_quick_replies(search_result, lang)
        deterministic_search_text = _build_transaction_selection_text(search_result, lang)
        if transaction_choices:
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(transaction_choices, "transaction_selection"),
            }
        _append_transcript_entry(session_id, "agent", deterministic_search_text)
        for chunk in _chunk_text_for_sse(deterministic_search_text):
            yield {"event": "token", "data": {"text": chunk}}
        try:
            trace.update(output={"final_response_text": deterministic_search_text})
        except Exception:
            pass
        flush_traces()
        yield {"event": "done", "data": {}}
        return

    response_text = ""
    while True:
        llm_start = time.perf_counter()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=history,
            config=config,
        )
        llm_latency_ms = (time.perf_counter() - llm_start) * 1000.0

        if response.candidates and response.candidates[0].content:
            history.append(response.candidates[0].content)

        input_tokens, output_tokens = _extract_token_usage(response)
        log_llm_call(
            trace_obj=trace,
            prompt=_history_to_jsonable(history),
            response=_response_to_jsonable(response),
            model=model_name,
            latency_ms=llm_latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        response_text = _extract_response_text(response)

        finish_reason = None
        if response.candidates:
            finish_reason = getattr(response.candidates[0], "finish_reason", None)
        finish_reason_name = str(getattr(finish_reason, "value", finish_reason) or "")

        function_calls = response.function_calls or []
        if not function_calls:
            if response_text:
                _append_transcript_entry(session_id, "agent", response_text)
            for chunk in _chunk_text_for_sse(response_text):
                yield {"event": "token", "data": {"text": chunk}}

            if _response_mentions_reason_menu(response_text):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(reason_choices(lang), "reason_selection"),
                }
            if _response_requests_continue_confirmation(response_text, lang):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
                }

            if not response_text and finish_reason_name == "MALFORMED_FUNCTION_CALL":
                response_text = msg(lang, "malformed_function_call")
                _append_transcript_entry(session_id, "agent", response_text)
                for chunk in _chunk_text_for_sse(response_text):
                    yield {"event": "token", "data": {"text": chunk}}
            break

        deterministic_turn_text: str | None = None
        end_turn_after_tool_response = False
        tool_response_parts: list[types.Part] = []
        for function_call in function_calls:
            tool_name = function_call.name or ""
            args = dict(function_call.args or {})

            if tool_name == "get_transaction_context":
                transaction_id = args.get("transaction_id")
                if not _is_latest_search_candidate(state, transaction_id):
                    blocked_context_result = {"error": "transaction_not_in_latest_candidates"}
                    yield {"event": "tool_call", "data": {"name": tool_name, "args": args}}
                    yield {
                        "event": "tool_result",
                        "data": {"name": tool_name, "result": blocked_context_result},
                    }
                    deterministic_turn_text = msg(lang, "blocked_context_tool")
                    state["awaiting_transaction_confirmation"] = False
                    state["awaiting_cost_warning_confirmation"] = False
                    state["awaiting_optional_info"] = False
                    end_turn_after_tool_response = True
                    break

            yield {"event": "tool_call", "data": {"name": tool_name, "args": args}}
            tool_start = time.perf_counter()
            tool_result = _execute_tool_call(tool_name, args, history, session_id)
            tool_latency_ms = (time.perf_counter() - tool_start) * 1000.0
            log_tool_call(
                trace_obj=trace,
                tool_name=tool_name,
                input_args=args,
                output=tool_result,
                latency_ms=tool_latency_ms,
            )
            yield {
                "event": "tool_result",
                "data": {"name": tool_name, "result": tool_result},
            }
            if tool_name == "create_chargeback_ticket":
                _schedule_rules_summary_from_tool_result(tool_result, lang)
            if tool_name == "search_transactions":
                transaction_choices = _build_transaction_quick_replies(tool_result, lang)
                deterministic_turn_text = _build_transaction_selection_text(tool_result, lang)
                state["awaiting_transaction_confirmation"] = False
                state["awaiting_cost_warning_confirmation"] = False
                state["awaiting_optional_info"] = False
                if transaction_choices:
                    yield {
                        "event": "quick_replies",
                        "data": _build_quick_reply_payload(
                            transaction_choices,
                            "transaction_selection",
                        ),
                    }
                end_turn_after_tool_response = True
                break
            if tool_name == "get_transaction_context":
                payload = tool_result.get("result")
                transaction = payload.get("transaction") if isinstance(payload, dict) else None
                if isinstance(transaction, dict):
                    deterministic_turn_text = _build_transaction_confirmation_text(tool_result, lang)
                    state["awaiting_transaction_confirmation"] = True
                    state["awaiting_cost_warning_confirmation"] = False
                    state["awaiting_optional_info"] = False
                    yield {
                        "event": "quick_replies",
                        "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
                    }
                else:
                    deterministic_turn_text = msg(lang, "invalid_context_tool_result")
                    state["awaiting_transaction_confirmation"] = False
                    state["awaiting_cost_warning_confirmation"] = False
                    state["awaiting_optional_info"] = False
                end_turn_after_tool_response = True
                break
            tool_response_parts.append(
                types.Part.from_function_response(name=tool_name, response=tool_result)
            )

        final_response_text = deterministic_turn_text or response_text
        if final_response_text:
            _append_transcript_entry(session_id, "agent", final_response_text)
        for chunk in _chunk_text_for_sse(final_response_text):
            yield {"event": "token", "data": {"text": chunk}}

        if not end_turn_after_tool_response:
            if _response_mentions_reason_menu(response_text):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(reason_choices(lang), "reason_selection"),
                }
            if _response_requests_continue_confirmation(response_text, lang):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(continue_choices(lang), "continue_confirmation"),
                }

        response_text = final_response_text
        if end_turn_after_tool_response:
            break
        history.append(types.Content(role="user", parts=tool_response_parts))

    try:
        trace.update(output={"final_response_text": response_text})
    except Exception:
        pass
    flush_traces()
    yield {"event": "done", "data": {}}


def run_agent_loop_console() -> None:
    """Run a multi-turn console REPL with Gemini and real tool execution."""
    _ensure_runtime_ready()
    console_session_id = "__console__"
    reset_session(console_session_id)
    console_lang = normalize_language(os.getenv("AGENT_CONSOLE_LANGUAGE", "es"))

    print(msg(console_lang, "repl_greeting"))
    print(msg(console_lang, "repl_exit_hint"))

    while True:
        try:
            user_text = input(f"{msg(console_lang, 'repl_you')}: ").strip()
        except EOFError:
            print(f"\n{msg(console_lang, 'repl_goodbye')}")
            break
        if user_text.lower() in {"salir", "exit", "quit"}:
            print(msg(console_lang, "repl_goodbye"))
            break
        if not user_text:
            continue

        async def _consume_turn() -> None:
            text_chunks: list[str] = []
            async for event in run_agent_turn(console_session_id, user_text, language=console_lang):
                if event["event"] == "token":
                    text_chunks.append(event["data"]["text"])
                elif event["event"] == "tool_call":
                    print(_format_tool_call(event["data"]["name"], event["data"]["args"]))
                elif event["event"] == "done":
                    text = "".join(text_chunks).strip()
                    if text:
                        prefix = "Agente" if console_lang == "es" else "Agent"
                        print(f"{prefix}: {text}")

            return None

        asyncio.run(_consume_turn())


if __name__ == "__main__":
    run_agent_loop_console()
