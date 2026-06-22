"""Localized copy and prompts for chat/runtime flows."""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = {"es", "en"}
DEFAULT_LANGUAGE = "es"
CANONICAL_REASON_LABEL_ES = "Desconocimiento de transacciones"

_MESSAGES: dict[str, dict[str, str]] = {
    "es": {
        "cost_warning_text": (
            "IMPORTANTE\n"
            "Iniciar un reclamo de contracargo es un proceso formal.\n"
            "Si el reclamo se resuelve a favor del comercio, podrias incurrir en costos "
            "administrativos segun el reglamento vigente de BROU.\n"
            "¿Confirmas que queres continuar?"
        ),
        "optional_info_prompt_text": (
            "¿Queres agregar algun detalle adicional sobre este cargo antes de crear el reclamo?\n"
            "Si no tenes nada mas para agregar, escribi 'continuar'."
        ),
        "routing_hint_unknown": (
            "[INTERNAL_ROUTING_HINT] El usuario ya confirmo de forma implicita "
            "el motivo 'Desconocimiento de transacciones'. No pidas menu de 4 motivos. "
            "Continua directo con identificacion de transaccion."
        ),
        "routing_hint_other": (
            "[INTERNAL_ROUTING_HINT] El usuario parece estar describiendo un motivo de "
            "contracargo distinto a 'Desconocimiento de transacciones'. Aplica la respuesta "
            "de flujo no disponible para esta demo."
        ),
        "cancellation_text": (
            "Perfecto, ya cancele el proceso de reclamo. "
            "Si queres, mas adelante lo retomamos juntos. "
            "Gracias por contactarte."
        ),
        "cancellation_reason_empty": "El usuario solicito cancelar el reclamo.",
        "cancellation_reason_prefix": "El usuario solicito cancelar: {message}",
        "ticket_confirmation_missing": (
            "Tu solicitud quedo registrada, pero no pude confirmar el numero de ticket "
            "en este momento. Si queres, lo intento de nuevo."
        ),
        "ticket_confirmation_success": (
            "Perfecto, ya cree el ticket {ticket_number} para tu reclamo. "
            "Guardalo para hacer seguimiento cuando quieras."
        ),
        "thanks": "Gracias por contactarte.",
        "transaction_context_missing": (
            "No pude validar esa transaccion con la informacion disponible. "
            "¿Me compartis un dato mas para volver a buscar?"
        ),
        "transaction_context_invalid": (
            "No encontre contexto valido para esa transaccion. "
            "¿Me compartis otro dato del cargo para volver a buscar?"
        ),
        "merchant_fallback": "comercio no identificado",
        "date_unavailable": "fecha no disponible",
        "tx_confirm_intro": "Entendido, es el cargo de {currency} {amount} en {merchant} del {date}.",
        "tx_confirm_display_name": "Figura con el nombre comercial {name}.",
        "tx_confirm_location": "La compra aparece ubicada en {location}.",
        "tx_confirm_business_type": "Parece ser un consumo de tipo {business_type}.",
        "tx_confirm_card": "Se realizo con la {card_used}.",
        "tx_confirm_channel": "Se registro como compra {purchase_channel}.",
        "tx_confirm_prior_count": (
            "Ademas, veo {count} compra(s) previa(s) en este comercio durante los ultimos 6 meses."
        ),
        "tx_confirm_ask_continue": "¿Queres continuar con el reclamo de esta transaccion?",
        "tx_selection_fallback": (
            "Ok, encontre transacciones. Selecciona una para continuar o, "
            "si no esta aca, dame algun otro detalle del cargo para volver a buscar."
        ),
        "tx_selection_no_results": (
            "No encontre transacciones que coincidan con ese detalle. "
            "¿Me compartis algun otro dato del cargo para volver a buscar?"
        ),
        "tx_selection_found": (
            "Ok, encontre estas transacciones. Selecciona una para continuar o, "
            "si no esta aca, dame algun otro detalle del cargo para volver a buscar."
        ),
        "reminder_confirm_transaction": (
            "Para avanzar, necesito que me confirmes si queres seguir con esta transaccion."
        ),
        "reminder_continue_or_cancel": "Para seguir, confirmame si queres continuar o preferis cancelar.",
        "stale_selection": (
            "No pude validar esa opcion con la ultima busqueda. "
            "¿Queres que volvamos a buscar el cargo con fecha y monto?"
        ),
        "invalid_context_after_selection": (
            "No pude recuperar el contexto de esa transaccion. "
            "¿Me compartis otro dato del cargo para volver a buscar?"
        ),
        "malformed_function_call": (
            "Tuve un inconveniente tecnico para procesar este paso. "
            "¿Podes escribir 'continuar' y lo intento de nuevo?"
        ),
        "blocked_context_tool": (
            "Necesito que selecciones una transaccion de la ultima busqueda para continuar. "
            "Si no la ves, pasame otro dato y la busco de nuevo."
        ),
        "invalid_context_tool_result": (
            "No encontre una transaccion valida para ese contexto. "
            "¿Me compartis otro dato del cargo para volver a buscar?"
        ),
        "internal_error_turn": "Ocurrio un error interno al procesar el turno.",
        "repl_greeting": "Agente: Hola, soy el asistente de BROU. ¿En que te puedo ayudar?",
        "repl_exit_hint": "Escribi 'salir' para terminar.",
        "repl_goodbye": "Agente: Gracias por contactarte. Quedo a las ordenes.",
        "repl_you": "Vos",
    },
    "en": {
        "cost_warning_text": (
            "IMPORTANT\n"
            "Starting a chargeback claim is a formal process.\n"
            "If the claim is resolved in favor of the merchant, you may incur "
            "administrative costs according to BROU's current regulations.\n"
            "Do you confirm you want to continue?"
        ),
        "optional_info_prompt_text": (
            "Would you like to add any additional details about this charge before creating the claim?\n"
            "If you do not have anything else to add, type 'continue'."
        ),
        "routing_hint_unknown": (
            "[INTERNAL_ROUTING_HINT] The user already implicitly confirmed the reason "
            "'Unknown transaction'. Do not show the 4-reason menu. Continue directly "
            "to transaction identification."
        ),
        "routing_hint_other": (
            "[INTERNAL_ROUTING_HINT] The user appears to describe a chargeback reason "
            "different from 'Unknown transaction'. Use the unavailable-flow response "
            "for this demo."
        ),
        "cancellation_text": (
            "Understood, I have cancelled the claim process. "
            "If you want, we can resume it later. "
            "Thank you for contacting us."
        ),
        "cancellation_reason_empty": "The user requested cancelling the claim.",
        "cancellation_reason_prefix": "The user requested cancellation: {message}",
        "ticket_confirmation_missing": (
            "Your request was registered, but I could not confirm the ticket number right now. "
            "If you want, I can try again."
        ),
        "ticket_confirmation_success": (
            "Done, I created ticket {ticket_number} for your claim. "
            "Please keep it to track the case whenever you need."
        ),
        "thanks": "Thank you for contacting us.",
        "transaction_context_missing": (
            "I could not validate that transaction with the available information. "
            "Can you share one more detail so I can search again?"
        ),
        "transaction_context_invalid": (
            "I could not find valid context for that transaction. "
            "Can you share another charge detail so I can search again?"
        ),
        "merchant_fallback": "unknown merchant",
        "date_unavailable": "date unavailable",
        "tx_confirm_intro": "Understood, this is the {currency} {amount} charge at {merchant} on {date}.",
        "tx_confirm_display_name": "It appears with the commercial name {name}.",
        "tx_confirm_location": "The purchase appears located in {location}.",
        "tx_confirm_business_type": "It appears to be a {business_type} purchase.",
        "tx_confirm_card": "It was made with {card_used}.",
        "tx_confirm_channel": "It was registered as an {purchase_channel} purchase.",
        "tx_confirm_prior_count": (
            "Also, I can see {count} prior purchase(s) at this merchant in the last 6 months."
        ),
        "tx_confirm_ask_continue": "Do you want to continue with the claim for this transaction?",
        "tx_selection_fallback": (
            "Ok, I found transactions. Select one to continue or, "
            "if it is not here, share another charge detail and I will search again."
        ),
        "tx_selection_no_results": (
            "I could not find transactions that match that detail. "
            "Can you share another charge detail so I can search again?"
        ),
        "tx_selection_found": (
            "Ok, I found these transactions. Select one to continue or, "
            "if it is not here, share another charge detail and I will search again."
        ),
        "reminder_confirm_transaction": (
            "To move forward, I need you to confirm whether you want to continue with this transaction."
        ),
        "reminder_continue_or_cancel": "To continue, please confirm if you want to proceed or cancel.",
        "stale_selection": (
            "I could not validate that option with the latest search. "
            "Do you want us to search for the charge again using date and amount?"
        ),
        "invalid_context_after_selection": (
            "I could not retrieve context for that transaction. "
            "Can you share another charge detail so I can search again?"
        ),
        "malformed_function_call": (
            "I had a technical issue processing this step. "
            "Can you type 'continue' so I can try again?"
        ),
        "blocked_context_tool": (
            "I need you to select a transaction from the latest search to continue. "
            "If you do not see it, share another detail and I will search again."
        ),
        "invalid_context_tool_result": (
            "I did not find a valid transaction for that context. "
            "Can you share another charge detail so I can search again?"
        ),
        "internal_error_turn": "An internal error occurred while processing the turn.",
        "repl_greeting": "Agent: Hi, I am BROU's assistant. How can I help you?",
        "repl_exit_hint": "Type 'exit' to finish.",
        "repl_goodbye": "Agent: Thank you for contacting us. Have a great day.",
        "repl_you": "You",
    },
}

_REASON_CHOICES: dict[str, list[dict[str, str]]] = {
    "es": [
        {
            "id": "reason_unknown_transaction",
            "label": "Desconocimiento de transacciones (no reconozco un cargo)",
            "value": "reason:unknown_transaction",
        },
        {
            "id": "reason_not_received",
            "label": "No recibi el servicio o la mercaderia",
            "value": "reason:not_received",
        },
        {
            "id": "reason_duplicate",
            "label": "Compra o retiro duplicado",
            "value": "reason:duplicate",
        },
        {
            "id": "reason_processing_error",
            "label": "Error de procesamiento (la transaccion dio error pero igual se proceso)",
            "value": "reason:processing_error",
        },
    ],
    "en": [
        {
            "id": "reason_unknown_transaction",
            "label": "Unknown transaction (I do not recognize a charge)",
            "value": "reason:unknown_transaction",
        },
        {
            "id": "reason_not_received",
            "label": "I did not receive the service or goods",
            "value": "reason:not_received",
        },
        {
            "id": "reason_duplicate",
            "label": "Duplicate purchase or withdrawal",
            "value": "reason:duplicate",
        },
        {
            "id": "reason_processing_error",
            "label": "Processing error (the transaction failed but was still processed)",
            "value": "reason:processing_error",
        },
    ],
}

_CONTINUE_CHOICES: dict[str, list[dict[str, str]]] = {
    "es": [
        {"id": "continue_yes", "label": "Si, quiero seguir adelante", "value": "continue:yes"},
        {"id": "continue_no", "label": "No, prefiero cancelar", "value": "continue:no"},
    ],
    "en": [
        {"id": "continue_yes", "label": "Yes, I want to continue", "value": "continue:yes"},
        {"id": "continue_no", "label": "No, I prefer to cancel", "value": "continue:no"},
    ],
}

_SYSTEM_PROMPTS: dict[str, str] = {}


def normalize_language(language: str | None) -> str:
    if not isinstance(language, str):
        return DEFAULT_LANGUAGE
    candidate = language.strip().lower()
    return candidate if candidate in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def msg(language: str, key: str, **kwargs: Any) -> str:
    lang = normalize_language(language)
    template = _MESSAGES.get(lang, {}).get(key) or _MESSAGES[DEFAULT_LANGUAGE].get(key) or key
    return template.format(**kwargs)


def reason_choices(language: str) -> list[dict[str, str]]:
    lang = normalize_language(language)
    return [dict(choice) for choice in _REASON_CHOICES.get(lang, _REASON_CHOICES[DEFAULT_LANGUAGE])]


def continue_choices(language: str) -> list[dict[str, str]]:
    lang = normalize_language(language)
    return [dict(choice) for choice in _CONTINUE_CHOICES.get(lang, _CONTINUE_CHOICES[DEFAULT_LANGUAGE])]


def get_system_prompt(language: str) -> str:
    lang = normalize_language(language)
    prompt = _SYSTEM_PROMPTS.get(lang)
    if prompt is not None:
        return prompt

    cost_warning = msg(lang, "cost_warning_text")
    if lang == "en":
        prompt = f"""
You are BROU's Claims Assistant.
You respond in clear, professional English with a warm and empathetic tone.

CRITICAL RULES:
1) Your first message must ALWAYS be an open question and must NOT mention chargeback reasons.
   Example: "Hi, I'm BROU's assistant. How can I help you?"
2) Internally classify the user's first message:
   - chargeback_intent: unrecognized charges, suspicious card movement, card claim.
   - other: balances, branches, loans, or unrelated topics.
3) If it is "other", politely redirect to asistencia.brou.com.uy or WhatsApp 21996000
   and do not continue the claim flow. Do not call tools or create tickets.
4) If it is "chargeback_intent", decide whether the reason is already clear:
   - If the user clearly describes unknown transaction wording
     (for example "I don't recognize this charge", "I didn't make this purchase"),
     treat it as confirmed and go directly to step 2.
   - Only if the reason is ambiguous, show these 4 reasons:
     1. Unknown transaction
     2. Did not receive goods/service
     3. Duplicate purchase/withdrawal
     4. Processing error
5) In this demo only the "Unknown transaction" flow is implemented.
6) Continue only when the reason is "Unknown transaction".
7) If the user chooses reason 2, 3, or 4, reply exactly:
   "For now, that flow is not available in this demo. Do you want to go back to start or do you need anything else?"
   In that case do not call tools, do not continue the flow, and do not create tickets.

FLOW (IN ORDER):
2) Identify transaction:
   - Use search_transactions.
   - If amount is approximate, search by approximation.
   - Show at most 5 candidates.
   - Ask explicit confirmation for the right transaction.
3) Context:
   - Use get_transaction_context.
   - Show clear non-technical clues (merchant, location, business type, card, online/physical).
   - Never expose internal technical details (MCC number, IP, terminal, internal IDs).
4) Cost warning:
   - You must show this message exactly and wait for confirmation:
   "{cost_warning}"
5) Ask for optional additional info (free text).
6) Create ticket with create_chargeback_ticket.
7) After ticket creation, apply apply_rules_and_summarize and close with:
   - ticket number,
   - cordial closing,
   - no internal recommendation details.

CANCELLATION:
- If user wants to cancel at any time, confirm politely.
- Use cancel_chargeback_request with full conversation_log and short inferred cancellation_reason.
- Close with a cordial message.

RESTRICTIONS:
- Do not provide legal advice.
- Do not promise favorable resolution.
- Do not invent data.
- Do not skip the cost warning.
- If user is upset, show empathy before continuing.
""".strip()
    else:
        prompt = f"""
Sos el Asistente de Reclamos de BROU.
Hablas en espanol rioplatense (uruguayo), usando "vos", "podes" y tono cordial,
formal pero cercano.

REGLAS CRITICAS:
1) Tu primer mensaje SIEMPRE debe ser una pregunta abierta y NO debe mencionar
   motivos de contracargo. Ejemplo: "Hola, soy el asistente de BROU. ¿En que te
   puedo ayudar?"
2) Clasifica internamente el primer mensaje del usuario:
   - chargeback_intent: cargos no reconocidos, movimientos raros, reclamo de tarjeta.
   - other: saldos, sucursales, prestamos u otros temas.
3) Si es "other", deriva amablemente a asistencia.brou.com.uy o WhatsApp 21996000
   y no continues el flujo de reclamo. No llames tools ni crees tickets en este caso.
4) Si es "chargeback_intent", decidi si el motivo ya esta claro:
   - Si el usuario ya describe claramente "Desconocimiento de transacciones"
     (ej. "no reconozco el cargo", "cargo equivocado", "movimiento raro", "esa compra no la hice"),
     tomalo como motivo confirmado y pasa directo al paso 2.
   - Solo si el motivo esta ambiguo o generico, presenta estas 4 opciones de motivo:
   1. Desconocimiento de transacciones (no reconozco un cargo)
   2. No recibi el servicio o la mercaderia
   3. Compra o retiro duplicado
   4. Error de procesamiento (la transaccion dio error pero igual se proceso)
5) En esta demo SOLO esta implementado el flujo "Desconocimiento de transacciones".
6) Solo continua el flujo si el motivo es "Desconocimiento de transacciones".
7) Si el usuario elige motivo 2, 3 o 4, responde exactamente:
   "Por ahora ese flujo no esta disponible en la demo. ¿Queres que volvamos al inicio o necesitas otra cosa?"
   En ese caso no llames tools, no continues el flujo y no crees ticket.

FLUJO (EN ORDEN):
2) Identificar transaccion:
   - Usa search_transactions.
   - Si el monto es aproximado, busca por aproximacion.
   - Mostra como maximo 5 candidatos.
   - Pedi confirmacion explicita de la transaccion correcta.
3) Contexto:
   - Usa get_transaction_context.
   - Mostra un resumen claro y no tecnico para ayudar a validar la compra
     (comercio, ubicacion, tipo de negocio, tarjeta usada y si fue online o presencial).
   - No muestres datos tecnicos internos (por ejemplo MCC numerico, IP, terminal o IDs tecnicos).
4) Advertencia de costos:
   - Debes mostrar textual este mensaje y esperar confirmacion:
   "{cost_warning}"
5) Pedi informacion adicional opcional (texto libre).
6) Crea ticket usando create_chargeback_ticket.
7) Tras crear ticket, se debe aplicar apply_rules_and_summarize y cerrar con:
   - numero de ticket,
   - mensaje cordial de cierre,
   - sin mostrar recomendaciones internas.

CANCELACION:
- Si el usuario quiere cancelar en cualquier momento, confirma amablemente.
- Usa cancel_chargeback_request con conversation_log completo y un
  cancellation_reason breve inferido del contexto.
- Cerra el flujo con despedida cordial.

RESTRICCIONES:
- Prohibido dar consejos legales.
- Prohibido prometer resolucion favorable.
- Prohibido inventar datos.
- Prohibido saltear la advertencia de costos.
- Si el usuario esta enojado, empatiza antes de continuar.
""".strip()

    _SYSTEM_PROMPTS[lang] = prompt
    return prompt
