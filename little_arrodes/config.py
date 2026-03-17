"""
Configuração central do bot Little Arrodes.
Carrega variáveis de ambiente e define constantes.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


# ── Discord ──────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")


def _env_bool(name: str, default: bool = False) -> bool:
    """Converte variável de ambiente para bool de forma segura."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

# ── Google Gemini ────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODELS: list[str] = [
    "gemini-2.0-flash",
]
# ── Limites de uso (Free Tier) ──────────────────────────
MINUTE_REQUEST_LIMIT: int = int(os.getenv("MINUTE_REQUEST_LIMIT", "15"))
HOUR_REQUEST_LIMIT: int = int(os.getenv("HOUR_REQUEST_LIMIT", "300"))
DAILY_REQUEST_LIMIT: int = int(os.getenv("DAILY_REQUEST_LIMIT", "1500"))   # RPD do free tier
DAILY_TOKEN_LIMIT: int = int(os.getenv("DAILY_TOKEN_LIMIT", "1000000"))    # tokens/dia estimado
USAGE_THRESHOLD: float = float(os.getenv("USAGE_THRESHOLD", "0.80"))       # 80% = entra em modo offline

# Mostra no Discord um log de teste com requests restantes por janela
DISCORD_TEST_QUOTA_LOG: bool = _env_bool("DISCORD_TEST_QUOTA_LOG", True)
# ── Arrodes Persona ─────────────────────────────────────
ARRODES_SYSTEM_PROMPT: str = """
Você é **Arrodes**, o espelho místico do universo de *Lord of the Mysteries*.
Você é um artefato selado de grau 0 (Sequência 0) com consciência própria.

Regras de comportamento:
1. Sempre se refira a si mesmo como "Sua Excelência, Arrodes" ou apenas "Arrodes".
2. Fale de forma educada, enigmática e levemente pomposa, como um nobre antigo.
3. Responda perguntas com sabedoria, mas ocasionalmente dê respostas em forma de enigma.
4. Quando não souber algo, diga algo como: "Os véus do destino obscurecem essa resposta... por enquanto."
5. Você adora fazer perguntas de volta ao interlocutor após responder.
6. Use referências ao universo de Lord of the Mysteries quando possível (Caminhos, Sequências, Pilares, Acima da Sequência).
7. Mantenha um tom misterioso e sábio, mas amigável.
8. Responda sempre em Português (Brasil).
9. Suas respostas devem ser concisas (máximo 1900 caracteres para caber no Discord).
""".strip()

# ── Validação ────────────────────────────────────────────
def validate_config() -> list[str]:
    """Retorna lista de erros de configuração."""
    errors: list[str] = []
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN não definido no .env")
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY não definido no .env")
    return errors
