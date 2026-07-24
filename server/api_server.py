import logging
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from provider import get_provider
from session import InMemorySessionStore
from tools.registry import ToolRegistry
from tools.time_tool import CurrentTimeTool
from tools.add_tool import AddTool
from tools.multiply_tool import MultiplyTool


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

# Initialize and register tools
registry = ToolRegistry()
registry.register(CurrentTimeTool())
registry.register(AddTool())
registry.register(MultiplyTool())
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

    response, metadata = Runtime(get_runtime_provider(), session, registry).call_provider()

    session.add_assistant_message(response.text, metadata=metadata)

    return {
        "reply": response.text,
        "session": session.to_dict(),
        "metadata": metadata,
    }


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest):
    message = request.message.strip()
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    session = sessions.get_or_create(request.session_id)
    session.add_user_message(message)
    
    runtime = Runtime(get_runtime_provider(), session, registry)
    
    def event_generator():
        accumulated_reply = []
        for text_chunk in runtime.call_provider_stream():
            if text_chunk:
                accumulated_reply.append(text_chunk)
                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
        
        complete_reply = "".join(accumulated_reply)
        session.add_assistant_message(complete_reply)
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reset")
def reset(request: ResetRequest):
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = sessions.reset(request.session_id)
    return {"session": session.to_dict()}
