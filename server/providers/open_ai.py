import time
import logging
import json

from openai import AsyncOpenAI
from response import LLMResponse, ToolCall
from .base import LLMProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = AsyncOpenAI(api_key=self.api_key)
        
    async def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        messages = session if isinstance(session, list) else self._build_request(session)
        openai_tools = self._to_openai_tools(tools)
        
        start_time = time.time()
        
        params = {
            "model": self.model_name,
            "messages": messages,
        }
        if openai_tools:
            params["tools"] = openai_tools
            
        logger.info(f"Sending request to OpenAI with model {self.model_name}")
        response = await self.client.chat.completions.create(**params)
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        prompt_tokens = 0
        candidates_tokens = 0
        total_tokens = 0
        
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            candidates_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
        response_text = response.choices[0].message.content or ""
        
        generic_tool_calls = []
        if response.choices and response.choices[0].message.tool_calls:
            for tc in response.choices[0].message.tool_calls:
                if tc.type == "function":
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception as e:
                        logger.error(f"Error parsing tool call arguments: {e}")
                        args = {}
                    generic_tool_calls.append(
                        ToolCall(
                            name=tc.function.name,
                            args=args,
                            id=tc.id
                        )
                    )
        else:
            generic_tool_calls = None
            
        return LLMResponse(
            text=response_text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            total_tokens=total_tokens,
            model_name=self.model_name,
            function_calls=generic_tool_calls,
        )

    async def generate_stream(self, session, tools: list[dict] | None = None):
        messages = session if isinstance(session, list) else self._build_request(session)
        openai_tools = self._to_openai_tools(tools)
        
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }
        if openai_tools:
            params["tools"] = openai_tools

        response = await self.client.chat.completions.create(**params)
        
        # Tool call aggregation across chunks
        current_tool_calls = {}

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                
                if delta.content:
                    yield {"type": "text", "content": delta.content}
                    
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.index not in current_tool_calls:
                            current_tool_calls[tc.index] = {"id": tc.id, "name": tc.function.name, "arguments": ""}
                        if tc.function.arguments:
                            current_tool_calls[tc.index]["arguments"] += tc.function.arguments
        
        if current_tool_calls:
            generic_tool_calls = []
            for tc_index in sorted(current_tool_calls.keys()):
                tc = current_tool_calls[tc_index]
                try:
                    args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}
                generic_tool_calls.append(
                    ToolCall(
                        name=tc["name"],
                        args=args,
                        id=tc["id"]
                    )
                )
            yield {"type": "tool_calls", "content": generic_tool_calls}


    def _to_openai_tools(self, tools: list[dict] | None):
        if not tools:
            return None
            
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters") or {
                        "type": "object",
                        "properties": {},
                    }
                }
            })
        return openai_tools

    def _build_request(self, session) -> list[dict]:
        if not session.messages:
            return []

        logger.info("\n=== Rebuilding Request for OpenAI ===")
        for idx, m in enumerate(session.messages):
            logger.info(f"Msg #{idx}: role={m.role}, tool_name={m.tool_name}, id={m.tool_call_id}")

        messages = []
        i = 0
        n = len(session.messages)
        while i < n:
            message = session.messages[i]
            
            if message.role == "user":
                messages.append({
                    "role": "user",
                    "content": message.content
                })
                i += 1
            elif message.role == "assistant":
                messages.append({
                    "role": "assistant",
                    "content": message.content
                })
                i += 1
            elif message.role == "tool_call":
                tool_calls = []
                while i < n and session.messages[i].role == "tool_call":
                    m = session.messages[i]
                    tool_calls.append({
                        "id": m.tool_call_id or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": m.tool_name,
                            "arguments": json.dumps(m.args) if isinstance(m.args, dict) else (m.args or "{}")
                        }
                    })
                    i += 1
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls
                })
            elif message.role == "tool-result":
                while i < n and session.messages[i].role == "tool-result":
                    m = session.messages[i]
                    messages.append({
                        "role": "tool",
                        "tool_call_id": m.tool_call_id or f"call_{i}",
                        "name": m.tool_name,
                        "content": m.content
                    })
                    i += 1
            else:
                messages.append({
                    "role": message.role,
                    "content": message.content
                })
                i += 1

        logger.info(f"Built OpenAI messages with {len(messages)} items.")
        for idx, msg in enumerate(messages):
            # Print simple summary of the mapped message
            logger.info(f"  Mapped Msg #{idx}: role={msg.get('role')} keys={list(msg.keys())}")
        return messages
