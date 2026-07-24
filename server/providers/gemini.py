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
            parts = response.candidates[0].content.parts if (response.candidates and response.candidates[0].content and response.candidates[0].content.parts) else []
            for part in parts:
                if part.function_call:
                    fc = part.function_call
                    generic_tool_calls.append(
                        ToolCall(
                            name=fc.name,
                            args=fc.args,
                            id=fc.id,
                            thought_signature=getattr(part, "thought_signature", None)
                        )
                    )
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

    def _build_request(self, session) -> list[types.Content]:
        if not session.messages:
            return []

        logger.info("\n=== Rebuilding Request ===")
        for idx, m in enumerate(session.messages):
            logger.info(f"Msg #{idx}: role={m.role}, tool_name={m.tool_name}, id={m.tool_call_id}, has_sig={m.thought_signature is not None}")

        contents = []
        for message in session.messages:
            if message.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message.content)]
                    )
                )
            elif message.role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=message.content)]
                    )
                )
            elif message.role == "tool_call":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=message.tool_name,
                                    args=message.args,
                                    id=message.tool_call_id
                                ),
                                thought_signature=message.thought_signature
                            )
                        ]
                    )
                )
            elif message.role == "tool-result":
                try:
                    response_dict = json.loads(message.content)
                    if not isinstance(response_dict, dict):
                        response_dict = {"result": message.content}
                except Exception:
                    response_dict = {"result": message.content}

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=message.tool_name or "",
                                    response=response_dict,
                                    id=message.tool_call_id
                                )
                            )
                        ]
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role=message.role,
                        parts=[types.Part.from_text(text=message.content or "")]
                    )
                )

        logger.info(f"\nBuilt native contents with {len(contents)} messages.")
        return contents