const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const stopButton = document.querySelector("#stopButton");

const sessionsListEl = document.querySelector("#sessionsList");
const newChatButton = document.querySelector("#newChatButton");
const API_BASE_URL = "http://127.0.0.1:8000";

let abortController = null;

let sessionId = getSessionId();

function getSessionId() {
  const existing = localStorage.getItem("ai-runtime-session-id");
  if (
    existing &&
    existing !== "null" &&
    existing !== "undefined" &&
    existing.trim() !== ""
  ) {
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

      const evalBtn = document.createElement("button");
      evalBtn.className = "eval-btn";
      evalBtn.title = "Evaluate Session";
      evalBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`;
      evalBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        window.open(`/evaluation.html?session_id=${s.session_id}`, "_blank");
      });
      itemEl.appendChild(evalBtn);

      itemEl.addEventListener("click", () => switchSession(s.session_id));
      sessionsListEl.appendChild(itemEl);
    });
  } catch (err) {
    console.error("Error loading sessions:", err);
  }
}

function renderChatMessages(chatMessages) {
  if (chatMessages.length === 0) {
    /* addMessage(
      "assistant",
      "Send a message to test the agent with session history.",
    ); */
  } else {
    chatMessages.forEach((msg) => {
      addMessage(msg.role, msg.content, msg.metadata);
    });
  }
}

function checkForPendingUI(messages) {
  if (!messages || messages.length === 0) return null;

  const lastMsg = messages[messages.length - 1];
  if (lastMsg && lastMsg.role === "tool_call") {
    return {
      type: "ui",
      component: lastMsg.tool_name,
      tool_call_id: lastMsg.tool_call_id,
      args: lastMsg.args || {},
    };
  }

  return null;
}

async function renderSessionMessagesAndUI(data) {
  messagesEl.innerHTML = "";

  const messages = (data.messages || []).filter((m) => m.role !== "client-ui");
  // Explicitly filter out client-ui and only render user and assistant messages in chat bubbles
  const chatMessages = messages.filter(
    (msg) => msg.role === "user" || msg.role === "assistant",
  );

  renderChatMessages(chatMessages);

  // Handle pending client-side UI forms on reload or switch
  const uiData = checkForPendingUI(messages);
  console.log("uiData", uiData);
  if (uiData) {
    const lastChatMsg = chatMessages[chatMessages.length - 1];
    let assistantMsgEl = null;
    let currentText = "";

    if (!lastChatMsg || lastChatMsg.role === "user") {
      // The pending UI is in response to the user's latest message -> create a fresh assistant bubble below it
      assistantMsgEl = addMessage("assistant", "");
      currentText = "";
    } else {
      // If the last message rendered was already an assistant message, attach the UI to it
      const assistantMessages = messagesEl.querySelectorAll(".message.assistant");
      assistantMsgEl =
        assistantMessages[assistantMessages.length - 1] ||
        addMessage("assistant", "");
      currentText = lastChatMsg.content || "";
    }

    if (uiData.component === "select_course") {
      await renderCourseSelector(uiData, assistantMsgEl, currentText);
    } else if (uiData.component === "run_exam_scheduling") {
      await renderExamScheduleForm(uiData, assistantMsgEl, currentText);
    } else if (uiData.component === "run_exam_rescheduling") {
      await renderExamRescheduleForm(uiData, assistantMsgEl, currentText);
    }
  }
}

async function switchSession(id) {
  if (!id || id === "null" || id === "undefined" || id.trim() === "") return;
  if (id === sessionId) return;

  sessionId = id;
  localStorage.setItem("ai-runtime-session-id", id);

  // Highlight active session
  document.querySelectorAll(".session-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.sessionId === sessionId);
  });

  // Close sidebar on mobile after selecting a session
  const sb = document.querySelector(".sidebar");
  const overlay = document.querySelector("#sidebarOverlay");
  if (sb && overlay) {
    sb.classList.remove("open");
    overlay.classList.remove("open");
  }

  messagesEl.innerHTML =
    '<div class="loading-history">Loading history...</div>';

  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`);
    if (!response.ok) throw new Error("Failed to load session history");
    const data = await response.json();
    await renderSessionMessagesAndUI(data);
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

  let hasThinking = false;
  let text = content;
  if (text.endsWith("Thinking...")) {
    hasThinking = true;
    text = text.slice(0, -11).trimEnd();
  }

  let renderedHtml = "";
  if (typeof window.marked !== "undefined") {
    try {
      renderedHtml = window.marked.parse(text, { breaks: true, gfm: true });
    } catch (e) {
      console.error("Marked parse error:", e);
      renderedHtml = fallbackMarkdown(text);
    }
  } else {
    renderedHtml = fallbackMarkdown(text);
  }

  if (hasThinking) {
    renderedHtml += `<div style="margin-top: 8px;"><span class="thinking-indicator">Thinking<span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span></span></div>`;
  }

  return renderedHtml;
}

function fallbackMarkdown(content) {
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
    const uuid =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : Math.random().toString(36).substring(2, 15) +
          Math.random().toString(36).substring(2, 15);
    msgId = "msg-" + uuid;
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
    ["Prompt tokens", metadata.prompt_tokens || "-"],
    ["Output tokens", metadata.candidates_tokens || "-"],
    ["Total tokens", metadata.total_tokens || "-"],
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

  // Check if this is the first message before adding the new one
  const isFirstMessage =
    messagesEl.querySelectorAll(".message.user").length === 0;

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

    await readStreamAndProcess(response, pendingEl, "");
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
    if (isFirstMessage) {
      loadSessions(); // Only update sidebar on first message
    }
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

// Stream processor
async function readStreamAndProcess(response, messageEl, currentText) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let accumulatedText = currentText;

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

            if (data.type === "ui") {
              // Handle UI component request
              if (data.component === "select_course") {
                renderCourseSelector(data, messageEl, accumulatedText);
              } else if (data.component === "run_exam_scheduling") {
                renderExamScheduleForm(data, messageEl, accumulatedText);
              } else if (data.component === "run_exam_rescheduling") {
                renderExamRescheduleForm(data, messageEl, accumulatedText);
              }
              return; // Stop reading this stream, wait for UI
            } else if (data.text) {
              accumulatedText += data.text;
              updateMessage(messageEl, accumulatedText);
            }
          } catch (e) {
            console.error("Error parsing SSE chunk:", e);
          }
        }
      }
    }
  }
}

// Generative UI component renderer
async function renderCourseSelector(uiData, messageEl, currentText) {
  updateMessage(messageEl, currentText); // Render what we have so far
  const contentEl = messageEl.querySelector(".message-content");

  // Fetch courses from API
  let courses = [];
  try {
    const response = await fetch(`${API_BASE_URL}/api/courses`);
    if (response.ok) {
      courses = await response.json();
    } else {
      console.error("Failed to fetch courses");
    }
  } catch (err) {
    console.error("Error fetching courses:", err);
  }

  const optionsHtml = courses
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");

  const uiWrapper = document.createElement("div");
  uiWrapper.className = "genui-card";
  uiWrapper.innerHTML = `
        <div class="course-selector-container">
            <div class="course-selector-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M12 16v-4"></path>
                    <path d="M12 8h.01"></path>
                </svg>
                <h4>Input Required</h4>
            </div>
            <p class="course-selector-desc">${uiData.args.reason || "Please select a course to continue."}</p>
            
            <div class="custom-select-wrapper">
                <select id="courseSelect" class="course-select">
                    <option value="" disabled selected>-- Select a Course --</option>
                    ${optionsHtml}
                </select>
            </div>
            
            <div class="course-selector-footer">
                <button id="submitCourseBtn" class="course-submit-btn">Submit Selection</button>
            </div>
        </div>
    `;

  contentEl.appendChild(uiWrapper);

  const btn = uiWrapper.querySelector("#submitCourseBtn");
  const select = uiWrapper.querySelector("#courseSelect");

  btn.addEventListener("click", async () => {
    const selected = select.value;
    if (!selected) return alert("Please select a course");

    // Disable UI
    select.disabled = true;
    btn.disabled = true;
    btn.textContent = "Submitting...";

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/stream_tool_result`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            tool_call_id: uiData.tool_call_id,
            tool_name: uiData.component,
            result: selected,
          }),
        },
      );

      if (!response.ok) throw new Error("Failed to submit tool result");

      // Remove the UI card and replace it with text showing what the user chose
      uiWrapper.remove();
      const nextText = currentText + `\n\n*(User selected: ${selected})*\n\n`;
      updateMessage(messageEl, nextText + "Thinking...");

      // Resume streaming
      await readStreamAndProcess(response, messageEl, nextText);
    } catch (err) {
      btn.textContent = "Error";
      console.error(err);
    }
  });
}

// Generative UI component renderer for Exam Scheduling
async function renderExamScheduleForm(uiData, messageEl, currentText) {
  updateMessage(messageEl, currentText); // Render what we have so far
  const contentEl = messageEl.querySelector(".message-content");

  // Fetch courses for the course dropdown
  let courses = [];
  try {
    const response = await fetch(`${API_BASE_URL}/api/courses`);
    if (response.ok) {
      courses = await response.json();
    }
  } catch (err) {
    console.error("Error fetching courses:", err);
  }

  const args = uiData.args || {};
  // Extract fields from new structure
  const fields = args.fields || {};
  const getFieldVal = (name) =>
    fields[name] && fields[name].value ? fields[name].value : "";
  const isDisabled = (name) =>
    fields[name] && fields[name].status === "provided" ? "disabled" : "";

  const courseOptionsHtml = courses
    .map(
      (c) =>
        `<option value="${c.name}" ${getFieldVal("course_name") === c.name ? "selected" : ""}>${c.name}</option>`,
    )
    .join("");

  const examTypeOptionsHtml = ["Midterm", "Final", "Quiz", "Assignment"]
    .map(
      (t) =>
        `<option value="${t}" ${getFieldVal("exam_type") === t ? "selected" : ""}>${t}</option>`,
    )
    .join("");

  const uiWrapper = document.createElement("div");
  uiWrapper.className = "genui-card";
  uiWrapper.innerHTML = `
        <div class="exam-schedule-container" style="display: flex; flex-direction: column; gap: 12px; padding: 15px; border: 1px solid var(--panel-border); border-radius: 8px; margin-top: 10px; background: var(--bg-soft);">
            <div class="course-selector-header" style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                <h4 style="margin: 0; font-size: 1.1em;">Schedule Exam</h4>
            </div>
            <p style="margin: 0; font-size: 0.9em; color: var(--text-muted, var(--muted));">${args.reason || "Please provide the missing exam details."}</p>
            
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <label style="font-size: 0.85em; font-weight: 500;">Course</label>
                <select id="es_course" class="course-select" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; opacity: ${isDisabled("course_name") ? "0.7" : "1"};" ${isDisabled("course_name")}>
                    <option value="" disabled ${!getFieldVal("course_name") ? "selected" : ""}>-- Select Course --</option>
                    ${courseOptionsHtml}
                </select>
            </div>

            <div style="display: flex; flex-direction: column; gap: 4px;">
                <label style="font-size: 0.85em; font-weight: 500;">Exam Type</label>
                <select id="es_type" class="course-select" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; opacity: ${isDisabled("exam_type") ? "0.7" : "1"};" ${isDisabled("exam_type")}>
                    <option value="" disabled ${!getFieldVal("exam_type") ? "selected" : ""}>-- Select Type --</option>
                    ${examTypeOptionsHtml}
                </select>
            </div>

            <div style="display: flex; gap: 10px;">
                <div style="display: flex; flex-direction: column; gap: 4px; flex: 1;">
                    <label style="font-size: 0.85em; font-weight: 500;">Date</label>
                    <input type="date" id="es_date" value="${getFieldVal("date")}" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; box-sizing: border-box; opacity: ${isDisabled("date") ? "0.7" : "1"};" ${isDisabled("date")} />
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px; flex: 1;">
                    <label style="font-size: 0.85em; font-weight: 500;">Time</label>
                    <input type="time" id="es_time" value="${getFieldVal("time")}" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; box-sizing: border-box; opacity: ${isDisabled("time") ? "0.7" : "1"};" ${isDisabled("time")} />
                </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 4px;">
                <label style="font-size: 0.85em; font-weight: 500;">Duration (minutes)</label>
                <input type="number" id="es_duration" value="${getFieldVal("duration_minutes") || "60"}" placeholder="e.g. 60" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; box-sizing: border-box; opacity: ${isDisabled("duration_minutes") ? "0.7" : "1"};" ${isDisabled("duration_minutes")} />
            </div>
            
            <button id="submitExamBtn" class="course-submit-btn" style="margin-top: 10px; padding: 10px; border-radius: 4px; border: none; background: var(--accent); color: white; cursor: pointer; font-weight: bold;">Schedule Exam</button>
        </div>
    `;

  contentEl.appendChild(uiWrapper);

  const btn = uiWrapper.querySelector("#submitExamBtn");
  btn.addEventListener("click", async () => {
    const course_name = uiWrapper.querySelector("#es_course").value;
    const exam_type = uiWrapper.querySelector("#es_type").value;
    const date = uiWrapper.querySelector("#es_date").value;
    const time = uiWrapper.querySelector("#es_time").value;
    const duration_minutes = uiWrapper.querySelector("#es_duration").value;

    if (!course_name || !exam_type || !date || !time || !duration_minutes) {
      return alert("Please fill out all fields.");
    }

    // Hide the form UI immediately after submitting
    uiWrapper.style.display = "none";

    btn.disabled = true;
    btn.textContent = "Submitting...";

    const resultPayload = {
      course_name,
      exam_type,
      date,
      time,
      duration_minutes: parseInt(duration_minutes, 10),
    };

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/stream_tool_result`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            tool_call_id: uiData.tool_call_id,
            tool_name: uiData.component,
            result: JSON.stringify(resultPayload),
          }),
        },
      );

      if (!response.ok) throw new Error("Failed to submit tool result");

      uiWrapper.remove();
      const nextText =
        currentText +
        `\n\n*(User selected: ${exam_type} for ${course_name} on ${date} at ${time})*\n\n`;
      updateMessage(messageEl, nextText + "Thinking...");

      await readStreamAndProcess(response, messageEl, nextText);
    } catch (err) {
      uiWrapper.style.display = "block"; // Show again on error
      btn.disabled = false;
      btn.textContent = "Error, try again";
      console.error(err);
    }
  });
}

// Generative UI component renderer for Exam Rescheduling
async function renderExamRescheduleForm(uiData, messageEl, currentText) {
  updateMessage(messageEl, currentText);
  const contentEl = messageEl.querySelector(".message-content");

  // Fetch scheduled exams from API
  let exams = [];
  try {
    const response = await fetch(`${API_BASE_URL}/api/exams`);
    if (response.ok) {
      exams = await response.json();
    }
  } catch (err) {
    console.error("Error fetching exams:", err);
  }

  const args = uiData.args || {};
  const fields = args.fields || {};
  const getFieldVal = (name) =>
    fields[name] && fields[name].value ? fields[name].value : "";
  const isDisabled = (name) =>
    fields[name] && fields[name].status === "provided" ? "disabled" : "";

  // exam options
  const examOptionsHtml = exams
    .map(
      (e) =>
        `<option value="${e.id}" ${getFieldVal("exam_id") === e.id ? "selected" : ""}>${e.course_name} (${e.exam_type}) - ${e.date}</option>`,
    )
    .join("");

  const uiWrapper = document.createElement("div");
  uiWrapper.className = "genui-card";
  uiWrapper.innerHTML = `
        <div class="exam-schedule-container" style="display: flex; flex-direction: column; gap: 12px; padding: 15px; border: 1px solid var(--panel-border); border-radius: 8px; margin-top: 10px; background: var(--bg-soft);">
            <div class="course-selector-header" style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
                <h4 style="margin: 0; font-size: 1.1em;">Reschedule Exam</h4>
            </div>
            <p style="margin: 0; font-size: 0.9em; color: var(--text-muted, var(--muted));">${args.reason || "Please select the exam and provide a new date and time."}</p>
            
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <label style="font-size: 0.85em; font-weight: 500;">Select Exam</label>
                <select id="es_exam_id" class="course-select" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; opacity: ${isDisabled("exam_id") ? "0.7" : "1"};" ${isDisabled("exam_id")}>
                    <option value="" disabled ${!getFieldVal("exam_id") ? "selected" : ""}>-- Select Exam --</option>
                    ${examOptionsHtml}
                </select>
            </div>

            <div style="display: flex; gap: 10px;">
                <div style="display: flex; flex-direction: column; gap: 4px; flex: 1;">
                    <label style="font-size: 0.85em; font-weight: 500;">New Date</label>
                    <input type="date" id="es_new_date" value="${getFieldVal("new_date")}" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; box-sizing: border-box; opacity: ${isDisabled("new_date") ? "0.7" : "1"};" ${isDisabled("new_date")} />
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px; flex: 1;">
                    <label style="font-size: 0.85em; font-weight: 500;">New Time</label>
                    <input type="time" id="es_new_time" value="${getFieldVal("new_time")}" style="padding: 8px; border-radius: 4px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--text); width: 100%; box-sizing: border-box; opacity: ${isDisabled("new_time") ? "0.7" : "1"};" ${isDisabled("new_time")} />
                </div>
            </div>
            
            <button id="submitRescheduleBtn" class="course-submit-btn" style="margin-top: 10px; padding: 10px; border-radius: 4px; border: none; background: var(--accent); color: white; cursor: pointer; font-weight: bold;">Reschedule Exam</button>
        </div>
    `;

  contentEl.appendChild(uiWrapper);

  const btn = uiWrapper.querySelector("#submitRescheduleBtn");
  btn.addEventListener("click", async () => {
    const exam_id = uiWrapper.querySelector("#es_exam_id").value;
    const new_date = uiWrapper.querySelector("#es_new_date").value;
    const new_time = uiWrapper.querySelector("#es_new_time").value;

    if (!exam_id || !new_date || !new_time) {
      return alert("Please fill out all fields.");
    }

    uiWrapper.style.display = "none";
    btn.disabled = true;
    btn.textContent = "Submitting...";

    const resultPayload = {
      exam_id,
      new_date,
      new_time,
    };

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/stream_tool_result`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            tool_call_id: uiData.tool_call_id,
            tool_name: uiData.component,
            result: JSON.stringify(resultPayload),
          }),
        },
      );

      if (!response.ok) throw new Error("Failed to submit tool result");

      uiWrapper.remove();
      const nextText =
        currentText +
        `\n\n*(User requested to reschedule exam ${exam_id} to ${new_date} at ${new_time})*\n\n`;
      updateMessage(messageEl, nextText + "Thinking...");

      await readStreamAndProcess(response, messageEl, nextText);
    } catch (err) {
      uiWrapper.style.display = "block"; // Show again on error
      btn.disabled = false;
      btn.textContent = "Error, try again";
      console.error(err);
    }
  });
}

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
    await renderSessionMessagesAndUI(data);
  } catch (err) {
    messagesEl.innerHTML = "";
    addMessage(
      "assistant",
      "Send a message to test the agent with session history.",
    );
  }
}

// Theme Toggle Logic
const themeToggleBtn = document.querySelector("#themeToggleBtn");
const themeIconLight = document.querySelector(".theme-icon-light");
const themeIconDark = document.querySelector(".theme-icon-dark");
const themeBtnText = document.querySelector(".theme-btn-text");

function applyTheme(theme) {
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
    if (themeIconLight) themeIconLight.style.display = "none";
    if (themeIconDark) themeIconDark.style.display = "block";
    if (themeBtnText) themeBtnText.textContent = "Light Mode";
  } else {
    document.documentElement.setAttribute("data-theme", "light");
    if (themeIconLight) themeIconLight.style.display = "block";
    if (themeIconDark) themeIconDark.style.display = "none";
    if (themeBtnText) themeBtnText.textContent = "Dark Mode";
  }
}

// Load saved theme or default to dark mode
const savedTheme = localStorage.getItem("ai-runtime-theme") || "dark";
applyTheme(savedTheme);

if (themeToggleBtn) {
  themeToggleBtn.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    localStorage.setItem("ai-runtime-theme", newTheme);
    applyTheme(newTheme);
  });
}

// Mobile Sidebar Toggle
const mobileMenuBtn = document.querySelector("#mobileMenuBtn");
const sidebar = document.querySelector(".sidebar");
const sidebarOverlay = document.querySelector("#sidebarOverlay");

if (mobileMenuBtn && sidebar && sidebarOverlay) {
  mobileMenuBtn.addEventListener("click", () => {
    sidebar.classList.add("open");
    sidebarOverlay.classList.add("open");
  });

  sidebarOverlay.addEventListener("click", () => {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("open");
  });
}

initializeApp();
