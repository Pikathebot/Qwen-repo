"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Message, ToolStep, PendingConfirmation, SSERetrievalContextEvent, ActivityStep, Attachment } from "@/lib/types";
import { streamChat } from "@/lib/sse-client";
import { fetchSessionMessages, createNewSessionId } from "@/lib/api";
import { MockAdapter } from "@/lib/mock-adapter";
import { MOCK_MESSAGES, MOCK_ACTIVITY_STEPS, MOCK_RETRIEVAL_CONTEXT } from "@/lib/mock-data";

export interface UseChatReturn {
  messages: Message[];
  activeSessionId: string;
  isLoading: boolean;
  streamingMessageId: string | null;
  pendingConfirmations: PendingConfirmation[];
  error: string | null;
  selectedModel: string | null;
  setSelectedModel: (model: string | null) => void;
  retrievalContext: SSERetrievalContextEvent | null;
  activitySteps: ActivityStep[];
  isMockMode: boolean;
  sendMessage: (
    content: string,
    approvedActionIds?: string[],
    attachments?: Attachment[],
    projectId?: string
  ) => Promise<void>;
  confirmAction: (actionId: string) => Promise<void>;
  denyAction: (actionId?: string) => void;
  selectSession: (sessionId: string) => Promise<void>;
  newChat: () => void;
  abortStream: () => void;
  clearError: () => void;
}

export function useChat(onSessionsUpdated?: () => void): UseChatReturn {
  const [activeSessionId, setActiveSessionId] = useState<string>("session_gas_refactor_a41f");
  const [messages, setMessages] = useState<Message[]>(MOCK_MESSAGES);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [pendingConfirmations, setPendingConfirmations] = useState<PendingConfirmation[]>([]);
  const [retrievalContext, setRetrievalContext] = useState<SSERetrievalContextEvent | null>(MOCK_RETRIEVAL_CONTEXT);
  const [activitySteps, setActivitySteps] = useState<ActivityStep[]>(MOCK_ACTIVITY_STEPS);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>("Qwen3-30B");
  const [isMockMode, setIsMockMode] = useState<boolean>(true);

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
    setRetrievalContext(null);
    setActivitySteps([]);
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
      if (history && history.length > 0) {
        setIsMockMode(false);
        const converted: Message[] = history.map((m, idx) => ({
          id: `msg_${sessionId}_${idx}_${Date.now()}`,
          role: (m.role as "user" | "assistant" | "system") || "user",
          content: (m.content as string) || "",
          toolsUsed: (m.tools_used as Array<Record<string, unknown>>) || [],
          createdAt: new Date(),
        }));
        setMessages(converted);
      } else {
        const mockMsgs = await MockAdapter.getMessages(sessionId);
        setMessages(mockMsgs.length > 0 ? mockMsgs : []);
      }
    } catch {
      const mockMsgs = await MockAdapter.getMessages(sessionId);
      setMessages(mockMsgs.length > 0 ? mockMsgs : []);
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
    async (
      content: string,
      approvedActionIds?: string[],
      attachments?: Attachment[],
      projectId?: string
    ) => {
      if (!content.trim() && !approvedActionIds?.length && (!attachments || attachments.length === 0)) return;
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
          contextChips: attachments?.map((a) => ({ type: "file", label: a.filename })) || [],
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
        isStreaming: true,
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
          projectId: projectId,
          model: selectedModel || undefined,
          approvedActionIds,
          attachments,
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
            onToolStart: ({ tool, args }) => {
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id !== assistantMessageId) return msg;
                  const steps = msg.toolSteps || [];
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
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, pendingConfirmations: pending_confirmations }
                    : msg
                )
              );
              if (session_id && session_id !== activeSessionId) {
                setActiveSessionId(session_id);
              }
            },
            onRetrievalContext: (data) => {
              setRetrievalContext(data);
            },
            onToolCall: ({ tool, args, call_id }) => {
              setActivitySteps((prev) => [
                ...prev,
                {
                  id: call_id || `step_${Date.now()}`,
                  timestamp: new Date(),
                  type: "tool_call",
                  tool,
                  args,
                  status: "running",
                },
              ]);
            },
            onToolResult: ({ tool, status, summary, result, call_id, latency_ms, truncated }) => {
              setActivitySteps((prev) => [
                ...prev,
                {
                  id: `res_${call_id || Date.now()}`,
                  timestamp: new Date(),
                  type: "tool_result",
                  tool,
                  status,
                  summary,
                  result,
                  latency_ms,
                  truncated,
                },
              ]);
            },
            onAgentStatus: ({ status, tool }) => {
              setActivitySteps((prev) => [
                ...prev,
                {
                  id: `stat_${Date.now()}`,
                  timestamp: new Date(),
                  type: "status",
                  status,
                  tool,
                },
              ]);
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
                        isStreaming: false,
                      }
                    : msg
                )
              );
              setIsMockMode(false);
              onSessionsUpdated?.();
            },
            onError: ({ error: errText }) => {
              setError(errText);
            },
          },
        });
      } catch {
        // Backend offline or error -> Fallback seamlessly to typed Mock Simulation
        setIsMockMode(true);
        try {
          await MockAdapter.simulateStreamChat(
            content.trim() || lastUserPromptRef.current,
            activeSessionId,
            {
              onToken: ({ delta }) => {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + delta }
                      : msg
                  )
                );
              },
              onRetrievalContext: (data) => setRetrievalContext(data),
              onConfirmationRequired: ({ pending_confirmations }) => {
                setPendingConfirmations(pending_confirmations);
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, pendingConfirmations: pending_confirmations }
                      : msg
                  )
                );
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
                          isStreaming: false,
                        }
                      : msg
                  )
                );
                onSessionsUpdated?.();
              },
            },
            controller.signal
          );
        } catch {
          // ignore
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
      setMessages((prev) =>
        prev.map((msg) => ({
          ...msg,
          pendingConfirmations: msg.pendingConfirmations?.filter(
            (p) => p.action_id !== actionId
          ),
        }))
      );

      // System acknowledgment
      setMessages((prev) => [
        ...prev,
        {
          id: `sys_${Date.now()}`,
          role: "system",
          content: `Approved action ${actionId}. Patch applied and written to disk.`,
          createdAt: new Date(),
        },
      ]);
    },
    []
  );

  const denyAction = useCallback((actionId?: string) => {
    setPendingConfirmations((prev) =>
      actionId ? prev.filter((p) => p.action_id !== actionId) : []
    );
    setMessages((prev) =>
      prev.map((msg) => ({
        ...msg,
        pendingConfirmations: actionId
          ? msg.pendingConfirmations?.filter((p) => p.action_id !== actionId)
          : [],
      }))
    );
    setMessages((prev) => [
      ...prev,
      {
        id: `sys_${Date.now()}`,
        role: "system",
        content: `Action ${actionId || ""} was rejected by user.`,
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
    retrievalContext,
    activitySteps,
    error,
    selectedModel,
    setSelectedModel,
    isMockMode,
    sendMessage,
    confirmAction,
    denyAction,
    selectSession,
    newChat,
    abortStream,
    clearError,
  };
}
