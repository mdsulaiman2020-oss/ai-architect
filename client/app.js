const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const stopButton = document.querySelector("#stopButton");
const sessionLabel = document.querySelector("#sessionLabel");
const sessionsListEl = document.querySelector("#sessionsList");
const newChatButton = document.querySelector("#newChatButton");
const API_BASE_URL = "http://127.0.0.1:8000";

let abortController = null;

let sessionId = getSessionId();
sessionLabel.textContent = `Session ${sessionId.slice(0, 8)}`;

function getSessionId() {
  const existing = localStorage.getItem("ai-runtime-session-id");
  if (existing && existing !== "null" && existing !== "undefined" && existing.trim() !== "") {
    return existing;
  }

  const created = crypto.randomUUID();
  localStorage.setItem("ai-runtime-session-id", created);
  return created;
}

async function loadSessions() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions`);
    if (!response.ok) throw new Error("Failed to fetch sessions");
    const sessions = await response.json();

    sessionsListEl.innerHTML = "";

    if (sessions.length === 0) {
      sessionsListEl.innerHTML = `<div class="no-sessions">No active chats</div>`;
      return;
    }

    sessions.forEach((s) => {
      const itemEl = document.createElement("div");
      itemEl.className = `session-item ${s.session_id === sessionId ? "active" : ""}`;
      itemEl.dataset.sessionId = s.session_id;

      const titleEl = document.createElement("span");
      titleEl.className = "session-title";
      titleEl.textContent = s.title || "New Chat";

      itemEl.appendChild(titleEl);

      itemEl.addEventListener("click", () => switchSession(s.session_id));
      sessionsListEl.appendChild(itemEl);
    });
  } catch (err) {
    console.error("Error loading sessions:", err);
  }
}

async function switchSession(id) {
  if (!id || id === "null" || id === "undefined" || id.trim() === "") return;
  if (id === sessionId) return;

  sessionId = id;
  localStorage.setItem("ai-runtime-session-id", id);
  sessionLabel.textContent = `Session ${sessionId.slice(0, 8)}`;

  // Highlight active session
  document.querySelectorAll(".session-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.sessionId === sessionId);
  });

  messagesEl.innerHTML =
    '<div class="loading-history">Loading history...</div>';

  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`);
    if (!response.ok) throw new Error("Failed to load session history");
    const data = await response.json();

    messagesEl.innerHTML = "";

    const messages = data.messages || [];
    const chatMessages = messages.filter(
      (msg) => msg.role === "user" || msg.role === "assistant",
    );
    if (chatMessages.length === 0) {
      addMessage(
        "assistant",
        "Send a message to test the agent with session history.",
      );
    } else {
      chatMessages.forEach((msg) => {
        addMessage(msg.role, msg.content, msg.metadata);
      });
    }
  } catch (err) {
    messagesEl.innerHTML = "";
    addMessage("error", "Failed to load session history: " + err.message);
  }
}

function renderMarkdown(content) {
  if (!content) return "";
  if (content === "Thinking...") {
    return `<span class="thinking-indicator">Thinking<span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span></span>`;
  }
  if (typeof window.marked !== "undefined") {
    try {
      return window.marked.parse(content, { breaks: true, gfm: true });
    } catch (e) {
      console.error("Marked parse error:", e);
    }
  }

  // Fallback safe markdown parser
  let escaped = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks
  escaped = escaped.replace(/```([\s\S]*?)```/g, (_, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });

  // Inline code
  escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold (**text** or __text__)
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/__(.*?)__/g, "<strong>$1</strong>");

  // Italic (*text* or _text_)
  escaped = escaped.replace(/\*(.*?)\*/g, "<em>$1</em>");
  escaped = escaped.replace(/_(.*?)_/g, "<em>$1</em>");

  // Line breaks
  escaped = escaped.replace(/\n/g, "<br>");

  return escaped;
}

function addCopyButtons(container) {
  const pres = container.querySelectorAll("pre");
  pres.forEach((pre) => {
    if (pre.querySelector(".copy-code-btn")) return;
    const button = document.createElement("button");
    button.className = "copy-code-btn";
    button.type = "button";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      const codeEl = pre.querySelector("code");
      const textToCopy = codeEl ? codeEl.innerText : pre.innerText;
      try {
        await navigator.clipboard.writeText(textToCopy);
        button.textContent = "Copied!";
        setTimeout(() => {
          button.textContent = "Copy";
        }, 2000);
      } catch (err) {
        button.textContent = "Error";
      }
    });
    pre.appendChild(button);
  });
}

function createMessageActions(messageEl, contentEl) {
  const actionsEl = document.createElement("div");
  actionsEl.className = "message-actions";

  let msgId = messageEl.dataset.messageId;
  if (!msgId) {
    msgId = "msg-" + crypto.randomUUID();
    messageEl.dataset.messageId = msgId;
  }

  // Copy Full Message button
  const copyBtn = document.createElement("button");
  copyBtn.className = "action-btn copy-msg-btn";
  copyBtn.type = "button";
  copyBtn.title = "Copy response";
  copyBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(contentEl.innerText);
      const span = copyBtn.querySelector("span");
      span.textContent = "Copied!";
      setTimeout(() => {
        span.textContent = "Copy";
      }, 2000);
    } catch (e) {
      console.error("Copy error:", e);
    }
  });

  // Thumbs Up button
  const upBtn = document.createElement("button");
  upBtn.className = "action-btn thumb-up-btn";
  upBtn.type = "button";
  upBtn.title = "Good response";
  upBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>`;

  // Thumbs Down button
  const downBtn = document.createElement("button");
  downBtn.className = "action-btn thumb-down-btn";
  downBtn.type = "button";
  downBtn.title = "Bad response";
  downBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>`;

  async function handleFeedback(rating, targetBtn, otherBtn) {
    if (targetBtn.classList.contains("active")) return;

    targetBtn.classList.add("active");
    otherBtn.classList.remove("active");

    try {
      await postJson("/api/feedback", {
        session_id: sessionId,
        message_id: msgId,
        rating: rating,
        content: contentEl.innerText,
      });
    } catch (err) {
      console.error("Feedback submission error:", err);
    }
  }

  upBtn.addEventListener("click", () => handleFeedback("up", upBtn, downBtn));
  downBtn.addEventListener("click", () =>
    handleFeedback("down", downBtn, upBtn),
  );

  actionsEl.append(copyBtn, upBtn, downBtn);
  return actionsEl;
}

function addMessage(role, content, metadata = null) {
  const messageEl = document.createElement("div");
  messageEl.className = `message ${role}`;

  const contentEl = document.createElement("div");
  contentEl.className = "message-content markdown-body";
  contentEl.innerHTML = renderMarkdown(content);
  addCopyButtons(contentEl);
  messageEl.appendChild(contentEl);

  if (role === "assistant" && content !== "Thinking...") {
    messageEl.appendChild(createMessageActions(messageEl, contentEl));
  }

  if (metadata) {
    messageEl.appendChild(createMetadataButton(metadata));
  }

  messagesEl.appendChild(messageEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return messageEl;
}

function createMetadataButton(metadata) {
  const buttonEl = document.createElement("button");
  buttonEl.className = "metadata-button";
  buttonEl.type = "button";
  buttonEl.setAttribute("aria-label", "Response metadata");
  buttonEl.textContent = "i";

  const tooltipEl = document.createElement("span");
  tooltipEl.className = "metadata-tooltip";

  const rows = [
    ["Model", metadata.model_name || "-"],
    [
      "Latency",
      metadata.latency_ms ? `${Math.round(metadata.latency_ms)} ms` : "-",
    ],
    ["Prompt tokens", metadata.prompt_tokens ?? "-"],
    ["Output tokens", metadata.candidates_tokens ?? "-"],
    ["Total tokens", metadata.total_tokens ?? "-"],
  ];

  for (const [label, value] of rows) {
    const rowEl = document.createElement("span");
    rowEl.className = "metadata-row";

    const labelEl = document.createElement("span");
    labelEl.className = "metadata-label";
    labelEl.textContent = label;

    const valueEl = document.createElement("span");
    valueEl.className = "metadata-value";
    valueEl.textContent = value;

    rowEl.append(labelEl, valueEl);
    tooltipEl.appendChild(rowEl);
  }

  buttonEl.appendChild(tooltipEl);
  return buttonEl;
}

function updateMessage(messageEl, content, metadata = null) {
  const contentEl = messageEl.querySelector(".message-content");
  contentEl.innerHTML = renderMarkdown(content);
  addCopyButtons(contentEl);

  if (
    messageEl.classList.contains("assistant") &&
    content &&
    content !== "Thinking..."
  ) {
    if (!messageEl.querySelector(".message-actions")) {
      messageEl.appendChild(createMessageActions(messageEl, contentEl));
    }
  }

  const existingMetadata = messageEl.querySelector(".metadata-button");
  if (existingMetadata) {
    existingMetadata.remove();
  }

  if (metadata) {
    messageEl.appendChild(createMetadataButton(metadata));
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setLoading(isLoading, isChat = false) {
  inputEl.disabled = isLoading;

  if (isLoading) {
    if (isChat) {
      sendButton.style.display = "none";
      stopButton.style.display = "flex";
    } else {
      sendButton.disabled = true;
    }
  } else {
    sendButton.disabled = false;
    sendButton.style.display = "flex";
    stopButton.style.display = "none";
  }
}

async function postJson(url, body, signal = null) {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || "Request failed");
  }
  return payload;
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = inputEl.value.trim();
  if (!message) {
    return;
  }

  inputEl.value = "";
  inputEl.style.height = "auto";
  addMessage("user", message);
  const pendingEl = addMessage("assistant", "Thinking...");

  setLoading(true, true);
  abortController = new AbortController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        message,
      }),
      signal: abortController.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Stream request failed");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6);
          if (dataStr === "[DONE]") break;

          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              if (data.text) {
                accumulatedText += data.text;
                updateMessage(pendingEl, accumulatedText);
              }
            } catch (e) {
              console.error("Error parsing SSE chunk:", e);
            }
          }
        }
      }
    }
  } catch (error) {
    if (error.name === "AbortError") {
      updateMessage(pendingEl, "Request cancelled.");
      pendingEl.classList.add("error");
    } else {
      pendingEl.remove();
      addMessage("error", error.message);
    }
  } finally {
    abortController = null;
    setLoading(false);
    loadSessions(); // Update sidebar with first message preview
    inputEl.focus();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${inputEl.scrollHeight}px`;
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

// Stop event and click handler
stopButton.addEventListener("click", () => {
  const stopEvent = new CustomEvent("stop");
  formEl.dispatchEvent(stopEvent);
});

formEl.addEventListener("stop", () => {
  if (abortController) {
    abortController.abort();
  }
});

// New Chat button
newChatButton.addEventListener("click", async () => {
  const newId = crypto.randomUUID();
  await switchSession(newId);
  loadSessions();
});

// Initial Onload setup
async function initializeApp() {
  await loadSessions();

  // Load current session history if it exists
  messagesEl.innerHTML =
    '<div class="loading-history">Loading history...</div>';
  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`);
    if (!response.ok) throw new Error("Failed to load active session");
    const data = await response.json();
    messagesEl.innerHTML = "";

    const messages = data.messages || [];
    const chatMessages = messages.filter(
      (msg) => msg.role === "user" || msg.role === "assistant",
    );
    if (chatMessages.length === 0) {
      addMessage(
        "assistant",
        "Send a message to test the agent with session history.",
      );
    } else {
      chatMessages.forEach((msg) => {
        addMessage(msg.role, msg.content, msg.metadata);
      });
    }
  } catch (err) {
    messagesEl.innerHTML = "";
    addMessage(
      "assistant",
      "Send a message to test the agent with session history.",
    );
  }
}

initializeApp();
