import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # e.g. http://127.0.0.1:11434/v1 for Ollama
MODEL = os.getenv("CREER_MODEL", "gpt-4o-mini")
CREER_OFFLINE = os.getenv("CREER_OFFLINE", "").lower() in ("1", "true", "yes")
# Optional extra packs directory (merged with backend/packs; user overrides on id collision)
CREER_PACKS_DIR = os.getenv("CREER_PACKS_DIR", "").strip() or None
# Optional public base URL for absolute registry download links
CREER_PUBLIC_BASE_URL = os.getenv("CREER_PUBLIC_BASE_URL", "").strip() or None
# Comma-separated peer Creer registry base URLs for federation (v0.8+)
CREER_REGISTRY_PEERS = os.getenv("CREER_REGISTRY_PEERS", "").strip() or None
# Optional token for mutating registry/pack write endpoints (v1.0+)
# When set, POST /packs/install, DELETE /packs/{id}, POST /registry/peers/probe require auth
CREER_REGISTRY_TOKEN = os.getenv("CREER_REGISTRY_TOKEN", "").strip() or None
