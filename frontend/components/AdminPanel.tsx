"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchBackendJson } from "@/lib/backendApi";

type TicketSummary = {
  total: number;
  open: number;
  cancelled_by_user: number;
  by_status?: Record<string, number>;
};

type TicketListItem = {
  id: string;
  ticket_number: string;
  status: string;
  reason_label_es: string;
  created_at: string;
  updated_at: string;
  transaction_id?: string | null;
  transaction?: {
    id: string;
    transaction_at: string;
    merchant_name: string;
    total_amount: number;
    currency: string;
    card_last4?: string | null;
  } | null;
};

type TicketDetail = {
  id: string;
  ticket_number: string;
  user_id: string;
  transaction_id?: string | null;
  reason_code: string;
  reason_label_es: string;
  user_additional_info?: string | null;
  status: string;
  resolved_by?: string | null;
  agent_summary?: string | null;
  agent_recommendation?: string | null;
  conversation_log?: Array<Record<string, unknown>> | null;
  created_at: string;
  updated_at: string;
  transaction?: Record<string, unknown> | null;
};

type ConversationMessage = {
  roleLabel: string;
  content: string;
  timestamp?: string;
  bubbleClass: string;
  isToolMessage?: boolean;
};

const STATUS_LABELS: Record<string, string> = {
  open: "Abierto",
  cancelled_by_user: "Cancelado por el usuario",
  in_review: "En revision",
  resolved_favorable: "Resuelto favorable",
  resolved_unfavorable: "Resuelto desfavorable",
};

const STATUS_BADGE_CLASSES: Record<string, string> = {
  open: "border-sky-200 bg-sky-50 text-sky-700",
  cancelled_by_user: "border-slate-300 bg-slate-100 text-slate-600",
  in_review: "border-amber-200 bg-amber-50 text-amber-700",
  resolved_favorable: "border-emerald-200 bg-emerald-50 text-emerald-700",
  resolved_unfavorable: "border-rose-200 bg-rose-50 text-rose-700",
};

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("es-UY");
}

function formatAmount(amount?: number, currency?: string): string {
  if (amount == null || !currency) {
    return "-";
  }
  return new Intl.NumberFormat("es-UY", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function getStatusBadgeClass(status: string): string {
  return STATUS_BADGE_CLASSES[status] ?? "border-brou-blue/30 bg-brou-blue/5 text-brou-blue";
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toTextValue(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number") {
    return String(value);
  }
  return null;
}

function toNumberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function toBooleanValue(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  return null;
}

function mapCardBrand(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const labels: Record<string, string> = {
    visa: "Visa",
    mastercard: "Mastercard",
    amex: "American Express",
  };
  return labels[value] ?? value.toUpperCase();
}

function mapEntryMode(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const labels: Record<string, string> = {
    chip: "Chip",
    contactless: "Contactless",
    manual: "Ingreso manual",
    online: "En linea",
  };
  return labels[value] ?? value;
}

function mapCvm(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const labels: Record<string, string> = {
    pin: "PIN",
    signature: "Firma",
    biometric: "Biometria",
    none: "Sin verificacion",
  };
  return labels[value] ?? value;
}

function mapRole(entry: Record<string, unknown>): { roleLabel: string; bubbleClass: string } {
  const rawRole = typeof entry.role === "string" ? entry.role.toLowerCase() : "";
  if (rawRole.includes("user") || rawRole.includes("cliente")) {
    return { roleLabel: "Cliente", bubbleClass: "border-slate-200 bg-white" };
  }
  if (rawRole.includes("assistant") || rawRole.includes("agent")) {
    return { roleLabel: "Asistente", bubbleClass: "border-sky-200 bg-sky-50/70" };
  }
  if (rawRole.includes("tool")) {
    return { roleLabel: "Herramienta", bubbleClass: "border-indigo-200 bg-indigo-50/70" };
  }
  return { roleLabel: "Sistema", bubbleClass: "border-slate-200 bg-slate-50" };
}

function buildConversationMessages(
  log?: Array<Record<string, unknown>> | null,
): ConversationMessage[] {
  if (!Array.isArray(log)) {
    return [];
  }

  return log
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((entry) => {
      const mappedRole = mapRole(entry);
      const rawContent =
        typeof entry.content === "string"
          ? entry.content
          : JSON.stringify(entry.content ?? "", null, 2);
      const content =
        mappedRole.roleLabel === "Herramienta" ? formatToolConversationContent(rawContent) : rawContent;
      const timestamp = typeof entry.ts === "string" ? entry.ts : undefined;

      return {
        roleLabel: mappedRole.roleLabel,
        bubbleClass: mappedRole.bubbleClass,
        content,
        timestamp,
        isToolMessage: mappedRole.roleLabel === "Herramienta",
      };
    });
}

function formatToolName(name: string): string {
  const labels: Record<string, string> = {
    search_transactions: "Busqueda de transacciones",
    get_transaction_context: "Contexto de transaccion",
    create_chargeback_ticket: "Creacion de reclamo",
    cancel_chargeback_request: "Cancelacion de reclamo",
    apply_rules_and_summarize: "Analisis y resumen",
  };
  return labels[name] ?? name;
}

function summarizeSearchTransactions(payload: Record<string, unknown>): string {
  const results = Array.isArray(payload.results) ? payload.results : [];
  const total = typeof payload.total_results === "number" ? payload.total_results : results.length;
  if (total === 0) {
    return "No se encontraron transacciones con los criterios enviados.";
  }

  const topItems = results
    .slice(0, 3)
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const row = item as Record<string, unknown>;
      const merchant = toTextValue(row.merchant_name) ?? "Comercio";
      const amount = toNumberValue(row.total_amount);
      const currency = toTextValue(row.currency) ?? "";
      const date = formatDate(toTextValue(row.transaction_at));
      const amountLabel = amount != null ? formatAmount(amount, currency || undefined) : currency;
      return `- ${merchant} (${amountLabel || "-"}) - ${date}`;
    })
    .filter((line): line is string => Boolean(line));

  return [
    `Se encontraron ${total} transacciones.`,
    topItems.length > 0 ? "Primeros resultados:" : null,
    ...topItems,
  ]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

function summarizeTransactionContext(payload: Record<string, unknown>): string {
  const transaction = toRecord(payload.transaction);
  if (!transaction) {
    return "No se pudo recuperar el contexto de la transaccion.";
  }

  const merchant = toTextValue(transaction.merchant_name) ?? "Comercio";
  const amount = toNumberValue(transaction.total_amount);
  const currency = toTextValue(transaction.currency);
  const date = formatDate(toTextValue(transaction.transaction_at));
  const sameMerchantCount =
    typeof payload.same_merchant_count_6m === "number" ? payload.same_merchant_count_6m : null;

  const summary = [
    `Transaccion validada: ${merchant}.`,
    `Monto: ${amount != null ? formatAmount(amount, currency ?? undefined) : "-"}.`,
    `Fecha: ${date}.`,
  ];
  if (sameMerchantCount != null) {
    summary.push(`Historial en el mismo comercio (6 meses): ${sameMerchantCount}.`);
  }
  return summary.join("\n");
}

function summarizeTicketCreation(payload: Record<string, unknown>): string {
  const ticketNumber = toTextValue(payload.ticket_number);
  if (!ticketNumber) {
    return "Se registro el reclamo, pero sin numero de ticket visible.";
  }
  return `Reclamo creado correctamente. Numero de ticket: ${ticketNumber}.`;
}

function parseToolResultPayload(raw: string): { toolName: string; payload: Record<string, unknown> | null } | null {
  const match = raw.match(/^RESULT\s+([a-z_]+):\s+([\s\S]+)$/i);
  if (!match) {
    return null;
  }
  const toolName = match[1] ?? "";
  const payloadRaw = match[2] ?? "";
  try {
    const payload = JSON.parse(payloadRaw) as Record<string, unknown>;
    return { toolName, payload };
  } catch {
    return { toolName, payload: null };
  }
}

function parseToolCallPayload(raw: string): { toolName: string; args: Record<string, unknown> | null } | null {
  const match = raw.match(/^CALL\s+\[tool:\s*([a-z_]+)\(([\s\S]*)\)\]$/i);
  if (!match) {
    return null;
  }
  const toolName = match[1] ?? "";
  const argsRaw = match[2] ?? "";
  try {
    const args = JSON.parse(argsRaw) as Record<string, unknown>;
    return { toolName, args };
  } catch {
    return { toolName, args: null };
  }
}

function summarizeToolCall(toolName: string, args: Record<string, unknown> | null): string {
  if (!args) {
    return `Ejecutando ${formatToolName(toolName)}.`;
  }
  if (toolName === "search_transactions") {
    const merchant = toTextValue(args.merchant_query);
    const lastN = toNumberValue(args.last_n);
    const dateFrom = toTextValue(args.date_from);
    const dateTo = toTextValue(args.date_to);
    const amount = toNumberValue(args.approximate_amount ?? args.min_amount);
    return [
      `Ejecutando ${formatToolName(toolName)}.`,
      merchant ? `Comercio: ${merchant}.` : null,
      amount != null ? `Monto de referencia: ${amount}.` : null,
      dateFrom || dateTo ? `Rango: ${dateFrom ?? "-"} a ${dateTo ?? "-"}.` : null,
      lastN != null ? `Limite: ${Math.trunc(lastN)} resultados.` : null,
    ]
      .filter((line): line is string => Boolean(line))
      .join("\n");
  }
  return `Ejecutando ${formatToolName(toolName)}.`;
}

function summarizeToolResult(toolName: string, payload: Record<string, unknown> | null): string {
  if (!payload) {
    return `${formatToolName(toolName)} finalizo sin detalle legible.`;
  }
  if (payload.error) {
    return `${formatToolName(toolName)} devolvio error.`;
  }

  const result = toRecord(payload.result);
  if (!result) {
    return `${formatToolName(toolName)} completado.`;
  }

  if (toolName === "search_transactions") {
    return summarizeSearchTransactions(result);
  }
  if (toolName === "get_transaction_context") {
    return summarizeTransactionContext(result);
  }
  if (toolName === "create_chargeback_ticket" || toolName === "cancel_chargeback_request") {
    return summarizeTicketCreation(result);
  }
  return `${formatToolName(toolName)} completado correctamente.`;
}

function formatToolConversationContent(rawContent: string): string {
  const callPayload = parseToolCallPayload(rawContent);
  if (callPayload) {
    return summarizeToolCall(callPayload.toolName, callPayload.args);
  }

  const resultPayload = parseToolResultPayload(rawContent);
  if (resultPayload) {
    return summarizeToolResult(resultPayload.toolName, resultPayload.payload);
  }

  return "Evento de herramienta procesado.";
}

function buildTransactionFields(transaction: Record<string, unknown>): Array<{ label: string; value: string }> {
  const amount = toNumberValue(transaction.total_amount);
  const currency = toTextValue(transaction.currency);
  const merchantCity = toTextValue(transaction.merchant_city);
  const merchantCountry = toTextValue(transaction.merchant_country);
  const location = [merchantCity, merchantCountry].filter(Boolean).join(", ");
  const cardPresent = toBooleanValue(transaction.card_present);
  const tokenized = toBooleanValue(transaction.is_tokenized);
  const salesTax = toNumberValue(transaction.sales_tax);
  const fxRate = toNumberValue(transaction.fx_rate);

  const fields: Array<{ label: string; value: string | null }> = [
    { label: "Comercio", value: toTextValue(transaction.merchant_name) },
    { label: "Nombre comercial", value: toTextValue(transaction.merchant_dba) },
    { label: "Fecha de transaccion", value: formatDate(toTextValue(transaction.transaction_at)) },
    { label: "Monto", value: amount != null ? formatAmount(amount, currency ?? undefined) : null },
    { label: "Moneda", value: currency },
    { label: "Tarjeta", value: toTextValue(transaction.card_last4) ? `**** ${toTextValue(transaction.card_last4)}` : null },
    { label: "Marca", value: mapCardBrand(toTextValue(transaction.card_brand)) },
    { label: "Rubro (MCC)", value: toTextValue(transaction.mcc) },
    { label: "Ciudad/Pais", value: location || null },
    { label: "Modo de ingreso", value: mapEntryMode(toTextValue(transaction.entry_mode)) },
    { label: "Verificacion del titular", value: mapCvm(toTextValue(transaction.cvm)) },
    { label: "Tarjeta presente", value: cardPresent == null ? null : cardPresent ? "Si" : "No" },
    { label: "Operacion tokenizada", value: tokenized == null ? null : tokenized ? "Si" : "No" },
    {
      label: "Impuesto",
      value: salesTax != null ? formatAmount(salesTax, currency ?? undefined) : null,
    },
    { label: "Tipo de cambio", value: fxRate != null ? fxRate.toFixed(4) : null },
    { label: "Referencia cliente", value: toTextValue(transaction.customer_reference) },
    { label: "Numero de factura", value: toTextValue(transaction.invoice_number) },
    { label: "Codigo postal", value: toTextValue(transaction.merchant_postal_code) },
    { label: "Terminal", value: toTextValue(transaction.terminal_id) },
    { label: "IP", value: toTextValue(transaction.ip_address) },
    { label: "ID de transaccion", value: toTextValue(transaction.id) },
  ];

  return fields
    .filter((field): field is { label: string; value: string } => Boolean(field.value))
    .map((field) => ({ label: field.label, value: field.value }));
}

export default function AdminPanel() {
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicket, setSelectedTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadAdminData = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const [summaryData, listData] = await Promise.all([
          fetchBackendJson<TicketSummary>("/admin/tickets/summary"),
          fetchBackendJson<{ items: TicketListItem[] }>("/admin/tickets"),
        ]);

        if (!isMounted) {
          return;
        }

        setSummary(summaryData);
        setTickets(listData.items ?? []);
        const firstTicketId = (listData.items ?? [])[0]?.id ?? null;
        setSelectedTicketId(firstTicketId);
      } catch {
        if (isMounted) {
          setErrorMessage("No se pudo cargar la informacion del panel admin.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadAdminData();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadDetail = async () => {
      if (!selectedTicketId) {
        setSelectedTicket(null);
        return;
      }
      setDetailLoading(true);
      try {
        const detail = await fetchBackendJson<TicketDetail>(`/admin/tickets/${selectedTicketId}`);
        if (!isMounted) {
          return;
        }
        setSelectedTicket(detail);
      } catch {
        if (isMounted) {
          setSelectedTicket(null);
        }
      } finally {
        if (isMounted) {
          setDetailLoading(false);
        }
      }
    };

    void loadDetail();
    return () => {
      isMounted = false;
    };
  }, [selectedTicketId]);

  const conversationMessages = useMemo(
    () => buildConversationMessages(selectedTicket?.conversation_log),
    [selectedTicket],
  );

  const transactionFields = useMemo(() => {
    const transaction = toRecord(selectedTicket?.transaction);
    if (!transaction) {
      return [];
    }
    return buildTransactionFields(transaction);
  }, [selectedTicket]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-200 bg-white text-sm text-gray-600 shadow-sm">
        Cargando panel admin...
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-red-200 bg-white px-4 text-sm text-red-700 shadow-sm">
        {errorMessage}
      </div>
    );
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-4 xl:grid-cols-12">
      <div className="flex min-h-0 flex-col gap-4 xl:col-span-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tickets totales</p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.total ?? 0}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Abiertos</p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.open ?? 0}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Cancelados por usuario
            </p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.cancelled_by_user ?? 0}</p>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-gray-700">
            Tickets
          </div>
          {tickets.length === 0 ? (
            <div className="px-4 py-6 text-sm text-gray-500">No hay tickets cargados.</div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {tickets.map((ticket) => {
                const isSelected = ticket.id === selectedTicketId;
                return (
                  <li key={ticket.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedTicketId(ticket.id)}
                      className={[
                        "w-full px-4 py-3 text-left transition hover:bg-slate-50",
                        isSelected ? "bg-brou-blue/5" : "",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-gray-900">{ticket.ticket_number}</p>
                        <span
                          className={[
                            "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase",
                            getStatusBadgeClass(ticket.status),
                          ].join(" ")}
                        >
                          {getStatusLabel(ticket.status)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-gray-600">{ticket.reason_label_es}</p>
                      <p className="mt-1 text-xs text-gray-500">
                        {ticket.transaction?.merchant_name ?? "Sin transaccion"} -{" "}
                        {formatAmount(ticket.transaction?.total_amount, ticket.transaction?.currency)}
                      </p>
                      <p className="mt-1 text-[11px] text-gray-400">Creado: {formatDate(ticket.created_at)}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Detalle del ticket</h2>
        {detailLoading ? (
          <p className="mt-4 text-sm text-gray-500">Cargando detalle...</p>
        ) : !selectedTicket ? (
          <p className="mt-4 text-sm text-gray-500">Selecciona un ticket para ver el detalle.</p>
        ) : (
          <div className="mt-3 space-y-3 text-sm text-gray-700">
            <p>
              <span className="font-semibold text-gray-900">Numero:</span> {selectedTicket.ticket_number}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Estado:</span>{" "}
              <span
                className={[
                  "ml-1 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase",
                  getStatusBadgeClass(selectedTicket.status),
                ].join(" ")}
              >
                {getStatusLabel(selectedTicket.status)}
              </span>
            </p>
            <p>
              <span className="font-semibold text-gray-900">Motivo:</span> {selectedTicket.reason_label_es}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Resumen:</span>{" "}
              {selectedTicket.agent_summary || "Sin resumen"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Recomendacion:</span>{" "}
              {selectedTicket.agent_recommendation || "Sin recomendacion"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Info adicional del cliente:</span>{" "}
              {selectedTicket.user_additional_info || "Sin comentarios"}
            </p>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-600">Transaccion</p>
              {transactionFields.length > 0 ? (
                <dl className="grid grid-cols-1 gap-2 text-xs text-gray-700 sm:grid-cols-2">
                  {transactionFields.map((field) => (
                    <div key={field.label} className="rounded-md border border-slate-200 bg-white px-2 py-2">
                      <dt className="font-semibold text-gray-500">{field.label}</dt>
                      <dd className="mt-0.5 break-words text-gray-800">{field.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="text-xs text-gray-500">Sin transaccion asociada.</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Conversacion</h2>
        {detailLoading ? (
          <p className="mt-4 text-sm text-gray-500">Cargando conversacion...</p>
        ) : !selectedTicket ? (
          <p className="mt-4 text-sm text-gray-500">Selecciona un ticket para ver la conversacion.</p>
        ) : conversationMessages.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">Sin registro de conversacion.</p>
        ) : (
          <div className="mt-3 space-y-3">
            {conversationMessages.map((message, index) => (
              <article
                key={`${message.roleLabel}-${index}`}
                className={`rounded-lg border px-3 py-2 text-sm text-gray-700 ${message.bubbleClass}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-600">
                    {message.roleLabel}
                  </p>
                  {message.timestamp ? (
                    <p className="text-[11px] text-gray-500">{formatDate(message.timestamp)}</p>
                  ) : null}
                </div>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
