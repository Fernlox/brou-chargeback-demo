# Project Context (Living Document)

Last updated: 2026-05-11

## What this project is

BROU chargeback assistant demo: a conversational agent that guides users through a dispute flow and creates chargeback tickets in Supabase.

This is a demo environment with fictional data and one implemented reason flow:
- `unknown_transaction` / "Desconocimiento de transacciones"

## High-level architecture

- Frontend (`frontend/`): Next.js App Router UI with manual SSE parsing in `ChatWindow`.
- Backend (`backend/`): FastAPI API + SSE endpoint + Gemini orchestration.
- Data (`supabase/`): SQL migrations and deterministic seed generator.
- Rules (`rules.md`): business rule source used by runtime summarization.

## Core runtime flow

1. User sends message from frontend.
2. Frontend posts to `POST /chat/stream`.
3. Backend `run_agent_turn()` calls Gemini with tool declarations and routing hints.
4. Agent invokes tools from `backend/tools.py` against Supabase.
5. After optional additional-info prompt, backend now has a deterministic closure path that creates ticket data directly (instead of relying fully on model function-calling reliability for that last step).
6. Ticket is created and enriched with `apply_rules_and_summarize()`.
7. SSE events now prioritize tool events (`tool_call` / `tool_result`) before response text when tool calls are present, and include structured `quick_replies`.

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

## Critical files

- Backend entrypoint: `backend/main.py`
- Agent loop and prompt: `backend/agent.py`
- Tool implementations: `backend/tools.py`
- DB client bootstrap: `backend/db.py`
- Tracing layer: `backend/tracing.py`
- Frontend chat UI: `frontend/components/ChatWindow.tsx`
- DB schema: `supabase/migrations/*.sql`
- Seed script: `supabase/seed.py`
- Rule engine input: `rules.md`

## Operational assumptions

- No authentication (single demo user via `DEMO_USER_ID`).
- Supabase service role key is used server-side.
- Langfuse tracing is optional (no-op fallback if not configured).
- Frontend and backend run locally (`localhost:3000` and `localhost:8000` by default).

## Update policy for this file

Update this document when architecture, flow ownership, core files, or operational assumptions change.
