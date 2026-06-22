"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "es" | "en";

type DictionaryValue = string | DictionaryTree;
type DictionaryTree = { [key: string]: DictionaryValue };

type LanguageContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  locale: string;
};

const dictionaries: Record<Lang, DictionaryTree> = {
  es: {
    appShell: {
      titleChat: "Asistente de Reclamos",
      titleAdmin: "Panel de Administracion",
      tabAssistant: "Asistente",
      tabAdmin: "Admin",
      languageLabel: "Idioma",
      footer: "Demo - datos ficticios",
    },
    chat: {
      initialGreeting: "Hola, soy el asistente de BROU. ¿En qué te puedo ayudar?",
      streamStartError: "No se pudo iniciar el stream.",
      timeoutError: "Se interrumpió la respuesta por demora. Probá enviar de nuevo.",
      backendError: "No pude conectar con el backend en este momento.",
      chooseOption: "Elegi una opcion:",
      toolCallPrefix: "Uso de herramienta",
      typing: "escribiendo...",
      placeholder: "Contame qué pasó...",
      stop: "Detener",
      send: "Enviar",
    },
    admin: {
      status: {
        open: "Abierto",
        cancelled_by_user: "Cancelado por el usuario",
        in_review: "En revision",
        resolved_favorable: "Resuelto favorable",
        resolved_unfavorable: "Resuelto desfavorable",
      },
      cardBrand: {
        visa: "Visa",
        mastercard: "Mastercard",
        amex: "American Express",
      },
      entryMode: {
        chip: "Chip",
        contactless: "Contactless",
        manual: "Ingreso manual",
        online: "En linea",
      },
      cvm: {
        pin: "PIN",
        signature: "Firma",
        biometric: "Biometria",
        none: "Sin verificacion",
      },
      role: {
        customer: "Cliente",
        assistant: "Asistente",
        tool: "Herramienta",
        system: "Sistema",
      },
      toolNames: {
        search_transactions: "Busqueda de transacciones",
        get_transaction_context: "Contexto de transaccion",
        create_chargeback_ticket: "Creacion de reclamo",
        cancel_chargeback_request: "Cancelacion de reclamo",
        apply_rules_and_summarize: "Analisis y resumen",
      },
      toolSummary: {
        noTransactions: "No se encontraron transacciones con los criterios enviados.",
        merchantFallback: "Comercio",
        foundTransactions: "Se encontraron {total} transacciones.",
        firstResults: "Primeros resultados:",
        noContext: "No se pudo recuperar el contexto de la transaccion.",
        validatedTransaction: "Transaccion validada: {merchant}.",
        amount: "Monto: {amount}.",
        date: "Fecha: {date}.",
        sameMerchantHistory: "Historial en el mismo comercio (6 meses): {count}.",
        ticketCreatedNoNumber: "Se registro el reclamo, pero sin numero de ticket visible.",
        ticketCreatedWithNumber: "Reclamo creado correctamente. Numero de ticket: {ticketNumber}.",
        runningTool: "Ejecutando {toolName}.",
        merchant: "Comercio: {merchant}.",
        amountReference: "Monto de referencia: {amount}.",
        range: "Rango: {from} a {to}.",
        limit: "Limite: {limit} resultados.",
        unreadableDetails: "{toolName} finalizo sin detalle legible.",
        error: "{toolName} devolvio error.",
        completed: "{toolName} completado.",
        completedSuccessfully: "{toolName} completado correctamente.",
        processedEvent: "Evento de herramienta procesado.",
      },
      fields: {
        merchant: "Comercio",
        merchantDisplayName: "Nombre comercial",
        transactionDate: "Fecha de transaccion",
        amount: "Monto",
        currency: "Moneda",
        card: "Tarjeta",
        brand: "Marca",
        mcc: "Rubro (MCC)",
        location: "Ciudad/Pais",
        entryMode: "Modo de ingreso",
        cvm: "Verificacion del titular",
        cardPresent: "Tarjeta presente",
        tokenized: "Operacion tokenizada",
        tax: "Impuesto",
        fxRate: "Tipo de cambio",
        customerReference: "Referencia cliente",
        invoiceNumber: "Numero de factura",
        postalCode: "Codigo postal",
        terminal: "Terminal",
        ip: "IP",
        transactionId: "ID de transaccion",
        yes: "Si",
        no: "No",
      },
      loadError: "No se pudo cargar la informacion del panel admin.",
      loadingPanel: "Cargando panel admin...",
      totalTickets: "Tickets totales",
      openTickets: "Abiertos",
      cancelledByUser: "Cancelados por usuario",
      tickets: "Tickets",
      noTickets: "No hay tickets cargados.",
      noTransaction: "Sin transaccion",
      createdAt: "Creado: {date}",
      ticketDetail: "Detalle del ticket",
      loadingDetail: "Cargando detalle...",
      selectTicketDetail: "Selecciona un ticket para ver el detalle.",
      number: "Numero:",
      ticketStatus: "Estado:",
      reason: "Motivo:",
      reasonByCode: {
        unknown_transaction: "Desconocimiento de transacciones",
        not_received: "No recibi el servicio o la mercaderia",
        duplicate: "Compra o retiro duplicado",
        processing_error: "Error de procesamiento",
      },
      summary: "Resumen:",
      noSummary: "Sin resumen",
      recommendation: "Recomendacion:",
      noRecommendation: "Sin recomendacion",
      additionalInfo: "Info adicional del cliente:",
      noComments: "Sin comentarios",
      transaction: "Transaccion",
      noLinkedTransaction: "Sin transaccion asociada.",
      conversation: "Conversacion",
      loadingConversation: "Cargando conversacion...",
      selectTicketConversation: "Selecciona un ticket para ver la conversacion.",
      noConversation: "Sin registro de conversacion.",
    },
  },
  en: {
    appShell: {
      titleChat: "Claims Assistant",
      titleAdmin: "Admin Panel",
      tabAssistant: "Assistant",
      tabAdmin: "Admin",
      languageLabel: "Language",
      footer: "Demo - fictional data",
    },
    chat: {
      initialGreeting: "Hi, I'm BROU's assistant. How can I help you?",
      streamStartError: "Could not start the stream.",
      timeoutError: "The response was interrupted due to timeout. Please try again.",
      backendError: "I couldn't connect to the backend right now.",
      chooseOption: "Choose an option:",
      toolCallPrefix: "Tool usage",
      typing: "typing...",
      placeholder: "Tell me what happened...",
      stop: "Stop",
      send: "Send",
    },
    admin: {
      status: {
        open: "Open",
        cancelled_by_user: "Cancelled by user",
        in_review: "In review",
        resolved_favorable: "Resolved favorable",
        resolved_unfavorable: "Resolved unfavorable",
      },
      cardBrand: {
        visa: "Visa",
        mastercard: "Mastercard",
        amex: "American Express",
      },
      entryMode: {
        chip: "Chip",
        contactless: "Contactless",
        manual: "Manual entry",
        online: "Online",
      },
      cvm: {
        pin: "PIN",
        signature: "Signature",
        biometric: "Biometric",
        none: "No verification",
      },
      role: {
        customer: "Customer",
        assistant: "Assistant",
        tool: "Tool",
        system: "System",
      },
      toolNames: {
        search_transactions: "Transaction search",
        get_transaction_context: "Transaction context",
        create_chargeback_ticket: "Claim creation",
        cancel_chargeback_request: "Claim cancellation",
        apply_rules_and_summarize: "Analysis and summary",
      },
      toolSummary: {
        noTransactions: "No transactions were found with the submitted criteria.",
        merchantFallback: "Merchant",
        foundTransactions: "{total} transactions were found.",
        firstResults: "Top results:",
        noContext: "Transaction context could not be retrieved.",
        validatedTransaction: "Validated transaction: {merchant}.",
        amount: "Amount: {amount}.",
        date: "Date: {date}.",
        sameMerchantHistory: "Same merchant history (6 months): {count}.",
        ticketCreatedNoNumber: "The claim was created, but no ticket number is visible.",
        ticketCreatedWithNumber: "Claim created successfully. Ticket number: {ticketNumber}.",
        runningTool: "Running {toolName}.",
        merchant: "Merchant: {merchant}.",
        amountReference: "Reference amount: {amount}.",
        range: "Range: {from} to {to}.",
        limit: "Limit: {limit} results.",
        unreadableDetails: "{toolName} finished without readable details.",
        error: "{toolName} returned an error.",
        completed: "{toolName} completed.",
        completedSuccessfully: "{toolName} completed successfully.",
        processedEvent: "Tool event processed.",
      },
      fields: {
        merchant: "Merchant",
        merchantDisplayName: "Display name",
        transactionDate: "Transaction date",
        amount: "Amount",
        currency: "Currency",
        card: "Card",
        brand: "Brand",
        mcc: "Category (MCC)",
        location: "City/Country",
        entryMode: "Entry mode",
        cvm: "Cardholder verification",
        cardPresent: "Card present",
        tokenized: "Tokenized transaction",
        tax: "Tax",
        fxRate: "FX rate",
        customerReference: "Customer reference",
        invoiceNumber: "Invoice number",
        postalCode: "Postal code",
        terminal: "Terminal",
        ip: "IP",
        transactionId: "Transaction ID",
        yes: "Yes",
        no: "No",
      },
      loadError: "Could not load admin panel data.",
      loadingPanel: "Loading admin panel...",
      totalTickets: "Total tickets",
      openTickets: "Open",
      cancelledByUser: "Cancelled by user",
      tickets: "Tickets",
      noTickets: "No tickets available.",
      noTransaction: "No transaction",
      createdAt: "Created: {date}",
      ticketDetail: "Ticket detail",
      loadingDetail: "Loading detail...",
      selectTicketDetail: "Select a ticket to view details.",
      number: "Number:",
      ticketStatus: "Status:",
      reason: "Reason:",
      reasonByCode: {
        unknown_transaction: "Unknown transaction",
        not_received: "Service or goods not received",
        duplicate: "Duplicate purchase or withdrawal",
        processing_error: "Processing error",
      },
      summary: "Summary:",
      noSummary: "No summary",
      recommendation: "Recommendation:",
      noRecommendation: "No recommendation",
      additionalInfo: "Additional customer info:",
      noComments: "No comments",
      transaction: "Transaction",
      noLinkedTransaction: "No linked transaction.",
      conversation: "Conversation",
      loadingConversation: "Loading conversation...",
      selectTicketConversation: "Select a ticket to view conversation.",
      noConversation: "No conversation log.",
    },
  },
};

const localeByLang: Record<Lang, string> = {
  es: "es-UY",
  en: "en-US",
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

function getByPath(tree: DictionaryTree, key: string): string | null {
  const parts = key.split(".");
  let current: DictionaryValue = tree;
  for (const part of parts) {
    if (typeof current !== "object" || current == null || !(part in current)) {
      return null;
    }
    current = (current as DictionaryTree)[part];
  }
  return typeof current === "string" ? current : null;
}

function formatTemplate(template: string, params?: Record<string, string | number>): string {
  if (!params) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key];
    return value == null ? `{${key}}` : String(value);
  });
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("es");

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang,
      locale: localeByLang[lang],
      t: (key, params) => {
        const template = getByPath(dictionaries[lang], key) ?? getByPath(dictionaries.es, key) ?? key;
        return formatTemplate(template, params);
      },
    }),
    [lang],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLang(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLang must be used within LanguageProvider.");
  }
  return context;
}
