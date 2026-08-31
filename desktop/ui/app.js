const API_BASE = window.location.origin && window.location.origin.startsWith("http") ? window.location.origin : "http://127.0.0.1:8000";

// --- Application State ---
let activeSessionId = "session_" + Math.random().toString(36).substring(2, 9);
let routingMode = "auto";
let currentMode = "WORKSPACE";
let isConversationStarted = false;
let isProcessing = false;
let isRecording = false;
let isVoiceReplyEnabled = false;
let speechRecognition = null;
let mediaRecorder = null;
let audioChunks = [];
let pendingActionIds = [];

// --- DOM Elements ---
const appLayout = document.getElementById("appLayout");
const sidebar = document.getElementById("sidebar");
const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
const sidebarExpandBtn = document.getElementById("sidebarExpandBtn");
const newChatBtn = document.getElementById("newChatBtn");
const refreshSessionsBtn = document.getElementById("refreshSessionsBtn");
const sessionsList = document.getElementById("sessionsList");
const sessionGroupHeader = document.getElementById("sessionGroupHeader");
const skillsList = document.getElementById("skillsList");
const skillsCountBadge = document.getElementById("skillsCountBadge");

// Mode & Workspace Elements
const modeWorkspaceBtn = document.getElementById("modeWorkspaceBtn");
const modeSystemBtn = document.getElementById("modeSystemBtn");
const activeProjectIndicator = document.getElementById("activeProjectIndicator");
const activeProjectName = document.getElementById("active-project-name");

// Top Nav Elements
const modelSelect = document.getElementById("modelSelect");
const activeTierBadge = document.getElementById("activeTierBadge");
const modeToggle = document.getElementById("modeToggle");
const modePill = document.getElementById("modePill");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");
const voiceToggleIcon = document.getElementById("voiceToggleIcon");
const unloadModelBtn = document.getElementById("unloadModelBtn");

// Governor & Telemetry Elements
const governorWidgetContainer = document.getElementById("governorWidgetContainer");
const governorPill = document.getElementById("governorPill");
const governorPillLabel = document.getElementById("governor-pill__label");
const governorCommandPanel = document.getElementById("governorCommandPanel");
const panelStatusTag = document.getElementById("panelStatusTag");
const govPauseResumeBtn = document.getElementById("govPauseResumeBtn");
const govPauseResumeIcon = document.getElementById("govPauseResumeIcon");
const govPauseResumeLabel = document.getElementById("govPauseResumeLabel");
const govOverride5mBtn = document.getElementById("govOverride5mBtn");
const govCustomDurationInput = document.getElementById("govCustomDurationInput");
const govCustomOverrideBtn = document.getElementById("govCustomOverrideBtn");
const govForceReloadBtn = document.getElementById("govForceReloadBtn");
const govClearErrorBtn = document.getElementById("govClearErrorBtn");
const govHistoryList = document.getElementById("govHistoryList");

// Telemetry Tooltip & Meters
const govGpuVal = document.getElementById("govGpuVal");
const govVramVal = document.getElementById("govVramVal");
const govCpuVal = document.getElementById("govCpuVal");
const govRamVal = document.getElementById("govRamVal");
const govMeterGpuVal = document.getElementById("govMeterGpuVal");
const govMeterGpuFill = document.getElementById("govMeterGpuFill");
const govMeterVramVal = document.getElementById("govMeterVramVal");
const govMeterVramFill = document.getElementById("govMeterVramFill");
const govMeterCpuVal = document.getElementById("govMeterCpuVal");
const govMeterCpuFill = document.getElementById("govMeterCpuFill");
const govMeterRamVal = document.getElementById("govMeterRamVal");
const govMeterRamFill = document.getElementById("govMeterRamFill");

// Chat Viewport Elements
const chatViewport = document.getElementById("chatViewport");
const welcomeHero = document.getElementById("welcomeHero");
const emptyStateTitle = document.getElementById("empty-state-title");
const emptyStateSubtitle = document.getElementById("empty-state-subtitle");
const suggWorkspaceCard = document.getElementById("suggWorkspaceCard");
const messagesContainer = document.getElementById("messagesContainer");
const loadingBubble = document.getElementById("loadingBubble");
const confirmationPanel = document.getElementById("confirmationPanel");
const confDetailsText = document.getElementById("confDetailsText");
const approveActionBtn = document.getElementById("approveActionBtn");
const rejectActionBtn = document.getElementById("rejectActionBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// Composer Elements
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");

// Quick Skill Buttons
const skillReviewBtn = document.getElementById("skillReviewBtn");
const skillDiagBtn = document.getElementById("skillDiagBtn");
const skillWebSearchBtn = document.getElementById("skillWebSearchBtn");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  initMarkdownParser();
  initUI();
  initVoice();
  initTelemetry();
  initKeyShortcuts();
  syncVoiceOutputState();
  updateModelTierBadge();
  setChatMode(currentMode, false);
  fetchSessions();
  fetchModelsAndSkills();
});

function initMarkdownParser() {
  if (window.marked) {
    marked.setOptions({
      gfm: true,
      breaks: true,
      headerIds: false,
      mangle: false
    });
  }
}

function initUI() {
  // Auto-expand textarea
  if (promptInput) {
    promptInput.addEventListener("input", () => {
      promptInput.style.height = "auto";
      promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
    });

    // Enter to send, Shift+Enter for new line
    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    });

    setTimeout(() => promptInput.focus(), 150);
  }

  // Send button
  if (sendBtn) {
    sendBtn.addEventListener("click", () => handleSubmit());
  }

  // New Chat button
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => startNewSession());
  }

  // Refresh Sessions button
  if (refreshSessionsBtn) {
    refreshSessionsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fetchSessions();
    });
  }

  // Sidebar Collapse / Expand
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener("click", () => toggleSidebar(false));
  }
  if (sidebarExpandBtn) {
    sidebarExpandBtn.addEventListener("click", () => toggleSidebar(true));
  }

  // Routing Mode Toggle
  if (modeToggle) {
    modeToggle.addEventListener("click", () => cycleRoutingMode());
  }

  // Sidebar Mode Segmented Buttons
  if (modeWorkspaceBtn) {
    modeWorkspaceBtn.addEventListener("click", () => setChatMode("WORKSPACE", true));
  }
  if (modeSystemBtn) {
    modeSystemBtn.addEventListener("click", () => setChatMode("SYSTEM", true));
  }

  // Model Dropdown Change Listener
  if (modelSelect) {
    modelSelect.addEventListener("change", () => updateModelTierBadge());
  }

  // Safety Confirmation Buttons
  if (approveActionBtn) {
    approveActionBtn.addEventListener("click", () => handleApproveAction());
  }
  if (rejectActionBtn) {
    rejectActionBtn.addEventListener("click", () => {
      if (confirmationPanel) confirmationPanel.style.display = "none";
      pendingActionIds = [];
    });
  }

  // Voice Toggle Button
  if (voiceToggleBtn) {
    voiceToggleBtn.addEventListener("click", async () => {
      isVoiceReplyEnabled = !isVoiceReplyEnabled;
      updateVoiceButtonUI();
      try {
        await fetch(`${API_BASE}/api/voice/output`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: isVoiceReplyEnabled })
        });
      } catch (err) {
        console.debug("Error updating voice output state:", err);
      }
    });
  }

  // Free VRAM Button
  if (unloadModelBtn) {
    unloadModelBtn.addEventListener("click", async () => {
      const label = unloadModelBtn.querySelector("span");
      unloadModelBtn.style.opacity = "0.6";
      if (label) label.textContent = "Freeing VRAM...";

      try {
        const selected = modelSelect && modelSelect.value !== "heavy" ? modelSelect.value : null;
        const res = await fetch(`${API_BASE}/models/unload`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_name: selected })
        });
        await res.json();
        if (label) label.textContent = "VRAM Cleared!";
        setTimeout(() => {
          if (label) label.textContent = "Free VRAM";
          unloadModelBtn.style.opacity = "1";
        }, 2000);
        pollGovernor();
      } catch (err) {
        if (label) label.textContent = "Error";
        setTimeout(() => {
          if (label) label.textContent = "Free VRAM";
          unloadModelBtn.style.opacity = "1";
        }, 2000);
      }
    });
  }

  // Governor Command Panel Toggle
  if (governorPill && governorWidgetContainer) {
    governorPill.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = governorWidgetContainer.classList.toggle("open");
      if (isOpen) {
        fetchGovernorHistory();
      }
    });

    document.addEventListener("click", (e) => {
      if (governorWidgetContainer.classList.contains("open") && !governorWidgetContainer.contains(e.target)) {
        governorWidgetContainer.classList.remove("open");
      }
    });

    if (governorCommandPanel) {
      governorCommandPanel.addEventListener("click", (e) => e.stopPropagation());
    }
  }

  // Governor Action Buttons
  if (govPauseResumeBtn) {
    govPauseResumeBtn.addEventListener("click", async () => {
      const isPaused = govPauseResumeBtn.classList.contains("active-resume");
      const endpoint = isPaused ? "/governor/resume" : "/governor/pause";
      try {
        govPauseResumeBtn.style.opacity = "0.6";
        await fetch(`${API_BASE}${endpoint}`, { method: "POST" });
        await pollGovernor();
        await fetchGovernorHistory();
      } catch (err) {
        console.error("Governor pause/resume error:", err);
      } finally {
        govPauseResumeBtn.style.opacity = "1";
      }
    });
  }

  if (govOverride5mBtn) {
    govOverride5mBtn.addEventListener("click", async () => {
      try {
        govOverride5mBtn.style.opacity = "0.6";
        await fetch(`${API_BASE}/governor/resume-override`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ duration_seconds: 300 })
        });
        await pollGovernor();
        await fetchGovernorHistory();
      } catch (err) {
        console.error("Governor override error:", err);
      } finally {
        govOverride5mBtn.style.opacity = "1";
      }
    });
  }

  if (govCustomOverrideBtn && govCustomDurationInput) {
    govCustomOverrideBtn.addEventListener("click", async () => {
      const mins = parseFloat(govCustomDurationInput.value) || 15;
      const seconds = Math.max(10, mins * 60);
      try {
        govCustomOverrideBtn.style.opacity = "0.6";
        await fetch(`${API_BASE}/governor/resume-override`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ duration_seconds: seconds })
        });
        await pollGovernor();
        await fetchGovernorHistory();
      } catch (err) {
        console.error("Governor custom override error:", err);
      } finally {
        govCustomOverrideBtn.style.opacity = "1";
      }
    });
  }

  if (govForceReloadBtn) {
    govForceReloadBtn.addEventListener("click", async () => {
      try {
        govForceReloadBtn.style.opacity = "0.6";
        await fetch(`${API_BASE}/governor/force-reload`, { method: "POST" });
        await pollGovernor();
        await fetchGovernorHistory();
      } catch (err) {
        console.error("Governor force reload error:", err);
      } finally {
        govForceReloadBtn.style.opacity = "1";
      }
    });
  }

  if (govClearErrorBtn) {
    govClearErrorBtn.addEventListener("click", async () => {
      try {
        govClearErrorBtn.style.opacity = "0.6";
        await fetch(`${API_BASE}/governor/clear-error`, { method: "POST" });
        await pollGovernor();
        await fetchGovernorHistory();
      } catch (err) {
        console.error("Governor clear error error:", err);
      } finally {
        govClearErrorBtn.style.opacity = "1";
      }
    });
  }

  // Quick Skills
  if (skillReviewBtn) {
    skillReviewBtn.addEventListener("click", () => {
      if (promptInput) promptInput.value = "Review the codebase files in backend/app for quality, reliability, and security.";
      handleSubmit();
    });
  }
  if (skillDiagBtn) {
    skillDiagBtn.addEventListener("click", () => {
      if (promptInput) promptInput.value = "Check system diagnostics, disk usage, and hardware telemetry stats.";
      handleSubmit();
    });
  }
  if (skillWebSearchBtn) {
    skillWebSearchBtn.addEventListener("click", () => {
      if (promptInput) {
        promptInput.value = "Search the web for the latest updates on ";
        promptInput.focus();
      }
    });
  }

  // Suggestion Cards
  document.querySelectorAll(".suggestion-card").forEach(card => {
    card.addEventListener("click", () => {
      const p = card.getAttribute("data-prompt");
      if (p && promptInput) {
        promptInput.value = p;
        handleSubmit();
      }
    });
  });
}

function initKeyShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Ctrl+B: Toggle Sidebar
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
      e.preventDefault();
      const isCollapsed = sidebar && sidebar.classList.contains("collapsed");
      toggleSidebar(isCollapsed);
    }
    // Alt+G: Toggle Governor
    else if (e.altKey && e.key.toLowerCase() === "g") {
      e.preventDefault();
      if (governorWidgetContainer) {
        const isOpen = governorWidgetContainer.classList.toggle("open");
        if (isOpen) fetchGovernorHistory();
      }
    }
    // Ctrl+N: New Chat
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
      e.preventDefault();
      startNewSession();
    }
    // Escape: Close Governor or Confirmation
    else if (e.key === "Escape") {
      if (governorWidgetContainer && governorWidgetContainer.classList.contains("open")) {
        governorWidgetContainer.classList.remove("open");
      }
      if (confirmationPanel && confirmationPanel.style.display !== "none") {
        confirmationPanel.style.display = "none";
      }
    }
  });
}

function toggleSidebar(expand) {
  if (!sidebar) return;
  if (expand) {
    sidebar.classList.remove("collapsed");
    if (sidebarExpandBtn) sidebarExpandBtn.style.display = "none";
  } else {
    sidebar.classList.add("collapsed");
    if (sidebarExpandBtn) sidebarExpandBtn.style.display = "flex";
  }
}

// --- Submit Query Handler with Live SSE Streaming ---
async function handleSubmit(approvedTokens = null) {
  const query = promptInput ? promptInput.value.trim() : "";
  if (!query && !approvedTokens) return;
  if (isProcessing) return;

  isProcessing = true;
  isConversationStarted = true;
  if (sendBtn) sendBtn.style.opacity = "0.5";
  if (welcomeHero) welcomeHero.style.display = "none";
  if (confirmationPanel) confirmationPanel.style.display = "none";

  if (!approvedTokens) {
    appendUserMessage(query);
    if (promptInput) {
      promptInput.value = "";
      promptInput.style.height = "auto";
    }
  }

  if (loadingBubble) loadingBubble.style.display = "none";

  const selectedModel = modelSelect ? modelSelect.value : "prism-ml/bonsai-27b";
  const isHeavy = selectedModel === "heavy";

  const payload = {
    message: query || "Approved action execution.",
    session_id: activeSessionId,
    model: isHeavy ? null : selectedModel,
    mode: isHeavy ? "heavy" : routingMode,
    chat_mode: currentMode,
    approved_action_ids: approvedTokens
  };

  const streamMessage = createStreamingAssistantMessage();
  let accumulatedText = "";
  let toolsUsed = [];
  let activeSkills = [];
  let modelName = selectedModel;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000);

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (response.status === 429) {
      const err = await response.json();
      streamMessage.finalizeText(`Resource Governor Throttled: ${err.detail || "System under high load."}`);
      return;
    }

    if (response.status === 404) {
      // Graceful fallback to standard /chat endpoint if streaming endpoint is unavailable
      const fallbackRes = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      if (!fallbackRes.ok) {
        const err = await fallbackRes.text();
        streamMessage.finalizeText(`Error: ${err}`);
        return;
      }
      const data = await fallbackRes.json();
      if (data.status === "confirmation_required") {
        streamMessage.remove();
        showConfirmationPrompt(data);
        if (isVoiceReplyEnabled) {
          speakText("Confirmation required before executing the requested system action.");
        }
      } else {
        streamMessage.finalize(data.response, data.tools_used, data.active_skills, data.model);
        if (isVoiceReplyEnabled && data.response) {
          speakText(data.response);
        }
        fetchSessions();
      }
      return;
    }

    if (!response.ok) {
      const err = await response.text();
      streamMessage.finalizeText(`Error: ${err}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        if (!block.trim()) continue;
        const eventLines = block.split("\n");
        let eventType = "message";
        let eventData = "";

        for (const line of eventLines) {
          if (line.startsWith("event: ")) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            eventData = line.substring(6).trim();
          }
        }

        if (!eventData) continue;

        let parsedData = {};
        try {
          parsedData = JSON.parse(eventData);
        } catch {
          parsedData = { text: eventData };
        }

        if (eventType === "token") {
          const delta = parsedData.delta || "";
          accumulatedText += delta;
          streamMessage.updateText(accumulatedText);
        } else if (eventType === "tool_start") {
          streamMessage.addOrUpdateToolStep(parsedData.tool, parsedData.args, "running", null);
        } else if (eventType === "tool_end") {
          toolsUsed.push(parsedData);
          streamMessage.addOrUpdateToolStep(parsedData.tool, parsedData.args, parsedData.status, parsedData.result);
        } else if (eventType === "confirmation_required") {
          streamMessage.remove();
          showConfirmationPrompt(parsedData);
          if (isVoiceReplyEnabled) {
            speakText("Confirmation required before executing the requested system action.");
          }
          return;
        } else if (eventType === "done") {
          if (parsedData.response && parsedData.response.length > accumulatedText.length) {
            accumulatedText = parsedData.response;
          }
          toolsUsed = parsedData.tools_used || toolsUsed;
          activeSkills = parsedData.active_skills || [];
          modelName = parsedData.model || selectedModel;
        } else if (eventType === "error") {
          accumulatedText += `\n\nError: ${parsedData.error}`;
          streamMessage.updateText(accumulatedText);
        }
      }
    }

    streamMessage.finalize(accumulatedText, toolsUsed, activeSkills, modelName);
    if (isVoiceReplyEnabled && accumulatedText) {
      speakText(accumulatedText);
    }
    fetchSessions();

  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      streamMessage.finalizeText(`Timeout: Jarvis took too long to respond. The system may be busy.`);
    } else {
      streamMessage.finalizeText(`Connection Error: Could not reach backend API at ${API_BASE}. Make sure Jarvis backend is running.`);
    }
  } finally {
    isProcessing = false;
    if (sendBtn) sendBtn.style.opacity = "1";
    if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
    if (promptInput) promptInput.focus();
  }
}

function createStreamingAssistantMessage() {
  if (!messagesContainer) return { updateText() {}, addOrUpdateToolStep() {}, finalizeText() {}, finalize() {}, remove() {} };
  const row = document.createElement("div");
  row.className = "msg-row assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = `<div class="streaming-text-container"><span class="streaming-cursor"></span></div><div class="tool-step-container"></div>`;

  row.appendChild(bubble);
  messagesContainer.appendChild(row);
  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;

  const textContainer = bubble.querySelector(".streaming-text-container");
  const toolContainer = bubble.querySelector(".tool-step-container");
  const activeToolCards = new Map();

  return {
    updateText(rawText) {
      if (textContainer) {
        textContainer.innerHTML = renderMarkdownToHtml(rawText) + `<span class="streaming-cursor"></span>`;
        if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
      }
    },
    addOrUpdateToolStep(toolName, args, status, result) {
      if (!toolContainer) return;
      let card = activeToolCards.get(toolName);
      if (!card) {
        card = createToolStepCard({ tool: toolName, args: args, status: status, result: result });
        toolContainer.appendChild(card);
        activeToolCards.set(toolName, card);
      } else {
        const pill = card.querySelector(".step-status-pill");
        if (pill) {
          const isSuccess = status !== "error";
          pill.className = `step-status-pill ${isSuccess ? "success" : "error"}`;
          pill.textContent = isSuccess ? "Success" : "Failed";
        }
        if (result) {
          const body = card.querySelector(".tool-step-body");
          if (body) {
            body.innerHTML = `<div><strong>Result:</strong><pre style="margin-top:4px; white-space:pre-wrap;">${escapeHtml(typeof result === 'string' ? result : JSON.stringify(result, null, 2))}</pre></div>`;
          }
        }
      }
      if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
    },
    finalizeText(errorText) {
      if (textContainer) {
        textContainer.innerHTML = renderMarkdownToHtml(errorText);
      }
    },
    finalize(finalText, tools, activeSkills, model) {
      if (textContainer) {
        textContainer.innerHTML = renderMarkdownToHtml(finalText);
      }

      const actionsBar = document.createElement("div");
      actionsBar.className = "msg-actions-bar";

      if (activeSkills && activeSkills.length > 0) {
        const tag = document.createElement("div");
        tag.className = "tier-badge tier-badge--1";
        tag.innerHTML = `<i class="ti ti-sparkles"></i> ${escapeHtml(activeSkills.join(", "))}`;
        actionsBar.appendChild(tag);
      }

      const readBtn = document.createElement("button");
      readBtn.className = "read-aloud-btn";
      readBtn.innerHTML = `<i class="ti ti-volume"></i> Read Aloud`;
      readBtn.addEventListener("click", () => speakText(finalText));
      actionsBar.appendChild(readBtn);

      bubble.appendChild(actionsBar);

      enhanceCodeBlocks(bubble);
      if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
    },
    remove() {
      row.remove();
    }
  };
}

// --- Mode & Model Controls ---
function setChatMode(mode, fromUserClick = false) {
  if (isConversationStarted && fromUserClick) {
    const alertMsg = "Mode is locked for the current chat session. Start a 'New Chat' to switch mode.";
    if (window.confirm ? confirm(alertMsg + "\n\nWould you like to start a new chat now?") : false) {
      startNewSession();
      setChatMode(mode, false);
    }
    return;
  }

  currentMode = mode;

  if (mode === "WORKSPACE") {
    if (modeWorkspaceBtn) modeWorkspaceBtn.classList.add("mode-toggle__option--active");
    if (modeSystemBtn) modeSystemBtn.classList.remove("mode-toggle__option--active");
    if (activeProjectIndicator) activeProjectIndicator.style.display = "flex";
    if (emptyStateTitle) emptyStateTitle.textContent = "Working in " + (activeProjectName ? activeProjectName.textContent : "JARVIS core");
    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Workspace mode - writes stay inside this project folder";
    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "flex";
    if (sessionGroupHeader) sessionGroupHeader.textContent = "Workspace Chats";
  } else {
    if (modeSystemBtn) modeSystemBtn.classList.add("mode-toggle__option--active");
    if (modeWorkspaceBtn) modeWorkspaceBtn.classList.remove("mode-toggle__option--active");
    if (activeProjectIndicator) activeProjectIndicator.style.display = "none";
    if (emptyStateTitle) emptyStateTitle.textContent = "System Mode Active";
    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Full PC access - confirmation required outside safe workspace paths";
    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "none";
    if (sessionGroupHeader) sessionGroupHeader.textContent = "System Chats";
  }
}

function updateModelTierBadge() {
  if (!modelSelect || !activeTierBadge) return;

  const val = modelSelect.value;
  if (val === "qwen2.5:0.5b") {
    activeTierBadge.className = "tier-badge tier-badge--1";
    activeTierBadge.textContent = "Tier 1 · fast";
  } else if (val === "heavy") {
    activeTierBadge.className = "tier-badge tier-badge--3";
    activeTierBadge.textContent = "Tier 3 · cloud";
  } else {
    activeTierBadge.className = "tier-badge tier-badge--2";
    activeTierBadge.textContent = "Tier 2 · local";
  }
}

async function syncVoiceOutputState() {
  try {
    const res = await fetch(`${API_BASE}/api/voice/output`);
    if (res.ok) {
      const data = await res.json();
      isVoiceReplyEnabled = Boolean(data.enabled);
      updateVoiceButtonUI();
    }
  } catch (err) {
    console.debug("Error syncing voice output state:", err);
  }
}

function updateVoiceButtonUI() {
  if (!voiceToggleBtn) return;
  const textEl = voiceToggleBtn.querySelector(".voice-text");
  if (isVoiceReplyEnabled) {
    voiceToggleBtn.classList.add("active");
    if (voiceToggleIcon) voiceToggleIcon.className = "ti ti-volume voice-icon";
    if (textEl) textEl.textContent = "Voice: ON";
  } else {
    voiceToggleBtn.classList.remove("active");
    if (voiceToggleIcon) voiceToggleIcon.className = "ti ti-volume-off voice-icon";
    if (textEl) textEl.textContent = "Voice: OFF";
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
  }
}

function cycleRoutingMode() {
  const modes = ["auto", "normal", "heavy"];
  const nextIdx = (modes.indexOf(routingMode) + 1) % modes.length;
  routingMode = modes[nextIdx];
  if (modePill) {
    modePill.textContent = routingMode.charAt(0).toUpperCase() + routingMode.slice(1);
  }
}

function startNewSession() {
  activeSessionId = "session_" + Math.random().toString(36).substring(2, 9);
  isConversationStarted = false;

  if (messagesContainer) messagesContainer.innerHTML = "";
  if (welcomeHero) welcomeHero.style.display = "flex";
  if (confirmationPanel) confirmationPanel.style.display = "none";
  if (loadingBubble) loadingBubble.style.display = "none";

  setChatMode(currentMode, false);
  fetchSessions();

  if (promptInput) promptInput.focus();
}

// --- Session Drawer & History Management ---
async function fetchSessions() {
  if (!sessionsList) return;
  try {
    const res = await fetch(`${API_BASE}/sessions`);
    if (!res.ok) return;
    const sessions = await res.json();

    sessionsList.innerHTML = "";

    if (!Array.isArray(sessions) || sessions.length === 0) {
      const defaultItem = document.createElement("div");
      defaultItem.className = "session-item active";
      defaultItem.innerHTML = `
        <i class="ti ti-message-2 session-icon"></i>
        <span class="session-name">Current Session</span>
      `;
      sessionsList.appendChild(defaultItem);
      return;
    }

    sessions.forEach(sess => {
      const sId = sess.session_id || sess.id || sess;
      const title = sess.title || `Chat ${sId.substring(0, 8)}`;
      const isActive = sId === activeSessionId;

      const item = document.createElement("div");
      item.className = `session-item ${isActive ? "active" : ""}`;
      item.setAttribute("data-session-id", sId);
      item.innerHTML = `
        <i class="ti ti-message-2 session-icon"></i>
        <span class="session-name" title="${title}">${title}</span>
        <button class="session-delete-btn" title="Delete Session">
          <i class="ti ti-trash"></i>
        </button>
      `;

      item.addEventListener("click", () => {
        loadSession(sId);
      });

      const delBtn = item.querySelector(".session-delete-btn");
      if (delBtn) {
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          deleteSession(sId, item);
        });
      }

      sessionsList.appendChild(item);
    });

  } catch (err) {
    console.debug("Error fetching sessions:", err);
  }
}

async function loadSession(sessionId) {
  if (isProcessing) return;
  activeSessionId = sessionId;
  isConversationStarted = true;

  document.querySelectorAll(".session-item").forEach(el => {
    if (el.getAttribute("data-session-id") === sessionId) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });

  if (welcomeHero) welcomeHero.style.display = "none";
  if (confirmationPanel) confirmationPanel.style.display = "none";
  if (messagesContainer) messagesContainer.innerHTML = "";
  if (loadingBubble) loadingBubble.style.display = "flex";

  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
    if (loadingBubble) loadingBubble.style.display = "none";

    if (!res.ok) {
      appendAssistantMessage(`Could not load messages for session ${sessionId}.`);
      return;
    }

    const messages = await res.json();
    if (!Array.isArray(messages) || messages.length === 0) {
      if (welcomeHero) welcomeHero.style.display = "flex";
      return;
    }

    messages.forEach(msg => {
      const role = msg.role || "user";
      const content = msg.content || "";
      const toolsUsed = msg.tools_used || (msg.metadata ? msg.metadata.tools_used : []);
      const activeSkills = msg.active_skills || (msg.metadata ? msg.metadata.active_skills : []);
      const model = msg.model || (msg.metadata ? msg.metadata.model : "");

      if (role === "user") {
        appendUserMessage(content);
      } else {
        appendAssistantMessage(content, toolsUsed, activeSkills, model);
      }
    });

  } catch (err) {
    if (loadingBubble) loadingBubble.style.display = "none";
    appendAssistantMessage(`Error loading session history: ${err}`);
  }
}

async function deleteSession(sessionId, element) {
  if (window.confirm ? !confirm("Are you sure you want to delete this session?") : false) {
    return;
  }
  try {
    await fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" });
    if (element) {
      element.style.opacity = "0";
      setTimeout(() => element.remove(), 200);
    }
    if (activeSessionId === sessionId) {
      startNewSession();
    }
  } catch (err) {
    console.error("Error deleting session:", err);
  }
}

// --- Dynamic Models & Skills Discovery ---
async function fetchModelsAndSkills() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return;
    const data = await res.json();

    // 1. Update Models Dropdown
    if (modelSelect && Array.isArray(data.available_models) && data.available_models.length > 0) {
      const currentVal = modelSelect.value;
      const heavyOpt = '<option value="heavy">Heavy Mode (OpenRouter)</option>';
      
      const opts = data.available_models.map(m => {
        let label = m;
        if (m.includes("bonsai")) label = "Bonsai 27B (LM Studio)";
        else if (m.includes("hermes")) label = "Hermes 3 8B (Ollama)";
        else if (m.includes("qwen2.5:0.5b")) label = "Qwen 2.5 0.5B (Ollama)";
        else if (m.includes("qwen3.8")) label = "Qwen 3.8 9B (LM Studio)";
        return `<option value="${m}">${label}</option>`;
      }).join("") + heavyOpt;

      modelSelect.innerHTML = opts;
      if (data.available_models.includes(currentVal) || currentVal === "heavy") {
        modelSelect.value = currentVal;
      } else if (data.configured_model && data.available_models.includes(data.configured_model)) {
        modelSelect.value = data.configured_model;
      }
      updateModelTierBadge();
    }

    // 2. Update Skills Count Badge
    if (skillsCountBadge && data.available_skills_count !== undefined) {
      skillsCountBadge.textContent = `${data.available_skills_count} Active`;
    }

  } catch (err) {
    console.debug("Error loading health models/skills:", err);
  }
}

// --- Message Rendering Engine ---
function appendUserMessage(text) {
  if (!messagesContainer) return;
  const row = document.createElement("div");
  row.className = "msg-row user";
  
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  
  row.appendChild(bubble);
  messagesContainer.appendChild(row);
  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
}

function appendAssistantMessage(text, toolsUsed = [], activeSkills = [], modelName = "") {
  if (!messagesContainer) return;
  const row = document.createElement("div");
  row.className = "msg-row assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = renderMarkdownToHtml(text);

  // Render Collapsible Tool Execution Steps
  if (toolsUsed && toolsUsed.length > 0) {
    const toolsContainer = document.createElement("div");
    toolsContainer.className = "tool-step-container";

    toolsUsed.forEach(t => {
      const stepCard = createToolStepCard(t);
      toolsContainer.appendChild(stepCard);
    });

    bubble.appendChild(toolsContainer);
  }

  // Actions Bar
  const actionsBar = document.createElement("div");
  actionsBar.className = "msg-actions-bar";

  if (activeSkills && activeSkills.length > 0) {
    const tag = document.createElement("div");
    tag.className = "tier-badge tier-badge--1";
    tag.innerHTML = `<i class="ti ti-sparkles"></i> ${escapeHtml(activeSkills.join(", "))}`;
    actionsBar.appendChild(tag);
  }

  // Read Aloud button
  const readBtn = document.createElement("button");
  readBtn.className = "read-aloud-btn";
  readBtn.innerHTML = `<i class="ti ti-volume"></i> Read Aloud`;
  readBtn.addEventListener("click", () => speakText(text));
  actionsBar.appendChild(readBtn);

  bubble.appendChild(actionsBar);
  row.appendChild(bubble);
  messagesContainer.appendChild(row);

  // Post-render syntax highlighting & copy listeners
  enhanceCodeBlocks(bubble);

  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
}

function createToolStepCard(toolItem) {
  const card = document.createElement("div");
  card.className = "tool-step-card";

  const toolName = toolItem.tool || "tool_execution";
  let iconClass = "ti-tool";
  if (toolName.includes("search") || toolName.includes("fetch")) iconClass = "ti-world-search";
  else if (toolName.includes("file") || toolName.includes("read") || toolName.includes("write")) iconClass = "ti-file-code";
  else if (toolName.includes("command") || toolName.includes("powershell")) iconClass = "ti-terminal-2";
  else if (toolName.includes("diagnostics") || toolName.includes("status")) iconClass = "ti-activity";

  const argsObj = toolItem.args || {};
  let argsPreview = "";
  if (argsObj.query) argsPreview = `query: "${argsObj.query}"`;
  else if (argsObj.file_path) argsPreview = `path: "${argsObj.file_path}"`;
  else if (argsObj.command) argsPreview = `cmd: "${argsObj.command}"`;
  else if (Object.keys(argsObj).length > 0) argsPreview = JSON.stringify(argsObj);

  const isSuccess = toolItem.status !== "error";
  const statusLabel = isSuccess ? "Success" : "Failed";
  const statusClass = isSuccess ? "success" : "error";

  card.innerHTML = `
    <div class="tool-step-header">
      <div class="tool-step-left">
        <i class="ti ${iconClass} tool-step-icon"></i>
        <span class="tool-step-name">${escapeHtml(toolName)}</span>
        ${argsPreview ? `<span class="tool-step-args-preview">${escapeHtml(argsPreview)}</span>` : ""}
      </div>
      <div class="tool-step-right">
        <span class="step-status-pill ${statusClass}">${statusLabel}</span>
        <i class="ti ti-chevron-down step-chevron"></i>
      </div>
    </div>
    <div class="tool-step-body">
      ${toolItem.result ? `<div><strong>Result:</strong><pre style="margin-top:4px; white-space:pre-wrap;">${escapeHtml(typeof toolItem.result === 'string' ? toolItem.result : JSON.stringify(toolItem.result, null, 2))}</pre></div>` : `<div>Arguments: ${escapeHtml(JSON.stringify(argsObj, null, 2))}</div>`}
    </div>
  `;

  const header = card.querySelector(".tool-step-header");
  if (header) {
    header.addEventListener("click", () => {
      card.classList.toggle("open");
    });
  }

  return card;
}

function renderMarkdownToHtml(text) {
  if (!text) return "";
  if (window.marked) {
    try {
      return marked.parse(text);
    } catch {
      // Fallback to basic sanitization
    }
  }
  return fallbackFormatMarkdown(text);
}

function fallbackFormatMarkdown(text) {
  let formatted = escapeHtml(text);
  formatted = formatted.replace(/```([\w]*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
  formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/\n/g, '<br>');
  return formatted;
}

function enhanceCodeBlocks(container) {
  const preElements = container.querySelectorAll("pre");
  preElements.forEach(pre => {
    if (pre.closest(".code-block-wrapper") || pre.closest(".conf-payload-box")) return;

    const codeEl = pre.querySelector("code");
    const rawCode = codeEl ? codeEl.textContent : pre.textContent;

    // Detect language class
    let lang = "plaintext";
    if (codeEl) {
      const classes = Array.from(codeEl.classList);
      const langClass = classes.find(c => c.startsWith("language-"));
      if (langClass) {
        lang = langClass.replace("language-", "");
      }
    }

    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";

    const header = document.createElement("div");
    header.className = "code-header";
    header.innerHTML = `
      <span>${escapeHtml(lang)}</span>
      <button class="copy-code-btn" title="Copy code to clipboard">
        <i class="ti ti-copy"></i>
        <span>Copy</span>
      </button>
    `;

    const copyBtn = header.querySelector(".copy-code-btn");
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(rawCode);
        copyBtn.classList.add("copied");
        copyBtn.innerHTML = `<i class="ti ti-check"></i> <span>Copied!</span>`;
        setTimeout(() => {
          copyBtn.classList.remove("copied");
          copyBtn.innerHTML = `<i class="ti ti-copy"></i> <span>Copy</span>`;
        }, 2000);
      } catch (e) {
        console.error("Clipboard copy error:", e);
      }
    });

    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);

    // Apply Prism syntax highlighting
    if (window.Prism && codeEl) {
      Prism.highlightElement(codeEl);
    }
  });
}

// --- Safety Confirmation UI ---
function showConfirmationPrompt(data) {
  pendingActionIds = (data.pending_confirmations || []).map(p => p.action_id);
  
  const cardsHtml = (data.pending_confirmations || []).map(p => {
    const isHigh = p.risk_tier === "HIGH_RISK";
    const badgeClass = isHigh ? "conf-risk-badge high" : "conf-risk-badge confirm";
    const toolIcon = p.tool.includes("command") ? "ti-terminal-2" : p.tool.includes("write") ? "ti-edit" : p.tool.includes("delete") ? "ti-trash" : "ti-tool";
    
    let payloadHtml = "";
    if (p.args && p.args.command) {
      payloadHtml = `
        <div class="conf-payload-label">Command to execute in PowerShell:</div>
        <div class="conf-payload-box">&gt; ${escapeHtml(p.args.command)}</div>
      `;
    } else if (p.args && p.args.file_path) {
      payloadHtml = `
        <div class="conf-payload-label">Target File Path:</div>
        <div class="conf-payload-box">${escapeHtml(p.args.file_path)}</div>
      `;
      if (p.args.content) {
        payloadHtml += `
          <div class="conf-payload-label" style="margin-top:6px;">Content Preview:</div>
          <div class="conf-payload-box">${escapeHtml(p.args.content.substring(0, 300))}${p.args.content.length > 300 ? '...' : ''}</div>
        `;
      }
    } else if (p.args && Object.keys(p.args).length > 0) {
      payloadHtml = `
        <div class="conf-payload-label">Arguments:</div>
        <div class="conf-payload-box">${escapeHtml(JSON.stringify(p.args, null, 2))}</div>
      `;
    }

    const reasonHtml = p.reason ? `<div class="conf-reason-text">${escapeHtml(p.reason)}</div>` : "";

    return `
      <div class="conf-action-card">
        <div class="conf-action-header">
          <span class="conf-tool-name"><i class="ti ${toolIcon}"></i> ${escapeHtml(p.tool)}</span>
          <span class="${badgeClass}">${escapeHtml(p.risk_tier)}</span>
        </div>
        ${payloadHtml}
        ${reasonHtml}
      </div>
    `;
  }).join("");

  if (confDetailsText) {
    confDetailsText.innerHTML = `
      <div>Jarvis requests authorization to perform the following system operation(s):</div>
      <div style="display:flex; flex-direction:column; gap:10px; margin-top:8px;">${cardsHtml}</div>
    `;
  }
  
  if (confirmationPanel) confirmationPanel.style.display = "flex";
  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function handleApproveAction() {
  if (confirmationPanel) confirmationPanel.style.display = "none";
  handleSubmit(pendingActionIds);
}

// --- Text-to-Speech (TTS) Engine ---
let currentAudio = null;

function sanitizeForSpeech(text) {
  if (!text) return "";
  return text
    .replace(/```[\s\S]*?```/g, " [code block omitted] ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function speakText(text) {
  const clean = sanitizeForSpeech(text);
  if (!clean) return;

  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }

  // 1. Local Voice Output via backend (/voice/speak)
  try {
    const res = await fetch(`${API_BASE}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: clean })
    });

    if (res.ok) {
      const data = await res.json();
      if (data.status === "spoken") {
        return;
      }
    }
  } catch (err) {
    console.debug("Local voice speak fallback to browser TTS:", err);
  }

  // 2. Fallback to Browser SpeechSynthesis
  try {
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => v.lang && v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("David") || v.name.includes("Ryan") || v.name.includes("George")));
    if (englishVoice) {
      utterance.voice = englishVoice;
    }

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.debug("Browser TTS error:", err);
  }
}

// --- Voice Recognition & Audio Recording ---
function initVoice() {
  if (!micBtn) return;

  micBtn.addEventListener("click", async () => {
    if (isRecording) {
      stopVoiceRecording();
    } else {
      startVoiceRecording();
    }
  });
}

async function startVoiceRecording() {
  if (isRecording) {
    stopVoiceRecording();
    return;
  }

  isRecording = true;
  if (micBtn) micBtn.classList.add("recording");
  if (promptInput) promptInput.placeholder = "Listening... Speak now...";

  audioChunks = [];
  let speechRecognizedText = "";

  // 1. Live browser speech preview
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      speechRecognition = new SpeechRecognition();
      speechRecognition.continuous = false;
      speechRecognition.interimResults = true;
      speechRecognition.lang = "en-US";

      speechRecognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        speechRecognizedText = cleanWakeWord(transcript);
        if (promptInput) promptInput.value = speechRecognizedText;
      };

      speechRecognition.onerror = (e) => {
        console.debug("SpeechRecognition error:", e);
      };

      speechRecognition.start();
    } catch (e) {
      console.debug("SpeechRecognition unavailable:", e);
    }
  }

  // 2. MediaRecorder stream for backend Whisper
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      isRecording = false;
      if (micBtn) micBtn.classList.remove("recording");
      if (promptInput) promptInput.placeholder = "Message Jarvis, or ask to execute tools...";
      stream.getTracks().forEach(track => track.stop());

      if (speechRecognizedText && speechRecognizedText.trim().length > 1) {
        if (promptInput) promptInput.value = speechRecognizedText.trim();
        handleSubmit();
      } else if (audioChunks.length > 0) {
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        await sendAudioToBackendTranscribe(audioBlob);
      }
    };

    mediaRecorder.start(250);

  } catch (err) {
    console.error("Microphone capture error:", err);
    isRecording = false;
    if (micBtn) micBtn.classList.remove("recording");
    if (promptInput) promptInput.placeholder = "Message Jarvis, or ask to execute tools...";
  }
}

function cleanWakeWord(text) {
  if (!text) return "";
  const lower = text.toLowerCase();
  const wakePrefixes = ["hey jarvis", "ok jarvis", "okay jarvis", "hello jarvis", "jarvis"];
  let cleaned = text;
  for (const w of wakePrefixes) {
    if (lower.startsWith(w)) {
      cleaned = text.substring(w.length).trim().replace(/^[,.?! ]+/, "");
      break;
    }
  }
  return cleaned || text;
}

function stopVoiceRecording() {
  if (speechRecognition) {
    try { speechRecognition.stop(); } catch {}
  }
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try { mediaRecorder.stop(); } catch {}
  }
  isRecording = false;
  if (micBtn) micBtn.classList.remove("recording");
}

async function sendAudioToBackendTranscribe(blob) {
  try {
    if (loadingBubble) loadingBubble.style.display = "flex";
    const formData = new FormData();
    formData.append("file", blob, "recording.webm");

    const res = await fetch(`${API_BASE}/voice/transcribe`, {
      method: "POST",
      body: formData
    });

    if (loadingBubble) loadingBubble.style.display = "none";

    if (res.ok) {
      const data = await res.json();
      if (data.text && data.text.trim()) {
        const transcript = cleanWakeWord(data.text.trim());
        if (promptInput) promptInput.value = transcript;
        handleSubmit();
      }
    }
  } catch (err) {
    if (loadingBubble) loadingBubble.style.display = "none";
    console.error("Transcription upload error:", err);
  }
}

// --- Telemetry Poller & Visualizers ---
function initTelemetry() {
  setInterval(pollGovernor, 2000);
  pollGovernor();
}

async function pollGovernor() {
  try {
    const res = await fetch(`${API_BASE}/governor/status`);
    if (res.ok) {
      const data = await res.json();
      const st = (data.status || "IDLE").toUpperCase();
      
      // Update sidebar status badge
      if (statusDot) {
        statusDot.className = (st === "PAUSED" || st === "UNLOADED" || st === "ERROR") ? "status-dot throttled" : "status-dot connected";
      }
      if (statusText) {
        if (st === "PAUSED") statusText.textContent = "Paused (Manual)";
        else if (st === "UNLOADED") statusText.textContent = "VRAM Unloaded";
        else if (st === "ERROR") statusText.textContent = "Governor Error";
        else if (st === "LOADING") statusText.textContent = "Loading Model...";
        else if (st === "RUNNING") statusText.textContent = "Jarvis Active";
        else statusText.textContent = "Jarvis Ready";
      }

      // Update Governor Pill & Arc Ring
      if (governorPill) {
        governorPill.className = "governor-pill";
        if (st === "IDLE") governorPill.classList.add("governor-pill--idle");
        else if (st === "RUNNING") governorPill.classList.add("governor-pill--running");
        else if (st === "LOADING") governorPill.classList.add("governor-pill--loading");
        else if (st === "PAUSED") governorPill.classList.add("governor-pill--paused");
        else if (st === "UNLOADED") governorPill.classList.add("governor-pill--unloaded");
        else if (st === "ERROR") governorPill.classList.add("governor-pill--error");
        else governorPill.classList.add("governor-pill--idle");

        if (governorPillLabel) {
          if (data.is_manual_override && data.override_expires_at) {
            const nowSec = Date.now() / 1000;
            const remaining = Math.max(0, Math.round(data.override_expires_at - nowSec));
            if (remaining > 0) {
              const mins = Math.floor(remaining / 60);
              const secs = remaining % 60;
              governorPillLabel.textContent = `Override: ${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
            } else {
              governorPillLabel.textContent = `Governor: ${st.toLowerCase()}`;
            }
          } else if (data.is_manual_override) {
            governorPillLabel.textContent = "Override: active";
          } else if (st === "LOADING") {
            governorPillLabel.textContent = "Governor: loading...";
          } else {
            governorPillLabel.textContent = `Governor: ${st.toLowerCase()}`;
          }
        }
      }

      // Update Command Panel Status Tag
      if (panelStatusTag) {
        panelStatusTag.textContent = st;
        panelStatusTag.className = `gov-panel__status-tag tag-${st.toLowerCase()}`;
      }

      // Update Pause / Resume Button State
      if (govPauseResumeBtn && govPauseResumeLabel && govPauseResumeIcon) {
        const isPausedOrOverridden = st === "PAUSED" || data.manual_override_active;
        if (isPausedOrOverridden) {
          govPauseResumeBtn.classList.add("active-resume");
          govPauseResumeIcon.className = "ti ti-player-play";
          govPauseResumeLabel.textContent = "Resume";
        } else {
          govPauseResumeBtn.classList.remove("active-resume");
          govPauseResumeIcon.className = "ti ti-player-pause";
          govPauseResumeLabel.textContent = "Pause";
        }
      }

      // Contextual Action Visibility
      if (govForceReloadBtn) {
        if (data.model_unloaded || data.pending_reload) {
          govForceReloadBtn.classList.remove("hidden");
        } else {
          govForceReloadBtn.classList.add("hidden");
        }
      }

      if (govClearErrorBtn) {
        if (st === "ERROR") {
          govClearErrorBtn.classList.remove("hidden");
        } else {
          govClearErrorBtn.classList.add("hidden");
        }
      }

      // Update Telemetry Metrics & Visualizer Progress Bars
      const m = data.metrics || {};
      const gpuPct = Math.round(m.gpu_util_percent || 0);
      const vramUsedGb = m.vram_used_mb ? (m.vram_used_mb / 1024).toFixed(1) : "0.0";
      const vramTotalGb = m.vram_total_mb ? (m.vram_total_mb / 1024).toFixed(1) : "8.0";
      const vramPct = m.vram_util_percent || (m.vram_total_mb ? Math.round((m.vram_used_mb / m.vram_total_mb) * 100) : 0);
      const cpuPct = Math.round(m.cpu_percent || 0);
      const ramPct = Math.round(m.ram_percent || 0);

      // Tooltip values
      if (govGpuVal) govGpuVal.textContent = m.gpu_available ? `${gpuPct}%` : "N/A";
      if (govVramVal) govVramVal.textContent = `${vramUsedGb} GB`;
      if (govCpuVal) govCpuVal.textContent = `${cpuPct}%`;
      if (govRamVal) govRamVal.textContent = `${ramPct}%`;

      // Command Panel Visualizer Meters
      if (govMeterGpuVal) govMeterGpuVal.textContent = `${gpuPct}%`;
      if (govMeterGpuFill) govMeterGpuFill.style.width = `${Math.min(100, Math.max(0, gpuPct))}%`;

      if (govMeterVramVal) govMeterVramVal.textContent = `${vramUsedGb} / ${vramTotalGb} GB (${vramPct}%)`;
      if (govMeterVramFill) govMeterVramFill.style.width = `${Math.min(100, Math.max(0, vramPct))}%`;

      if (govMeterCpuVal) govMeterCpuVal.textContent = `${cpuPct}%`;
      if (govMeterCpuFill) govMeterCpuFill.style.width = `${Math.min(100, Math.max(0, cpuPct))}%`;

      if (govMeterRamVal) govMeterRamVal.textContent = `${ramPct}%`;
      if (govMeterRamFill) govMeterRamFill.style.width = `${Math.min(100, Math.max(0, ramPct))}%`;

      if (governorWidgetContainer && governorWidgetContainer.classList.contains("open")) {
        fetchGovernorHistory();
      }

    } else {
      setDisconnectedUI();
    }
  } catch {
    setDisconnectedUI();
  }
}

function setDisconnectedUI() {
  if (statusDot) statusDot.className = "status-dot";
  if (statusText) statusText.textContent = "Offline";
  if (governorPill) {
    governorPill.className = "governor-pill governor-pill--disconnected";
    if (governorPillLabel) governorPillLabel.textContent = "Governor: offline";
  }
  if (panelStatusTag) {
    panelStatusTag.textContent = "OFFLINE";
    panelStatusTag.className = "gov-panel__status-tag tag-paused";
  }
}

async function fetchGovernorHistory() {
  if (!govHistoryList) return;
  try {
    const res = await fetch(`${API_BASE}/governor/history?limit=10`);
    if (!res.ok) return;
    const events = await res.json();
    if (!Array.isArray(events) || events.length === 0) {
      govHistoryList.innerHTML = '<div class="gov-history-empty">No transition events recorded.</div>';
      return;
    }

    const now = Date.now() / 1000;
    govHistoryList.innerHTML = events.map(e => {
      const diff = Math.max(0, Math.round(now - e.timestamp));
      let timeStr = "just now";
      if (diff >= 60) {
        timeStr = `${Math.floor(diff / 60)}m ago`;
      } else if (diff > 0) {
        timeStr = `${diff}s ago`;
      }

      const toSt = (e.to_status || "IDLE").toLowerCase();
      const reasonsStr = Array.isArray(e.raw_reasons) && e.raw_reasons.length > 0 
        ? e.raw_reasons.join("; ") 
        : "automatic transition";

      return `
        <div class="gov-history-item hist-${toSt}">
          <div class="gov-hist-header">
            <span>${e.from_status || 'IDLE'} → ${e.to_status || 'IDLE'}</span>
            <span class="gov-hist-time">${timeStr}</span>
          </div>
          <div class="gov-hist-reasons" title="${reasonsStr}">${escapeHtml(reasonsStr)}</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Error fetching governor history:", err);
  }
}



