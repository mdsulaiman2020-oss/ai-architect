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
