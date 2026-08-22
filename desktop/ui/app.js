const API_BASE = window.location.origin && window.location.origin.startsWith("http") ? window.location.origin : "http://127.0.0.1:8000";


// State
let activeSessionId = "session_" + Math.random().toString(36).substring(2, 9);
let routingMode = "auto";
let currentMode = "WORKSPACE";
let isConversationStarted = false;
let isProcessing = false;
let isRecording = false;
let isVoiceReplyEnabled = true;
let speechRecognition = null;
let mediaRecorder = null;
let audioChunks = [];
let pendingActionIds = [];

// DOM Elements
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");
const modelSelect = document.getElementById("modelSelect");
const modeToggle = document.getElementById("modeToggle");
const modePill = document.getElementById("modePill");

// Mode & Sidebar Elements
const modeWorkspaceBtn = document.getElementById("modeWorkspaceBtn");
const modeSystemBtn = document.getElementById("modeSystemBtn");
const activeProjectIndicator = document.getElementById("activeProjectIndicator");
const activeProjectName = document.getElementById("active-project-name");
const sessionGroupHeader = document.getElementById("sessionGroupHeader");

// Top Nav Elements
const activeModelName = document.getElementById("activeModelName");
const activeTierBadge = document.getElementById("activeTierBadge");
const governorPill = document.getElementById("governorPill");
const governorPillLabel = document.getElementById("governor-pill__label");
const govGpuVal = document.getElementById("govGpuVal");
const govVramVal = document.getElementById("govVramVal");
const govCpuVal = document.getElementById("govCpuVal");
const govRamVal = document.getElementById("govRamVal");

// Chat Viewport Elements
const newChatBtn = document.getElementById("newChatBtn");
const sessionsList = document.getElementById("sessionsList");
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
const skillReviewBtn = document.getElementById("skillReviewBtn");
const skillDiagBtn = document.getElementById("skillDiagBtn");
const unloadModelBtn = document.getElementById("unloadModelBtn");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  initUI();
  initVoice();
  initTelemetry();
  updateModelTierBadge();
  setChatMode(currentMode, false);
});

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

    // Auto focus
    setTimeout(() => promptInput.focus(), 150);
  }

  // Send button
  if (sendBtn) {
    sendBtn.addEventListener("click", () => handleSubmit());
  }

  // New Chat
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => startNewSession());
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
    voiceToggleBtn.addEventListener("click", () => {
      isVoiceReplyEnabled = !isVoiceReplyEnabled;
      const textEl = voiceToggleBtn.querySelector(".voice-text");
      if (isVoiceReplyEnabled) {
        voiceToggleBtn.classList.add("active");
        if (textEl) textEl.textContent = "Voice: ON";
      } else {
        voiceToggleBtn.classList.remove("active");
        if (textEl) textEl.textContent = "Voice: OFF";
        if (window.speechSynthesis) window.speechSynthesis.cancel();
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
        if (label) label.textContent = "VRAM Cleared! ✓";
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

  // Quick Skills
  if (skillReviewBtn) {
    skillReviewBtn.addEventListener("click", () => {
      if (promptInput) promptInput.value = "Please review the code in backend/app/main.py for quality and security.";
      handleSubmit();
    });
  }
  if (skillDiagBtn) {
    skillDiagBtn.addEventListener("click", () => {
      if (promptInput) promptInput.value = "Check system diagnostics, disk usage, and hardware telemetry.";
      handleSubmit();
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

// --- Submit Query Handler ---
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

  if (loadingBubble) loadingBubble.style.display = "flex";
  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;

  const selectedModel = modelSelect ? modelSelect.value : "hermes3:8b";
  const isHeavy = selectedModel === "heavy";

  const payload = {
    message: query || "Approved action execution.",
    session_id: activeSessionId,
    model: isHeavy ? null : selectedModel,
    mode: isHeavy ? "heavy" : routingMode,
    chat_mode: currentMode,
    approved_action_ids: approvedTokens
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000); // 180s safety timeout for deep reasoning

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    if (loadingBubble) loadingBubble.style.display = "none";

    if (response.status === 429) {
      const err = await response.json();
      appendAssistantMessage(`⚠️ **Resource Governor Throttled**: ${err.detail || "System under high load."}`);
      return;
    }

    if (!response.ok) {
      const err = await response.text();
      appendAssistantMessage(`❌ **Error**: ${err}`);
      return;
    }

    const data = await response.json();

    if (data.status === "confirmation_required") {
      showConfirmationPrompt(data);
      if (isVoiceReplyEnabled) {
        speakText("Confirmation required before executing the requested system action.");
      }
    } else {
      appendAssistantMessage(data.response, data.tools_used, data.active_skills, data.model);
      if (isVoiceReplyEnabled) {
        speakText(data.response);
      }
    }

  } catch (err) {
    clearTimeout(timeoutId);
    if (loadingBubble) loadingBubble.style.display = "none";
    if (err.name === "AbortError") {
      appendAssistantMessage(`⏱️ **Timeout**: Jarvis took too long to respond. The system may be busy.`);
    } else {
      appendAssistantMessage(`❌ **Connection Error**: Could not reach backend API at ${API_BASE}. Make sure Jarvis backend is running.`);
    }
  } finally {
    isProcessing = false;
    if (sendBtn) sendBtn.style.opacity = "1";
    if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
    if (promptInput) promptInput.focus();
  }
}

// --- Mode & Model Controls ---
function setChatMode(mode, fromUserClick = false) {
  if (isConversationStarted && fromUserClick) {
    // Mode is locked for active conversation
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
    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Workspace mode — writes stay inside this folder";
    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "block";
    if (sessionGroupHeader) sessionGroupHeader.textContent = "Workspace Chats";
  } else {
    if (modeSystemBtn) modeSystemBtn.classList.add("mode-toggle__option--active");
    if (modeWorkspaceBtn) modeWorkspaceBtn.classList.remove("mode-toggle__option--active");
    if (activeProjectIndicator) activeProjectIndicator.style.display = "none";
    if (emptyStateTitle) emptyStateTitle.textContent = "System mode";
    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Full PC access — confirmation required outside safe paths";
    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "none";
    if (sessionGroupHeader) sessionGroupHeader.textContent = "System Chats";
  }
}

function updateModelTierBadge() {
  if (!modelSelect || !activeTierBadge) return;

  const val = modelSelect.value;
  if (val === "qwen2.5:0.5b") {
    if (activeModelName) activeModelName.textContent = "Qwen 2.5 0.5B";
    activeTierBadge.className = "tier-badge tier-badge--1";
    activeTierBadge.textContent = "Tier 1 · fast";
  } else if (val === "heavy") {
    if (activeModelName) activeModelName.textContent = "Cloud LLM";
    activeTierBadge.className = "tier-badge tier-badge--3";
    activeTierBadge.textContent = "Tier 3 · cloud";
  } else {
    // Local Tier 2 flagship models
    const nameMap = {
      "prism-ml/bonsai-27b": "Bonsai 27B",
      "bonsai-27b": "Bonsai 27B",
      "hermes3:8b": "Hermes 3 8B",
      "llama3.1:8b": "Llama 3.1 8B",
      "llama3.2:3b": "Llama 3.2 3B",
      "phi3.5:3.8b": "Phi 3.5 3.8B"
    };
    if (activeModelName) activeModelName.textContent = nameMap[val] || val;
    activeTierBadge.className = "tier-badge tier-badge--2";
    activeTierBadge.textContent = "Tier 2 · local";
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

  if (sessionsList) {
    const item = document.createElement("div");
    item.className = "session-item active";
    item.innerHTML = `<span class="session-icon">💬</span><span class="session-name">${currentMode === "WORKSPACE" ? "📁" : "💻"} Chat ${activeSessionId.substring(8)}</span>`;
    
    document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
    sessionsList.prepend(item);

    item.addEventListener("click", () => {
      document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
      item.classList.add("active");
    });
  }

  if (promptInput) promptInput.focus();
}

// --- Message Rendering ---

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
  bubble.innerHTML = formatMarkdownText(text);

  const actionsBar = document.createElement("div");
  actionsBar.style.display = "flex";
  actionsBar.style.alignItems = "center";
  actionsBar.style.flexWrap = "wrap";
  actionsBar.style.gap = "6px";
  actionsBar.style.marginTop = "6px";

  if (activeSkills && activeSkills.length > 0) {
    const tag = document.createElement("div");
    tag.className = "tool-badge";
    tag.textContent = `🎯 Skill: ${activeSkills.join(", ")}`;
    actionsBar.appendChild(tag);
  }

  if (toolsUsed && toolsUsed.length > 0) {
    toolsUsed.forEach(t => {
      const tag = document.createElement("div");
      tag.className = "tool-badge";
      tag.textContent = `⚡ Executed: ${t.tool}`;
      actionsBar.appendChild(tag);
    });
  }

  // Read Aloud button
  const readBtn = document.createElement("button");
  readBtn.className = "read-aloud-btn";
  readBtn.innerHTML = "🔊 Read Aloud";
  readBtn.addEventListener("click", () => speakText(text));
  actionsBar.appendChild(readBtn);

  bubble.appendChild(actionsBar);
  row.appendChild(bubble);
  messagesContainer.appendChild(row);
  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
}

function formatMarkdownText(text) {
  if (!text) return "";
  let formatted = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks
  formatted = formatted.replace(/```([\w]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre style="background:#07090e; padding:12px; border-radius:8px; margin:8px 0; overflow-x:auto; font-family:var(--font-mono); font-size:13px;"><code>${code}</code></pre>`;
  });

  // Inline code
  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:#07090e; padding:2px 6px; border-radius:4px; font-family:var(--font-mono); font-size:12.5px;">$1</code>');
  // Bold
  formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Line breaks
  formatted = formatted.replace(/\n/g, '<br>');

  return formatted;
}

// --- Safety Confirmation UI ---
function showConfirmationPrompt(data) {
  pendingActionIds = (data.pending_confirmations || []).map(p => p.action_id);
  
  const cardsHtml = (data.pending_confirmations || []).map(p => {
    const isHigh = p.risk_tier === "HIGH_RISK";
    const badgeClass = isHigh ? "conf-risk-badge high" : "conf-risk-badge confirm";
    const toolIcon = p.tool.includes("command") ? "⚡" : p.tool.includes("write") ? "📝" : p.tool.includes("delete") ? "🗑️" : "🔧";
    
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

    const reasonHtml = p.reason ? `<div class="conf-reason-text">ℹ️ ${escapeHtml(p.reason)}</div>` : "";

    return `
      <div class="conf-action-card">
        <div class="conf-action-header">
          <span class="conf-tool-name">${toolIcon} ${escapeHtml(p.tool)}</span>
          <span class="${badgeClass}">${escapeHtml(p.risk_tier)}</span>
        </div>
        ${payloadHtml}
        ${reasonHtml}
      </div>
    `;
  }).join("");

  if (confDetailsText) {
    confDetailsText.innerHTML = `
      <div>Jarvis wants to execute the following operation(s) on your system:</div>
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
    .replace(/[•⚡🎯📝⚠️📊🔍💬✓]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function speakText(text) {
  const clean = sanitizeForSpeech(text);
  if (!clean) return;

  // Stop any currently playing audio
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }

  // 1. Try Ultra-Realistic Studio Neural Speech via Jarvis Backend (en-GB-RyanNeural)
  try {
    const res = await fetch(`${API_BASE}/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: clean, voice: "en-GB-RyanNeural" })
    });

    if (res.ok) {
      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);
      currentAudio = new Audio(audioUrl);
      currentAudio.play();
      return;
    }
  } catch (err) {
    console.debug("Neural TTS fallback to browser TTS:", err);
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

  // 1. Start live browser speech preview if available
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

  // 2. Start robust MediaRecorder stream for backend Whisper
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
      if (promptInput) promptInput.placeholder = "Ask Jarvis anything, or use / for skills...";
      stream.getTracks().forEach(track => track.stop());

      // If live Web Speech got text, use it; otherwise send recorded audio to local Whisper
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
    if (promptInput) promptInput.placeholder = "Ask Jarvis anything, or use / for skills...";
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


// --- Telemetry Poller ---
function initTelemetry() {
  setInterval(pollGovernor, 2500);
  pollGovernor();
}

async function pollGovernor() {
  try {
    const res = await fetch(`${API_BASE}/governor/status`);
    if (res.ok) {
      const data = await res.json();
      
      // Update sidebar status badge
      if (statusDot) statusDot.className = data.throttled ? "status-dot throttled" : "status-dot connected";
      if (statusText) statusText.textContent = data.throttled ? "Throttled (Load)" : "Jarvis Ready";

      // Update top bar Governor Pill state (4 distinct states)
      if (governorPill) {
        if (data.model_unloaded) {
          governorPill.className = "governor-pill governor-pill--paused";
          if (governorPillLabel) governorPillLabel.textContent = "Governor: paused";
        } else if (data.throttled) {
          governorPill.className = "governor-pill governor-pill--throttled";
          if (governorPillLabel) governorPillLabel.textContent = "Governor: high load";
        } else {
          governorPill.className = "governor-pill governor-pill--normal";
          if (governorPillLabel) governorPillLabel.textContent = "Governor: normal";
        }
      }

      // Update Hover Tooltip Telemetry Metrics
      const m = data.metrics || {};
      if (govGpuVal) govGpuVal.textContent = m.gpu_available ? `${Math.round(m.gpu_util_percent || 0)}%` : "N/A";
      if (govVramVal) govVramVal.textContent = m.vram_used_mb ? `${(m.vram_used_mb / 1024).toFixed(1)} GB` : "N/A";
      if (govCpuVal) govCpuVal.textContent = `${Math.round(m.cpu_percent || 0)}%`;
      if (govRamVal) govRamVal.textContent = m.ram_percent ? `${Math.round(m.ram_percent)}%` : "N/A";

    } else {
      if (statusDot) statusDot.className = "status-dot";
      if (statusText) statusText.textContent = "Offline";
      if (governorPill) {
        governorPill.className = "governor-pill governor-pill--disconnected";
        if (governorPillLabel) governorPillLabel.textContent = "Governor: offline";
      }
    }
  } catch {
    if (statusDot) statusDot.className = "status-dot";
    if (statusText) statusText.textContent = "Offline";
    if (governorPill) {
      governorPill.className = "governor-pill governor-pill--disconnected";
      if (governorPillLabel) governorPillLabel.textContent = "Governor: offline";
    }
  }
}


