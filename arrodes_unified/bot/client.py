"""
Cliente Discord do Arrodes Unified.
Inicializa o bot, carrega cogs e gerencia eventos.
"""

import asyncio
import sys

import discord
from discord.ext import commands

from core import config
from core.logger import setup_logger

log = setup_logger()


def create_bot() -> commands.Bot:
    """Cria e configura a instancia do bot Discord."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix=config.BOT_PREFIX,
        intents=intents,
        description="Arrodes - O espelho mistico de Lord of the Mysteries",
        help_command=commands.DefaultHelpCommand(no_category="Geral"),
    )

    @bot.event
    async def on_ready() -> None:
        log.info("=" * 50)
        log.info("Bot conectado como: %s (ID: %s)", bot.user, bot.user.id)
        log.info("Servidores: %d", len(bot.guilds))
        log.info("Modo: %s", config.MODE)
        log.info("discord.py v%s", discord.__version__)
        log.info("=" * 50)

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="atraves do espelho | #call_arrodes",
        )
        await bot.change_presence(activity=activity)

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"Argumento faltando: `{error.param.name}`\n"
                f"Use `{config.BOT_PREFIX}help {ctx.command}` para mais info.",
                mention_author=False,
            )
            return
        if isinstance(error, commands.NotOwner):
            await ctx.reply("Apenas o dono do bot pode usar este comando.", mention_author=False)
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"Comando em cooldown. Tente em {error.retry_after:.1f}s.",
                mention_author=False,
            )
            return
        log.error("Erro no comando '%s': %s", ctx.command, error, exc_info=error)
        await ctx.reply("Ocorreu um erro inesperado. Os logs foram registrados.", mention_author=False)

    return bot


INITIAL_COGS = [
    "bot.cogs.arrodes",
    "bot.cogs.admin",
]


async def run_bot() -> None:
    """Funcao principal: carrega cogs e inicia o bot."""
    errors = config.validate_config()
    if errors:
        for err in errors:
            log.critical("CONFIG ERROR: %s", err)
        log.critical("Corrija o .env e tente novamente.")
        sys.exit(1)

    bot = create_bot()

    async with bot:
        for cog in INITIAL_COGS:
            try:
                await bot.load_extension(cog)
                log.info("Cog '%s' carregado.", cog)
            except Exception as e:
                log.error("Falha ao carregar cog '%s': %s", cog, e, exc_info=True)

        log.info("Iniciando bot (modo: %s)...", config.MODE)
        await bot.start(config.DISCORD_TOKEN)
