import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from google import genai

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    text: str
    latency_ms: float
    prompt_tokens: int
    candidates_tokens: int
    total_tokens: int
    model_name: str

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> LLMResponse:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)

    def generate(self, prompt: str) -> LLMResponse:
        logger.info(f"Calling Gemini API with model: {self.model_name}...")
        logger.info(f"Prompt: '{prompt}'")
        
        start_time = time.time()
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
        except Exception as e:
            logger.error(f"API Call failed: {e}")
            raise
            
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
        
        return LLMResponse(
            text=response.text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            total_tokens=total_tokens,
            model_name=used_model
        )
