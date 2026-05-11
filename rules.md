# Reglas de evaluación de contracargos — BROU

> Este archivo es leído en runtime por la tool `apply_rules_and_summarize`.
> Editar libremente sin tocar código. El agente lo carga en cada invocación.

## Reglas activas

1. **Monto bajo.** Si el monto reclamado es menor a USD 10 (o equivalente en UYU usando `fx_rate` cuando exista), recomendar:
   > "Devolución directa al cliente sin investigación adicional. El costo operativo de investigar supera el monto reclamado."

2. **Comercio frecuente.** Si el cliente tiene 3 o más transacciones previas con el mismo `merchant_name` en los últimos 6 meses, recomendar:
   > "Solicitar al cliente verificar si la compra pudo haber sido realizada por un familiar autorizado o corresponder a una suscripción olvidada antes de escalar el caso."

3. **Transacción presencial con verificación fuerte.** Si `card_present = true` y `cvm in ('pin','biometric')`, recomendar:
   > "Caso requiere investigación adicional. Hay verificación de identidad fuerte presente (PIN o biometría). Solicitar al cliente reporte policial y revisar coincidencia con su ubicación habitual."

4. **Comercio o ubicación sospechosa.** Si `merchant_country` no es UY, o el `mcc` está en lista de alto riesgo (5967 servicios para adultos online, 7995 apuestas, 6051 cuasi‑cash / cripto), marcar como sospechosa y recomendar:
   > "Priorizar el caso. Posible fraude internacional o de alta categoría de riesgo. Bloquear preventivamente la tarjeta."

5. **Tarjeta tokenizada (Apple Pay / Google Pay).** Si `is_tokenized = true`, recomendar:
   > "Investigar dispositivo asociado. Es más probable robo o compromiso del dispositivo móvil que de la tarjeta física. Solicitar al cliente revisar dispositivos vinculados."

## Reglas para casos cancelados

- Si el ticket tiene `status = 'cancelled_by_user'`, generar igualmente un resumen indicando:
  - Hasta qué paso del flujo llegó la conversación.
  - Si el usuario explicitó una razón para cancelar, transcribirla.
  - Marcar `recommendation` como: `"Sin acción. Caso cerrado por decisión del cliente."`

## Combinación de reglas

Si más de una regla aplica al mismo ticket, la `recommendation` debe listar las acciones priorizadas en este orden: 4 (sospecha) → 3 (verificación fuerte) → 5 (tokenización) → 2 (frecuente) → 1 (monto bajo).
