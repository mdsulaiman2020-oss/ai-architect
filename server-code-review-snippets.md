# Server Code Review Snippets

## server/api_server.py

```python
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from provider import get_provider
from session import InMemorySessionStore


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from runtime import Runtime

app = FastAPI(title="AI Runtime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = InMemorySessionStore()
provider = None

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ResetRequest(BaseModel):
    session_id: str


def get_runtime_provider():
    global provider
    if provider is None:
        provider = get_provider()
    return provider


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    message = request.message.strip()
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    session = sessions.get_or_create(request.session_id)
    session.add_user_message(message)

    response, metadata = Runtime(get_runtime_provider(), session).call_provider()

    session.add_assistant_message(response.text, metadata=metadata)

    return {
        "reply": response.text,
        "session": session.to_dict(),
        "metadata": metadata,
    }


@app.post("/api/reset")
def reset(request: ResetRequest):
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = sessions.reset(request.session_id)
    return {"session": session.to_dict()}
```

## server/runtime.py

```python
from fastapi import HTTPException
import logging

from tools.registry import ToolRegistry
from tools.time import get_current_time_and_zone
from tools.calculator import add, multiply

logger = logging.getLogger(__name__)

class Runtime:
    def __init__(self, provider, session):
        self.session = session
        self.provider = provider

        # Initialize and register tools
        self.registry = ToolRegistry()
        self.registry.register(
            name="current_time",
            description="Get the current local time and timezone",
            handler=get_current_time_and_zone,
            parameters=None,
        )
        self.registry.register(
            name="add",
            description="Add two numbers",
            handler=add,
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        )
        self.registry.register(
            name="multiply",
            description="Multiply two numbers",
            handler=multiply,
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        )

    def call_provider(self):
        # Accumulate stats
        total_latency_ms = 0.0
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_total_tokens = 0
        used_model_name = ""

        max_iterations = 5
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            try:
                response = self.provider.generate(self.session, tools=self.registry.list_tools())
            except Exception:
                logger.exception("Failed to generate response")
                raise HTTPException(status_code=500, detail="Failed to generate response")

            # Accumulate metadata
            total_latency_ms += response.latency_ms
            total_prompt_tokens += response.prompt_tokens
            total_candidates_tokens += response.candidates_tokens
            total_total_tokens += response.total_tokens
            used_model_name = response.model_name

            # If there are no tool calls, we're done
            if not response.function_calls:
                metadata = {
                    "latency_ms": total_latency_ms,
                    "prompt_tokens": total_prompt_tokens,
                    "candidates_tokens": total_candidates_tokens,
                    "total_tokens": total_total_tokens,
                    "model_name": used_model_name,
                }
                return response, metadata

            # Process tool calls
            for fc in response.function_calls:
                logger.info(f"Executing tool call: {fc.name} with args {fc.args}")
                try:
                    result = self.registry.execute(fc.name, **fc.args)
                except Exception as e:
                    logger.error(f"Error executing tool {fc.name}: {e}")
                    result = f"Error: {e}"

                # Format argument string for prompt history
                arg_str = ", ".join(f"{k}={v}" for k, v in fc.args.items())

                # Append tool call and output to the transcript
                self.session.add_tool_call_message(f"{fc.name}({arg_str})")
                self.session.add_tool_result_message(f"{str(result)}")

        raise HTTPException(
            status_code=500,
            detail="Tool execution loop exceeded maximum allowed iterations"
        )
```

## server/session.py

```python
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str
    content: str
    metadata: dict | None = None


@dataclass
class ConversationSession:
    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str, metadata: dict | None = None) -> None:
        self.messages.append(
            ChatMessage(role="assistant", content=content, metadata=metadata)
        )

    def add_tool_call_message(self, content: str, metadata: dict | None = None) -> None:
        self.messages.append(ChatMessage(role="tool-call", content=content, metadata=metadata))

    def add_tool_result_message(self, content: str, metadata: dict | None = None) -> None:
        self.messages.append(ChatMessage(role="tool-result", content=content, metadata=metadata))

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": [self._message_to_dict(message) for message in self.messages],
        }

    def _message_to_dict(self, message: ChatMessage) -> dict:
        data = {"role": message.role, "content": message.content}
        if message.metadata is not None:
            data["metadata"] = message.metadata
        return data


class InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: str) -> ConversationSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> ConversationSession:
        self._sessions[session_id] = ConversationSession(session_id=session_id)
        return self._sessions[session_id]
```

## server/response.py

```python
class LLMResponse:
    def __init__(self, text: str, latency_ms: float, prompt_tokens: int, candidates_tokens: int, total_tokens: int, model_name: str, function_calls: list | None = None):
        self.text = text
        self.latency_ms = latency_ms
        self.prompt_tokens = prompt_tokens
        self.candidates_tokens = candidates_tokens
        self.total_tokens = total_tokens
        self.model_name = model_name
        self.function_calls = function_calls
```

## server/provider.py

```python
import logging

from config import Config

logger = logging.getLogger(__name__)

def get_provider():
    logger.info(f"provider type: {Config.PROVIDER_TYPE}")

    if Config.PROVIDER_TYPE == "gemini":
        from providers.gemini import GeminiProvider

        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")

        return GeminiProvider(api_key=Config.GEMINI_API_KEY, model_name=Config.MODEL_NAME)
    else:
        raise ValueError(f"Unsupported provider type: {Config.PROVIDER_TYPE}")
```

## server/config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROVIDER_TYPE = os.environ.get("PROVIDER_TYPE", "gemini").lower()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-3.5-flash-lite")
```

## server/providers/base.py

```python
from abc import ABC, abstractmethod
from response import LLMResponse

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        pass
```

## server/providers/gemini.py

```python
import time
from google import genai
from response import LLMResponse
from .base import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)

    def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        if isinstance(session, str):
            prompt = session
        else:
            prompt = self._build_request(session)

        gemini_tools = self._to_gemini_tools(tools)

        start_time = time.time()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "tools": gemini_tools,
            } if gemini_tools else None,
        )
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        prompt_tokens = 0
        candidates_tokens = 0
        total_tokens = 0

        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            total_tokens = response.usage_metadata.total_token_count

        used_model = getattr(response, "model_version", self.model_name)

        return LLMResponse(
            text=response.text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            total_tokens=total_tokens,
            model_name=used_model,
            function_calls=response.function_calls,
        )

    def _to_gemini_tools(self, tools: list[dict] | None):
        if not tools:
            return None

        function_declarations = []

        for tool in tools:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters") or {
                    "type": "object",
                    "properties": {},
                },
            })

        return [
            {
                "function_declarations": function_declarations,
            }
        ]

    def _build_request(self, session) -> str:
        if not session.messages:
            return ""

        transcript = [
            "You are a helpful AI assistant. Continue the conversation using the transcript below.",
            "",
        ]

        for message in session.messages:
            if message.role == "user":
                label = "User"
            elif message.role == "assistant":
                label = "Assistant"
            elif message.role == "tool-call":
                label = "Tool Call"
            elif message.role == "tool-result":
                label = "Tool Result"
            else:
                label = message.role.capitalize()
            transcript.append(f"{label}: {message.content}")

        transcript.append("Assistant:")
        return "\n".join(transcript)
```

## server/tools/registry.py

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name: str, description: str, handler,parameters: dict):
        self._tools[name] = {
            "description": description,
            "handler": handler,
            "parameters": parameters,
        }

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for name, tool in self._tools.items()
        ]

    def execute(self, name: str, **arguments):
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        return self._tools[name]["handler"](**arguments)
```

## server/tools/calculator.py

```python
def add(a: int, b: int) -> int:
    return a + b


def multiply(a: int, b: int) -> int:
    return (a * b) * 10
```

## server/tools/time.py

```python
from datetime import datetime

def get_current_time_and_zone() -> dict:
    """
    Get the current local time and timezone information.

    Returns:
        dict: A dictionary containing:
            - 'iso': The ISO-8601 formatted datetime string.
            - 'formatted': A human-readable string in 'YYYY-MM-DD HH:MM:SS' format.
            - 'timezone': The timezone name/abbreviation (e.g., 'UTC', 'IST').
            - 'utc_offset': The UTC offset (e.g., '+0000', '+0530').
    """
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(),
        "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": now.tzname(),
        "utc_offset": now.strftime("%z")
    }
```

## server/tests/test_tool_registry.py

```python
from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from tools.calculator import add, multiply
from tools.registry import ToolRegistry
from tools.time import get_current_time_and_zone


def main():
    registry = ToolRegistry()

    registry.register(
        name="add",
        description="Add two numbers",
        handler=add,
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
    )
    registry.register(
        name="current_time",
        description="Get the current local time and timezone",
        handler=get_current_time_and_zone,
        parameters=None,
    )

    print("Available tools:")
    for tool in registry.list_tools():
        print(f"- {tool['name']}: {tool['description']}")

    print()
    print("Tool results:")
    print("add:", registry.execute("add", a=2, b=3))
    # print("multiply:", registry.execute("multiply", a=4, b=5))
    print("current_time:", registry.execute("current_time"))


if __name__ == "__main__":
    main()
```

## server/app.py

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from config import Config
from provider import get_provider

def main():
    key = Config.GEMINI_API_KEY
    if key:
        logger.info("GEMINI_API_KEY is set")
        logger.info("Calling Gemini API...")
        provider = get_provider()
        try:
            response = provider.generate("Say hello world!")
            logger.info(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
    else:
        logger.error("GEMINI_API_KEY is not set")

if __name__ == "__main__":
    main()
```

## server/requirements.txt

```text
google-genai
python-dotenv
fastapi
uvicorn
```
