# Project State (Living Snapshot)

Last updated: 2026-05-11
Owner: Cursor agent tasks

## Current delivery status

- Backend API is reachable and healthy (`/health` returns `supabase=true`).
- Sample transaction endpoint works (`/transactions/sample` returns 5 rows).
- Frontend lint passes.
- Python backend modules compile without syntax errors.
- Chat send button can recover from hung SSE turns (manual stop + idle timeout).
- Chat now supports structured quick-reply buttons from backend SSE events.

## What was checked in this audit

- Source review of backend, frontend, DB migrations, and seed tooling.
- Runtime smoke checks for core backend endpoints.
- Static checks:
  - `frontend`: `npm run lint`, `npm run build`
  - `backend`: `python -m compileall backend`

Latest run for this update:
  - `frontend`: `npm run lint` (pass)
  - `backend`: `python3 -m compileall backend` (pass)
  - `frontend`: `npm run lint` (pass, tool UI polish)
  - `backend`: `python3 -m compileall backend` (pass, deterministic ticket closure hardening)
  - `frontend`: `npm run lint` (pass, transaction selection + tool rendering UX)
  - `backend`: `python3 -m compileall backend` (pass, cancellation idempotency + SSE ordering)
  - `backend`: `python3 -m compileall backend` (pass, deterministic transaction confirmation/warning flow + internal recommendation hidden)

## Issues found

### Fixed

1. Seed reseed failure due to foreign key ordering
   - Area: `supabase/seed.py`
   - Symptom: deleting demo user transactions can fail when existing `chargeback_tickets` reference them.
   - Fix: delete demo user tickets before deleting demo user transactions.

2. Health status could report `ok` while dependency was degraded
   - Area: `backend/main.py`
   - Symptom: `/health` returned `"status": "ok"` even when Supabase check failed.
   - Fix: return `"status": "degraded"` when Supabase connectivity is unavailable.

3. Chat send button could remain blocked after a stalled stream
   - Area: `frontend/components/ChatWindow.tsx`
   - Symptom: if `/chat/stream` did not finish promptly, `isStreaming` stayed active and the send button remained unusable.
   - Fix: added stream abort control (`Detener`), abort signal wiring in `fetch`, and an idle timeout to auto-unblock the UI.

4. Dev-origin blocking could keep chat UI non-interactive in local loopback host
   - Area: `frontend/next.config.ts`
   - Symptom: requests from `127.0.0.1` to Next dev assets could be blocked, which may prevent hydration and leave the server-rendered disabled state in place.
   - Fix: configured `allowedDevOrigins: ["127.0.0.1"]` for local development.

5. Frontend/backend port mismatch could break chat sends locally
   - Area: `frontend/components/ChatWindow.tsx`
   - Symptom: UI could show "No pude conectar con el backend..." when `NEXT_PUBLIC_BACKEND_URL` pointed to a non-backend service on `:8000` while API was available on `:8001`.
   - Fix: added local backend URL candidate fallback (`:8000` and `:8001`, localhost and 127.0.0.1), retrying on connection/server errors before surfacing failure.

6. Chargeback reason routing and option UX were too text-dependent
   - Area: `backend/agent.py`, `frontend/components/ChatWindow.tsx`
   - Symptom: phrases like "cargo equivocado" could still force explicit typed reason confirmation, and option-heavy turns required manual typing.
   - Fix: added deterministic reason hints for unknown transaction wording, SSE `quick_replies` events, and clickable chat buttons for reason selection, transaction selection, and continue/cancel confirmations.

7. Tool-only assistant turns showed an empty bubble and weak tool status visuals
   - Area: `frontend/components/ChatWindow.tsx`
   - Symptom: when a tool call arrived before text, chat rendered an empty assistant bubble above a basic grey chip (`get_transaction_context...`) and could also show `escribiendo...` simultaneously.
   - Fix: assistant bubble now hides for tool-only turns, tool status uses clearer running/done badges with friendly tool labels (including `get_transaction_context`), and typing placeholder is suppressed while a tool is visibly running.

8. Final optional-info step could end silently without creating a ticket
   - Area: `backend/agent.py`
   - Symptom: after the assistant asked for optional extra information, Gemini could return `MALFORMED_FUNCTION_CALL` with no usable `function_calls`, causing the turn to finish with no ticket creation and no ticket-number confirmation.
   - Fix: added deterministic final-step handling that creates `create_chargeback_ticket` directly from the optional-info reply, preserves user comment in `user_additional_info`, includes ticket number in closure text, fills missing `transaction_id` from session state, and adds a non-silent fallback message for malformed function-call finishes.

9. Cancellation turns could create duplicate cancellation tickets and expose ticket number unnecessarily
   - Area: `backend/agent.py`
   - Symptom: repeated cancellation wording (or noisy strings containing cancel keywords) could trigger extra `cancel_chargeback_request` inserts; cancellation response could mention the internal ticket number.
   - Fix: tightened cancellation intent detection using normalized token matching, added per-session cancellation idempotency guard (`chargeback_flow_cancelled`), and standardized cancellation closure text without ticket mention.

10. Transaction selection UX showed internal IDs and duplicated option copy
   - Area: `backend/agent.py`, `frontend/components/ChatWindow.tsx`
   - Symptom: selecting a transaction could display `Selecciono la transacción <uuid>` in user bubbles; search turns could show model-written option text plus quick replies with similar data.
   - Fix: quick replies now include a user-facing `display_text` while keeping UUID in hidden `value`, frontend sends hidden value but renders readable selection text, backend emits deterministic hybrid copy for search results, and tool usage blocks render before assistant text as `Uso de herramienta: <tool>`.

11. Post-selection turns could leak model/internal content and collapse confirmation steps
   - Area: `backend/agent.py`
   - Symptom: after selecting a transaction, a second Gemini-written message could still appear in the same turn; ticket closure could expose internal `agent_recommendation`; transaction confirmation and formal cost warning could appear as a single combined step.
   - Fix: short-circuit deterministic turn closure after `search_transactions` and `get_transaction_context`, add session-phase gates for explicit transaction confirmation and then separate cost-warning acknowledgment, remove recommendation from user-facing ticket confirmation text, and update warning copy to a more visible no-emoji format.

### Open

1. Inconsistent project docs across repository
   - Root `README.md` and `frontend/README.md` are not fully aligned with current implementation details and versions.
   - Impact: onboarding confusion and outdated operational guidance.

2. Limited automated regression tests
   - No dedicated backend/frontend test suite in repo source paths.
   - Impact: behavior regressions can slip through after prompt/toolflow changes.

3. Chat flow reliability depends mostly on prompt quality
   - Most steps now have stronger backend guardrails, but non-happy-path closures can still vary by model behavior in some edge conversations.
   - Impact: occasional incomplete happy-path closure without stronger guardrails or tests.

## Recommended next tasks

1. Add deterministic backend integration tests for key chat transitions.
2. Add a minimal frontend chat interaction test for SSE + tool chips.
3. Refresh root and frontend README files to align with real stack and flow.

## Update policy for this file

Update this file at the end of tasks that change behavior, known issues, quality checks, or operational status.
