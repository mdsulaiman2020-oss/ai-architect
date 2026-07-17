import logging
import sys
from config import Config
from provider import GeminiProvider

# Setup logging: limit root logger to WARNING to avoid 3rd-party library logs, but set ours to INFO
logging.basicConfig(level=logging.WARNING, stream=sys.stdout, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.getLogger("provider").setLevel(logging.INFO)

def get_provider():
    if Config.PROVIDER_TYPE == "gemini":
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            logger.error("Error: GEMINI_API_KEY environment variable is not set.")
            logger.error("Please set it securely (e.g., set GEMINI_API_KEY=your_key_here) before running this script.")
            return None
        return GeminiProvider(api_key=api_key, model_name=Config.MODEL_NAME)
    else:
        logger.error(f"Error: Unsupported PROVIDER_TYPE '{Config.PROVIDER_TYPE}'")
        return None

def main():
    # Initialize client based on config
    provider = get_provider()
    if not provider:
        return
    
    prompt = "Tell me a very short joke."
    
    # 2. Call provider API & measure latency
    try:
        response = provider.generate(prompt)
    except Exception:
        return

    # 3. Print response
    logger.info("\n--- Response ---")
    logger.info(response.text)
    logger.info("----------------\n")

    # 4. Print metrics
    logger.info("--- Metrics ---")
    logger.info(f"Latency: {response.latency_ms:.2f} ms")
    
    logger.info("Token usage:")
    logger.info(f"  - Prompt tokens: {response.prompt_tokens}")
    logger.info(f"  - Candidate tokens: {response.candidates_tokens}")
    logger.info(f"  - Total tokens: {response.total_tokens}")
    
    logger.info(f"Model name: {response.model_name}")

if __name__ == "__main__":
    main()
