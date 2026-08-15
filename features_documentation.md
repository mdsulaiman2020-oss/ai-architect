# AI Runtime Features Documentation

This document outlines the list of features and architectural milestones we have covered and implemented so far in the `01-ai-runtime` project.

## 1. Core AI Runtime Engine (`server/runtime.py`)

- **Streaming LLM Responses:** Handles continuous token generation from the AI provider to provide a real-time, low-latency chat experience.
- **Tool Execution Loop:** Intelligently intercepts LLM tool/function calls, executes them securely on the backend against a tool registry, and feeds results back into the LLM context.
- **Generative UI (Human-in-the-Loop):** Supports pausing the execution stream when a tool explicitly requires user input (e.g., `ready_for_user_confirmation` or `needs_schedule_input`). It safely suspends the backend and instructs the frontend to render a dynamic component.
- **Sub-Agent Orchestration:** Supports nested agent architectures by capturing and managing `_sub_agent_messages` inside tool results, allowing agents to delegate work and report back detailed logs.

## 2. API & State Management (`server/api_server.py` & MongoDB)

- **Session Persistence:** Connects to MongoDB to manage multi-turn conversational state, ensuring memory persists across browser reloads.
- **Conversational Endpoints:** Exposes robust REST endpoints for streaming chat (`/api/chat/stream`) and tool result submissions (`/api/chat/stream_tool_result`).
- **Resilient State Saving:** Fixed critical edge cases where in-memory session changes (like Generative UI `tool_calls` without accompanying text) are guaranteed to be saved to the database.

## 3. Frontend Client Architecture (`client/app.js` & `client/index.html`)

- **Event Stream Parsing:** Connects to the backend via Server-Sent Events (SSE) to render incoming text chunks in real-time.
- **Dynamic UI Rendering:** Intercepts `type: "ui"` events to swap out standard text messages for interactive HTML forms (e.g., Course Selection, Exam Scheduling forms).
- **Session History Navigation:** Allows users to load and switch between previous chat sessions via a responsive sidebar.
- **State Hydration:** When a session is reloaded, the client automatically detects unresolved pending tool calls in the message history and perfectly re-hydrates the appropriate UI forms.
- **Theming & UI Polish:** Supports modern Dark/Light mode toggling and utilizes a clean CSS layout for chat interactions.

## 4. Specialized Agents & Tools (`server/agents/`)

### A. Exam Scheduling Agent

- **Validation Engine:** Built on `ExamSchedulingService` to strictly validate course names, exam types, dates, and times.
- **Multi-Step Confirmation Flow:** Prevents the LLM from hallucinating confirmations. Uses an explicit `"action": "prepare"` and `"action": "confirm"` loop to ensure the user physically interacts with the Generative UI before committing to the database.
- **Conflict Resolution:** Checks for scheduling conflicts before presenting the final proposed schedule to the user.

### B. Assessment Agent

- **Validation Orchestration:** Runs complex validation tasks across different assessment scopes (`topics`, `outcomes`, `all`).
- **Sub-Validators:** Leverages specific validator components (e.g., `AssessmentTopicsValidator`, `AssessmentQuestionTopicAlignmentValidator`) to generate comprehensive reports on missing or invalid assessment mapping items.
- **Delegation Tool:** Exposes `run_assessment_agent` as a tool, allowing the main agent to delegate specialized tasks cleanly.
