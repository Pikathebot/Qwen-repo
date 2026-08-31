"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Message, ToolStep, PendingConfirmation } from "@/lib/types";
import { streamChat } from "@/lib/sse-client";
import { fetchSessionMessages, createNewSessionId } from "@/lib/api";

export interface UseChatReturn {
  messages: Message[];
  activeSessionId: string;
  isLoading: boolean;
  streamingMessageId: string | null;
  pendingConfirmations: PendingConfirmation[];
  error: string | null;
  selectedModel: string | null;
  setSelectedModel: (model: string | null) => void;
  sendMessage: (content: string, approvedActionIds?: string[]) => Promise<void>;
  confirmAction: (actionId: string) => Promise<void>;
  denyAction: () => void;
  selectSession: (sessionId: string) => Promise<void>;
  newChat: () => void;
  abortStream: () => void;
  clearError: () => void;
}

export function useChat(onSessionsUpdated?: () => void): UseChatReturn {
  const [activeSessionId, setActiveSessionId] = useState<string>(createNewSessionId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [pendingConfirmations, setPendingConfirmations] = useState<PendingConfirmation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastUserPromptRef = useRef<string>("");

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const newChat = useCallback(() => {
    abortControllerRef.current?.abort();
    const newId = createNewSessionId();
    setActiveSessionId(newId);
    setMessages([]);
    setPendingConfirmations([]);
    setError(null);
    setIsLoading(false);
    setStreamingMessageId(null);
  }, []);

  const selectSession = useCallback(async (sessionId: string) => {
    abortControllerRef.current?.abort();
    setIsLoading(true);
    setError(null);
    setActiveSessionId(sessionId);
    setPendingConfirmations([]);

    try {
      const history = await fetchSessionMessages(sessionId);
      const converted: Message[] = history.map((m, idx) => ({
        id: `msg_${sessionId}_${idx}_${Date.now()}`,
        role: (m.role as "user" | "assistant" | "system") || "user",
        content: (m.content as string) || "",
        toolsUsed: (m.tools_used as Array<Record<string, unknown>>) || [],
        createdAt: new Date(),
      }));
      setMessages(converted);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load session messages";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    setStreamingMessageId(null);
  }, []);

  const sendMessage = useCallback(
    async (content: string, approvedActionIds?: string[]) => {
      if (!content.trim() && !approvedActionIds?.length) return;
      if (isLoading) return;

      setError(null);
      if (content.trim()) {
        lastUserPromptRef.current = content.trim();
      }

      const userMessageId = `user_${Date.now()}`;
      if (content.trim()) {
        const userMsg: Message = {
          id: userMessageId,
          role: "user",
          content: content.trim(),
          createdAt: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
      }

      const assistantMessageId = `asst_${Date.now()}`;
      const assistantPlaceholder: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        toolSteps: [],
        createdAt: new Date(),
      };
      setMessages((prev) => [...prev, assistantPlaceholder]);
      setStreamingMessageId(assistantMessageId);
      setIsLoading(true);
      setPendingConfirmations([]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await streamChat({
          message: content.trim() || lastUserPromptRef.current,
          sessionId: activeSessionId,
          model: selectedModel || undefined,
          approvedActionIds,
          signal: controller.signal,
          callbacks: {
            onToken: ({ delta }) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: msg.content + delta }
                    : msg
                )
              );
            },
            onToolDraft: ({ tool, args_delta }) => {
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id !== assistantMessageId) return msg;
                  const steps = msg.toolSteps || [];
                  const existingIndex = steps.findIndex(
                    (s) => s.tool === tool && s.status === "running"
                  );
                  if (existingIndex >= 0) {
                    const updatedSteps = [...steps];
                    const prevStep = updatedSteps[existingIndex];
                    const prevRaw = typeof prevStep.args?.raw === "string" ? prevStep.args.raw : "";
                    updatedSteps[existingIndex] = {
                      ...prevStep,
                      args: { raw: prevRaw + args_delta },
                    };
                    return { ...msg, toolSteps: updatedSteps };
                  }
                  const newStep: ToolStep = {
                    id: `tool_${tool}_${Date.now()}`,
                    tool,
                    args: { raw: args_delta },
                    status: "running",
                  };
                  return { ...msg, toolSteps: [...steps, newStep] };
                })
              );
            },
            onToolStart: ({ tool, args }) => {
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id !== assistantMessageId) return msg;
                  const steps = msg.toolSteps || [];
                  const existingIndex = steps.findIndex(
                    (s) => s.tool === tool && s.status === "running"
                  );
                  if (existingIndex >= 0) {
                    const updatedSteps = [...steps];
                    updatedSteps[existingIndex] = {
                      ...updatedSteps[existingIndex],
                      args: args || updatedSteps[existingIndex].args,
                      status: "running",
                    };
                    return { ...msg, toolSteps: updatedSteps };
                  }
                  const newStep: ToolStep = {
                    id: `tool_${tool}_${Date.now()}`,
                    tool,
                    args,
                    status: "running",
                  };
                  return { ...msg, toolSteps: [...steps, newStep] };
                })
              );
            },
            onToolEnd: ({ tool, args, status, result }) => {
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id !== assistantMessageId) return msg;
                  const steps = (msg.toolSteps || []).map((step) =>
                    step.tool === tool && step.status === "running"
                      ? { ...step, status, result, args }
                      : step
                  );
                  return { ...msg, toolSteps: steps };
                })
              );
            },
            onConfirmationRequired: ({ pending_confirmations, session_id }) => {
              setPendingConfirmations(pending_confirmations);
              if (session_id && session_id !== activeSessionId) {
                setActiveSessionId(session_id);
              }
            },
            onDone: ({ response, model, provider, tools_used, active_skills }) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: response || msg.content,
                        model,
                        provider,
                        toolsUsed: tools_used,
                        activeSkills: active_skills,
                      }
                    : msg
                )
              );
              onSessionsUpdated?.();
            },
            onError: ({ error: errText }) => {
              setError(errText);
            },
          },
        });
      } catch (err: unknown) {
        if (!controller.signal.aborted) {
          const errMsg = err instanceof Error ? err.message : String(err);
          setError(errMsg);
        }
      } finally {
        setIsLoading(false);
        setStreamingMessageId(null);
        abortControllerRef.current = null;
      }
    },
    [activeSessionId, isLoading, selectedModel, onSessionsUpdated]
  );

  const confirmAction = useCallback(
    async (actionId: string) => {
      setPendingConfirmations((prev) => prev.filter((p) => p.action_id !== actionId));
      await sendMessage("", [actionId]);
    },
    [sendMessage]
  );

  const denyAction = useCallback(() => {
    setPendingConfirmations([]);
    setMessages((prev) => [
      ...prev,
      {
        id: `sys_${Date.now()}`,
        role: "system",
        content: "Action execution was denied by user.",
        createdAt: new Date(),
      },
    ]);
  }, []);

  return {
    messages,
    activeSessionId,
    isLoading,
    streamingMessageId,
    pendingConfirmations,
    error,
    selectedModel,
    setSelectedModel,
    sendMessage,
    confirmAction,
    denyAction,
    selectSession,
    newChat,
    abortStream,
    clearError,
  };
}
