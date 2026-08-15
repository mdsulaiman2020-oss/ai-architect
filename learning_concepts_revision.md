# AI, Agent & Python Concepts Revision Guide

This document serves as a study and revision guide based on the work completed in the `01-ai-runtime` project. It highlights the core concepts, patterns, and technologies you have built and learned.

## 🤖 AI & Agent Concepts

### 1. Function Calling (Tool Calling)

- **Concept:** How an LLM interacts with external systems. Instead of generating plain text, the LLM outputs structured JSON that matches a predefined schema to trigger backend functions.
- **Implementation:** Defined strict JSON schemas (e.g., `parameters` property in `exam_schedule_agent.py`) and intercepted the `tool_calls` payload in the streaming loop before the user sees it.

### 2. Generative UI & Human-in-the-Loop

- **Concept:** Moving beyond text-based chat by allowing the LLM to dynamically trigger client-side UI components (like forms or date pickers).
- **Implementation:** When the LLM calls a tool, the backend can return a specific status (e.g., `"needs_schedule_input"` or `"ready_for_user_confirmation"`). The `runtime.py` pauses the execution stream, yielding a UI payload to the frontend. The user fills out the form, which is then submitted back as a `tool-result` to resume the LLM.

### 3. Multi-Agent Orchestration

- **Concept:** Delegating complex, domain-specific tasks to specialized "sub-agents" rather than bloating a single main prompt.
- **Implementation:** The `AssessmentAgent` runs independently with its own tools and orchestrates validation. The primary runtime captures these `_sub_agent_messages` and nests them within the session history, allowing hierarchical agent structures.

### 4. Prompt Engineering & Hallucination Mitigation

- **Concept:** Writing robust system instructions that force the LLM to adhere to strict business logic.
- **Implementation:** Adding critical safeguards like _"DO NOT silently change any parameters"_ and explicitly defining a multi-step `action` flow (`prepare` vs `confirm`) to stop the LLM from aggressively auto-confirming actions without explicit user input.

### 5. Conversational Memory & State Tracking

- **Concept:** Ensuring the LLM has the exact context of what happened during tool execution.
- **Implementation:** Understanding the strict sequence of OpenAI/Gemini message roles: `user` -> `assistant` (with `tool_call`) -> `tool-result`. You mastered the tricky edge case of ensuring that even when a tool triggers a UI (and yields no text), the `tool_call` must still be saved to the MongoDB session history so the frontend can rehydrate on reload.

---

## 🐍 Python & Backend Concepts

### 1. Advanced Asynchronous Programming (`asyncio`)

- **Concept:** Handling high-concurrency, non-blocking I/O operations (like network requests to AI APIs or MongoDB).
- **Implementation:**
  - Using `async for` to iterate over streaming data chunks (`call_provider_stream`).
  - Using `asyncio.timeout` to gracefully handle hanging API requests.
  - Using `inspect.iscoroutine()` to dynamically check if a tool execution requires `await`, allowing the tool registry to seamlessly support both synchronous and asynchronous tools.

### 2. FastAPI & Streaming Responses

- **Concept:** Building modern, high-performance web APIs in Python.
- **Implementation:** Utilizing FastAPI's `StreamingResponse` to push Server-Sent Events (SSE) (e.g., `yield f"data: {json.dumps(...)}\n\n"`) to the client, providing that immediate "typing" effect rather than making the user wait for the entire response to generate.

### 3. Stateful Architecture & Database Persistence

- **Concept:** Moving from in-memory arrays to persistent data stores.
- **Implementation:** Using MongoDB (via `pymongo`) to read and update deeply nested session objects. You learned how critical it is to ensure state is safely flushed to the database (`sessions.save(session)`) regardless of whether the execution path exits early due to a UI interruption.

### 4. Exception Handling & Graceful Degradation

- **Concept:** Ensuring that backend errors don't crash the application or leak sensitive stack traces to the LLM.
- **Implementation:** Refactoring `runtime.py` to wrap tool executions in a `try/except` block, returning a generic, safe string to the LLM (e.g., _"An internal server error occurred..."_) so the agent can gracefully inform the user rather than hallucinating over raw Python errors.
