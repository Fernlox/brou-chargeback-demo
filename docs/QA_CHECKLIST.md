# QA Checklist — Paso 18 (End-to-End)

Fecha de ejecución: 2026-05-11

> Instrucción de uso: marcar cada ítem con `[x]` si pasa.  
> Si falla, dejarlo en `[ ]` y documentar debajo: síntoma, evidencia, archivo a tocar y mini plan de fix.

## Setup

- [x] `.env` completo, todas las variables seteadas.
  - Evidencia: verificación automática de `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DEMO_USER_ID`, `NEXT_PUBLIC_BACKEND_URL` sin faltantes.
- [x] Migraciones aplicadas en Supabase (verificar tablas en Studio).
  - Evidencia: `/health` con `supabase=true` y tools operativas (`search_transactions`, `create_chargeback_ticket`, `apply_rules_and_summarize`).
- [ ] `python supabase/seed.py` corre sin errores y reporta 90 transacciones.
  - Síntoma: el seed falla al limpiar `transactions` por FK con `chargeback_tickets`.
  - Evidencia: error `23503` (`transactions` referenciada por `chargeback_tickets_transaction_id_fkey`).
  - Archivo probable a tocar: `supabase/seed.py`.
  - Mini plan de fix:
    1. limpiar primero `chargeback_tickets` del `DEMO_USER_ID` (o transacciones relacionadas),
    2. luego borrar/insertar `transactions`,
    3. mantener salida final con conteo 90.
- [x] Backend levanta con `uvicorn main:app --reload --port 8000` y `/health` devuelve 200.
  - Evidencia: readiness de uvicorn en terminal y validación de `/health` por `TestClient` (`200`, `{"status":"ok","supabase":true}`).
- [ ] Frontend levanta con `npm run dev` y carga en localhost:3000.
  - Síntoma: startup confirmado (`Next.js Ready`) pero proceso se corta al final de la ventana de ejecución de esta sesión automatizada.
  - Evidencia: logs `npm run dev` muestran URL local y `Ready in 376ms`, seguido de finalización del job.
  - Archivo probable a tocar: sin cambios de código por ahora (revalidación manual).
  - Mini plan de fix:
    1. correr `npm run dev` en terminal interactiva local,
    2. abrir `http://localhost:3000`,
    3. marcar check cuando se confirme carga estable.

## Tools (vía endpoints REST)

- [x] `POST /tools/search_transactions` con monto exacto devuelve resultados.
  - Evidencia: `status=200`, `total_results=1`.
- [x] `POST /tools/search_transactions` con `approximate_amount=1500` devuelve resultados ordenados por cercanía.
  - Evidencia: `status=200`, orden por cercanía validado programáticamente (`ordered=true`).
- [x] Cuando no hay match a 20%, fallback a 35% activado y reportado en `amount_tolerance_used_pct`.
  - Evidencia: caso detectado (`approximate_amount=14700`) con `amount_tolerance_used_pct=35.0`.
- [x] `merchant_query` matchea sustrings laxos ("uber" → Uber + Uber Eats).
  - Evidencia: resultados contienen `Uber` y `Uber Eats`.
- [x] `POST /tools/get_transaction_context` devuelve historial y count del comercio.
  - Evidencia: `same_merchant_history` (lista) y `same_merchant_count_6m` (entero) presentes.
- [x] `POST /tools/create_chargeback_ticket` genera ticket_number con formato `CB-2026-NNNNNN`.
  - Evidencia: `ticket_number=CB-2026-000008`, regex válida para año actual.
- [x] `POST /tools/apply_rules_and_summarize` devuelve summary y recommendation, y persiste en DB.
  - Evidencia: response con ambos campos + persistencia confirmada en `chargeback_tickets`.

## Flujos del agente (vía frontend)

- [ ] Flujo feliz completo: saludo → intención → motivo → búsqueda → confirmación → contexto → advertencia → info → ticket → cierre con resumen. Ticket queda con status='open' y agent_summary poblado.
  - Síntoma: en corrida automatizada de conversación, el flujo llegó hasta pedir info adicional pero no cerró con creación de ticket en ese turno.
  - Evidencia: transcript `qa-happy-singleproc2` termina sin `create_chargeback_ticket`.
  - Archivo probable a tocar: `backend/agent.py` (coordinación final paso 6→7 del prompt/loop).
  - Mini plan de fix:
    1. agregar criterio más explícito en prompt para crear ticket inmediatamente tras recibir info adicional,
    2. agregar test conversacional automatizado de cierre feliz.
- [x] Flujo con regla 1 (monto bajo): elegir transacción de < USD 10 → recomendación de devolución directa.
  - Evidencia: ticket de `Spotify USD 7.99` con recomendación de devolución directa.
- [x] Flujo con regla 2 (frecuente): elegir transacción de Netflix → recomendación menciona suscripción/familiar.
  - Evidencia: recomendación incluye “suscripción olvidada”/“familiar autorizado”.
- [x] Flujo con regla 4 (internacional): elegir transacción AliExpress → recomendación menciona fraude internacional.
  - Evidencia: recomendación incluye “fraude internacional”.
- [x] Flujo con regla 5 (tokenizada): elegir transacción tokenizada → recomendación menciona dispositivo.
  - Evidencia: recomendación incluye “dispositivo asociado”.
- [x] Cancelación a mitad de flujo (en paso 3 de verificación contextual): ticket con status='cancelled_by_user', resolved_by='agent', agent_summary cubre hasta dónde llegó.
  - Evidencia: flujo `qa-cancel-debug` crea ticket `CB-2026-000009`; DB confirma `status='cancelled_by_user'`, `resolved_by='agent'`, resumen completo.
- [x] Motivo no implementado: elegir opción 2/3/4 → mensaje de "no disponible en demo", sin ticket creado.
  - Evidencia: input `Compra duplicada` devuelve mensaje exacto; `tool_calls=[]`.
- [ ] Detección directa del caso 1: texto como "Veo un cargo equivocado en mi tarjeta" evita pedir menú de motivos y pasa a identificar transacción.
  - Síntoma: falta validación manual post-cambio.
  - Evidencia: se agregó clasificación heurística + routing hint en `backend/agent.py`.
  - Archivo probable a tocar: `backend/agent.py` (si en validación manual vuelve a pedir menú de motivos).
  - Mini plan de fix:
    1. revisar keywords de detección en `_classify_chargeback_reason_hint`,
    2. reforzar instrucción del `SYSTEM_PROMPT`,
    3. repetir prueba con frases variantes.
- [ ] Botones de opciones en chat (`quick_replies`) para motivos, selección de transacción y continuar/cancelar.
  - Síntoma: falta validación manual post-cambio.
  - Evidencia: backend emite evento SSE `quick_replies` y frontend renderiza botones clickeables en `ChatWindow.tsx`.
  - Archivo probable a tocar: `frontend/components/ChatWindow.tsx` y/o `backend/agent.py` (si no aparecen opciones o no envían texto correcto).
  - Mini plan de fix:
    1. validar en navegador que aparezcan botones en cada paso esperado,
    2. revisar payload del evento `quick_replies`,
    3. ajustar mapeo `label/value` en frontend.
- [x] Intent fuera de scope: "quiero ver mi saldo" → derivación a canales BROU, sin tools llamadas.
  - Evidencia: respuesta deriva a `asistencia.brou.com.uy` / `21996000`; `tool_calls=[]`.
- [x] Tono del agente: usa "vos/podés/querés" consistentemente. NO menciona motivos de contracargo en el primer mensaje. NO se salta el paso de advertencia de costos.
  - Evidencia: respuestas observadas usan voseo; advertencia de costos aparece antes de continuar; saludo inicial sin listado de motivos está hardcodeado en frontend.
- [ ] Chips de tool calls aparecen en el frontend al ejecutarse tools.
  - Síntoma: no se validó visualmente en navegador en esta corrida automatizada.
  - Evidencia: código de render existe en `frontend/components/ChatWindow.tsx`, pero falta verificación manual de UI.
  - Archivo probable a tocar: `frontend/components/ChatWindow.tsx` (solo si falla validación manual).
  - Mini plan de fix:
    1. abrir frontend local,
    2. ejecutar un flujo con tool calls (`search_transactions`, `get_transaction_context`),
    3. confirmar chips running/done en pantalla.

## Tracing

- [ ] Cada conversación genera una trace en Langfuse con todos los spans (LLM calls + tool calls + user turns).
  - Síntoma: no validado en UI de Langfuse durante esta ejecución.
  - Evidencia: instrumentación activa en backend, pero faltó inspección visual de trazas.
  - Archivo probable a tocar: `backend/tracing.py` (si faltan spans en validación manual).
  - Mini plan de fix:
    1. abrir Langfuse,
    2. ejecutar una conversación completa,
    3. revisar presence/shape de spans por turno y tool.
- [ ] Los prompts y respuestas están sin obfuscar.
  - Síntoma: no validado en dashboard.
  - Evidencia: no hay capa explícita de obfuscación en código, pero falta confirmación en UI.
  - Archivo probable a tocar: `backend/tracing.py` (si se detecta redacción no esperada).
  - Mini plan de fix:
    1. abrir un trace reciente en Langfuse,
    2. revisar campos prompt/response completos.

## Reglas y límites

- [x] No hay autenticación; el `user_id` viene del `.env`.
  - Evidencia: el flujo usa `DEMO_USER_ID` y no hay capa auth en backend/frontend.
- [x] El agente NO inventa transacciones inexistentes.
  - Evidencia: búsquedas y confirmaciones observadas usan IDs/merchants existentes en DB.
- [x] El agente NO promete resoluciones favorables.
  - Evidencia: respuestas revisadas no prometen resolución; mantienen tono condicional/procedimental.
- [x] El agente NO da consejos legales.
  - Evidencia: respuestas revisadas se mantienen en proceso operativo de reclamo.

## Notas de fallos y plan de fix

Fallos actuales documentados en los ítems:
- Seed script (`supabase/seed.py`) por FK al limpiar `transactions`.
- Verificación manual pendiente de frontend estable en localhost:3000.
- Flujo feliz completo no cerró ticket en la corrida automatizada.
- Verificación visual pendiente de chips en frontend.
- Verificación manual pendiente de tracing en Langfuse.
