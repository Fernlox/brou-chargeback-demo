# Technology Stack (Living Reference)

Last updated: 2026-05-08

## Application layers

- Frontend: Next.js `16.2.6`, React `19.2.4`, TypeScript `^5`, Tailwind CSS `^4`.
- Backend: Python (venv-based), FastAPI `0.115.12`, Uvicorn `0.34.2`, SSE via `sse-starlette`.
- Database/API: Supabase (Postgres + PostgREST Python client).
- LLM: Google Gemini via `google-genai` `1.18.0`.
- Observability: Langfuse `2.60.5` (optional).

## Backend Python dependencies

Defined in `backend/requirements.txt`:
- `fastapi==0.115.12`
- `uvicorn[standard]==0.34.2`
- `python-dotenv==1.1.0`
- `supabase>=2.0,<3`
- `google-genai==1.18.0`
- `langfuse==2.60.5`
- `sse-starlette==2.1.3`
- `pydantic>=2,<3`

## Frontend Node dependencies

Defined in `frontend/package.json`:
- Runtime: `next`, `react`, `react-dom`
- Dev: `typescript`, `eslint`, `eslint-config-next`, `tailwindcss`, `@types/*`

## Data model components

- `transactions` table: seeded demo card transactions.
- `chargeback_tickets` table: persisted chargeback and cancellation cases.
- Runtime rules source: `rules.md` (applied by `apply_rules_and_summarize`).

## Environment variables (critical)

- Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL`
- Supabase: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEMO_USER_ID`
- Backend host/CORS: `BACKEND_HOST`, `BACKEND_PORT`, `FRONTEND_ORIGIN`
- Frontend API URL: `NEXT_PUBLIC_BACKEND_URL`
- Langfuse (optional): `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

## Update policy for this file

Update when dependency versions, services, runtime providers, or required env vars change.
