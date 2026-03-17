"""
Little Arrodes — Bot Discord inspirado no Arrodes de Lord of the Mysteries.
Ponto de entrada principal (Docker).
"""

import asyncio
import sys

import discord
from discord.ext import commands

import config
from utils.logger import setup_logger

# ── Logger ───────────────────────────────────────────────
log = setup_logger()

# ── Validação de configuração ────────────────────────────
errors = config.validate_config()
if errors:
    for err in errors:
        log.critical("CONFIG ERROR: %s", err)
    log.critical("Corrija as variáveis de ambiente e tente novamente.")
    sys.exit(1)

# ── Intents ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

# ── Bot ──────────────────────────────────────────────────
bot = commands.Bot(
    command_prefix=config.BOT_PREFIX,
    intents=intents,
    description="🔮 Arrodes — O espelho místico de Lord of the Mysteries",
    help_command=commands.DefaultHelpCommand(no_category="Geral"),
)

# ── Lista de Cogs para carregar ──────────────────────────
INITIAL_COGS = [
    "cogs.arrodes",
    "cogs.admin",
]


# ── Eventos ──────────────────────────────────────────────
@bot.event
async def on_ready() -> None:
    log.info("=" * 50)
    log.info("Bot conectado como: %s (ID: %s)", bot.user, bot.user.id)
    log.info("Servidores: %d", len(bot.guilds))
    log.info("discord.py v%s", discord.__version__)
    log.info("=" * 50)

    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="através do espelho | #call_arrodes",
    )
    await bot.change_presence(activity=activity)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(
            f"⚠️ Argumento faltando: `{error.param.name}`\n"
            f"Use `{config.BOT_PREFIX}help {ctx.command}` para mais informações.",
            mention_author=False,
        )
        log.warning("Argumento faltando em %s: %s", ctx.command, error)
        return

    if isinstance(error, commands.NotOwner):
        await ctx.reply("🚫 Apenas o dono do bot pode usar este comando.", mention_author=False)
        log.warning("Acesso negado para %s no comando %s", ctx.author, ctx.command)
        return

    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(
            f"⏳ Comando em cooldown. Tente novamente em {error.retry_after:.1f}s.",
            mention_author=False,
        )
        return

    log.error("Erro não tratado no comando '%s': %s", ctx.command, error, exc_info=error)
    await ctx.reply(
        "❌ Ocorreu um erro inesperado. Os logs foram registrados.",
        mention_author=False,
    )


# ── Startup ──────────────────────────────────────────────
async def main() -> None:
    async with bot:
        for cog in INITIAL_COGS:
            try:
                await bot.load_extension(cog)
                log.info("Cog '%s' carregado.", cog)
            except Exception as e:
                log.error("Falha ao carregar cog '%s': %s", cog, e, exc_info=True)

        log.info("Iniciando bot...")
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot encerrado pelo usuário (Ctrl+C).")
    except Exception as e:
        log.critical("Erro fatal: %s", e, exc_info=True)
        sys.exit(1)
