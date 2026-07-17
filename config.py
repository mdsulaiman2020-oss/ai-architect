import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROVIDER_TYPE = os.environ.get("PROVIDER_TYPE", "gemini").lower()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    MODEL_NAME = "gemini-2.5-flash"
