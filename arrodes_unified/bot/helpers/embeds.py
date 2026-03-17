"""
Builders de embeds Discord para respostas do Arrodes.
"""

import discord


ARRODES_COLOR = discord.Color.from_rgb(148, 103, 189)


def build_response_embed(
    question: str,
    answer: str,
    tier: str = "",
) -> discord.Embed:
    """
    Cria embed formatado para resposta do Arrodes.

    Args:
        question: Pergunta do usuario.
        answer: Resposta do Arrodes.
        tier: Indicador do tier que respondeu (para debug).
    """
    embed = discord.Embed(title="Arrodes Responde", color=ARRODES_COLOR)
    embed.add_field(name="Pergunta", value=question[:1024], inline=False)
    embed.add_field(name="Resposta", value=answer[:1024], inline=False)
    if tier:
        embed.set_footer(text=f"via {tier}")
    return embed


def build_usage_embed(status: dict) -> discord.Embed:
    """Cria embed com status de uso da API."""

    def progress_bar(percent: float) -> str:
        filled = int(percent / 10)
        bar = "=" * filled + "-" * (10 - filled)
        return f"`[{bar}]` {percent:.1f}%"

    if status["is_offline"]:
        color = discord.Color.red()
        status_text = "OFFLINE (respostas prontas)"
    elif status["request_percent"] >= 60 or status["token_percent"] >= 60:
        color = discord.Color.orange()
        status_text = "Uso elevado"
    else:
        color = discord.Color.green()
        status_text = "Online"

    embed = discord.Embed(
        title="Uso da API",
        description=f"**Status:** {status_text}",
        color=color,
    )
    embed.add_field(
        name="Requests",
        value=(
            f"{progress_bar(status['request_percent'])}\n"
            f"`{status['requests']:,}` / `{status['request_limit']:,}` req/dia"
        ),
        inline=False,
    )
    embed.add_field(
        name="Tokens",
        value=(
            f"{progress_bar(status['token_percent'])}\n"
            f"`{status['tokens']:,}` / `{status['token_limit']:,}` tokens/dia"
        ),
        inline=False,
    )
    embed.add_field(
        name="Config",
        value=f"Threshold: **{status['threshold_percent']}%**",
        inline=False,
    )
    embed.set_footer(text=f"Data: {status['date']}")
    return embed
