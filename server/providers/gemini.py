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

    def generate_stream(self, session, tools: list[dict] | None = None):
        contents = session if isinstance(session, str) else self._build_request(session)
        gemini_tools = self._to_gemini_tools(tools)
        
        response_stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config={
                "tools": gemini_tools,
            } if gemini_tools else None,
        )
        
        for chunk in response_stream:
            if chunk.text:
                yield {"type": "text", "content": chunk.text}
                
            if chunk.function_calls:
                generic_tool_calls = []
                # Handle possible multiple parts for native tools
                parts = chunk.candidates[0].content.parts if (chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts) else []
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
                if generic_tool_calls:
                    yield {"type": "tool_calls", "content": generic_tool_calls}


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
        i = 0
        n = len(session.messages)
        while i < n:
            message = session.messages[i]
            
            if message.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message.content)]
                    )
                )
                i += 1
            elif message.role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=message.content)]
                    )
                )
                i += 1
            elif message.role == "tool_call":
                parts = []
                thought_sig = None
                while i < n and session.messages[i].role == "tool_call":
                    m = session.messages[i]
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=m.tool_name,
                                args=m.args,
                                id=m.tool_call_id
                            )
                        )
                    )
                    if m.thought_signature:
                        thought_sig = m.thought_signature
                    i += 1
                
                content_obj = types.Content(role="model", parts=parts)
                if thought_sig:
                    content_obj.parts[0].thought_signature = thought_sig
                contents.append(content_obj)
                
            elif message.role == "tool-result":
                parts = []
                while i < n and session.messages[i].role == "tool-result":
                    m = session.messages[i]
                    try:
                        response_dict = json.loads(m.content)
                        if not isinstance(response_dict, dict):
                            response_dict = {"result": m.content}
                    except Exception:
                        response_dict = {"result": m.content}
                    
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=m.tool_name or "",
                                response=response_dict,
                                id=m.tool_call_id
                            )
                        )
                    )
                    i += 1
                
                contents.append(
                    types.Content(
                        role="user",
                        parts=parts
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role=message.role,
                        parts=[types.Part.from_text(text=message.content or "")]
                    )
                )
                i += 1


        logger.info(f"\nBuilt native contents with {len(contents)} messages.")
        for idx, c in enumerate(contents):
            try:
                c_dict = c.model_dump(exclude_none=True)
                for part in c_dict.get("parts", []):
                    if part.get("thought_signature") and isinstance(part["thought_signature"], bytes):
                        import base64
                        part["thought_signature"] = base64.b64encode(part["thought_signature"]).decode("utf-8")
                logger.info(f"  Content #{idx}: {c_dict}")
            except Exception as e:
                logger.info(f"  Content #{idx}: (dump error: {e}) {c}")
        return contents