import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # e.g. http://127.0.0.1:11434/v1 for Ollama
MODEL = os.getenv("CREER_MODEL", "gpt-4o-mini")
CREER_OFFLINE = os.getenv("CREER_OFFLINE", "").lower() in ("1", "true", "yes")
