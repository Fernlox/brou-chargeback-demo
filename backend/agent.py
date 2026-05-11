"""Agent runtime for console and SSE chat streaming."""

from __future__ import annotations

import json
import os
import inspect
import asyncio
import time
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types

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

COST_WARNING_TEXT = (
    "IMPORTANTE\n"
    "Iniciar un reclamo de contracargo es un proceso formal.\n"
    "Si el reclamo se resuelve a favor del comercio, podrías incurrir en costos "
    "administrativos según el reglamento vigente de BROU.\n"
    "¿Confirmás que querés continuar?"
)

OPTIONAL_INFO_PROMPT_TEXT = (
    "¿Querés agregar algún detalle adicional sobre este cargo antes de crear el reclamo?\n"
    "Si no tenés nada más para agregar, escribí 'continuar'."
)

REASON_CHOICES: list[dict[str, str]] = [
    {
        "id": "reason_unknown_transaction",
        "label": "Desconocimiento de transacciones (no reconozco un cargo)",
        "value": "Desconocimiento de transacciones (no reconozco un cargo)",
    },
    {
        "id": "reason_not_received",
        "label": "No recibí el servicio o la mercadería",
        "value": "No recibí el servicio o la mercadería",
    },
    {
        "id": "reason_duplicate",
        "label": "Compra o retiro duplicado",
        "value": "Compra o retiro duplicado",
    },
    {
        "id": "reason_processing_error",
        "label": "Error de procesamiento (la transacción dio error pero igual se procesó)",
        "value": "Error de procesamiento (la transacción dio error pero igual se procesó)",
    },
]

CONTINUE_CHOICES: list[dict[str, str]] = [
    {
        "id": "continue_yes",
        "label": "Sí, quiero seguir adelante",
        "value": "Sí, quiero seguir adelante",
    },
    {
        "id": "continue_no",
        "label": "No, prefiero cancelar",
        "value": "No, prefiero cancelar",
    },
]

SYSTEM_PROMPT = f"""
Sos el Asistente de Reclamos de BROU.
Hablás en español rioplatense (uruguayo), usando "vos", "podés" y tono cordial,
formal pero cercano.

REGLAS CRITICAS:
1) Tu primer mensaje SIEMPRE debe ser una pregunta abierta y NO debe mencionar
   motivos de contracargo. Ejemplo: "Hola, soy el asistente de BROU. ¿En qué te
   puedo ayudar?"
2) Clasificá internamente el primer mensaje del usuario:
   - chargeback_intent: cargos no reconocidos, movimientos raros, reclamo de tarjeta.
   - other: saldos, sucursales, préstamos u otros temas.
3) Si es "other", derivá amablemente a asistencia.brou.com.uy o WhatsApp 21996000
   y no continúes el flujo de reclamo. No llames tools ni crees tickets en este caso.
4) Si es "chargeback_intent", decidí si el motivo ya está claro:
   - Si el usuario ya describe claramente "Desconocimiento de transacciones"
     (ej. "no reconozco el cargo", "cargo equivocado", "movimiento raro", "esa compra no la hice"),
     tomalo como motivo confirmado y pasá directo al paso 2 (Identificar transacción).
   - Solo si el motivo está ambiguo o genérico, presentá estas 4 opciones de motivo:
   1. Desconocimiento de transacciones (no reconozco un cargo)
   2. No recibí el servicio o la mercadería
   3. Compra o retiro duplicado
   4. Error de procesamiento (la transacción dio error pero igual se procesó)
5) En esta demo SOLO está implementado el flujo "Desconocimiento de transacciones".
6) Solo continuá el flujo si el motivo es "Desconocimiento de transacciones" (ya sea por confirmación
   explícita o por detección clara en el mensaje del usuario).
7) Si el usuario elige motivo 2, 3 o 4, respondé exactamente:
   "Por ahora ese flujo no está disponible en la demo. ¿Querés que volvamos al inicio o necesitás otra cosa?"
   En ese caso no llames tools, no continúes el flujo y no crees ticket.
8) Si luego el usuario reformula y aclara que en realidad es "Desconocimiento de transacciones",
   retomá el flujo en el paso 2 (Identificar transacción).

FLUJO (EN ORDEN):
2) Identificar transacción:
   - Usá search_transactions.
   - Si el monto es aproximado, buscá por aproximación.
   - Mostrá como máximo 5 candidatos.
   - Pedí confirmación explícita de la transacción correcta.
3) Contexto:
   - Usá get_transaction_context.
   - Si aplica, mostrá same_merchant_count_6m y same_merchant_history.
4) Advertencia de costos:
   - Debés mostrar textual este mensaje y esperar confirmación:
   "{COST_WARNING_TEXT}"
5) Pedí información adicional opcional (texto libre).
6) Creá ticket usando create_chargeback_ticket.
7) Tras crear ticket, se debe aplicar apply_rules_and_summarize y cerrar con:
   - número de ticket,
   - mensaje cordial de cierre,
   - sin mostrar recomendaciones internas.

CANCELACION:
- Si el usuario quiere cancelar en cualquier momento (ej. "cancelar", "dejá",
  "no quiero seguir", "olvidate"), confirmá amablemente.
- Usá cancel_chargeback_request con conversation_log completo y un
  cancellation_reason breve inferido del contexto.
- Cerrá el flujo con despedida cordial.

RESTRICCIONES:
- Prohibido dar consejos legales.
- Prohibido prometer resolución favorable.
- Prohibido inventar datos.
- Prohibido saltear la advertencia de costos.
- Si el usuario está enojado, empatizá antes de continuar.
""".strip()

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
_GEMINI_CONFIG: types.GenerateContentConfig | None = None


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
            "properties": {"transaction_id": {"type": "string"}},
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
            },
            "required": ["user_id", "conversation_log", "cancellation_reason"],
        },
        "apply_rules_and_summarize": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
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


def _ensure_runtime_ready() -> tuple[genai.Client, str, types.GenerateContentConfig]:
    """Lazily initialize Gemini runtime dependencies."""
    global _GEMINI_CLIENT, _GEMINI_MODEL, _GEMINI_CONFIG

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")

    if not gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")
    if not gemini_model:
        raise RuntimeError("Missing GEMINI_MODEL in environment.")

    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=gemini_api_key)
    if _GEMINI_CONFIG is None:
        _GEMINI_CONFIG = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=_build_tools_config(),
        )
    _GEMINI_MODEL = gemini_model
    return _GEMINI_CLIENT, _GEMINI_MODEL, _GEMINI_CONFIG


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


def _classify_chargeback_reason_hint(text: str) -> str:
    """Return coarse reason hint: unknown_transaction, other_reason, ambiguous_chargeback, none."""
    normalized = _normalize_text(text)

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
    )
    chargeback_generic_patterns = (
        "cargo",
        "tarjeta",
        "reclamo",
        "contracargo",
        "movimiento",
    )

    if any(pattern in normalized for pattern in other_reason_patterns):
        return "other_reason"
    if any(pattern in normalized for pattern in unknown_patterns):
        return "unknown_transaction"
    if any(pattern in normalized for pattern in chargeback_generic_patterns):
        return "ambiguous_chargeback"
    return "none"


def _build_routing_hint(reason_hint: str) -> str | None:
    """Build internal routing guidance for the model."""
    if reason_hint == "unknown_transaction":
        return (
            "[INTERNAL_ROUTING_HINT] El usuario ya confirmó de forma implícita "
            "el motivo 'Desconocimiento de transacciones'. No pidas menú de 4 motivos. "
            "Continuá directo con identificación de transacción."
        )
    if reason_hint == "other_reason":
        return (
            "[INTERNAL_ROUTING_HINT] El usuario parece estar describiendo un motivo de "
            "contracargo distinto a 'Desconocimiento de transacciones'. Aplicá la respuesta "
            "de flujo no disponible para esta demo."
        )
    return None


def _response_mentions_reason_menu(response_text: str) -> bool:
    """Detect if model answer is presenting the 4 reason options."""
    normalized = _normalize_text(response_text)
    return (
        "desconocimiento de transacciones" in normalized
        and "no recibi el servicio" in normalized
        and "compra o retiro duplicado" in normalized
        and "error de procesamiento" in normalized
    )


def _response_requests_continue_confirmation(response_text: str) -> bool:
    """Detect if model asks explicit continue/cancel confirmation."""
    normalized = _normalize_text(response_text)
    if _normalize_text(COST_WARNING_TEXT) in normalized:
        return True
    return "confirmas que queres continuar" in normalized or "queres seguir adelante" in normalized


def _looks_like_continue_confirmation(text: str) -> bool:
    """Detect user intent to continue while waiting explicit confirmation."""
    normalized = _normalize_text(" ".join(text.strip().split()))
    if not normalized:
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
    )
    if any(phrase in normalized for phrase in explicit_phrases):
        return True

    short_confirmations = {"si", "ok", "dale", "continuar", "confirmo", "de acuerdo"}
    return normalized in short_confirmations


def _build_quick_reply_payload(
    choices: list[dict[str, str]],
    group: str,
) -> dict[str, Any]:
    """Build SSE payload for quick replies."""
    return {"group": group, "choices": choices}


def _build_transaction_quick_replies(tool_result: dict[str, Any]) -> list[dict[str, str]]:
    """Build quick replies for transaction selection from search results."""
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
            if isinstance(card_last4, str) and card_last4.strip()
            else ""
        )
        display_text = f"{date_repr} - {merchant_name} - {currency} {amount_repr}{card_suffix}"
        choices.append(
            {
                "id": f"tx_{transaction_id}",
                "label": display_text,
                "value": f"Selecciono la transacción {transaction_id}",
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

    phrase_keywords = (
        "no quiero seguir",
        "olvidate",
        "olvidate de esto",
        "no quiero continuar",
        "quiero cancelar",
        "prefiero cancelar",
    )
    if any(keyword in normalized for keyword in phrase_keywords):
        return True

    token_keywords = {"cancelar", "cancela", "deja"}
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return any(token in token_keywords for token in tokens)


def _infer_cancellation_reason(user_message: str) -> str:
    """Generate a short cancellation reason from the user text."""
    normalized = " ".join(user_message.strip().split())
    if not normalized:
        return "El usuario solicito cancelar el reclamo."
    if len(normalized) > 140:
        normalized = normalized[:137].rstrip() + "..."
    return f"El usuario solicito cancelar: {normalized}"


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
    return has_optional_info_prompt


def _extract_additional_info(user_message: str) -> str | None:
    """Convert the user's optional-info reply into free text or explicit empty info."""
    compact = " ".join(user_message.strip().split())
    if not compact:
        return None

    normalized = _normalize_text(compact)
    no_info_patterns = (
        "continuar",
        "continua",
        "continuemos",
        "seguir",
        "sigamos",
        "no tengo nada mas para agregar",
        "no tengo nada para agregar",
        "nada mas para agregar",
        "no hay nada mas para agregar",
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


def _build_ticket_confirmation_text(tool_result: dict[str, Any]) -> str:
    """Create the final user-facing closure message after ticket creation."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return (
            "Tu solicitud quedó registrada, pero no pude confirmar el número de ticket "
            "en este momento. Si querés, lo intento de nuevo."
        )

    ticket_number = payload.get("ticket_number")
    if not isinstance(ticket_number, str) or not ticket_number.strip():
        return (
            "Tu solicitud quedó registrada, pero no pude confirmar el número de ticket "
            "en este momento. Si querés, lo intento de nuevo."
        )

    message = (
        f"Perfecto, ya creé el ticket {ticket_number} para tu reclamo. "
        "Guardalo para hacer seguimiento cuando quieras."
    )
    return f"{message}\nGracias por contactarte."


def _format_transaction_date(transaction_at: str) -> str:
    """Format ISO-like transaction timestamp into DD/MM/YYYY."""
    date_raw = transaction_at[:10]
    date_parts = date_raw.split("-")
    if len(date_parts) == 3:
        return f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
    return date_raw


def _build_transaction_confirmation_text(tool_result: dict[str, Any]) -> str:
    """Build deterministic confirmation + deterrence after selected transaction context."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return (
            "Entendido. ¿Confirmás que querés continuar con el reclamo de este cargo?"
        )

    transaction = payload.get("transaction")
    if not isinstance(transaction, dict):
        return (
            "Entendido. ¿Confirmás que querés continuar con el reclamo de este cargo?"
        )

    merchant_name = str(transaction.get("merchant_name") or "comercio no identificado").strip()
    currency = str(transaction.get("currency") or "USD").strip()
    transaction_at = str(transaction.get("transaction_at") or "").strip()
    total_amount = transaction.get("total_amount")

    amount_repr = "?"
    if isinstance(total_amount, (int, float)):
        amount_repr = f"{float(total_amount):.2f}"
    date_repr = _format_transaction_date(transaction_at) if transaction_at else "fecha no disponible"

    message = (
        f"Entendido, es el cargo de {currency} {amount_repr} en {merchant_name} "
        f"del {date_repr}."
    )

    same_merchant_count_6m = payload.get("same_merchant_count_6m")
    has_prior_with_merchant = isinstance(same_merchant_count_6m, int) and same_merchant_count_6m > 0
    if has_prior_with_merchant:
        message = (
            f"{message}\nAntes de seguir, te comento que veo compras previas en este mismo comercio "
            "durante los últimos 6 meses."
        )

    return (
        f"{message}\n"
        "¿Querés continuar con el reclamo de esta transacción?"
    )


def _build_transaction_selection_text(tool_result: dict[str, Any]) -> str:
    """Build deterministic copy for transaction quick-reply turns."""
    payload = tool_result.get("result")
    if not isinstance(payload, dict):
        return (
            "Ok, encontré transacciones. Seleccioná una para continuar o, "
            "si no está acá, dame algún otro detalle del cargo para volver a buscar."
        )

    raw_results = payload.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        return (
            "No encontré transacciones que coincidan con ese detalle. "
            "¿Me compartís algún otro dato del cargo para volver a buscar?"
        )

    merchant_name = ""
    first_result = raw_results[0]
    if isinstance(first_result, dict):
        maybe_merchant = first_result.get("merchant_name")
        if isinstance(maybe_merchant, str):
            merchant_name = maybe_merchant.strip()

    return (
        "Ok, encontré estas transacciones. Seleccioná una para continuar o, "
        "si no está acá, dame algún otro detalle del cargo para volver a buscar."
    )


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

    if tool_name == "search_transactions":
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
            transaction_id = _get_session_state(session_id).get("transaction_id")
            if transaction_id:
                args["transaction_id"] = transaction_id
        if args.get("reason_code") != "unknown_transaction":
            args["reason_code"] = "unknown_transaction"
        args.setdefault("reason_label_es", "Desconocimiento de transacciones")
        args.setdefault("user_additional_info", None)
        args.setdefault("status", "open")
        args.setdefault("resolved_by", None)

    if tool_name == "cancel_chargeback_request":
        if not args.get("user_id") or args.get("user_id") == "DEMO_USER_ID":
            args["user_id"] = os.getenv("DEMO_USER_ID")

    if tool_name in {"create_chargeback_ticket", "cancel_chargeback_request"}:
        args.setdefault("conversation_log", _snapshot_transcript(session_id))

    if tool_name == "get_transaction_context" and args.get("transaction_id"):
        _get_session_state(session_id)["transaction_id"] = args.get("transaction_id")

    args_for_log = {key: value for key, value in args.items() if key != "conversation_log"}
    tool_call_repr = _format_tool_call(tool_name, args_for_log)
    _append_transcript_entry(session_id, "tool", f"CALL {tool_call_repr}")

    try:
        if tool_name == "create_chargeback_ticket":
            ticket_payload = fn(**args)
            ticket_id = ticket_payload.get("ticket_id")
            if ticket_id:
                rules_payload = apply_rules_and_summarize(ticket_id=ticket_id)
                ticket_payload = {
                    **ticket_payload,
                    "agent_summary": rules_payload.get("summary"),
                    "agent_recommendation": rules_payload.get("recommendation"),
                }
            if args.get("transaction_id"):
                _get_session_state(session_id)["transaction_id"] = args.get("transaction_id")
            _append_transcript_entry(
                session_id,
                "tool",
                f"RESULT {tool_name}: {json.dumps(ticket_payload, ensure_ascii=False, default=str)}",
            )
            return {"result": ticket_payload}

        tool_payload = fn(**args)
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


async def run_agent_turn(session_id: str, user_message: str):
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

    client, model_name, config = _ensure_runtime_ready()
    history = _get_session_history(session_id)
    _get_session_transcript(session_id)
    reason_hint = _classify_chargeback_reason_hint(user_message)
    routing_hint = _build_routing_hint(reason_hint)
    user_parts = [types.Part.from_text(text=user_message)]
    if routing_hint:
        user_parts.append(types.Part.from_text(text=routing_hint))
    history.append(types.Content(role="user", parts=user_parts))
    state = _get_session_state(session_id)
    state["last_reason_hint"] = reason_hint
    _append_transcript_entry(session_id, "user", user_message.strip())
    trace = start_trace(session_id=session_id, user_message=user_message)
    log_user_turn(trace, user_message)

    if _looks_like_cancellation(user_message):
        cancellation_text = (
            "Perfecto, ya cancelé el proceso de reclamo. "
            "Si querés, más adelante lo retomamos juntos. "
            "Gracias por contactarte."
        )
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
            "cancellation_reason": _infer_cancellation_reason(user_message),
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
            warning_text = COST_WARNING_TEXT
            _append_transcript_entry(session_id, "agent", warning_text)
            for chunk in _chunk_text_for_sse(warning_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
            }
        else:
            reminder_text = (
                "Para avanzar, necesito que me confirmes si querés seguir con esta transacción."
            )
            _append_transcript_entry(session_id, "agent", reminder_text)
            for chunk in _chunk_text_for_sse(reminder_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
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
            optional_info_text = OPTIONAL_INFO_PROMPT_TEXT
            _append_transcript_entry(session_id, "agent", optional_info_text)
            for chunk in _chunk_text_for_sse(optional_info_text):
                yield {"event": "token", "data": {"text": chunk}}
        else:
            reminder_text = (
                "Para seguir, confirmame si querés continuar o preferís cancelar."
            )
            _append_transcript_entry(session_id, "agent", reminder_text)
            for chunk in _chunk_text_for_sse(reminder_text):
                yield {"event": "token", "data": {"text": chunk}}
            yield {
                "event": "quick_replies",
                "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
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
            "reason_label_es": "Desconocimiento de transacciones",
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

        final_text = _build_ticket_confirmation_text(create_ticket_result)
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
                    "data": _build_quick_reply_payload(REASON_CHOICES, "reason_selection"),
                }
            if _response_requests_continue_confirmation(response_text):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
                }

            if not response_text and finish_reason_name == "MALFORMED_FUNCTION_CALL":
                response_text = (
                    "Tuve un inconveniente técnico para procesar este paso. "
                    "¿Podés escribir 'continuar' y lo intento de nuevo?"
                )
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
            if tool_name == "search_transactions":
                transaction_choices = _build_transaction_quick_replies(tool_result)
                deterministic_turn_text = _build_transaction_selection_text(tool_result)
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
                deterministic_turn_text = _build_transaction_confirmation_text(tool_result)
                state["awaiting_transaction_confirmation"] = True
                state["awaiting_cost_warning_confirmation"] = False
                state["awaiting_optional_info"] = False
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
                }
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
                    "data": _build_quick_reply_payload(REASON_CHOICES, "reason_selection"),
                }
            if _response_requests_continue_confirmation(response_text):
                yield {
                    "event": "quick_replies",
                    "data": _build_quick_reply_payload(CONTINUE_CHOICES, "continue_confirmation"),
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

    print("Agente: Hola, soy el asistente de BROU. ¿En qué te puedo ayudar?")
    print("Escribí 'salir' para terminar.")

    while True:
        try:
            user_text = input("Vos: ").strip()
        except EOFError:
            print("\nAgente: Gracias por contactarte. Quedo a las órdenes.")
            break
        if user_text.lower() in {"salir", "exit", "quit"}:
            print("Agente: Gracias por contactarte. Quedo a las órdenes.")
            break
        if not user_text:
            continue

        async def _consume_turn() -> None:
            text_chunks: list[str] = []
            async for event in run_agent_turn(console_session_id, user_text):
                if event["event"] == "token":
                    text_chunks.append(event["data"]["text"])
                elif event["event"] == "tool_call":
                    print(_format_tool_call(event["data"]["name"], event["data"]["args"]))
                elif event["event"] == "done":
                    text = "".join(text_chunks).strip()
                    if text:
                        print(f"Agente: {text}")

            return None

        asyncio.run(_consume_turn())


if __name__ == "__main__":
    run_agent_loop_console()
