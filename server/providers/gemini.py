import time
import logging
import json

from google import genai
from google.genai import types
from response import LLMResponse, ToolCall
from .base import LLMProvider

logger = logging.getLogger(__name__)
class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)
        
    def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        contents = session if isinstance(session, str) else self._build_request(session)

        gemini_tools = self._to_gemini_tools(tools)
        
        start_time = time.time()
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
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
        
        generic_tool_calls = []
        if response.function_calls:
            for fc in response.function_calls:
                generic_tool_calls.append(ToolCall(name=fc.name, args=fc.args, id=fc.id))
        else:
            generic_tool_calls = None

        return LLMResponse(
            text=response.text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            total_tokens=total_tokens,
            model_name=used_model,
            function_calls=generic_tool_calls,
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
                content = message.content
            elif message.role == "assistant":
                label = "Assistant"
                content = message.content
            elif message.role == "tool_call":
                label = "Tool Call"
                arg_str = ", ".join(f"{k}={v}" for k, v in message.args.items()) if message.args else ""
                content = f"{message.tool_name}({arg_str})"
            elif message.role == "tool-result":
                label = "Tool Result"
                content = message.content
            else:
                label = message.role.capitalize()
                content = message.content
            
            transcript.append(f"{label}: {content}")

        transcript.append("Assistant:")

        transcript_str = "\n".join(transcript)
        logger.info(f"\nTranscript:\n{transcript_str}")
        return transcript_str