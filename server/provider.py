import logging

from config import Config

logger = logging.getLogger(__name__)

def get_provider():
    logger.info(f"provider type: {Config.PROVIDER_TYPE}")

    if Config.PROVIDER_TYPE == "gemini":
        from providers.gemini import GeminiProvider

        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")

        return GeminiProvider(api_key=Config.GEMINI_API_KEY, model_name=Config.MODEL_NAME)
    elif Config.PROVIDER_TYPE == "openai":
        from providers.open_ai import OpenAIProvider

        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")

        return OpenAIProvider(api_key=Config.OPENAI_API_KEY, model_name=Config.MODEL_NAME)
    else:
        raise ValueError(f"Unsupported provider type: {Config.PROVIDER_TYPE}")    
