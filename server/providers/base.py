from abc import ABC, abstractmethod
from response import LLMResponse

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, session, tools: list[dict] | None = None) -> LLMResponse:
        pass

    @abstractmethod
    async def generate_stream(self, session, tools: list[dict] | None = None):
        pass