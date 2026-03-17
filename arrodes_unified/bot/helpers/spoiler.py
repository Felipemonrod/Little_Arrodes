"""
Filtro de spoiler para proteger conteudo sensivel do lore.
Envolve em || spoiler || mencoes a Sequencias criticas (0-7).
"""

import re

# Regex para detectar mencoes a Sequencias 0-7
_SPOILER_PATTERN = re.compile(r"sequ[eê]ncia [0-7]", re.IGNORECASE)


def apply_spoiler_filter(text: str) -> str:
    """
    Se o texto menciona Sequencias de 0 a 7, envolve em spoiler tags do Discord.

    Args:
        text: Texto da resposta do bot.

    Returns:
        Texto original ou envolvido em || spoiler ||.
    """
    if _SPOILER_PATTERN.search(text):
        return f"|| {text} ||"
    return text
