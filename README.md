# BROU — Asistente de Reclamos (Demo de Contracargos)

Prototipo funcional end‑to‑end de un agente conversacional para gestionar contracargos del **Banco República (BROU, Uruguay)**.

> Demo. Datos ficticios. No procesa pagos reales ni consume APIs bancarias reales.

---

## ¿Qué hace?

Un agente en español rioplatense atiende al cliente, identifica si tiene un cargo no reconocido, lo ayuda a buscar la transacción en su historial, le advierte de los costos del proceso y, si confirma, abre un ticket de contracargo y aplica reglas de negocio para sugerir un tratamiento.

Único motivo de contracargo implementado en esta demo: **Desconocimiento de transacciones**. Los otros tres motivos están declarados pero responden con un mensaje de "no disponible en la demo".

---

## Stack

- **Backend:** Python 3.12 + FastAPI + SSE.
- **Modelo:** Gemini (`gemini-2.5-pro` por defecto), function calling nativo.
- **Base de datos:** Supabase (Postgres) — instancia en Supabase Cloud.
- **Frontend:** Next.js 14 (App Router) + Tailwind CSS.
- **Tracing:** Langfuse (cloud o self‑hosted).
- **Despliegue:** todo local, levantado a mano.

---

## Estructura del repo

```
brou-chargeback-demo/
├── README.md
├── .env.example
├── rules.md
├── PLAN.md                    # Plan paso a paso con prompts para Cursor + Codex
├── backend/
│   ├── main.py                # FastAPI app + endpoint SSE de chat
│   ├── agent.py               # Loop del agente, system prompt y cliente Gemini
│   ├── tools.py               # Las 5 tools del agente
│   ├── db.py                  # Cliente Supabase
│   ├── tracing.py             # Setup Langfuse
│   └── requirements.txt
├── frontend/                  # Next.js app
└── supabase/
    ├── migrations/
    │   ├── 001_transactions.sql
    │   └── 002_chargeback_tickets.sql
    └── seed.py                # 90 transacciones (30 × 3 meses)
```

---

## Prerequisitos

- Python 3.12
- Node.js 20+
- Cuenta en [Supabase](https://supabase.com) (free tier alcanza)
- Cuenta en [Langfuse](https://cloud.langfuse.com) (free tier alcanza) — opcional para correr la demo, recomendado para mostrarla
- API key de Google AI Studio para Gemini ([aistudio.google.com](https://aistudio.google.com))

---

## Setup

### 1. Clonar y preparar el `.env`

```bash
cp .env.example .env
# Editar .env con tus credenciales reales
```

Variables clave: `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEMO_USER_ID`, `LANGFUSE_*`.

`DEMO_USER_ID` puede ser cualquier UUID v4. Se usa como dueño fijo de las 90 transacciones del seed.

Además, para frontend:

```bash
cp frontend/.env.local.example frontend/.env.local
```

Verificá que `frontend/.env.local` tenga:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 2. Supabase Cloud

1. Crear un proyecto nuevo en https://supabase.com/dashboard.
2. Copiar `Project URL` y `service_role key` al `.env`.
3. Aplicar migraciones (desde el SQL Editor de Supabase, copiá y pegá los archivos de `supabase/migrations/` en orden) **o** con la Supabase CLI: `supabase db push`.
4. Cargar datos seed:
   ```bash
   cd backend
   pip install -r requirements.txt
   python ../supabase/seed.py
   ```

### 3. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Verificá `http://localhost:8000/health` → `{"status":"ok"}`.

Si el `8000` está ocupado y levantás backend en otro puerto (por ejemplo `8001`), actualizá `NEXT_PUBLIC_BACKEND_URL` en `.env` y reiniciá el frontend.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:3000`.

### 4.1 Arranque rápido con scripts (backend + frontend)

Podés levantar todo desde la raíz del repo con:

```bash
./scripts/run_dev.sh
```

También podés correr cada servicio por separado:

```bash
./scripts/run_backend.sh
./scripts/run_frontend.sh
```

Variables opcionales:
- `BACKEND_PORT` (default `8000`)
- `BACKEND_HOST` (default `127.0.0.1`, solo backend)
- `FRONTEND_PORT` (default `3000`, solo frontend)
- `NEXT_PUBLIC_BACKEND_URL` (default `http://localhost:$BACKEND_PORT`, solo frontend)

### 5. Langfuse (opcional pero recomendado)

Crear un proyecto en https://cloud.langfuse.com, copiar las keys al `.env` y reiniciar el backend.

Variables usadas por tracing:
- `LANGFUSE_PUBLIC_KEY` (`pk-lf-...`)
- `LANGFUSE_SECRET_KEY` (`sk-lf-...`)
- `LANGFUSE_HOST` (por defecto `https://cloud.langfuse.com`)

Comportamiento sin keys:
- Si faltan `LANGFUSE_PUBLIC_KEY` o `LANGFUSE_SECRET_KEY`, el backend usa un tracer no-op.
- La demo sigue funcionando normalmente, pero no envía trazas al dashboard de Langfuse.

Con keys configuradas, cada conversación queda registrada con prompts/respuestas completos y tool calls como spans.

---

## Guion de demo (sugerido)

### Escenario 1 - Camino feliz (regla 2, comercio frecuente tipo Netflix)

**Objetivo:** mostrar flujo completo hasta ticket creado con recomendación basada en reglas.

1. Usuario: "Hola, vi un cargo raro en la tarjeta."
2. Si el mensaje ya es claro (por ejemplo "cargo equivocado" / "no reconozco ese cargo"), el agente entra directo al flujo de **Desconocimiento de transacciones**.
3. Si es ambiguo, el agente ofrece las 4 opciones de motivo (con botones en la UI).
4. Dar referencia de búsqueda: "Fue de unos 19 USD, creo que de Netflix."
5. Confirmar la transacción correcta cuando el agente muestre candidatos (también con botones de selección).
6. El agente trae contexto y muestra historial/frecuencia del comercio.
7. Confirmar que se quiere continuar, aceptar advertencia de costos y aportar comentario opcional.
8. El agente crea ticket (`CB-YYYY-NNNNNN`) y cierra con mensaje cordial.
9. Resultado esperado: en DB, ticket con `agent_summary` y `agent_recommendation` poblados; recomendación alineada a regla 2 (comercio frecuente/suscripción).
10. Mostrar traza completa en Langfuse (turnos + tool calls + latencias).

### Escenario 2 - Cancelación a mitad de flujo

**Objetivo:** demostrar salida controlada cuando el usuario desiste.

1. Iniciar igual que el flujo feliz hasta antes de confirmación final (por ejemplo, luego de ver contexto de transacción).
2. Usuario: "Dejá, no quiero seguir con el reclamo."
3. Agente confirma cancelación y cierra cordialmente.
4. Resultado esperado: se genera ticket con `status='cancelled_by_user'`, `resolved_by='agent'`, `conversation_log` completo y resumen/recomendación cargados por reglas.

### Escenario 3 - Motivo no implementado

**Objetivo:** evidenciar control de alcance de la demo.

1. Usuario: "Tengo un cargo raro."
2. Agente presenta 4 motivos.
3. Elegir **"Compra duplicada"** (o motivo 2/4).
4. Resultado esperado: respuesta
   "Por ahora ese flujo no está disponible en la demo. ¿Querés que volvamos al inicio o necesitás otra cosa?"
5. No debe continuar el flujo de ticket para ese motivo.
6. Si el usuario reformula como desconocimiento, el agente retoma desde identificación de transacción.

---

## Decisiones de diseño en demo

- **No hay autenticación.** El `DEMO_USER_ID` es fijo y todas las transacciones le pertenecen.
- **Solo 1 motivo implementado.** "Desconocimiento de transacciones" es el único flujo completo; motivos 2/3/4 se responden como no disponibles.
- **Consultas fuera de alcance se derivan.** Para saldo/sucursales/préstamos se redirige a canales oficiales sin iniciar reclamo.
- **Experiencia conversacional sobre exactitud operativa.** El foco es mostrar el flujo E2E y tool orchestration, no automatización bancaria real.
- **Tracing sin obfuscación.** Langfuse loguea prompts y respuestas completas — es demo.
- **Frontend sin auth, sin persistencia de sesión.** Recargar la página borra el chat.
- **SSE por POST con parseo manual en frontend.** Se evita `EventSource` para soportar payload y estado de conversación, incluyendo eventos estructurados de `quick_replies`.
- **Resumen y recomendación post-ticket automáticos.** Al crear/cancelar ticket se aplica `rules.md` para poblar `agent_summary` y `agent_recommendation`.
- **Conversation log persistido.** Cada ticket guarda historial estructurado para auditoría de demo.
- **Sin hardening productivo.** No hay rate limiting, colas, retries distribuidos ni políticas de seguridad de producción.
- **El `seed.py` es idempotente** vía `DEMO_USER_ID`: si lo corrés dos veces, hace `delete from transactions where user_id = ...` antes de insertar.

---

## Troubleshooting

- **"Workspace still starting" en alguna llamada/tool:** esperar unos segundos y reintentar la acción.
- **401 contra Supabase:** verificar que `SUPABASE_SERVICE_ROLE_KEY` sea la service role key correcta (no usar anon key).
- **Gemini quota/límites:** revisar consumo y límites del proyecto en Google AI Studio.
- **SSE se corta o se congela en frontend:** revisar que no haya proxy intermedio con buffering para `text/event-stream`.

---

## Variables de entorno

Ver `.env.example`. En particular:

| Variable | Descripción |
|---|---|
| `GEMINI_API_KEY` | API key de Google AI Studio |
| `GEMINI_MODEL` | Por defecto `gemini-2.5-pro` |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (NO la anon) |
| `DEMO_USER_ID` | UUID v4 fijo para el usuario de la demo |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` por defecto |
| `NEXT_PUBLIC_BACKEND_URL` | (frontend) URL del backend para `POST /chat/stream` (`http://localhost:8000`) |

---

## Cómo se construyó

Este repo se arma siguiendo los pasos de [`PLAN.md`](./PLAN.md). Cada paso del plan trae un prompt listo para pegar en **Cursor + Codex** y construir esa pieza.
