const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const resetButton = document.querySelector("#resetButton");
const sessionLabel = document.querySelector("#sessionLabel");
const API_BASE_URL = "http://127.0.0.1:8000";

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

function addMessage(role, content, metadata = null) {
  const messageEl = document.createElement("div");
  messageEl.className = `message ${role}`;

  const contentEl = document.createElement("div");
  contentEl.className = "message-content";
  contentEl.textContent = content;
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
  contentEl.textContent = content;

  const existingMetadata = messageEl.querySelector(".metadata-button");
  if (existingMetadata) {
    existingMetadata.remove();
  }

  if (metadata) {
    messageEl.appendChild(createMetadataButton(metadata));
  }
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  inputEl.disabled = isLoading;
  resetButton.disabled = isLoading;
  sendButton.textContent = isLoading ? "Sending" : "Send";
}

async function postJson(url, body) {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
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

  setLoading(true);
  try {
    const payload = await postJson("/api/chat", {
      session_id: sessionId,
      message,
    });
    updateMessage(pendingEl, payload.reply, payload.metadata);
  } catch (error) {
    pendingEl.remove();
    addMessage("error", error.message);
  } finally {
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

addMessage("assistant", "Send a message to test the agent with session history.");
