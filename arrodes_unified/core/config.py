"""
Configuracao centralizada do Arrodes Unified.
Carrega variaveis de ambiente e define constantes para todos os modos.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# ── Discord ──────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

# ── Modo de Execucao ─────────────────────────────────────────
MODE: str = os.getenv("MODE", "combined").lower()

# ── Google Gemini (Tier 1) ───────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODELS: list[str] = ["gemini-2.0-flash"]

# ── Groq (Tier 2) ───────────────────────────────────────────
GROQ_KEYS: list[str] = [
    k for k in [
        os.getenv("GROQ_KEY_1"),
        os.getenv("GROQ_KEY_2"),
        os.getenv("GROQ_KEY_3"),
    ] if k
]
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Limites de uso (Free Tier Gemini) ────────────────────────
MINUTE_REQUEST_LIMIT: int = int(os.getenv("MINUTE_REQUEST_LIMIT", "15"))
HOUR_REQUEST_LIMIT: int = int(os.getenv("HOUR_REQUEST_LIMIT", "300"))
DAILY_REQUEST_LIMIT: int = int(os.getenv("DAILY_REQUEST_LIMIT", "1500"))
DAILY_TOKEN_LIMIT: int = int(os.getenv("DAILY_TOKEN_LIMIT", "1000000"))
USAGE_THRESHOLD: float = float(os.getenv("USAGE_THRESHOLD", "0.80"))

# ── API (modo combined) ─────────────────────────────────────
TIER2_API_PORT: int = int(os.getenv("TIER2_API_PORT", "8080"))

# ── RAG ──────────────────────────────────────────────────────
RAG_ALPHA: float = float(os.getenv("RAG_ALPHA", "0.7"))
RAG_CONFIDENCE_THRESHOLD: float = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.6"))

# ── Debug ────────────────────────────────────────────────────
DISCORD_TEST_QUOTA_LOG: bool = _env_bool("DISCORD_TEST_QUOTA_LOG", True)

# ── Caminhos ─────────────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR: str = os.path.join(BASE_DIR, "data")
LORE_DIR: str = os.path.join(DATA_DIR, "lore")
LOG_DIR: str = os.path.join(BASE_DIR, "logs")


def validate_config(mode: str | None = None) -> list[str]:
    """Retorna lista de erros de configuracao para o modo especificado."""
    _mode = mode or MODE
    errors: list[str] = []

    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN nao definido no .env")

    if _mode in ("little", "combined") and not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY necessaria para modo '%s'" % _mode)

    if _mode in ("arrodes", "combined") and not GROQ_KEYS:
        errors.append("Pelo menos GROQ_KEY_1 necessaria para modo '%s'" % _mode)

    if _mode not in ("little", "arrodes", "combined"):
        errors.append("MODE invalido: '%s'. Use: little, arrodes ou combined" % _mode)

    return errors
