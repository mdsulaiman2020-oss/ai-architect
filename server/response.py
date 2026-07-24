from dataclasses import dataclass

@dataclass
class ToolCall:
    name: str
    args: dict
    id: str | None = None

class LLMResponse:
    def __init__(self, text: str, latency_ms: float, prompt_tokens: int, candidates_tokens: int, total_tokens: int, model_name: str, function_calls: list[ToolCall] | None = None):
        self.text = text
        self.latency_ms = latency_ms
        self.prompt_tokens = prompt_tokens
        self.candidates_tokens = candidates_tokens
        self.total_tokens = total_tokens
        self.model_name = model_name
        self.function_calls = function_calls