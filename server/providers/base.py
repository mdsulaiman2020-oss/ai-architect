from abc import ABC, abstractmethod
from response import LLMResponse

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        pass

    @abstractmethod
    def generate_stream(self, session, tools: list[dict] | None = None):
        pass