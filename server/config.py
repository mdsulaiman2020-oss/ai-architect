import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROVIDER_TYPE = os.environ.get("PROVIDER_TYPE", "gemini").lower()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    
    # Dynamic default model based on the selected provider type
    _default_model = "gpt-4o-mini" if PROVIDER_TYPE == "openai" else "gemini-3.5-flash-lite"
    MODEL_NAME = os.environ.get("MODEL_NAME", _default_model)

    MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "digiassess-prod")

