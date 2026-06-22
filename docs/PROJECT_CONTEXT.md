# Project Context (Living Document)

Last updated: 2026-06-11

## What this project is

BROU chargeback assistant demo: a conversational agent that guides users through a dispute flow and creates chargeback tickets in Supabase.

This is a demo environment with fictional data and one implemented reason flow:
- `unknown_transaction` / "Desconocimiento de transacciones"

## High-level architecture

- Frontend (`frontend/`): Next.js App Router UI with a shared shell that toggles between `ChatWindow` and a read-only `AdminPanel`, plus in-app ES/EN language context (`frontend/lib/i18n.tsx`).
- Backend (`backend/`): FastAPI API + SSE endpoint + Gemini orchestration with language-aware copy/prompt module (`backend/copy.py`).
- Data (`supabase/`): SQL migrations and deterministic seed generator.
- Rules (`rules.md`): business rule source used by runtime summarization.

## Core runtime flow

1. User sends message from frontend.
2. Frontend posts to `POST /chat/stream` with `session_id`, `message`, and selected `language` (`es` or `en`).
3. Backend `run_agent_turn()` calls Gemini with tool declarations and routing hints.
4. Agent invokes tools from `backend/tools.py` against Supabase.
5. After optional additional-info prompt, backend now has a deterministic closure path that creates ticket data directly (instead of relying fully on model function-calling reliability for that last step).
6. Ticket is created and confirmed to the user immediately; `apply_rules_and_summarize()` now runs asynchronously in background.
7. SSE events now prioritize tool events (`tool_call` / `tool_result`) before response text when tool calls are present, and include structured `quick_replies`.
8. Admin panel loads read-only ticket aggregates/list/detail via `GET /admin/tickets/summary`, `GET /admin/tickets`, and `GET /admin/tickets/{ticket_id}`.
9. Frontend language toggle updates UI labels/placeholders immediately and resets the active chat session before the next turn in the selected language.

## Conversational routing behavior

- The assistant now attempts direct reason detection for first-party fraud/unknown charge wording
  (for example "cargo equivocado", "no reconozco ese cargo") and skips the reason menu when clear.
- If the reason is ambiguous, the assistant still presents the 4 predefined reason choices.
- Transaction candidate selection and continue confirmations can be exposed as structured quick-reply buttons in the frontend.
- Transaction search turns use deterministic backend copy plus quick replies to avoid duplicated model-generated listings.
- Transaction quick replies now separate hidden backend value (`transaction_id`) from user-visible text (date, merchant, amount, card suffix).
- Cancellation handling is idempotent per session: once cancelled, repeated cancellation intents do not create extra cancellation tickets.
- The optional free-text clarification step is hardened: user replies like `continuar` can close the flow reliably with ticket creation + ticket number even when the model emits malformed function-calling output.
- Transaction selection and transaction-context turns now return deterministic backend copy and end the turn immediately, so model post-tool prose is not shown in those steps.
- After selecting a transaction, the flow now enforces two separate confirmations: (1) transaction confirmation with optional deterrence context, and (2) formal cost warning acknowledgment before optional details and ticket creation.
- Transaction identification is now slot-driven in backend state: date, amount (approx/exact), and explicit currency hints are extracted deterministically from user text and reused in `search_transactions` calls.
- When amount is searched as approximate, if any candidate matches the exact stated amount (money precision), only exact-amount matches are returned to selection UI.
- Date parsing for short formats like `25/5` is anchored to current year in backend guardrails instead of model inference.
- Transaction context can only be requested for IDs from the latest search candidates; unknown/stale IDs are rejected with a safe re-search prompt.
- If context lookup does not return a valid `transaction`, the flow no longer advances to continue/cost confirmations.
- Transaction context now returns and displays user-friendly confirmation clues (merchant name, location hint, business type inferred from MCC, card suffix, and online vs physical channel) while hiding technical internals like MCC numbers or IP addresses from customer-facing copy.

## Critical files

- Backend entrypoint: `backend/main.py`
- Backend admin reads: `backend/admin.py`
- Agent loop and prompt: `backend/agent.py`
- Tool implementations: `backend/tools.py`
- DB client bootstrap: `backend/db.py`
- Tracing layer: `backend/tracing.py`
- Frontend shell/toggle: `frontend/components/AppShell.tsx`
- Frontend chat UI: `frontend/components/ChatWindow.tsx`
- Frontend admin UI: `frontend/components/AdminPanel.tsx`
- Frontend i18n provider/dictionary: `frontend/lib/i18n.tsx`
- Frontend backend URL helper: `frontend/lib/backendApi.ts`
- Backend localized copy/prompt source: `backend/copy.py`
- Dev launcher scripts: `scripts/run_backend.sh`, `scripts/run_frontend.sh`, `scripts/run_dev.sh`
- DB schema: `supabase/migrations/*.sql`
- Seed script: `supabase/seed.py`
- Rule engine input: `rules.md`

## Operational assumptions

- No authentication (single demo user via `DEMO_USER_ID`).
- Supabase service role key is used server-side.
- Langfuse tracing is optional (no-op fallback if not configured).
- Frontend and backend run locally (`localhost:3000` and `localhost:8000` by default).
- Admin panel is demo-only read access without auth hardening.

## Update policy for this file

Update this document when architecture, flow ownership, core files, or operational assumptions change.
