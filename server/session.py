import json
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    metadata: dict | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    args: dict | None = None
    thought_signature: bytes | None = None
    children: list["ChatMessage"] | None = None
    name: str | None = None


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

    def add_tool_call_message(self, tool_name: str, tool_call_id: str | None, args: dict, thought_signature: bytes | None = None, children: list[ChatMessage] | None = None) -> None:
        self.messages.append(
            ChatMessage(role="tool_call", tool_name=tool_name, tool_call_id=tool_call_id, args=args, thought_signature=thought_signature, children=children)
        )

    def add_tool_result_message(self, tool_call_id: str | None, tool_name: str, content: str) -> None:
        self.messages.append(
            ChatMessage(
                role="tool-result",
                content=content,
                tool_name=tool_name,
                tool_call_id=tool_call_id
            )
        )

    def add_validation_result_message(self, name: str, content: str) -> None:
        self.messages.append(
            ChatMessage(
                role="validation-result",
                content=content,
                name=name
            )
        )   
        
    def add_client_ui_message(self, component: str, tool_call_id: str, args: dict) -> None:
        self.messages.append(
            ChatMessage(
                role="client-ui",
                name=component,
                tool_call_id=tool_call_id,
                args=args
            )
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": [self._message_to_dict(message) for message in self.messages],
        }

    def _message_to_dict(self, message: ChatMessage) -> dict:
        data = {"role": message.role}
        if message.content is not None:
            data["content"] = message.content
        if message.tool_name is not None:
            data["tool_name"] = message.tool_name
        if message.tool_call_id is not None:
            data["tool_call_id"] = message.tool_call_id
        if message.args is not None:
            data["args"] = message.args
        if message.thought_signature is not None:
            import base64
            data["thought_signature"] = base64.b64encode(message.thought_signature).decode("utf-8")
        if message.metadata is not None:
            data["metadata"] = message.metadata
        if message.children is not None:
            data["children"] = [self._message_to_dict(child) for child in message.children]
        return data


    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSession":
        session_id = data.get("session_id", "")
        messages = []
        for m in data.get("messages", []):
            messages.append(cls._message_from_dict(m))
        return cls(session_id=session_id, messages=messages)

    @classmethod
    def _message_from_dict(cls, m: dict) -> ChatMessage:
        thought_sig = None
        if "thought_signature" in m and m["thought_signature"]:
            import base64
            try:
                thought_sig = base64.b64decode(m["thought_signature"])
            except Exception:
                pass
        children = None
        if "children" in m and m["children"]:
            children = [cls._message_from_dict(child) for child in m["children"]]
        return ChatMessage(
            role=m.get("role", "user"),
            content=m.get("content"),
            metadata=m.get("metadata"),
            tool_name=m.get("tool_name"),
            tool_call_id=m.get("tool_call_id"),
            args=m.get("args"),
            thought_signature=thought_sig,
            children=children,
        )


class MongoSessionStore:
    def _get_collection(self):
        from db import get_db
        return get_db()["agent_sessions"]

    def get_or_create(self, session_id: str) -> ConversationSession:
        doc = self._get_collection().find_one({"session_id": session_id})
        if doc:
            return ConversationSession.from_dict(doc)
        
        return ConversationSession(session_id=session_id)

    def save(self, session: ConversationSession) -> None:
        data = session.to_dict()
        from datetime import datetime, timezone
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._get_collection().update_one(
            {"session_id": session.session_id},
            {"$set": data},
            upsert=True
        )

    def reset(self, session_id: str) -> ConversationSession:
        from datetime import datetime, timezone
        self._get_collection().update_one({"session_id": session_id}, {"$set": {"status": "deleted", "deleted_at": datetime.now(timezone.utc).isoformat()}})
        session = ConversationSession(session_id=session_id)
        self.save(session)
        return session


# python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload

# python -m http.server 5500 --bind 127.0.0.1