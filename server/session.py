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

    def add_tool_call_message(self, tool_name: str, tool_call_id: str | None, args: dict, thought_signature: bytes | None = None) -> None:
        self.messages.append(
            ChatMessage(role="tool_call", tool_name=tool_name, tool_call_id=tool_call_id, args=args, thought_signature=thought_signature)
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
        return data


    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSession":
        session_id = data.get("session_id", "")
        messages = []
        for m in data.get("messages", []):
            thought_sig = None
            if "thought_signature" in m and m["thought_signature"]:
                import base64
                try:
                    thought_sig = base64.b64decode(m["thought_signature"])
                except Exception:
                    pass
            messages.append(
                ChatMessage(
                    role=m.get("role", "user"),
                    content=m.get("content"),
                    metadata=m.get("metadata"),
                    tool_name=m.get("tool_name"),
                    tool_call_id=m.get("tool_call_id"),
                    args=m.get("args"),
                    thought_signature=thought_sig,
                )
            )
        return cls(session_id=session_id, messages=messages)


class MongoSessionStore:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from pymongo import MongoClient
            from config import Config
            self._client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=2000)
        return self._client

    def _get_collection(self):
        from config import Config
        return self.client[Config.MONGODB_DB_NAME]["sessions"]

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
        self._get_collection().delete_one({"session_id": session_id})
        session = ConversationSession(session_id=session_id)
        self.save(session)
        return session


