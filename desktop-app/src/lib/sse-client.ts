import { Attachment, SSEEventMap, SSEEventCallbacks } from "./types";
import { API_BASE_URL } from "./api";

export interface StreamChatOptions {
  message: string;
  sessionId?: string;
  projectId?: string;
  model?: string;
  mode?: "auto" | "normal" | "heavy";
  chatMode?: "WORKSPACE" | "SYSTEM";
  systemPrompt?: string;
  approvedActionIds?: string[];
  attachments?: Attachment[];
  signal?: AbortSignal;
  callbacks: SSEEventCallbacks;
}

/**
 * Robust Server-Sent Events client using fetch + ReadableStream.
 * Handles partial chunk buffering, newline splitting, and typed event dispatching.
 */
export async function streamChat({
  message,
  sessionId,
  projectId,
  model,
  mode = "auto",
  chatMode = "WORKSPACE",
  systemPrompt,
  approvedActionIds,
  attachments,
  signal,
  callbacks,
}: StreamChatOptions): Promise<void> {
  const payload = {
    message,
    session_id: sessionId,
    project_id: projectId,
    model,
    mode,
    chat_mode: chatMode,
    system_prompt: systemPrompt,
    approved_action_ids: approvedActionIds,
    attachments,
  };


  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => "Unknown error");
    const errorMsg = `HTTP ${response.status}: ${errText}`;
    callbacks.onError?.({ error: errorMsg });
    throw new Error(errorMsg);
  }

  if (!response.body) {
    const errorMsg = "ReadableStream not supported on this response body.";
    callbacks.onError?.({ error: errorMsg });
    throw new Error(errorMsg);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split SSE packets by double newline
      const packets = buffer.split(/\r?\n\r?\n/);
      // Retain last potentially incomplete segment in buffer
      buffer = packets.pop() ?? "";

      for (const packet of packets) {
        const trimmed = packet.trim();
        if (!trimmed) continue;

        let currentEvent = "message";
        const dataLines: string[] = [];

        const lines = packet.split(/\r?\n/);
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }

        if (dataLines.length === 0) continue;
        const currentDataStr = dataLines.join("\n");

        try {
          const parsedData = JSON.parse(currentDataStr);
          dispatchEvent(currentEvent, parsedData, callbacks);
        } catch {
          if (currentEvent === "token") {
            callbacks.onToken?.({ delta: currentDataStr });
          } else if (currentEvent === "error") {
            callbacks.onError?.({ error: currentDataStr });
          }
        }
      }
    }

    if (buffer.trim()) {
      let currentEvent = "message";
      const dataLines: string[] = [];
      const lines = buffer.split(/\r?\n/);
      for (const line of lines) {
        if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length > 0) {
        const currentDataStr = dataLines.join("\n");
        try {
          const parsedData = JSON.parse(currentDataStr);
          dispatchEvent(currentEvent, parsedData, callbacks);
        } catch {
          // Ignore partial trailing junk
        }
      }
    }
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    const errMsg = err instanceof Error ? err.message : String(err);
    callbacks.onError?.({ error: errMsg });
    throw err;
  } finally {
    reader.releaseLock();
  }
}

function dispatchEvent(
  eventType: string,
  data: unknown,
  callbacks: SSEEventCallbacks
): void {
  switch (eventType) {
    case "token":
      callbacks.onToken?.(data as SSEEventMap["token"]);
      break;
    case "tool_draft":
      callbacks.onToolDraft?.(data as SSEEventMap["tool_draft"]);
      break;
    case "tool_start":
      callbacks.onToolStart?.(data as SSEEventMap["tool_start"]);
      break;
    case "tool_end":
      callbacks.onToolEnd?.(data as SSEEventMap["tool_end"]);
      break;
    case "confirmation_required":
      callbacks.onConfirmationRequired?.(
        data as SSEEventMap["confirmation_required"]
      );
      break;
    case "done":
      callbacks.onDone?.(data as SSEEventMap["done"]);
      break;
    case "error":
      callbacks.onError?.(data as SSEEventMap["error"]);
      break;
    default:
      break;
  }
}
