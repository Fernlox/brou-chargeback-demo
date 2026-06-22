"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchBackendJson } from "@/lib/backendApi";
import { useLang } from "@/lib/i18n";

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
  reason_code?: string;
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

type Translator = (key: string, params?: Record<string, string | number>) => string;

const STATUS_BADGE_CLASSES: Record<string, string> = {
  open: "border-sky-200 bg-sky-50 text-sky-700",
  cancelled_by_user: "border-slate-300 bg-slate-100 text-slate-600",
  in_review: "border-amber-200 bg-amber-50 text-amber-700",
  resolved_favorable: "border-emerald-200 bg-emerald-50 text-emerald-700",
  resolved_unfavorable: "border-rose-200 bg-rose-50 text-rose-700",
};

function formatDate(value?: string | null, locale = "es-UY"): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(locale);
}

function formatAmount(amount?: number, currency?: string, locale = "es-UY"): string {
  if (amount == null || !currency) {
    return "-";
  }
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function getStatusLabel(status: string, t: Translator): string {
  const translated = t(`admin.status.${status}`);
  return translated === `admin.status.${status}` ? status : translated;
}

function getStatusBadgeClass(status: string): string {
  return STATUS_BADGE_CLASSES[status] ?? "border-brou-blue/30 bg-brou-blue/5 text-brou-blue";
}

function getReasonLabel(reasonCode: string | undefined, reasonLabelEs: string, t: Translator): string {
  if (!reasonCode) {
    return reasonLabelEs;
  }
  const translated = t(`admin.reasonByCode.${reasonCode}`);
  return translated === `admin.reasonByCode.${reasonCode}` ? reasonLabelEs : translated;
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

function mapCardBrand(value: string | null, t: Translator): string | null {
  if (!value) {
    return null;
  }
  const translated = t(`admin.cardBrand.${value}`);
  return translated === `admin.cardBrand.${value}` ? value.toUpperCase() : translated;
}

function mapEntryMode(value: string | null, t: Translator): string | null {
  if (!value) {
    return null;
  }
  const translated = t(`admin.entryMode.${value}`);
  return translated === `admin.entryMode.${value}` ? value : translated;
}

function mapCvm(value: string | null, t: Translator): string | null {
  if (!value) {
    return null;
  }
  const translated = t(`admin.cvm.${value}`);
  return translated === `admin.cvm.${value}` ? value : translated;
}

function mapRole(entry: Record<string, unknown>, t: Translator): { roleLabel: string; bubbleClass: string } {
  const rawRole = typeof entry.role === "string" ? entry.role.toLowerCase() : "";
  if (rawRole.includes("user") || rawRole.includes("cliente")) {
    return { roleLabel: t("admin.role.customer"), bubbleClass: "border-slate-200 bg-white" };
  }
  if (rawRole.includes("assistant") || rawRole.includes("agent")) {
    return { roleLabel: t("admin.role.assistant"), bubbleClass: "border-sky-200 bg-sky-50/70" };
  }
  if (rawRole.includes("tool")) {
    return { roleLabel: t("admin.role.tool"), bubbleClass: "border-indigo-200 bg-indigo-50/70" };
  }
  return { roleLabel: t("admin.role.system"), bubbleClass: "border-slate-200 bg-slate-50" };
}

function buildConversationMessages(
  log?: Array<Record<string, unknown>> | null,
  t?: Translator,
  locale?: string,
): ConversationMessage[] {
  if (!Array.isArray(log)) {
    return [];
  }
  if (!t) {
    return [];
  }

  return log
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((entry) => {
      const mappedRole = mapRole(entry, t);
      const rawContent =
        typeof entry.content === "string"
          ? entry.content
          : JSON.stringify(entry.content ?? "", null, 2);
      const content =
        mappedRole.roleLabel === t("admin.role.tool")
          ? formatToolConversationContent(rawContent, t, locale)
          : rawContent;
      const timestamp = typeof entry.ts === "string" ? entry.ts : undefined;

      return {
        roleLabel: mappedRole.roleLabel,
        bubbleClass: mappedRole.bubbleClass,
        content,
        timestamp,
        isToolMessage: mappedRole.roleLabel === t("admin.role.tool"),
      };
    });
}

function formatToolName(name: string, t: Translator): string {
  const translated = t(`admin.toolNames.${name}`);
  return translated === `admin.toolNames.${name}` ? name : translated;
}

function summarizeSearchTransactions(payload: Record<string, unknown>, t: Translator, locale: string): string {
  const results = Array.isArray(payload.results) ? payload.results : [];
  const total = typeof payload.total_results === "number" ? payload.total_results : results.length;
  if (total === 0) {
    return t("admin.toolSummary.noTransactions");
  }

  const topItems = results
    .slice(0, 3)
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const row = item as Record<string, unknown>;
      const merchant = toTextValue(row.merchant_name) ?? t("admin.toolSummary.merchantFallback");
      const amount = toNumberValue(row.total_amount);
      const currency = toTextValue(row.currency) ?? "";
      const date = formatDate(toTextValue(row.transaction_at), locale);
      const amountLabel = amount != null ? formatAmount(amount, currency || undefined, locale) : currency;
      return `- ${merchant} (${amountLabel || "-"}) - ${date}`;
    })
    .filter((line): line is string => Boolean(line));

  return [
    t("admin.toolSummary.foundTransactions", { total }),
    topItems.length > 0 ? t("admin.toolSummary.firstResults") : null,
    ...topItems,
  ]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

function summarizeTransactionContext(payload: Record<string, unknown>, t: Translator, locale: string): string {
  const transaction = toRecord(payload.transaction);
  if (!transaction) {
    return t("admin.toolSummary.noContext");
  }

  const merchant = toTextValue(transaction.merchant_name) ?? t("admin.toolSummary.merchantFallback");
  const amount = toNumberValue(transaction.total_amount);
  const currency = toTextValue(transaction.currency);
  const date = formatDate(toTextValue(transaction.transaction_at), locale);
  const sameMerchantCount =
    typeof payload.same_merchant_count_6m === "number" ? payload.same_merchant_count_6m : null;

  const summary = [
    t("admin.toolSummary.validatedTransaction", { merchant }),
    t("admin.toolSummary.amount", {
      amount: amount != null ? formatAmount(amount, currency ?? undefined, locale) : "-",
    }),
    t("admin.toolSummary.date", { date }),
  ];
  if (sameMerchantCount != null) {
    summary.push(t("admin.toolSummary.sameMerchantHistory", { count: sameMerchantCount }));
  }
  return summary.join("\n");
}

function summarizeTicketCreation(payload: Record<string, unknown>, t: Translator): string {
  const ticketNumber = toTextValue(payload.ticket_number);
  if (!ticketNumber) {
    return t("admin.toolSummary.ticketCreatedNoNumber");
  }
  return t("admin.toolSummary.ticketCreatedWithNumber", { ticketNumber });
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

function summarizeToolCall(
  toolName: string,
  args: Record<string, unknown> | null,
  t: Translator,
): string {
  if (!args) {
    return t("admin.toolSummary.runningTool", { toolName: formatToolName(toolName, t) });
  }
  if (toolName === "search_transactions") {
    const merchant = toTextValue(args.merchant_query);
    const lastN = toNumberValue(args.last_n);
    const dateFrom = toTextValue(args.date_from);
    const dateTo = toTextValue(args.date_to);
    const amount = toNumberValue(args.approximate_amount ?? args.min_amount);
    return [
      t("admin.toolSummary.runningTool", { toolName: formatToolName(toolName, t) }),
      merchant ? t("admin.toolSummary.merchant", { merchant }) : null,
      amount != null ? t("admin.toolSummary.amountReference", { amount }) : null,
      dateFrom || dateTo
        ? t("admin.toolSummary.range", { from: dateFrom ?? "-", to: dateTo ?? "-" })
        : null,
      lastN != null ? t("admin.toolSummary.limit", { limit: Math.trunc(lastN) }) : null,
    ]
      .filter((line): line is string => Boolean(line))
      .join("\n");
  }
  return t("admin.toolSummary.runningTool", { toolName: formatToolName(toolName, t) });
}

function summarizeToolResult(
  toolName: string,
  payload: Record<string, unknown> | null,
  t: Translator,
  locale: string,
): string {
  if (!payload) {
    return t("admin.toolSummary.unreadableDetails", { toolName: formatToolName(toolName, t) });
  }
  if (payload.error) {
    return t("admin.toolSummary.error", { toolName: formatToolName(toolName, t) });
  }

  const result = toRecord(payload.result);
  if (!result) {
    return t("admin.toolSummary.completed", { toolName: formatToolName(toolName, t) });
  }

  if (toolName === "search_transactions") {
    return summarizeSearchTransactions(result, t, locale);
  }
  if (toolName === "get_transaction_context") {
    return summarizeTransactionContext(result, t, locale);
  }
  if (toolName === "create_chargeback_ticket" || toolName === "cancel_chargeback_request") {
    return summarizeTicketCreation(result, t);
  }
  return t("admin.toolSummary.completedSuccessfully", { toolName: formatToolName(toolName, t) });
}

function formatToolConversationContent(rawContent: string, t: Translator, locale = "es-UY"): string {
  const callPayload = parseToolCallPayload(rawContent);
  if (callPayload) {
    return summarizeToolCall(callPayload.toolName, callPayload.args, t);
  }

  const resultPayload = parseToolResultPayload(rawContent);
  if (resultPayload) {
    return summarizeToolResult(resultPayload.toolName, resultPayload.payload, t, locale);
  }

  return t("admin.toolSummary.processedEvent");
}

function buildTransactionFields(
  transaction: Record<string, unknown>,
  t: Translator,
  locale: string,
): Array<{ label: string; value: string }> {
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
    { label: t("admin.fields.merchant"), value: toTextValue(transaction.merchant_name) },
    { label: t("admin.fields.merchantDisplayName"), value: toTextValue(transaction.merchant_dba) },
    {
      label: t("admin.fields.transactionDate"),
      value: formatDate(toTextValue(transaction.transaction_at), locale),
    },
    {
      label: t("admin.fields.amount"),
      value: amount != null ? formatAmount(amount, currency ?? undefined, locale) : null,
    },
    { label: t("admin.fields.currency"), value: currency },
    {
      label: t("admin.fields.card"),
      value: toTextValue(transaction.card_last4) ? `**** ${toTextValue(transaction.card_last4)}` : null,
    },
    { label: t("admin.fields.brand"), value: mapCardBrand(toTextValue(transaction.card_brand), t) },
    { label: t("admin.fields.mcc"), value: toTextValue(transaction.mcc) },
    { label: t("admin.fields.location"), value: location || null },
    { label: t("admin.fields.entryMode"), value: mapEntryMode(toTextValue(transaction.entry_mode), t) },
    { label: t("admin.fields.cvm"), value: mapCvm(toTextValue(transaction.cvm), t) },
    {
      label: t("admin.fields.cardPresent"),
      value: cardPresent == null ? null : cardPresent ? t("admin.fields.yes") : t("admin.fields.no"),
    },
    {
      label: t("admin.fields.tokenized"),
      value: tokenized == null ? null : tokenized ? t("admin.fields.yes") : t("admin.fields.no"),
    },
    {
      label: t("admin.fields.tax"),
      value: salesTax != null ? formatAmount(salesTax, currency ?? undefined, locale) : null,
    },
    { label: t("admin.fields.fxRate"), value: fxRate != null ? fxRate.toFixed(4) : null },
    { label: t("admin.fields.customerReference"), value: toTextValue(transaction.customer_reference) },
    { label: t("admin.fields.invoiceNumber"), value: toTextValue(transaction.invoice_number) },
    { label: t("admin.fields.postalCode"), value: toTextValue(transaction.merchant_postal_code) },
    { label: t("admin.fields.terminal"), value: toTextValue(transaction.terminal_id) },
    { label: t("admin.fields.ip"), value: toTextValue(transaction.ip_address) },
    { label: t("admin.fields.transactionId"), value: toTextValue(transaction.id) },
  ];

  return fields
    .filter((field): field is { label: string; value: string } => Boolean(field.value))
    .map((field) => ({ label: field.label, value: field.value }));
}

export default function AdminPanel() {
  const { t, locale } = useLang();
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
          setErrorMessage(t("admin.loadError"));
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
  }, [t]);

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
    () => buildConversationMessages(selectedTicket?.conversation_log, t, locale),
    [selectedTicket, t, locale],
  );

  const transactionFields = useMemo(() => {
    const transaction = toRecord(selectedTicket?.transaction);
    if (!transaction) {
      return [];
    }
    return buildTransactionFields(transaction, t, locale);
  }, [selectedTicket, t, locale]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-200 bg-white text-sm text-gray-600 shadow-sm">
        {t("admin.loadingPanel")}
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
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("admin.totalTickets")}
            </p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.total ?? 0}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("admin.openTickets")}
            </p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.open ?? 0}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("admin.cancelledByUser")}
            </p>
            <p className="mt-2 text-2xl font-bold text-brou-blue">{summary?.cancelled_by_user ?? 0}</p>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-gray-700">
            {t("admin.tickets")}
          </div>
          {tickets.length === 0 ? (
            <div className="px-4 py-6 text-sm text-gray-500">{t("admin.noTickets")}</div>
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
                          {getStatusLabel(ticket.status, t)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-gray-600">
                        {getReasonLabel(ticket.reason_code, ticket.reason_label_es, t)}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {ticket.transaction?.merchant_name ?? t("admin.noTransaction")} -{" "}
                        {formatAmount(ticket.transaction?.total_amount, ticket.transaction?.currency, locale)}
                      </p>
                      <p className="mt-1 text-[11px] text-gray-400">
                        {t("admin.createdAt", { date: formatDate(ticket.created_at, locale) })}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-600">
          {t("admin.ticketDetail")}
        </h2>
        {detailLoading ? (
          <p className="mt-4 text-sm text-gray-500">{t("admin.loadingDetail")}</p>
        ) : !selectedTicket ? (
          <p className="mt-4 text-sm text-gray-500">{t("admin.selectTicketDetail")}</p>
        ) : (
          <div className="mt-3 space-y-3 text-sm text-gray-700">
            <p>
              <span className="font-semibold text-gray-900">{t("admin.number")}</span>{" "}
              {selectedTicket.ticket_number}
            </p>
            <p>
              <span className="font-semibold text-gray-900">{t("admin.ticketStatus")}</span>{" "}
              <span
                className={[
                  "ml-1 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase",
                  getStatusBadgeClass(selectedTicket.status),
                ].join(" ")}
              >
                {getStatusLabel(selectedTicket.status, t)}
              </span>
            </p>
            <p>
              <span className="font-semibold text-gray-900">{t("admin.reason")}</span>{" "}
              {getReasonLabel(selectedTicket.reason_code, selectedTicket.reason_label_es, t)}
            </p>
            <p>
              <span className="font-semibold text-gray-900">{t("admin.summary")}</span>{" "}
              {selectedTicket.agent_summary || t("admin.noSummary")}
            </p>
            <p>
              <span className="font-semibold text-gray-900">{t("admin.recommendation")}</span>{" "}
              {selectedTicket.agent_recommendation || t("admin.noRecommendation")}
            </p>
            <p>
              <span className="font-semibold text-gray-900">{t("admin.additionalInfo")}</span>{" "}
              {selectedTicket.user_additional_info || t("admin.noComments")}
            </p>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-600">
                {t("admin.transaction")}
              </p>
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
                <p className="text-xs text-gray-500">{t("admin.noLinkedTransaction")}</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-600">
          {t("admin.conversation")}
        </h2>
        {detailLoading ? (
          <p className="mt-4 text-sm text-gray-500">{t("admin.loadingConversation")}</p>
        ) : !selectedTicket ? (
          <p className="mt-4 text-sm text-gray-500">{t("admin.selectTicketConversation")}</p>
        ) : conversationMessages.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">{t("admin.noConversation")}</p>
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
                    <p className="text-[11px] text-gray-500">{formatDate(message.timestamp, locale)}</p>
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
