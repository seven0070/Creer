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


def _clamp_federation_max_hops(raw: str | None) -> int:
    """Parse CREER_FEDERATION_MAX_HOPS; default 1, clamp to 0–2."""
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 1
    return max(0, min(2, value))


# Max discovery hops for federated expand (v1.1+). 0 = no expand (configured peers only).
CREER_FEDERATION_MAX_HOPS = _clamp_federation_max_hops(
    os.getenv("CREER_FEDERATION_MAX_HOPS", "1")
)
# Comma-separated hostnames/URLs; if non-empty, ONLY these peers may be contacted
CREER_PEER_ALLOWLIST = os.getenv("CREER_PEER_ALLOWLIST", "").strip()
# Comma-separated hostnames/URLs always blocked
CREER_PEER_DENYLIST = os.getenv("CREER_PEER_DENYLIST", "").strip()
# When false (default), block private/link-local/loopback/metadata for outbound peers
CREER_ALLOW_PRIVATE_PEERS = os.getenv("CREER_ALLOW_PRIVATE_PEERS", "").lower() in (
    "1",
    "true",
    "yes",
)
