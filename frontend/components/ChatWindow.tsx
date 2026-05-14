"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { buildBackendCandidates } from "@/lib/backendApi";

type ToolCallStatus = "running" | "done";

type ToolCall = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: ToolCallStatus;
  result?: unknown;
};

type MessageRole = "user" | "agent";

type QuickReply = {
  id: string;
  label: string;
  value: string;
  displayText?: string;
};

type Message = {
  id: string;
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  quickReplies?: QuickReply[];
};

type ParsedSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

const INITIAL_GREETING = "Hola, soy el asistente de BROU. ¿En qué te puedo ayudar?";
const STREAM_IDLE_TIMEOUT_MS = 45_000;

function parseSseFrame(frame: string): ParsedSseEvent | null {
  const lines = frame.split(/\r?\n/);
  const dataLines: string[] = [];
  let eventName = "";

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) {
      continue;
    }

    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      let value = line.slice(5);
      if (value.startsWith(" ")) {
        value = value.slice(1);
      }
      dataLines.push(value);
    }
  }

  if (!eventName && dataLines.length === 0) {
    return null;
  }

  let parsedData: Record<string, unknown> = {};
  if (dataLines.length > 0) {
    const rawData = dataLines.join("\n");
    try {
      parsedData = JSON.parse(rawData) as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  return {
    event: eventName,
    data: parsedData,
  };
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    { id: crypto.randomUUID(), role: "agent", content: INITIAL_GREETING },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [hasTokenThisTurn, setHasTokenThisTurn] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const activeAgentMessageId = useRef<string | null>(null);
  const activeStreamController = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isStreaming]);

  const appendTokenToAgentMessage = (text: string) => {
    setMessages((prevMessages) => {
      const targetId = activeAgentMessageId.current;
      const targetIndex =
        targetId == null
          ? -1
          : prevMessages.findIndex((message) => message.id === targetId);

      if (targetIndex === -1) {
        const nextMessage: Message = {
          id: crypto.randomUUID(),
          role: "agent",
          content: text,
          toolCalls: [],
        };
        activeAgentMessageId.current = nextMessage.id;
        return [...prevMessages, nextMessage];
      }

      const nextMessages = [...prevMessages];
      const current = nextMessages[targetIndex];
      nextMessages[targetIndex] = {
        ...current,
        content: `${current.content}${text}`,
      };
      return nextMessages;
    });
  };

  const addToolCallChip = (name: string, args: Record<string, unknown>) => {
    const nextChip: ToolCall = {
      id: crypto.randomUUID(),
      name,
      args,
      status: "running",
    };

    setMessages((prevMessages) => {
      const targetId = activeAgentMessageId.current;
      const targetIndex =
        targetId == null
          ? -1
          : prevMessages.findIndex((message) => message.id === targetId);

      if (targetIndex === -1) {
        const nextMessage: Message = {
          id: crypto.randomUUID(),
          role: "agent",
          content: "",
          toolCalls: [nextChip],
        };
        activeAgentMessageId.current = nextMessage.id;
        return [...prevMessages, nextMessage];
      }

      const nextMessages = [...prevMessages];
      const current = nextMessages[targetIndex];
      nextMessages[targetIndex] = {
        ...current,
        toolCalls: [...(current.toolCalls ?? []), nextChip],
      };
      return nextMessages;
    });
  };

  const markToolCallDone = (name: string, result: unknown) => {
    setMessages((prevMessages) => {
      let found = false;
      const nextMessages = prevMessages.map((message) => {
        if (found || !message.toolCalls || message.toolCalls.length === 0) {
          return message;
        }

        const toolIndex = message.toolCalls.findIndex(
          (toolCall) => toolCall.name === name && toolCall.status === "running",
        );

        if (toolIndex === -1) {
          return message;
        }

        found = true;
        const nextToolCalls = [...message.toolCalls];
        nextToolCalls[toolIndex] = {
          ...nextToolCalls[toolIndex],
          status: "done",
          result,
        };

        return {
          ...message,
          toolCalls: nextToolCalls,
        };
      });

      return nextMessages;
    });
  };

  const setQuickRepliesOnAgentMessage = (quickReplies: QuickReply[]) => {
    if (quickReplies.length === 0) {
      return;
    }

    setMessages((prevMessages) => {
      const targetId = activeAgentMessageId.current;
      const targetIndex =
        targetId == null
          ? -1
          : prevMessages.findIndex((message) => message.id === targetId);

      if (targetIndex === -1) {
        const nextMessage: Message = {
          id: crypto.randomUUID(),
          role: "agent",
          content: "",
          quickReplies,
        };
        activeAgentMessageId.current = nextMessage.id;
        return [...prevMessages, nextMessage];
      }

      const nextMessages = [...prevMessages];
      const current = nextMessages[targetIndex];
      nextMessages[targetIndex] = {
        ...current,
        quickReplies,
      };
      return nextMessages;
    });
  };

  const consumeQuickReplies = (messageId: string) => {
    setMessages((prevMessages) =>
      prevMessages.map((message) =>
        message.id === messageId
          ? {
              ...message,
              quickReplies: [],
            }
          : message,
      ),
    );
  };

  const handleSseEvent = (event: ParsedSseEvent): boolean => {
    if (event.event === "token") {
      const text =
        typeof event.data.text === "string"
          ? event.data.text
          : String(event.data.text ?? "");
      if (text) {
        setHasTokenThisTurn(true);
        appendTokenToAgentMessage(text);
      }
      return false;
    }

    if (event.event === "tool_call") {
      if (typeof event.data.name === "string") {
        const args =
          event.data.args && typeof event.data.args === "object"
            ? (event.data.args as Record<string, unknown>)
            : {};
        addToolCallChip(event.data.name, args);
      }
      return false;
    }

    if (event.event === "tool_result") {
      if (typeof event.data.name === "string") {
        markToolCallDone(event.data.name, event.data.result);
      }
      return false;
    }

    if (event.event === "done") {
      return true;
    }

    if (event.event === "quick_replies") {
      const rawChoices = Array.isArray(event.data.choices) ? event.data.choices : [];
      const quickReplies: QuickReply[] = rawChoices
        .map((choice, index) => {
          if (!choice || typeof choice !== "object") {
            return null;
          }
          const maybeChoice = choice as Record<string, unknown>;
          const label = typeof maybeChoice.label === "string" ? maybeChoice.label.trim() : "";
          const value = typeof maybeChoice.value === "string" ? maybeChoice.value.trim() : "";
          if (!label || !value) {
            return null;
          }
          const displayText =
            typeof maybeChoice.display_text === "string"
              ? maybeChoice.display_text.trim()
              : undefined;
          const id = typeof maybeChoice.id === "string" ? maybeChoice.id : `quick_reply_${index}`;
          return { id, label, value, displayText };
        })
        .filter((choice): choice is QuickReply => Boolean(choice));

      setQuickRepliesOnAgentMessage(quickReplies);
      return false;
    }

    return false;
  };

  const sendUserText = async (text: string, visibleText?: string) => {
    if (isStreaming) {
      activeStreamController.current?.abort();
      return;
    }

    const trimmedInput = text.trim();
    if (!trimmedInput) {
      return;
    }

    const backendCandidates = buildBackendCandidates(process.env.NEXT_PUBLIC_BACKEND_URL);

    setInput("");
    setIsStreaming(true);
    setHasTokenThisTurn(false);
    activeAgentMessageId.current = null;
    const streamController = new AbortController();
    activeStreamController.current = streamController;
    setMessages((prevMessages) => [
      ...prevMessages,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: visibleText?.trim() || trimmedInput,
      },
    ]);
    let idleTimer: ReturnType<typeof setTimeout> | null = null;
    const resetIdleTimer = () => {
      if (idleTimer) {
        clearTimeout(idleTimer);
      }
      idleTimer = setTimeout(() => {
        streamController.abort();
      }, STREAM_IDLE_TIMEOUT_MS);
    };

    try {
      resetIdleTimer();
      let response: Response | null = null;
      let lastFetchError: unknown = null;
      for (const backendUrl of backendCandidates) {
        try {
          const candidateResponse = await fetch(`${backendUrl}/chat/stream`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            signal: streamController.signal,
            body: JSON.stringify({
              session_id: sessionId,
              message: trimmedInput,
            }),
          });

          if (!candidateResponse.ok || !candidateResponse.body) {
            const shouldRetry = candidateResponse.status >= 500 || !candidateResponse.body;
            if (!shouldRetry) {
              throw new Error("No se pudo iniciar el stream.");
            }
            lastFetchError = new Error(
              `Fallback backend ${backendUrl} returned ${candidateResponse.status}.`,
            );
            continue;
          }

          response = candidateResponse;
          break;
        } catch (error) {
          if (streamController.signal.aborted) {
            throw error;
          }
          lastFetchError = error;
        }
      }

      if (!response) {
        throw lastFetchError ?? new Error("No se pudo iniciar el stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamDone = false;

      while (!streamDone) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        resetIdleTimer();

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const parsedEvent = parseSseFrame(frame);
          if (!parsedEvent) {
            continue;
          }

          const eventDone = handleSseEvent(parsedEvent);
          if (eventDone) {
            streamDone = true;
            break;
          }
        }
      }

      if (!streamDone && buffer.trim()) {
        const parsedEvent = parseSseFrame(buffer);
        if (parsedEvent) {
          handleSseEvent(parsedEvent);
        }
      }
    } catch (error) {
      const wasAborted = error instanceof DOMException && error.name === "AbortError";
      setMessages((prevMessages) => [
        ...prevMessages,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: wasAborted
            ? "Se interrumpió la respuesta por demora. Probá enviar de nuevo."
            : "No pude conectar con el backend en este momento.",
        },
      ]);
    } finally {
      if (idleTimer) {
        clearTimeout(idleTimer);
      }
      activeAgentMessageId.current = null;
      activeStreamController.current = null;
      setIsStreaming(false);
      setHasTokenThisTurn(false);
    }
  };

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendUserText(input);
  };

  const handleQuickReplyClick = async (messageId: string, quickReply: QuickReply) => {
    consumeQuickReplies(messageId);
    await sendUserText(quickReply.value, quickReply.displayText ?? quickReply.label);
  };

  const hasRunningToolCall = messages.some((message) =>
    message.role === "agent"
      ? (message.toolCalls ?? []).some((toolCall) => toolCall.status === "running")
      : false,
  );

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message) => {
          const isUser = message.role === "user";
          const hasContent = message.content.trim().length > 0;
          const hasToolCalls = Boolean(message.toolCalls && message.toolCalls.length > 0);
          const hasQuickReplies = Boolean(message.quickReplies && message.quickReplies.length > 0);
          const shouldRenderBubble =
            isUser || hasContent || (!hasToolCalls && !hasQuickReplies) || hasQuickReplies;
          const fallbackText = hasQuickReplies ? "Elegi una opcion:" : "...";
          return (
            <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <div className="max-w-[85%] space-y-2">
                {!isUser && hasToolCalls ? (
                  <div className="rounded-2xl border border-brou-blue/30 bg-brou-blue/5 p-2">
                    {message.toolCalls.map((toolCall) => (
                      <div key={toolCall.id} className="rounded-xl px-2 py-1 text-xs text-gray-800">
                        Uso de herramienta: {toolCall.name}
                      </div>
                    ))}
                  </div>
                ) : null}

                {shouldRenderBubble ? (
                  <div
                    className={[
                      "whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm",
                      isUser
                        ? "bg-gray-200 text-gray-900"
                        : "border border-brou-blue bg-white text-gray-900",
                    ].join(" ")}
                  >
                    {hasContent ? message.content : fallbackText}
                  </div>
                ) : null}

                {!isUser && message.quickReplies && message.quickReplies.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {message.quickReplies.map((quickReply) => (
                      <button
                        key={quickReply.id}
                        type="button"
                        disabled={isStreaming}
                        onClick={() => {
                          void handleQuickReplyClick(message.id, quickReply);
                        }}
                        className="rounded-lg border border-brou-blue bg-white px-3 py-1 text-xs font-semibold text-brou-blue transition hover:bg-brou-blue/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {quickReply.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}

        {isStreaming && !hasTokenThisTurn && !hasRunningToolCall ? (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-brou-blue bg-white px-4 py-2 text-sm text-gray-500 shadow-sm">
              escribiendo...
            </div>
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={sendMessage}
        className="flex items-center gap-3 border-t border-slate-200 p-4"
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Contame qué pasó..."
          disabled={isStreaming}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-brou-blue focus:ring-2 focus:ring-brou-blue/20 disabled:bg-gray-100"
        />
        <button
          type="submit"
          disabled={!isStreaming && !input.trim()}
          className="rounded-lg bg-brou-blue px-4 py-2 text-sm font-semibold text-white transition hover:bg-brou-blue-dark disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isStreaming ? "Detener" : "Enviar"}
        </button>
      </form>
    </div>
  );
}
