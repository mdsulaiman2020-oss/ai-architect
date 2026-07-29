import logging
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from provider import get_provider
from session import MongoSessionStore
from tools.registry import ToolRegistry
from tools.time_tool import CurrentTimeTool
from tools.add_tool import AddTool
from tools.multiply_tool import MultiplyTool
from tools.student_search_tool import StudentSearchTool
from tools.fetch_url_tool import FetchURLTool


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

sessions = MongoSessionStore()
provider = None

# Initialize and register tools
registry = ToolRegistry()
registry.register(CurrentTimeTool())
registry.register(AddTool())
registry.register(MultiplyTool())
registry.register(StudentSearchTool())
registry.register(FetchURLTool())


class ChatRequest(BaseModel):
    session_id: str
    message: str

class ResetRequest(BaseModel):
    session_id: str

class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: str  # "up" or "down"
    content: str | None = None


def get_runtime_provider():
    global provider
    if provider is None:
        provider = get_provider()
    return provider


@app.get("/health")
def health():
    return {"status": "ok"}


import asyncio
from fastapi import Request

@app.post("/api/chat")
async def chat(request: Request, payload: ChatRequest):
    message = payload.message.strip()
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    session = sessions.get_or_create(payload.session_id)
    session.add_user_message(message)
    sessions.save(session)

    runtime = Runtime(get_runtime_provider(), session, registry)

    try:
        async with asyncio.timeout(60.0):
            response, metadata = await runtime.call_provider()
    except TimeoutError:
        logger.error("Request timed out in /api/chat")
        raise HTTPException(status_code=504, detail="Request timed out")
    except asyncio.CancelledError:
        logger.info("Request cancelled in /api/chat")
        raise

    session.add_assistant_message(response.text, metadata=metadata)
    sessions.save(session)

    return {
        "reply": response.text,
        "session": session.to_dict(),
        "metadata": metadata,
    }


@app.post("/api/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest):
    message = payload.message.strip()
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    session = sessions.get_or_create(payload.session_id)
    session.add_user_message(message)
    sessions.save(session)
    
    runtime = Runtime(get_runtime_provider(), session, registry)
    
    async def event_generator():
        accumulated_reply = []
        try:
            async with asyncio.timeout(60.0):
                async for text_chunk in runtime.call_provider_stream():
                    if await request.is_disconnected():
                        logger.info("Client disconnected. Aborting stream.")
                        break
                        
                    if text_chunk:
                        accumulated_reply.append(text_chunk)
                        yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                        
            if not await request.is_disconnected():
                complete_reply = "".join(accumulated_reply)
                session.add_assistant_message(complete_reply)
                sessions.save(session)
                yield "data: [DONE]\n\n"
        except TimeoutError:
            logger.error("Request timed out in stream.")
            yield f"data: {json.dumps({'text': '[Error: Request timed out]'})}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.info("Stream cancelled via asyncio.")
            raise
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reset")
def reset(request: ResetRequest):
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = sessions.reset(request.session_id)
    return {"session": session.to_dict()}


@app.post("/api/feedback")
def submit_feedback(request: FeedbackRequest):
    if request.rating not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'")

    try:
        from pymongo import MongoClient
        from config import Config
        from datetime import datetime, timezone

        client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=2000)
        db = client[Config.MONGODB_DB_NAME]
        db["message_feedback"].update_one(
            {"message_id": request.message_id},
            {
                "$set": {
                    "session_id": request.session_id,
                    "message_id": request.message_id,
                    "rating": request.rating,
                    "content": request.content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True
        )
        return {"status": "success", "rating": request.rating, "message_id": request.message_id}
    except Exception as e:
        logger.error(f"Error saving feedback to Mongo: {e}")
        return {"status": "success", "rating": request.rating, "message_id": request.message_id, "warning": str(e)}


@app.get("/api/sessions")
def list_sessions():
    try:
        from pymongo import MongoClient
        from config import Config
        client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=2000)
        collection = client[Config.MONGODB_DB_NAME]["sessions"]
        
        # Sort by updated_at desc, filtering out empty or invalid sessions
        cursor = collection.find({
            "session_id": {"$nin": [None, "null", "undefined", ""]},
            "messages": {"$exists": True, "$not": {"$size": 0}}
        }, {"session_id": 1, "messages": 1, "updated_at": 1}).sort("updated_at", -1)
        
        session_list = []
        for doc in cursor:
            session_id = doc.get("session_id")
            messages = doc.get("messages", [])
            
            # Find first user message for title
            title = "New Chat"
            for m in messages:
                if m.get("role") == "user" and m.get("content"):
                    user_content = m["content"].strip()
                    title = user_content[:40] + ("..." if len(user_content) > 40 else "")
                    break
                    
            session_list.append({
                "session_id": session_id,
                "title": title,
                "updated_at": doc.get("updated_at")
            })
        return session_list
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        # Return empty list on failure
        return []


@app.get("/api/sessions/{session_id}")
def get_session_history(session_id: str):
    session = sessions.get_or_create(session_id)
    return session.to_dict()

