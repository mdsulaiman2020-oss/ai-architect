import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from config import Config
from provider import get_provider

def main():
    key = Config.GEMINI_API_KEY
    if key:
        logger.info("GEMINI_API_KEY is set")
        logger.info("Calling Gemini API...")
        provider = get_provider()
        try:
            response = provider.generate("Say hello world!")
            logger.info(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
    else:
        logger.error("GEMINI_API_KEY is not set")

if __name__ == "__main__":
    main()
