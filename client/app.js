const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const stopButton = document.querySelector("#stopButton");
const resetButton = document.querySelector("#resetButton");
const sessionLabel = document.querySelector("#sessionLabel");
const API_BASE_URL = "http://127.0.0.1:8000";

let abortController = null;

const sessionId = getSessionId();
sessionLabel.textContent = `Session ${sessionId.slice(0, 8)}`;

function getSessionId() {
  const existing = localStorage.getItem("ai-runtime-session-id");
  if (existing) {
    return existing;
  }

  const created = crypto.randomUUID();
  localStorage.setItem("ai-runtime-session-id", created);
  return created;
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

function addMessage(role, content, metadata = null) {
  const messageEl = document.createElement("div");
  messageEl.className = `message ${role}`;

  const contentEl = document.createElement("div");
  contentEl.className = "message-content markdown-body";
  contentEl.innerHTML = renderMarkdown(content);
  addCopyButtons(contentEl);
  messageEl.appendChild(contentEl);

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
    ["Latency", metadata.latency_ms ? `${Math.round(metadata.latency_ms)} ms` : "-"],
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
  resetButton.disabled = isLoading;

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
    const decoder = new TextDecoder('utf-8');
    let accumulatedText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') break;
          
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
    inputEl.focus();
  }
});

resetButton.addEventListener("click", async () => {
  setLoading(true);
  try {
    await postJson("/api/reset", { session_id: sessionId });
    messagesEl.innerHTML = "";
    addMessage("assistant", "Session reset. Send a message to start again.");
  } catch (error) {
    addMessage("error", error.message);
  } finally {
    setLoading(false);
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

addMessage("assistant", "Send a message to test the agent with session history.");
