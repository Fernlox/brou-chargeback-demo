# Project State (Living Snapshot)

Last updated: 2026-06-11
Owner: Cursor agent tasks

## Current delivery status

- Backend API is reachable and healthy (`/health` returns `supabase=true`).
- Sample transaction endpoint works (`/transactions/sample` returns 5 rows).
- Frontend lint passes.
- Python backend modules compile without syntax errors.
- Chat send button can recover from hung SSE turns (manual stop + idle timeout).
- Chat now supports structured quick-reply buttons from backend SSE events.
- Admin panel now uses a wide 3-column layout in admin mode with clearer Spanish status tags, dedicated conversation panel, and human-readable transaction detail cards.
- Header now renders the official BROU SVG logo instead of placeholder text.
- App now supports in-session bilingual ES/EN switching across frontend UI and backend chat agent responses, including language-aware prompts, deterministic copy, and quick-reply labels.
- Admin ticket reason now localizes from `reason_code` in both ticket list and detail views instead of showing raw `reason_label_es` in English mode.
- Root-level dev scripts now start backend/frontend together (`./scripts/run_dev.sh`) or separately while wiring frontend to local backend URL.

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
  - `backend`: `backend/.venv/bin/python -m py_compile backend/agent.py backend/tools.py backend/tests/test_agent_guardrails.py` (pass)
  - `backend`: `backend/.venv/bin/python -m unittest backend/tests/test_agent_guardrails.py` (pass, transaction guardrails)
  - `backend`: `backend/.venv/bin/python -m unittest backend/tests/test_tools.py backend/tests/test_agent_guardrails.py` (pass, exact-amount search filtering + guardrails)
  - `backend`: `backend/.venv/bin/python -m py_compile backend/tools.py backend/agent.py backend/tests/test_tools.py` (pass)
  - `backend`: `python3 -m py_compile backend/main.py backend/admin.py` (pass, admin API endpoints)
  - `frontend`: `npm run lint` (pass, app shell toggle + admin panel)
  - `frontend`: `npm run lint` (pass, admin UX localization + layout polish)
  - `frontend`: `npm run lint` (pass, human-readable tool events in admin conversation view)
  - `backend`: `backend/.venv/bin/python -m unittest backend/tests/test_tools.py backend/tests/test_agent_guardrails.py` (pass, user-friendly transaction context + confirmation copy)
  - `backend`: `backend/.venv/bin/python -m py_compile backend/tools.py backend/agent.py` (pass)
  - `backend`: `python3 -m py_compile backend/agent.py` (pass, async post-ticket summarization decoupling)
  - `frontend`: `npm run lint` (pass, ES/EN i18n wiring in AppShell/ChatWindow/AdminPanel)
  - `frontend`: `npm run build` (pass, production build with i18n changes)
  - `backend`: `backend/.venv/bin/python -m py_compile backend/agent.py backend/tools.py backend/main.py backend/copy.py` (pass, bilingual backend runtime)
  - `backend`: `backend/.venv/bin/python -m unittest backend/tests/test_tools.py backend/tests/test_agent_guardrails.py` (pass, guardrails + tool formatting after bilingual update)
  - `scripts`: `bash -n scripts/run_backend.sh scripts/run_frontend.sh scripts/run_dev.sh` (pass)
  - `backend`: `backend/.venv/bin/python -c "import uvicorn; import backend.main; print('imports_ok')"` (pass, avoids stdlib `copy` shadowing)

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

12. Transaction identification could use wrong year/currency and allow invented context confirmations
   - Area: `backend/agent.py`, `backend/tools.py`
   - Symptom: model-driven search could call `search_transactions` with incorrect year (for example forcing `2024`), fail to re-search after user corrected exact amount, and then continue with non-validated transaction/context text.
   - Fix: added deterministic search-slot extraction (date/amount/explicit currency), backend-owned stateful re-search on amount updates, latest-candidate ID validation for context calls, hard stop when context payload lacks a valid `transaction`, and inclusive date-only `date_to` normalization to end-of-day.

13. There was no operator/admin visibility into created tickets
   - Area: `backend/main.py`, `backend/admin.py`, `frontend/components/AppShell.tsx`, `frontend/components/AdminPanel.tsx`
   - Symptom: demo only exposed conversational flow, with no way to inspect aggregate ticket volume or review ticket artifacts after creation.
   - Fix: added read-only admin endpoints (`/admin/tickets/summary`, `/admin/tickets`, `/admin/tickets/{ticket_id}`), introduced a header toggle between assistant/admin views, and built an admin panel with KPI cards, ticket list, and detail view showing summary, recommendation, conversation log, and transaction payload.

14. Approximate amount search could still show near matches when exact amount existed
   - Area: `backend/tools.py`
   - Symptom: searching transactions with an amount hint could return the exact amount row plus nearby tolerance-band rows, creating noisy candidate lists.
   - Fix: when an approximate-amount query includes at least one exact amount match (2-decimal money precision), search now returns only those exact-match rows; added regression tests for exact-match suppression and no-exact fallback behavior.

15. Admin panel consumed limited space and exposed internal JSON/status codes
   - Area: `frontend/components/AppShell.tsx`, `frontend/components/AdminPanel.tsx`
   - Symptom: admin view was constrained to a narrow container, status chips showed backend codes in English, transaction data appeared as raw JSON, and conversation was embedded in ticket detail with low readability.
   - Fix: widened admin container at shell level, added Spanish status labels with semantic colors (including gray `cancelled_by_user`), converted transaction details into labeled Spanish fields, and moved conversation into a dedicated third column with role-based message cards.

16. Admin conversation displayed raw tool CALL/RESULT JSON blocks
   - Area: `frontend/components/AdminPanel.tsx`
   - Symptom: tool transcript entries in the conversation panel showed internal `CALL [tool: ...]` and `RESULT ...` payloads as plain JSON, reducing readability for operators.
   - Fix: added tool-event parsing and user-friendly summaries (tool names in Spanish, concise call intent, and result summaries for search/context/ticket tools) so admin users see understandable operational messages instead of raw JSON.

17. Transaction context confirmation lacked practical user clues and could expose technical metadata
   - Area: `backend/tools.py`, `backend/agent.py`
   - Symptom: post-selection context copy mainly highlighted prior merchant frequency and did not consistently include merchant/location/business/card/channel clues; raw context payload retained technical fields not intended for user-facing validation.
   - Fix: `get_transaction_context` now returns sanitized customer-facing context (merchant display name, location hint, business type label, card suffix, online/presencial channel), and deterministic confirmation copy now uses those fields while avoiding MCC/IP-style technical details; added focused regression tests.

18. App header branding used a placeholder logo block
   - Area: `frontend/components/AppShell.tsx`, `frontend/components/BrouLogo.tsx`
   - Symptom: the top bar displayed a synthetic "B + BROU" mark instead of the official institution logo.
   - Fix: added a reusable `BrouLogo` SVG component and replaced header placeholder branding with the official logo artwork.

19. Ticket creation response latency was inflated by synchronous rules summarization
   - Area: `backend/agent.py`
   - Symptom: final ticket confirmation waited for `apply_rules_and_summarize` (DB reads + Gemini generation + DB update), making "ticket created" feel slow.
   - Fix: removed synchronous summarization from the ticket creation tool path and scheduled `apply_rules_and_summarize` asynchronously after emitting `tool_result`, so users receive ticket number confirmation immediately while internal summary/recommendation persists in background.

20. Website and chat flow were Spanish-only
   - Area: `frontend/components/AppShell.tsx`, `frontend/components/ChatWindow.tsx`, `frontend/components/AdminPanel.tsx`, `frontend/lib/i18n.tsx`, `backend/copy.py`, `backend/main.py`, `backend/agent.py`, `backend/tools.py`
   - Symptom: UI labels/placeholders/errors, chat quick replies, deterministic backend guardrail copy, and Gemini system instruction were fixed to Spanish.
   - Fix: added ES/EN language toggle in header, centralized frontend dictionary/context i18n, threaded `language` through `/chat/stream` + `/chat/reset`, introduced backend localized copy/system-prompt module, made quick-reply values language-stable (`reason:*`, `continue:*`, `tx_select:*`), and added bilingual keyword handling for guardrails/intents.

21. Dev launcher scripts failed on macOS and conflicted with stdlib import resolution
   - Area: `scripts/run_backend.sh`, `scripts/run_dev.sh`
   - Symptom: `./scripts/run_dev.sh` could crash with `ImportError` because `uvicorn` imported `backend/copy.py` instead of Python stdlib `copy`, and Bash 3.2 rejected `wait -n`.
   - Fix: run backend from repo root using `uvicorn backend.main:app` (avoids module shadowing) and replace `wait -n` with a Bash 3-compatible process-monitor loop.

22. Admin reason label stayed in Spanish in English UI mode
   - Area: `frontend/components/AdminPanel.tsx`, `frontend/lib/i18n.tsx`, `backend/admin.py`
   - Symptom: in English mode, the admin panel still displayed `Desconocimiento de transacciones` because list/detail views used raw `reason_label_es`.
   - Fix: include `reason_code` in admin ticket list payload and map reason display to localized labels from i18n dictionaries, with fallback to `reason_label_es` when code is unavailable.

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
