# Plan de implementación — BROU Chargeback Demo

Este plan está pensado para usarse con **Cursor + Codex**. Cada paso es un prompt autocontenido y copiable. Pegalo tal cual en el chat de Cursor con Codex apuntando a la raíz del repo `brou-chargeback-demo/`.

**Convención:** entre cada paso, corré lo que indique la sección "Validar" del prompt. No avances al siguiente paso si no pasa.

---

## Estado al arrancar

Estos archivos ya existen en el repo (creados a mano):

- `README.md`
- `.env.example`
- `rules.md`
- `PLAN.md` (este archivo)
- Carpetas vacías: `backend/`, `frontend/`, `supabase/migrations/`, `docs/`

**Antes de empezar**, copiar `.env.example` a `.env` y completar al menos `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `DEMO_USER_ID` (UUID v4). Las demás variables se pueden completar después.

---

## Paso 1 — Migración SQL: tabla `transactions`

**Objetivo:** crear `supabase/migrations/001_transactions.sql` con el schema de transacciones.

> Prompt para Cursor + Codex:

```text
Sos un ingeniero backend trabajando en el repo `brou-chargeback-demo/`. Necesito que crees el archivo `supabase/migrations/001_transactions.sql` con el schema de la tabla `transactions` para una demo de contracargos del Banco República (BROU).

Requerimientos exactos del schema:

- id uuid primary key, default gen_random_uuid()
- user_id uuid not null
- card_last4 text not null
- card_brand text not null, check in ('visa','mastercard','amex')
- total_amount numeric(14,2) not null
- currency text not null, check in ('UYU','USD')
- fx_rate numeric(10,4)
- transaction_at timestamptz not null
- merchant_name text not null
- merchant_dba text
- mcc text not null
- card_present boolean not null
- entry_mode text, check in ('chip','contactless','manual','online')
- sales_tax numeric(14,2)
- customer_reference text
- invoice_number text
- merchant_postal_code text
- merchant_city text
- merchant_country text default 'UY'
- terminal_id text
- ip_address text
- is_tokenized boolean default false
- cvm text, check in ('pin','signature','biometric','none')
- created_at timestamptz default now()

Crear índices:
- (user_id, transaction_at desc)
- (user_id, merchant_name)
- (user_id, total_amount)

El archivo debe poder ejecutarse tal cual en el SQL Editor de Supabase (Postgres 15+). Incluí `create extension if not exists "pgcrypto";` al principio si es necesario para `gen_random_uuid()`.

No agregues nada más que esa migración. No modifiques otros archivos.

Validar: el archivo se llama `supabase/migrations/001_transactions.sql`, contiene un único `CREATE TABLE` y 3 `CREATE INDEX`.
```

---

## Paso 2 — Migración SQL: tabla `chargeback_tickets`

**Objetivo:** crear `supabase/migrations/002_chargeback_tickets.sql`.

> Prompt para Cursor + Codex:

```text
En el repo `brou-chargeback-demo/`, creá `supabase/migrations/002_chargeback_tickets.sql` con la tabla `chargeback_tickets`.

Schema exacto:

- id uuid primary key default gen_random_uuid()
- ticket_number text unique not null  (formato 'CB-YYYY-NNNNNN')
- user_id uuid not null
- transaction_id uuid references transactions(id)
- reason_code text not null  ('unknown_transaction' para el MVP)
- reason_label_es text not null
- user_additional_info text
- status text not null default 'open' check in ('open','cancelled_by_user','in_review','resolved_favorable','resolved_unfavorable')
- resolved_by text check in ('agent','human','system')
- agent_summary text
- agent_recommendation text
- conversation_log jsonb
- created_at timestamptz default now()
- updated_at timestamptz default now()

Agregá un trigger simple que actualice `updated_at` en cada UPDATE.

Validar: el archivo crea la tabla y el trigger, depende de la migración 001 (referencia a `transactions`).
```

---

## Paso 3 — Seed de transacciones (`seed.py`)

**Objetivo:** generar 90 transacciones realistas para el usuario demo.

> Prompt para Cursor + Codex:

```text
En el repo `brou-chargeback-demo/`, creá el archivo `supabase/seed.py`. Este script:

1. Lee variables de entorno desde `.env` en la raíz: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEMO_USER_ID`.
2. Conecta a Supabase usando el SDK oficial de Python `supabase` (versión 2.x).
3. Borra todas las transacciones de ese `user_id` antes de insertar (idempotencia).
4. Inserta exactamente 90 transacciones distribuidas:
   - 30 transacciones por mes durante los últimos 3 meses (mes actual, mes -1, mes -2).
   - Fechas distribuidas a lo largo de cada mes (no todas el día 1), con horarios variados (mañana/tarde/noche).
5. Mezcla 80% UYU / 20% USD (aproximadamente).
6. Catálogo de comercios a samplear (mezclar libremente):
   - Supermercados: Tienda Inglesa, Devoto, Disco, Géant, Ta-Ta (MCC 5411), montos UYU 350–8500
   - Restaurantes / delivery: PedidosYa, Rappi, McDonald's, La Pasiva, Bar Tasende (MCC 5812 o 5814), UYU 400–3500
   - Suscripciones digitales en USD: Netflix, Spotify, HBO Max, Disney+, Amazon Prime, ChatGPT Plus (MCC 4899 o 5815), USD 4.99–19.99
   - Movilidad: Uber, Cabify, Uber Eats (MCC 4121), UYU 150–900
   - Telecomunicaciones: Antel, Movistar (MCC 4814), UYU 600–2500
   - E-commerce: MercadoLibre, Amazon, AliExpress (MCC 5942 o 5999), UYU 800–12000 o USD 15–200
   - Combustibles: Ancap, Petrobras (MCC 5541), UYU 1500–4500
   - Farmacias: San Roque, Farmashop (MCC 5912)

7. Garantías que el seed DEBE cumplir (validar al final, fallar si no):
   - Al menos 3 comercios distintos repetidos 4+ veces cada uno (ej. Netflix los 3 meses, varias en Tienda Inglesa, varios viajes en Uber).
   - Al menos 1 transacción internacional (`merchant_country='CN'`, ej. AliExpress).
   - Al menos 1 transacción tokenizada (`is_tokenized=true`).
   - Al menos 1 transacción con monto < USD 10 equivalente.
   - `entry_mode`: 'online' para suscripciones y e-commerce, 'contactless' o 'chip' para presenciales, 'manual' casi nunca.
   - `card_present`: false para online, true para presencial.
   - `cvm`: 'pin' o 'biometric' para presenciales, 'none' para online.

8. Para cada transacción, generar también: `card_last4` (mezclar 2-3 valores fijos), `card_brand` ('visa' o 'mastercard'), `terminal_id` y `ip_address` plausibles.

9. Imprimir al final un resumen: cantidad insertada, comercios únicos, transacciones por mes, top 5 comercios.

10. El script debe ser ejecutable como `python supabase/seed.py` desde la raíz del repo, después de `pip install supabase python-dotenv`.

No usar `Faker` salvo para nombres de calles/IPs. Los datos son ficticios pero específicos al catálogo.

Validar: correr `python supabase/seed.py` y verificar el resumen impreso.
```

---

## Paso 4 — Backend bootstrap (FastAPI + Supabase client)

**Objetivo:** levantar el backend mínimo con `/health` y cliente de Supabase.

> Prompt para Cursor + Codex:

```text
En el repo `brou-chargeback-demo/`, creá los siguientes archivos en `backend/`:

1. `backend/requirements.txt` con las dependencias (pinneadas a versiones estables a mayo 2026):
   - fastapi
   - uvicorn[standard]
   - python-dotenv
   - supabase  (>=2.0,<3)
   - google-genai  (SDK oficial de Gemini)
   - langfuse
   - sse-starlette  (para streaming SSE)
   - pydantic >=2

2. `backend/db.py`: módulo que exporta una función `get_supabase()` que devuelve un cliente Supabase singleton, leyendo `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` del `.env`. Cargar `.env` desde la raíz del repo con python-dotenv.

3. `backend/main.py`: app FastAPI con:
   - CORS habilitado para `FRONTEND_ORIGIN` (default `http://localhost:3000`).
   - Endpoint `GET /health` que devuelve `{"status":"ok","supabase":"<true/false>"}` (true si pudo hacer un `select 1` simbólico, ej. consultar count de `transactions`).
   - Endpoint `GET /transactions/sample` que devuelve las primeras 5 transacciones del `DEMO_USER_ID` ordenadas por fecha desc — útil para validar la conexión.
   - Lifecycle event al arranque que valide que las env vars críticas existen y loguea las que faltan.

4. Levantar con: `uvicorn main:app --reload --port 8000`.

Validar:
- `curl http://localhost:8000/health` → `{"status":"ok","supabase":true}`
- `curl http://localhost:8000/transactions/sample` → 5 transacciones JSON.
```

---

## Paso 5 — Tool `search_transactions`

**Objetivo:** implementar la primera tool del agente como función Python pura, expuesta también vía endpoint REST para testing.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/`, creá el archivo `tools.py` y agregá la primera tool: `search_transactions`.

Comportamiento:

Inputs (todos opcionales salvo user_id):
- user_id: uuid (siempre el de la demo)
- date_from, date_to: ISO date strings
- approximate_amount: float — monto aproximado mencionado por el usuario
- amount_tolerance_pct: float, default 20.0, mínimo 10.0
- min_amount, max_amount: floats — alternativa explícita; si vienen, ganan sobre approximate_amount
- currency: 'UYU' o 'USD'
- merchant_query: substring, case-insensitive, debe matchear en `merchant_name` y `merchant_dba` con LIKE laxo (ej. "tienda" matchea "Tienda Inglesa", "uber" matchea "Uber" y "Uber Eats")
- last_n: int, default 10, máx 20

Reglas de búsqueda por monto aproximado:
- Si viene approximate_amount y NO vienen min_amount/max_amount, calcular:
    min = approximate_amount * (1 - tolerance_pct/100)
    max = approximate_amount * (1 + tolerance_pct/100)
- Si esa búsqueda devuelve 0 resultados, ampliar a 35% UNA sola vez y reintentar. En la respuesta indicar `amount_tolerance_used_pct` con el valor efectivo.

Ordenamiento:
- Si hay approximate_amount: por |total_amount - approximate_amount| ascendente, desempate por transaction_at desc.
- Si no hay approximate_amount: transaction_at desc.

Output: dict con:
- `results`: lista de hasta `last_n` transacciones, cada una con campos: id, transaction_at, merchant_name, total_amount, currency, card_last4, entry_mode.
- `total_results`: int (cantidad antes de truncar a last_n).
- `amount_tolerance_used_pct`: float (solo si se usó approximate_amount).

Implementación:
- Usar el cliente de Supabase de `db.py`.
- La consulta debe ser un único `select`. El ordenamiento por cercanía al monto aproximado puede hacerse en Python después de traer los resultados filtrados (limitando a 50 candidatos antes de ordenar por cercanía).
- Documentar la función con docstring estilo Google con Args/Returns — el docstring se usará después como descripción para Gemini.

Además, en `main.py` registrá un endpoint `POST /tools/search_transactions` que reciba el payload JSON, llame a la función y devuelva el output. Esto es solo para testing, no es la interfaz que usará el agente.

Validar:
- `POST /tools/search_transactions` con body `{"approximate_amount": 1500, "currency": "UYU"}` devuelve resultados ordenados por cercanía a 1500.
- Probar con un monto que NO matchee a 20% para verificar el fallback a 35%.
- Probar `merchant_query: "uber"` y verificar que matchea Uber y Uber Eats.
```

---

## Paso 6 — Tool `get_transaction_context`

**Objetivo:** segunda tool: contexto de una transacción confirmada.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/tools.py`, agregá la función `get_transaction_context`.

Input:
- transaction_id: uuid

Comportamiento:
1. Traer la transacción completa por id.
2. Traer hasta 5 transacciones previas del MISMO `user_id` y MISMO `merchant_name`, EXCLUYENDO la actual, ordenadas por transaction_at desc.
3. Contar cuántas transacciones del mismo merchant_name tuvo el user en los últimos 6 meses (excluyendo la actual).

Output: dict
- `transaction`: el detalle completo de la transacción (todos los campos del schema).
- `same_merchant_history`: lista de hasta 5 elementos con {transaction_at, total_amount, currency}.
- `same_merchant_count_6m`: int.
- `nearby_transactions`: null (stub).
- `mcc_human_label`: null (stub).
- `geo_hint`: null (stub).

Si no se encuentra la transacción, retornar dict vacío con `error: "transaction_not_found"`.

Registrar también `POST /tools/get_transaction_context` con `{transaction_id}` para testing.

Validar: con un transaction_id de un comercio frecuente (ej. Netflix), `same_merchant_count_6m` debería ser >=2 según el seed.
```

---

## Paso 7 — Tool `create_chargeback_ticket` (+ generador de ticket_number)

**Objetivo:** tercera tool: persiste el ticket.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/tools.py`, agregá:

1. Función helper `generate_ticket_number()` → string en formato `CB-YYYY-NNNNNN`. La parte numérica debe ser secuencial dentro del año, calculada como `count(*) where ticket_number like 'CB-YYYY-%' + 1`, formateada con padding a 6 dígitos. Manejar la condición de carrera con un retry simple (en caso de unique violation, reintentar hasta 3 veces sumando 1).

2. Función `create_chargeback_ticket(user_id, transaction_id, reason_code, reason_label_es, user_additional_info, conversation_log, status='open', resolved_by=None)`:
   - Genera ticket_number con la función anterior.
   - Inserta fila en `chargeback_tickets`.
   - Retorna `{ticket_id, ticket_number}`.

3. Endpoint `POST /tools/create_chargeback_ticket` para testing.

Validar:
- Crear un ticket con datos de prueba.
- Verificar que el ticket_number sea `CB-2026-000001` (o el correlativo del año).
- Crear un segundo ticket: debe ser `CB-2026-000002`.
```

---

## Paso 8 — Tool `cancel_chargeback_request` (esqueleto, sin reglas todavía)

**Objetivo:** cuarta tool: cancelación que llama internamente a la función de creación.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/tools.py`, agregá `cancel_chargeback_request`.

Input:
- user_id: uuid
- transaction_id: uuid o null (puede no existir si canceló antes)
- conversation_log: list[dict]
- cancellation_reason: str

Comportamiento:
1. Llamar a `create_chargeback_ticket(...)` con:
   - reason_code='unknown_transaction'
   - reason_label_es='Desconocimiento de transacciones'
   - status='cancelled_by_user'
   - resolved_by='agent'
   - user_additional_info=cancellation_reason
   - conversation_log
2. Retornar `{ticket_id, ticket_number}`.
3. (En este paso NO llamamos todavía a apply_rules_and_summarize — eso lo encajamos en el paso 13.)

Endpoint `POST /tools/cancel_chargeback_request` para testing.

Validar: crear una cancelación y verificar que el ticket queda con status='cancelled_by_user'.
```

---

## Paso 9 — Cliente Gemini + system prompt + agent loop por consola

**Objetivo:** levantar el agente como REPL antes de meterle SSE/frontend.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/`, creá `agent.py`:

1. Importar el SDK oficial de Gemini (`from google import genai`).
2. Inicializar el cliente con `GEMINI_API_KEY` y modelo de `GEMINI_MODEL`.
3. Registrar las 4 tools existentes (search_transactions, get_transaction_context, create_chargeback_ticket, cancel_chargeback_request) como FunctionDeclarations para Gemini, derivando el schema desde los type hints de las funciones de `tools.py`. Si tener generación automática es complejo, hardcodeá las FunctionDeclaration manualmente — pero las descripciones deben coincidir con los docstrings.
4. Implementar un `system_prompt` en español rioplatense (uruguayo, "vos", "podés"). El system prompt debe:
   - Definir al modelo como "Asistente de Reclamos de BROU".
   - Empezar SIEMPRE con una pregunta abierta, SIN mencionar motivos de contracargo. Ej: "Hola, soy el asistente de BROU. ¿En qué te puedo ayudar?"
   - Clasificar internamente la intención del primer mensaje del usuario:
     - `chargeback_intent`: cargo no reconocido, movimiento raro, reclamo de tarjeta, etc.
     - `other`: saldos, sucursales, préstamos, etc.
   - Si `other`: derivar amablemente a asistencia.brou.com.uy o WhatsApp 21996000 y NO seguir el flujo.
   - Si `chargeback_intent`: presentar las 4 opciones de motivo:
     1. Desconocimiento de transacciones (no reconozco un cargo)
     2. No recibí el servicio o la mercadería
     3. Compra o retiro duplicado
     4. Error de procesamiento (la transacción dio error pero igual se procesó)
   - Solo continuar el flujo si confirma "Desconocimiento de transacciones". Para los otros 3, responder amablemente que no están disponibles en la demo y ofrecer volver al inicio.
   - Pasos siguientes (descritos al modelo en orden):
     2. Identificar la transacción → llamar `search_transactions` con monto aproximado si el usuario no recuerda exacto. Mostrar máximo 5 candidatos. Pedir confirmación.
     3. Verificación contextual → llamar `get_transaction_context`. Mostrar `same_merchant_count_6m` y `same_merchant_history` si hay frecuencia.
     4. Advertencia de costos: mostrar TEXTUAL este mensaje (configurable como constante en el código):
        > ⚠️ Importante: Iniciar un reclamo de contracargo es un proceso formal. En caso de que el reclamo sea resuelto a favor del comercio, podrías incurrir en costos administrativos según el reglamento vigente de BROU. ¿Confirmás que querés continuar?
     5. Información adicional opcional (texto libre).
     6. Crear ticket llamando `create_chargeback_ticket`.
     7. Aplicar reglas y resumen → (placeholder por ahora, lo implementamos en paso 13).
   - Si en cualquier paso el usuario quiere cancelar, llamar `cancel_chargeback_request` con resumen del progreso.
   - Tono: cordial, formal pero cercano, español rioplatense.
   - Prohibido: dar consejos legales, prometer resolución favorable, inventar datos, saltarse el paso 4.
   - Si el usuario está enojado: empatizar antes de avanzar.

5. Implementar `run_agent_loop_console()`: REPL en consola que mantiene el historial multi-turn, ejecuta function calls reales contra `tools.py`, e imprime las respuestas del agente con prefijo "Agente:" y los tool calls como "[tool: search_transactions(...)]".

6. Exportar `__main__` para correr con `python -m backend.agent`.

Definí la constante `COST_WARNING_TEXT` arriba del módulo, fácil de editar.

Validar: en consola, simular un flujo completo:
- "Hola"
- "Vi un cargo que no reconozco"
- elegir opción 1
- "Hace una semana, como 1500 pesos"
- confirmar la transacción
- "sí continúo"
- "no recuerdo más nada"
- recibir ticket número.

Verificar que el agente NO mencionó motivos en el primer mensaje y que SÍ presentó las 4 opciones después.
```

---

## Paso 10 — Endpoint SSE de chat

**Objetivo:** exponer el loop del agente como streaming HTTP.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/main.py`, agregá un endpoint `POST /chat/stream` que:

1. Recibe un body JSON: `{"session_id": str, "message": str}`.
2. Mantiene historial por `session_id` en un dict en memoria (para la demo no necesitamos Redis).
3. Llama al loop del agente (refactorizar `agent.py` para exponer `run_agent_turn(session_id, user_message) -> async generator` que yieldee eventos SSE).
4. Devuelve un `EventSourceResponse` (de `sse-starlette`) con eventos tipo:
   - `event: token` con `data: {"text": "..."}` para chunks de texto del modelo
   - `event: tool_call` con `data: {"name": "search_transactions", "args": {...}}` cuando el modelo decide llamar una tool
   - `event: tool_result` con `data: {"name": "...", "result": {...}}` después de ejecutarla
   - `event: done` con `data: {}` al final del turno

5. Asegurate de que el streaming use `text/event-stream` con headers correctos (`Cache-Control: no-cache`, `Connection: keep-alive`) y que el frontend pueda consumirlo con `EventSource` o `fetch` + ReadableStream.

6. Si Gemini soporta streaming nativo (`generate_content_stream`), usalo y convertí cada chunk a un evento `token`. Si no, simulá streaming dividiendo la respuesta final en chunks por palabra.

7. Endpoint `POST /chat/reset` que limpia el historial de un `session_id`.

Validar:
- `curl -N -X POST http://localhost:8000/chat/stream -H 'Content-Type: application/json' -d '{"session_id":"s1","message":"Hola"}'`
- Verificar que se reciben eventos `token` y un `done` al final.
```

---

## Paso 11 — Tracing con Langfuse

**Objetivo:** instrumentar el agente con tracing verboso.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/`, creá `tracing.py` y wireá Langfuse:

1. `tracing.py` inicializa el cliente de Langfuse leyendo `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Si las keys no están seteadas, exportar un mock no-op para no romper la demo.

2. Exponer helpers:
   - `start_trace(session_id, user_message) -> trace_obj`
   - `log_llm_call(trace_obj, prompt, response, model, latency_ms, input_tokens, output_tokens)`
   - `log_tool_call(trace_obj, tool_name, input_args, output, latency_ms)`
   - `log_user_turn(trace_obj, message)`
   - `log_intent_classification(trace_obj, message, classified_intent)` — si es razonable extraer la intención clasificada del modelo, sino skip

3. En `agent.py`:
   - Envolver cada turno completo del agente en una `trace` (o `update_trace` si el session ya tiene una corriendo).
   - Cada llamada a Gemini se registra como un span con prompt y respuesta COMPLETOS (es demo — sin redacción).
   - Cada tool call se registra como un span con input y output completos y latencia medida en `time.perf_counter()`.

4. Documentar en el README las env vars de Langfuse (ya están en `.env.example`).

Validar:
- Ejecutar un flujo completo desde el frontend o `curl /chat/stream`.
- Abrir el dashboard de Langfuse y verificar que aparece la trace con: el system prompt, el prompt del usuario, las llamadas a tools, y la respuesta final.
```

---

## Paso 12 — Tool `apply_rules_and_summarize` (segunda llamada a Gemini)

**Objetivo:** quinta tool: aplicar reglas y producir resumen estructurado.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/tools.py`, agregá `apply_rules_and_summarize`.

Comportamiento:
1. Input: `ticket_id` (uuid).
2. Lee `chargeback_tickets` por id (incluyendo conversation_log).
3. Si tiene `transaction_id`, lee también la transaction asociada.
4. Lee el archivo `rules.md` desde la raíz del repo en runtime (no cachear).
5. Hace una SEGUNDA llamada a Gemini (mismo modelo, SIN tools) con:
   - System prompt: "Sos un sistema experto en gestión de contracargos de BROU. Aplicá las reglas indicadas al caso y devolvé estrictamente el JSON pedido."
   - User prompt: contenido completo de `rules.md` + datos del ticket (status, reason, user_additional_info, conversation_log) + datos de la transacción (si hay).
   - Configurar `response_mime_type='application/json'` y un response_schema con:
     ```
     {
       "summary": str (3-5 líneas),
       "recommendation": str (acción concreta basada en las reglas)
     }
     ```
6. Persistir `summary` en `chargeback_tickets.agent_summary` y `recommendation` en `agent_recommendation`.
7. Output: `{summary, recommendation}`.

8. Hacer que `cancel_chargeback_request` ahora llame a `apply_rules_and_summarize` después de crear el ticket cancelado (cumple el spec).

9. Registrar la tool en el `agent.py` como FunctionDeclaration adicional para que Gemini pueda invocarla desde el paso 7 del workflow.

10. Endpoint `POST /tools/apply_rules_and_summarize` para testing manual.

Validar:
- Crear un ticket de prueba con un transaction_id de Netflix (frecuente).
- Llamar `apply_rules_and_summarize` y verificar que la `recommendation` menciona "verificar si la compra pudo haber sido realizada por un familiar autorizado o corresponder a una suscripción olvidada" (regla 2).
- Hacer otro test con transaction_id de monto < USD 10 → recomendación de devolución directa.
```

---

## Paso 13 — Frontend Next.js: bootstrap + branding BROU

**Objetivo:** levantar Next.js con Tailwind y el header de BROU.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/frontend/`, scaffoldear una app Next.js 14 (App Router) con Tailwind:

1. `npx create-next-app@latest . --ts --tailwind --app --eslint --use-npm --no-src-dir --import-alias "@/*"`
2. Configurar `tailwind.config.ts` con los colores BROU:
   - `brou-blue: '#003DA5'`
   - `brou-blue-dark: '#002B7F'`
   - `brou-yellow: '#FFC72C'`
   - `brou-gray: '#F5F5F5'`
3. Crear `app/page.tsx` con la home, que muestra:
   - Header full-width fondo `brou-blue`, altura ~64px:
     - Izquierda: texto "BROU" en blanco, font-bold, tracking-wider, text-2xl. Si querés, una "B" estilizada en un cuadrado blanco a la izquierda como logo placeholder.
     - Derecha: subtítulo "Asistente de Reclamos" en blanco/90.
   - Body: contenedor centrado max-w-3xl con un placeholder "Chat va acá".
   - Footer fixed bottom: texto pequeño centrado "Demo — datos ficticios", color gray-500.
4. Tipografía: importar Inter desde Google Fonts en `layout.tsx`.
5. `frontend/.env.local.example` con `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.

Validar: `npm run dev` y abrir http://localhost:3000. Header azul con "BROU" + "Asistente de Reclamos", body vacío con placeholder.
```

---

## Paso 14 — Frontend: ventana de chat + consumo de SSE

**Objetivo:** chat funcional contra `/chat/stream`.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/frontend/`, reemplazá el placeholder del body de `app/page.tsx` con un componente de chat completo.

Requerimientos:

1. Componente `<ChatWindow />` (puede ser client component, `'use client'`).
2. Estado local:
   - `messages: Message[]` con shape `{role: 'user' | 'agent', content: string, toolCalls?: ToolCall[]}`
   - `input: string`
   - `isStreaming: boolean`
   - `sessionId: string` — generado al montar con `crypto.randomUUID()`.

3. UI:
   - Lista de burbujas:
     - Usuario: alineadas a la derecha, fondo gris-200, esquinas redondeadas, texto negro.
     - Agente: alineadas a la izquierda, fondo blanco con borde 1px `brou-blue`, esquinas redondeadas, texto negro.
   - Auto-scroll al último mensaje al recibir streams.
   - Input de texto + botón "Enviar" en `brou-blue` con texto blanco. Submit con Enter.
   - Indicador "escribiendo..." (3 puntitos animados) cuando `isStreaming=true` y todavía no llegó ningún token del turno actual.
   - Chips discretos cuando llega un evento `tool_call`: ej. "🔍 Buscando transacciones..." en chip gris, debajo del último mensaje del agente y arriba del próximo. Al recibir el `tool_result` correspondiente, marcar el chip como "completado" (cambiar a tono más oscuro, mantener visible).

4. Lógica de conexión a SSE:
   - Al enviar un mensaje, hacer `POST /chat/stream` con `fetch` y leer el body como ReadableStream (NO usar `EventSource` porque no soporta POST). Parsear los eventos SSE manualmente (`event:` / `data:` / blank line delimiter).
   - Eventos:
     - `token`: appendear texto al último mensaje del agente (creando uno si no existe en el turno actual).
     - `tool_call`: agregar un chip en estado "running".
     - `tool_result`: marcar el chip correspondiente como "done".
     - `done`: cerrar el turno, `setIsStreaming(false)`.

5. Mensaje inicial del agente: al montar por primera vez, hacer un POST con `message: ""` (o un mensaje del tipo "__init__") para que el agente envíe el saludo de apertura. Alternativa: hardcodear "Hola, soy el asistente de BROU. ¿En qué te puedo ayudar?" como primer mensaje del agente y dejar que el modelo continúe desde ahí.

6. Estilo: Tailwind. Layout: contenedor max-w-3xl, mx-auto, height calc(100vh - header - footer), flex column, scroll en la lista, footer pegado abajo del contenedor con el input.

Validar:
- Abrir http://localhost:3000.
- Aparece el saludo del agente.
- Escribir "Vi un cargo raro" → el agente ofrece las 4 opciones.
- Continuar el flujo y ver los chips de tool calls aparecer.
```

---

## Paso 15 — Conversation log y robustez del flujo end-to-end

**Objetivo:** guardar el conversation_log en el ticket y cubrir caminos de cancelación.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/`, ajustar:

1. En `agent.py`, mantener el historial estructurado del turno actual y la sesión completa como `list[{"role": "user"|"agent"|"tool", "content": str, "ts": iso8601}]`.
2. Cuando el agente invoque `create_chargeback_ticket` o `cancel_chargeback_request`, pasar el `conversation_log` completo de la sesión hasta ese momento.
3. Tras crear el ticket en el paso 6 del workflow, el agente debe llamar `apply_rules_and_summarize(ticket_id)` y luego mostrarle al usuario:
   - El número de ticket.
   - Un mensaje de cierre cordial.
   - (Opcional) un resumen de una línea de la sugerencia, sin entrar en detalle técnico.
4. En cualquier punto, si el usuario dice algo tipo "cancelar", "dejá", "no quiero seguir", "olvidate", el agente debe:
   - Confirmar amablemente.
   - Llamar `cancel_chargeback_request` con el `conversation_log` y un `cancellation_reason` corto inferido del contexto.
   - Despedirse.

5. Asegurar que el system prompt explicita esta ruta de cancelación.

Validar:
- Flujo feliz: termina en ticket con agent_summary y agent_recommendation poblados.
- Flujo cancelado en paso 3: ticket con status='cancelled_by_user', resolved_by='agent', agent_summary explicando que canceló al ver el contexto.
- Inspeccionar `chargeback_tickets.conversation_log` en Supabase y verificar que está completo.
```

---

## Paso 16 — Manejo de motivos no implementados

**Objetivo:** cerrar el flujo cuando el usuario elige un motivo distinto al implementado.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/backend/agent.py`:

1. Reforzar en el system prompt que SOLO el flujo "Desconocimiento de transacciones" está disponible en la demo.
2. Cuando el usuario elija el motivo 2, 3 o 4, el agente debe:
   - Responder amablemente: "Por ahora ese flujo no está disponible en la demo. ¿Querés que volvamos al inicio o necesitás otra cosa?"
   - NO crear ticket.
   - Si el usuario reformula y dice que en realidad es desconocimiento, retomar el flujo en el paso 2.

3. Si el usuario hace una consulta clara fuera de scope desde el primer mensaje (saldos, sucursales, préstamos), el agente debe:
   - Responder cordial.
   - Sugerir asistencia.brou.com.uy o WhatsApp 21996000.
   - NO crear ticket.

Validar:
- Test 1: "Hola, quiero ver mi saldo" → derivación amable, sin tools llamadas.
- Test 2: "Tengo un cargo raro" → opciones → elegir "Compra duplicada" → mensaje de "no disponible en demo".
```

---

## Paso 17 — README final + script de demo

**Objetivo:** documentación final con guion ejecutable.

> Prompt para Cursor + Codex:

```text
Actualizar `brou-chargeback-demo/README.md`:

1. Verificar que la sección "Setup" tenga los comandos correctos según lo implementado.
2. Expandir la sección "Guion de demo (sugerido)" con 3 escenarios completos:
   - Camino feliz (regla 2 — comercio frecuente como Netflix).
   - Cancelación a mitad de flujo.
   - Motivo no implementado.
3. Agregar sección "Troubleshooting" con los problemas comunes:
   - "Workspace still starting" en cualquier llamada → reintentar.
   - 401 en Supabase → verificar service_role_key (NO la anon).
   - Gemini quota → verificar límites en AI Studio.
   - SSE se corta → verificar que el frontend no esté detrás de un proxy bufferiseante.
4. Agregar una sección "Decisiones de diseño en demo" con todas las decisiones que se tomaron en el camino para mantener la demo simple.

5. Crear `docs/DEMO_SCRIPT.md` con el guion paso a paso para una demo en vivo de ~10 minutos:
   - Pre-checks (backend up, frontend up, Langfuse abierto).
   - Apertura: por qué importa este caso (Uruguay, BROU, contracargos).
   - Demo del camino feliz.
   - Mostrar Langfuse con la trace completa.
   - Demo de la cancelación.
   - Cierre: qué falta para producción.

Validar: leer ambos documentos y que cualquier persona técnica pueda levantar el proyecto desde cero siguiendo el README.
```

---

## Paso 18 — QA final: checklist end-to-end

**Objetivo:** validar que todos los caminos funcionan antes de mostrar la demo.

> Prompt para Cursor + Codex:

```text
En `brou-chargeback-demo/`, creá `docs/QA_CHECKLIST.md` y ejecutá cada item, marcando con [x] los que pasan y dejando notas en los que no.

Checklist:

### Setup
- [ ] `.env` completo, todas las variables seteadas.
- [ ] Migraciones aplicadas en Supabase (verificar tablas en Studio).
- [ ] `python supabase/seed.py` corre sin errores y reporta 90 transacciones.
- [ ] Backend levanta con `uvicorn main:app --reload --port 8000` y `/health` devuelve 200.
- [ ] Frontend levanta con `npm run dev` y carga en localhost:3000.

### Tools (vía endpoints REST)
- [ ] `POST /tools/search_transactions` con monto exacto devuelve resultados.
- [ ] `POST /tools/search_transactions` con `approximate_amount=1500` devuelve resultados ordenados por cercanía.
- [ ] Cuando no hay match a 20%, fallback a 35% activado y reportado en `amount_tolerance_used_pct`.
- [ ] `merchant_query` matchea sustrings laxos ("uber" → Uber + Uber Eats).
- [ ] `POST /tools/get_transaction_context` devuelve historial y count del comercio.
- [ ] `POST /tools/create_chargeback_ticket` genera ticket_number con formato `CB-2026-NNNNNN`.
- [ ] `POST /tools/apply_rules_and_summarize` devuelve summary y recommendation, y persiste en DB.

### Flujos del agente (vía frontend)
- [ ] Flujo feliz completo: saludo → intención → motivo → búsqueda → confirmación → contexto → advertencia → info → ticket → cierre con resumen. Ticket queda con status='open' y agent_summary poblado.
- [ ] Flujo con regla 1 (monto bajo): elegir transacción de < USD 10 → recomendación de devolución directa.
- [ ] Flujo con regla 2 (frecuente): elegir transacción de Netflix → recomendación menciona suscripción/familiar.
- [ ] Flujo con regla 4 (internacional): elegir transacción AliExpress → recomendación menciona fraude internacional.
- [ ] Flujo con regla 5 (tokenizada): elegir transacción tokenizada → recomendación menciona dispositivo.
- [ ] Cancelación a mitad de flujo (en paso 3 de verificación contextual): ticket con status='cancelled_by_user', resolved_by='agent', agent_summary cubre hasta dónde llegó.
- [ ] Motivo no implementado: elegir opción 2/3/4 → mensaje de "no disponible en demo", sin ticket creado.
- [ ] Intent fuera de scope: "quiero ver mi saldo" → derivación a canales BROU, sin tools llamadas.
- [ ] Tono del agente: usa "vos/podés/querés" consistentemente. NO menciona motivos de contracargo en el primer mensaje. NO se salta el paso de advertencia de costos.
- [ ] Chips de tool calls aparecen en el frontend al ejecutarse tools.

### Tracing
- [ ] Cada conversación genera una trace en Langfuse con todos los spans (LLM calls + tool calls + user turns).
- [ ] Los prompts y respuestas están sin obfuscar.

### Reglas y límites
- [ ] No hay autenticación; el `user_id` viene del `.env`.
- [ ] El agente NO inventa transacciones inexistentes.
- [ ] El agente NO promete resoluciones favorables.
- [ ] El agente NO da consejos legales.

Si algún check falla, abrir un issue/TODO en `docs/QA_CHECKLIST.md` debajo del item con el detalle del bug y el archivo a tocar.

Validar: este paso se considera completo cuando todos los checkboxes están marcados o todos los fallos están documentados con un plan de fix.
```

---

## Resumen de pasos

| # | Paso | Archivo principal | Validación |
|---|---|---|---|
| 1 | Migración `transactions` | `supabase/migrations/001_transactions.sql` | SQL ejecuta sin error |
| 2 | Migración `chargeback_tickets` | `supabase/migrations/002_chargeback_tickets.sql` | SQL ejecuta sin error |
| 3 | Seed 90 transacciones | `supabase/seed.py` | 90 filas, garantías cumplidas |
| 4 | Backend bootstrap | `backend/main.py`, `db.py` | `/health` y `/transactions/sample` |
| 5 | Tool `search_transactions` | `backend/tools.py` | Match por monto aproximado y merchant_query |
| 6 | Tool `get_transaction_context` | `backend/tools.py` | Historial y count del comercio |
| 7 | Tool `create_chargeback_ticket` | `backend/tools.py` | ticket_number correlativo |
| 8 | Tool `cancel_chargeback_request` | `backend/tools.py` | Ticket con status='cancelled_by_user' |
| 9 | Cliente Gemini + agent loop CLI | `backend/agent.py` | Flujo completo por consola |
| 10 | Endpoint SSE `/chat/stream` | `backend/main.py` | Stream con tokens y tool calls |
| 11 | Tracing Langfuse | `backend/tracing.py` | Trace completa en dashboard |
| 12 | Tool `apply_rules_and_summarize` | `backend/tools.py` | Reglas correctamente aplicadas |
| 13 | Frontend bootstrap + branding | `frontend/app/page.tsx` | Header BROU visible |
| 14 | Frontend chat + SSE | `frontend/app/page.tsx` | Chat E2E contra backend |
| 15 | Conversation log + cierre | `backend/agent.py` | conversation_log persistido |
| 16 | Motivos no implementados | `backend/agent.py` | Mensaje correcto en motivos 2/3/4 |
| 17 | README + DEMO_SCRIPT | `README.md`, `docs/DEMO_SCRIPT.md` | Doc completa |
| 18 | QA checklist | `docs/QA_CHECKLIST.md` | Todos los checks ok |

---

## Cómo usar este plan en Cursor + Codex

1. Abrir Cursor en la raíz del repo `brou-chargeback-demo/`.
2. Activar Codex (Cmd+L en Cursor).
3. Para cada paso: copiar el bloque de prompt entre triple backticks, pegarlo en el chat de Cursor, y dejarlo correr.
4. Después de cada paso, ejecutar la sección "Validar" antes de avanzar al siguiente.
5. Si Codex se queda corto en algún paso, agregar contexto extra del spec original (`docs/spec.md` si lo movés ahí) o pedirle iteraciones específicas.

> **Tip:** podés referenciar archivos existentes en Cursor con `@archivo`. Por ejemplo, en el paso 5 podés agregar al final del prompt: "Mirá @backend/db.py y @backend/main.py para mantener consistencia."
