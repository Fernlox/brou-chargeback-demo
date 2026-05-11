# DEMO SCRIPT — BROU Chargeback Demo (~10 minutos)

## 1) Pre-checks (1 minuto)

Antes de empezar la demo, verificar:

- Backend levantado: `http://localhost:8000/health` responde `{"status":"ok","supabase":true}`.
- Frontend levantado: `http://localhost:3000` muestra header BROU y chat.
- Base seed cargada (90 transacciones para `DEMO_USER_ID`).
- Langfuse abierto en navegador (proyecto correcto).
- Variables necesarias configuradas:
  - `.env` con `GEMINI_*`, `SUPABASE_*`, `DEMO_USER_ID`, `LANGFUSE_*`.
  - `frontend/.env.local` con `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.

Mensaje sugerido:

> "Vamos a recorrer un caso de reclamo de contracargo de punta a punta, incluyendo búsqueda de transacción, creación de ticket, aplicación de reglas y trazabilidad completa."

---

## 2) Apertura (1 minuto)

Narrativa sugerida:

- "Este caso es relevante para Uruguay y para BROU porque muchos reclamos arrancan como conversaciones poco estructuradas."
- "La demo muestra cómo pasar de lenguaje natural a acciones auditables: tools, ticket y recomendación."
- "Todo corre local, con datos ficticios, pero usando componentes reales: FastAPI, Supabase, Gemini y Langfuse."

---

## 3) Camino feliz (4 minutos)

Objetivo: llegar a ticket generado con resumen y recomendación.

### Flujo conversacional sugerido

1. Usuario:
   - "Hola, vi un cargo raro en mi tarjeta."
2. Agente:
   - detecta motivo directo si el mensaje ya es claro, o muestra botones con opciones de motivo si es ambiguo.
3. Usuario:
   - si hubo opciones, elige "Desconocimiento de transacciones" con botón.
4. Usuario:
   - "Fue de unos 19 USD, creo que en Netflix."
5. Agente:
   - busca transacciones, muestra candidatos.
6. Usuario:
   - confirma la transacción correcta (preferentemente con botón de selección).
7. Agente:
   - muestra contexto del comercio (historial/frecuencia).
8. Usuario:
   - confirma continuar (también disponible como botón).
9. Agente:
   - muestra advertencia de costos.
10. Usuario:
    - acepta advertencia + agrega comentario opcional.
11. Agente:
    - crea ticket y responde con `ticket_number` + cierre cordial.

### Qué destacar mientras ocurre

- Chips de tools en UI (`tool_call` / `tool_result`).
- Streaming de respuesta por SSE (`token`).
- Ticket persistido en Supabase.
- Reglas aplicadas automáticamente para `agent_summary` y `agent_recommendation`.

---

## 4) Mostrar Langfuse (1.5 minutos)

Abrir la traza recién generada y recorrer:

- Turnos usuario/agente.
- Llamadas a tools (inputs/outputs y latencias).
- Respuesta final y metadatos del modelo.

Mensaje sugerido:

> "Lo importante no es solo que responda bien, sino que podamos auditar cómo llegó a esa respuesta."

---

## 5) Demo de cancelación (1.5 minutos)

Objetivo: mostrar robustez cuando el usuario desiste.

Flujo sugerido:

1. Iniciar reclamo normalmente hasta mitad del flujo.
2. Usuario:
   - "Mejor dejá, no quiero seguir."
3. Agente:
   - confirma cancelación y cierra cordialmente.
4. Resultado esperado:
   - ticket creado con `status='cancelled_by_user'`,
   - `resolved_by='agent'`,
   - `conversation_log` completo,
   - resumen/recomendación poblados.

Si hay tiempo, mostrar también este ticket en Supabase o en traza Langfuse.

---

## 6) Cierre: qué falta para producción (1 minuto)

Checklist breve para cerrar:

- Autenticación y autorización reales por cliente.
- Integraciones bancarias reales (core, tarjetas, antifraude).
- Seguridad y compliance (redacción/PII, políticas de retención, cifrado adicional).
- Guardrails más estrictos y tests automatizados E2E/CI.
- Operación productiva: observabilidad avanzada, alertas, retries distribuidos, colas y rate limiting.

Mensaje final sugerido:

> "La demo valida el flujo funcional y la arquitectura base. El siguiente paso es endurecerla para entornos regulados y producción."

