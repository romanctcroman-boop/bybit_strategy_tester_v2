/**
 * 📄 Streaming Chat Page JavaScript
 *
 * Page-specific scripts for streaming_chat.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from "../api.js";
import {
  formatNumber,
  formatCurrency,
  formatDate,
  debounce,
} from "../utils.js";

class StreamingChat {
  constructor() {
    this.ws = null;
    this.clientId = "client_" + Date.now();
    this.isStreaming = false;
    this.currentReasoning = "";
    this.currentContent = "";
    this.startTime = 0;
    this.fallbackMode = false;
    this.connectionAttempts = 0;
    this.maxConnectionAttempts = 3;

    this.chatContainer = document.getElementById("chat-container");
    this.statusEl = document.getElementById("status");
    this.promptInput = document.getElementById("prompt-input");
    this.sendBtn = document.getElementById("send-btn");
    this.agentSelect = document.getElementById("agent-select");
    this.thinkingMode = document.getElementById("thinking-mode");

    this.reasoningCharsEl = document.getElementById("reasoning-chars");
    this.contentCharsEl = document.getElementById("content-chars");
    this.latencyEl = document.getElementById("latency");

    this.bindEvents();
  }

  bindEvents() {
    this.sendBtn.addEventListener("click", () => this.sendMessage());
    this.promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
  }

  connect() {
    // Use same port as page, or default to 8000
    const wsPort = window.location.port || "8000";
    const wsUrl = `ws://${window.location.hostname}:${wsPort}/ws/v1/stream/agent/${this.clientId}`;

    this.updateStatus("Connecting...", "");
    console.log("Connecting to WebSocket:", wsUrl);

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.updateStatus("Connected", "connected");
      this.connectionAttempts = 0;
      this.fallbackMode = false;
    };

    this.ws.onclose = () => {
      this.connectionAttempts++;
      if (this.connectionAttempts >= this.maxConnectionAttempts) {
        this.enableFallbackMode();
      } else {
        this.updateStatus("Disconnected - Reconnecting...", "error");
        setTimeout(() => this.connect(), 3000);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      this.updateStatus("Connection error", "error");
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
  }

  enableFallbackMode() {
    this.fallbackMode = true;
    this.updateStatus("📴 Offline Mode (AI unavailable)", "offline");
    this.addSystemMessage(
      "⚠️ Backend server is unavailable. Running in offline demo mode. You can still explore the interface, but AI responses are simulated.",
    );
  }

  addSystemMessage(text) {
    const div = document.createElement("div");
    div.className = "message system";
    div.style.background = "rgba(255, 193, 7, 0.1)";
    div.style.borderLeft = "3px solid #ffc107";
    div.style.padding = "12px 16px";
    div.style.marginBottom = "12px";
    div.style.borderRadius = "8px";
    div.innerHTML = text;
    this.chatContainer.appendChild(div);
    this.scrollToBottom();
  }

  simulateFallbackResponse(prompt) {
    // Simulate AI response in fallback mode
    this.startTime = Date.now();
    this.currentReasoning = "";
    this.currentContent = "";

    this.addMessage(prompt, "user");
    this.reasoningEl = this.createReasoningBlock();
    this.contentEl = this.createContentBlock();

    // Simulate reasoning
    const reasoning = `Analyzing request: "${prompt.substring(0, 50)}..."
• Checking market conditions
• Evaluating risk parameters
• Processing strategy constraints`;

    // Simulate content response
    const responses = {
      strategy: `📊 **Strategy Suggestion (Demo)**

Based on your request, here's a basic framework:

1. **Entry Conditions**: RSI < 30 (oversold) + Price above 20 EMA
2. **Exit Conditions**: RSI > 70 (overbought) OR -2% stop loss
3. **Position Size**: 2% of capital per trade
4. **Timeframe**: 4H recommended

⚠️ *This is a demo response. Connect to the AI server for real analysis.*`,

      analysis: `📈 **Market Analysis (Demo)**

Current market overview:
• Trend: Ranging market with slight bullish bias
• Support: Previous swing low
• Resistance: 200-day moving average

⚠️ *This is a demo response. Connect to the AI server for real analysis.*`,

      default: `💬 **Response (Demo Mode)**

I received your message: "${prompt.substring(0, 100)}${prompt.length > 100 ? "..." : ""}"

I'm currently running in offline demo mode because the AI server is unavailable. 

To get real AI responses:
1. Start the backend server
2. Refresh this page
3. Wait for connection

⚠️ *This is a simulated response.*`,
    };

    let content;
    if (
      prompt.toLowerCase().includes("strategy") ||
      prompt.toLowerCase().includes("trading")
    ) {
      content = responses.strategy;
    } else if (
      prompt.toLowerCase().includes("analysis") ||
      prompt.toLowerCase().includes("market")
    ) {
      content = responses.analysis;
    } else {
      content = responses.default;
    }

    // Animate the response
    let reasoningIndex = 0;
    let contentIndex = 0;

    const reasoningInterval = setInterval(() => {
      if (reasoningIndex < reasoning.length) {
        this.currentReasoning += reasoning[reasoningIndex];
        this.reasoningEl.querySelector(".reasoning-content").textContent =
          this.currentReasoning;
        this.reasoningCharsEl.textContent = this.currentReasoning.length;
        reasoningIndex++;
      } else {
        clearInterval(reasoningInterval);

        // Start content after reasoning
        const contentInterval = setInterval(() => {
          if (contentIndex < content.length) {
            this.currentContent += content[contentIndex];
            this.contentEl.querySelector(".content-text").innerHTML =
              this.formatMarkdown(this.currentContent);
            this.contentCharsEl.textContent = this.currentContent.length;
            contentIndex++;
            this.scrollToBottom();
          } else {
            clearInterval(contentInterval);
            const latency = Date.now() - this.startTime;
            this.latencyEl.textContent = latency;
            this.sendBtn.disabled = false;
            this.isStreaming = false;
          }
        }, 10);
      }
    }, 20);

    this.sendBtn.disabled = true;
    this.isStreaming = true;
  }

  formatMarkdown(text) {
    // Simple markdown formatting
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br>");
  }

  updateStatus(text, className) {
    this.statusEl.textContent = text;
    this.statusEl.className = "status " + className;
  }

  sendMessage() {
    const prompt = this.promptInput.value.trim();
    if (!prompt) return;

    // Use fallback mode if enabled
    if (this.fallbackMode) {
      this.promptInput.value = "";
      this.simulateFallbackResponse(prompt);
      return;
    }

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect();
      setTimeout(() => this.sendMessage(), 1000);
      return;
    }

    this.startTime = Date.now();
    this.currentReasoning = "";
    this.currentContent = "";

    // Add user message
    this.addMessage(prompt, "user");

    // Create response containers
    this.reasoningEl = this.createReasoningBlock();
    this.contentEl = this.createContentBlock();

    // Send request
    this.ws.send(
      JSON.stringify({
        action: "query",
        agent: this.agentSelect.value,
        prompt: prompt,
        thinking_mode: this.thinkingMode.checked,
      }),
    );

    this.promptInput.value = "";
    this.sendBtn.disabled = true;
    this.isStreaming = true;
  }

  handleMessage(data) {
    switch (data.type) {
      case "start":
        console.log("Stream started:", data.agent);
        break;

      case "reasoning":
        this.currentReasoning += data.content;
        this.reasoningEl.querySelector(".reasoning-content").textContent =
          this.currentReasoning;
        this.reasoningCharsEl.textContent = this.currentReasoning.length;
        this.scrollToBottom();
        break;

      case "content":
        this.currentContent += data.content;
        this.contentEl.querySelector(".content-text").textContent =
          this.currentContent;
        this.contentCharsEl.textContent = this.currentContent.length;
        this.scrollToBottom();
        break;

      case "complete":
        const latency = Date.now() - this.startTime;
        this.latencyEl.textContent = latency;
        this.sendBtn.disabled = false;
        this.isStreaming = false;
        console.log("Stream complete:", data);
        break;

      case "error":
        this.addError(data.error);
        this.sendBtn.disabled = false;
        this.isStreaming = false;
        break;

      case "pong":
        console.log("Pong received");
        break;
    }
  }

  addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    this.chatContainer.appendChild(div);
    this.scrollToBottom();
  }

  createReasoningBlock() {
    const div = document.createElement("div");
    div.className = "reasoning-block";
    div.innerHTML = `
                    <div class="reasoning-header">
                        💭 Chain-of-Thought Reasoning
                        <div class="typing-indicator">
                            <span></span><span></span><span></span>
                        </div>
                    </div>
                    <div class="reasoning-content"></div>
                `;
    this.chatContainer.appendChild(div);
    return div;
  }

  createContentBlock() {
    const div = document.createElement("div");
    div.className = "content-block";
    div.innerHTML = `
                    <div class="content-header">
                        📝 Response
                    </div>
                    <div class="content-text"></div>
                `;
    this.chatContainer.appendChild(div);
    return div;
  }

  addError(message) {
    const div = document.createElement("div");
    div.className = "message error";
    div.style.background = "rgba(255, 107, 107, 0.1)";
    div.style.borderLeftColor = "var(--error-color)";
    div.textContent = "❌ Error: " + message;
    this.chatContainer.appendChild(div);
    this.scrollToBottom();
  }

  scrollToBottom() {
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }
}

// Initialize
const chat = new StreamingChat();
chat.connect();

// Tab switching
let currentTab = "strategy";

function switchTab(tabName) {
  currentTab = tabName;

  // Update tab buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });

  // Update tab content
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.id === `tab-${tabName}`);
  });

  // Update agent selection based on tab
  const agentSelect = document.getElementById("agent-select");
  if (tabName === "research") {
    agentSelect.value = "perplexity";
  } else {
    agentSelect.value = "deepseek";
  }
}

// Quick prompts
function usePrompt(prompt) {
  document.getElementById("prompt-input").value = prompt;
  document.getElementById("prompt-input").focus();
}

// History panel
let historyOpen = false;
let conversationHistory = JSON.parse(
  localStorage.getItem("ai_studio_history") || "[]",
);
const serverSyncEnabled = true;
const API_BASE = "/api/v1";

// Server sync functions
async function syncHistoryToServer() {
  if (!serverSyncEnabled || conversationHistory.length === 0) return;

  try {
    const response = await fetch(`${API_BASE}/chat/history/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversations: conversationHistory.map((c) => ({
          prompt: c.prompt,
          response: c.response || "",
          reasoning: c.reasoning || null,
          tab: c.tab,
          agent: c.agent || "deepseek",
          timestamp: c.timestamp,
        })),
        clear_existing: true,
      }),
    });

    if (response.ok) {
      const result = await response.json();
      console.log(`✅ Synced ${result.synced} conversations to server`);
    }
  } catch (e) {
    console.warn("Server sync failed, using localStorage:", e);
  }
}

async function loadHistoryFromServer() {
  if (!serverSyncEnabled) return;

  try {
    const response = await fetch(`${API_BASE}/chat/history?per_page=50`);
    if (response.ok) {
      const data = await response.json();
      if (data.conversations && data.conversations.length > 0) {
        conversationHistory = data.conversations.map((c) => ({
          id: c.id,
          prompt: c.prompt,
          response: c.response,
          reasoning: c.reasoning,
          tab: c.tab,
          agent: c.agent,
          timestamp: new Date(c.created_at).getTime(),
          starred: c.starred,
        }));
        localStorage.setItem(
          "ai_studio_history",
          JSON.stringify(conversationHistory),
        );
        console.log(`✅ Loaded ${data.total} conversations from server`);
      }
    }
  } catch (e) {
    console.warn("Failed to load from server, using localStorage:", e);
  }
}

async function saveConversationToServer(
  prompt,
  response,
  tab,
  reasoning = null,
) {
  if (!serverSyncEnabled) return;

  try {
    const agentSelect = document.getElementById("agent-select");
    const agent = agentSelect ? agentSelect.value : "deepseek";

    const res = await fetch(`${API_BASE}/chat/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        response,
        reasoning,
        tab,
        agent,
        timestamp: Date.now(),
      }),
    });

    if (res.ok) {
      const data = await res.json();
      return data.id;
    }
  } catch (e) {
    console.warn("Failed to save to server:", e);
  }
  return null;
}

async function deleteFromServer(conversationId) {
  if (!serverSyncEnabled || !conversationId) return;

  try {
    await fetch(`${API_BASE}/chat/history/${conversationId}`, {
      method: "DELETE",
    });
  } catch (e) {
    console.warn("Failed to delete from server:", e);
  }
}

async function toggleStarOnServer(conversationId, starred) {
  if (!serverSyncEnabled || !conversationId) return;

  try {
    await fetch(`${API_BASE}/chat/history/${conversationId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred }),
    });
  } catch (e) {
    console.warn("Failed to update star on server:", e);
  }
}

// Initialize: try to load from server first
loadHistoryFromServer();

function toggleHistory() {
  historyOpen = !historyOpen;
  document
    .getElementById("history-panel")
    .classList.toggle("open", historyOpen);
  if (historyOpen) {
    renderHistory();
  }
}

function renderHistory() {
  const container = document.getElementById("history-list");

  if (conversationHistory.length === 0) {
    container.innerHTML = `
                    <div class="history-empty">
                        <p>No saved conversations</p>
                        <p class="history-empty-sub">Your conversations will appear here</p>
                    </div>
                `;
    return;
  }

  container.innerHTML = conversationHistory
    .slice(-20)
    .reverse()
    .map((item, idx) => {
      const actualIdx = conversationHistory.length - 1 - idx;
      const starIcon = item.starred ? "⭐" : "☆";
      return `
                    <div class="history-item">
                        <div class="history-item-main" onclick="loadConversation(${actualIdx})">
                            <div class="history-item-title">${escapeHtml(item.prompt.substring(0, 50))}...</div>
                            <div class="history-item-meta">${item.tab} • ${item.agent || "deepseek"} • ${new Date(item.timestamp).toLocaleString()}</div>
                        </div>
                        <div class="history-item-actions">
                            <button class="history-btn" onclick="toggleStar(${actualIdx})" title="Star">${starIcon}</button>
                            <button class="history-btn delete" onclick="deleteConversation(${actualIdx})" title="Delete">🗑️</button>
                        </div>
                    </div>
                `;
    })
    .join("");
}

async function toggleStar(index) {
  const item = conversationHistory[index];
  if (item) {
    item.starred = !item.starred;
    localStorage.setItem(
      "ai_studio_history",
      JSON.stringify(conversationHistory),
    );
    await toggleStarOnServer(item.id, item.starred);
    renderHistory();
  }
}

async function deleteConversation(index) {
  if (!confirm("Delete this conversation?")) return;

  const item = conversationHistory[index];
  if (item && item.id) {
    await deleteFromServer(item.id);
  }
  conversationHistory.splice(index, 1);
  localStorage.setItem(
    "ai_studio_history",
    JSON.stringify(conversationHistory),
  );
  renderHistory();
}

async function saveToHistory(prompt, response, tab, reasoning = null) {
  const agentSelect = document.getElementById("agent-select");
  const agent = agentSelect ? agentSelect.value : "deepseek";

  // Save to server first
  const serverId = await saveConversationToServer(
    prompt,
    response,
    tab,
    reasoning,
  );

  conversationHistory.push({
    id: serverId,
    prompt,
    response,
    reasoning,
    tab,
    agent,
    timestamp: Date.now(),
  });

  // Keep only last 50 conversations
  if (conversationHistory.length > 50) {
    conversationHistory.shift();
  }

  localStorage.setItem(
    "ai_studio_history",
    JSON.stringify(conversationHistory),
  );
}

function loadConversation(index) {
  const item = conversationHistory[index];
  if (item) {
    switchTab(item.tab);
    document.getElementById("prompt-input").value = item.prompt;
    toggleHistory();
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Sync button for manual sync
async function manualSync() {
  const syncBtn = document.querySelector(".sync-btn");
  if (syncBtn) {
    syncBtn.disabled = true;
    syncBtn.textContent = "⏳";
  }

  await syncHistoryToServer();
  await loadHistoryFromServer();
  renderHistory();

  if (syncBtn) {
    syncBtn.disabled = false;
    syncBtn.textContent = "🔄";
  }
}

// Export conversation as Markdown
function exportAsMarkdown() {
  const messages = document.querySelectorAll(
    ".message, .reasoning-block, .content-block",
  );
  let markdown = `# AI Studio Conversation\n\nDate: ${new Date().toLocaleString()}\nTab: ${currentTab}\n\n---\n\n`;

  messages.forEach((msg) => {
    if (msg.classList.contains("message") && msg.classList.contains("user")) {
      markdown += `## 👤 User\n\n${msg.textContent}\n\n`;
    } else if (msg.classList.contains("reasoning-block")) {
      const content = msg.querySelector(".reasoning-content");
      if (content && content.textContent) {
        markdown += `## 💭 Reasoning\n\n\`\`\`\n${content.textContent}\n\`\`\`\n\n`;
      }
    } else if (msg.classList.contains("content-block")) {
      const content = msg.querySelector(".content-text");
      if (content && content.textContent) {
        markdown += `## 🤖 Response\n\n${content.textContent}\n\n`;
      }
    }
  });

  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ai-studio-${currentTab}-${Date.now()}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: switchTab, usePrompt, syncHistoryToServer, loadHistoryFromServer, saveConversationToServer

// Attach to window for backwards compatibility
if (typeof window !== "undefined") {
  window.streamingchatPage = {
    // Add public methods here
  };

  // Export functions for HTML onclick handlers
  window.switchTab = switchTab;
  window.usePrompt = usePrompt;
  window.toggleHistory = toggleHistory;
  window.manualSync = manualSync;
}
