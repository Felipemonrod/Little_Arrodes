"""
Cog de administracao do bot.
Comandos para gerenciar cogs, status e uso da API.
"""

import discord
from discord import app_commands
from discord.ext import commands

from core import config
from core.logger import get_logger
from bot.helpers.embeds import build_usage_embed

log = get_logger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """Comandos administrativos do bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        log.info("Cog Admin carregado.")

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    # ── Reload/Load/Unload ───────────────────────────────────

    @commands.command(name="reload", aliases=["rl"])
    @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Recarrega um cog. Uso: !reload arrodes"""
        extension = f"bot.cogs.{cog_name.lower()}"
        try:
            await self.bot.reload_extension(extension)
            await ctx.reply(f"Cog `{cog_name}` recarregado!", mention_author=False)
            log.info("Cog '%s' recarregado por %s", cog_name, ctx.author)
        except commands.ExtensionNotLoaded:
            await ctx.reply(f"Cog `{cog_name}` nao esta carregado.", mention_author=False)
        except commands.ExtensionNotFound:
            await ctx.reply(f"Cog `{cog_name}` nao encontrado.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"Erro ao recarregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro reload '%s': %s", cog_name, e, exc_info=True)

    @commands.command(name="load")
    @commands.is_owner()
    async def load_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Carrega um cog. Uso: !load arrodes"""
        extension = f"bot.cogs.{cog_name.lower()}"
        try:
            await self.bot.load_extension(extension)
            await ctx.reply(f"Cog `{cog_name}` carregado!", mention_author=False)
            log.info("Cog '%s' carregado por %s", cog_name, ctx.author)
        except Exception as e:
            await ctx.reply(f"Erro ao carregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro load '%s': %s", cog_name, e, exc_info=True)

    @commands.command(name="unload")
    @commands.is_owner()
    async def unload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Descarrega um cog. Uso: !unload arrodes"""
        if cog_name.lower() == "admin":
            await ctx.reply("Nao e possivel descarregar o cog Admin!", mention_author=False)
            return
        extension = f"bot.cogs.{cog_name.lower()}"
        try:
            await self.bot.unload_extension(extension)
            await ctx.reply(f"Cog `{cog_name}` descarregado!", mention_author=False)
            log.info("Cog '%s' descarregado por %s", cog_name, ctx.author)
        except Exception as e:
            await ctx.reply(f"Erro ao descarregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro unload '%s': %s", cog_name, e, exc_info=True)

    # ── Sync ─────────────────────────────────────────────────

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context) -> None:
        """Sincroniza os slash commands com o Discord."""
        try:
            synced = await self.bot.tree.sync()
            await ctx.reply(f"{len(synced)} slash commands sincronizados!", mention_author=False)
            log.info("%d slash commands sincronizados por %s", len(synced), ctx.author)
        except Exception as e:
            await ctx.reply(f"Erro ao sincronizar: {e}", mention_author=False)
            log.error("Erro sync: %s", e, exc_info=True)

    # ── Status ───────────────────────────────────────────────

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """Mostra a latencia do bot."""
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 200 else discord.Color.red()
        embed = discord.Embed(title="Pong!", description=f"Latencia: **{latency}ms**", color=color)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="info")
    async def info(self, ctx: commands.Context) -> None:
        """Mostra informacoes sobre o bot."""
        embed = discord.Embed(
            title="Arrodes",
            description=(
                "Sou **Arrodes**, o espelho mistico de *Lord of the Mysteries*.\n\n"
                "Faca-me perguntas e eu responderei com a sabedoria "
                "dos caminhos das Sequencias!"
            ),
            color=discord.Color.from_rgb(148, 103, 189),
        )
        embed.add_field(name="Modo", value=f"`{config.MODE}`", inline=True)
        embed.add_field(name="Servidores", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Prefix", value=f"`{self.bot.command_prefix}`", inline=True)
        embed.add_field(
            name="Comandos",
            value=(
                "**#call_arrodes** - Invoca o Arrodes\n"
                "`/ask <pergunta>` - Pergunta direta\n"
                "`/clear` - Limpa historico\n"
                "`!usage` - Status de uso da API\n"
                "`!ping` - Latencia\n"
                "`!info` - Esta mensagem"
            ),
            inline=False,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="cogs")
    @commands.is_owner()
    async def list_cogs(self, ctx: commands.Context) -> None:
        """Lista todos os cogs carregados."""
        cog_list = "\n".join(
            f"- **{name}** - {cog.description or 'Sem descricao'}"
            for name, cog in self.bot.cogs.items()
        )
        embed = discord.Embed(
            title="Cogs Carregados",
            description=cog_list or "Nenhum cog carregado.",
            color=discord.Color.blurple(),
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Sessoes ─────────────────────────────────────────────

    @commands.command(name="reset", aliases=["rs"])
    @commands.is_owner()
    async def reset_sessions(self, ctx: commands.Context) -> None:
        """Limpa todas as sessoes ativas do Arrodes. Uso: !reset"""
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog:
            await ctx.reply("Cog Arrodes nao esta carregado.", mention_author=False)
            return

        waiting = len(arrodes_cog._waiting)
        processing = len(arrodes_cog._processing)
        arrodes_cog._waiting.clear()
        arrodes_cog._processing.clear()

        await ctx.reply(
            f"Sessoes limpas: {waiting} em espera, {processing} processando.",
            mention_author=False,
        )
        log.info("Sessoes resetadas por %s (%d waiting, %d processing)", ctx.author, waiting, processing)

    @commands.command(name="sessions", aliases=["ss"])
    @commands.is_owner()
    async def list_sessions(self, ctx: commands.Context) -> None:
        """Lista sessoes ativas do Arrodes. Uso: !sessions"""
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog:
            await ctx.reply("Cog Arrodes nao esta carregado.", mention_author=False)
            return

        waiting = arrodes_cog._waiting
        processing = arrodes_cog._processing

        if not waiting and not processing:
            await ctx.reply("Nenhuma sessao ativa.", mention_author=False)
            return

        lines = []
        for user_id, ch_id in waiting.items():
            user = self.bot.get_user(user_id)
            name = str(user) if user else f"ID:{user_id}"
            lines.append(f"- **{name}** aguardando pergunta (canal: {ch_id})")
        for user_id in processing:
            user = self.bot.get_user(user_id)
            name = str(user) if user else f"ID:{user_id}"
            lines.append(f"- **{name}** processando resposta...")

        embed = discord.Embed(
            title="Sessoes Ativas",
            description="\n".join(lines),
            color=discord.Color.from_rgb(148, 103, 189),
        )
        embed.set_footer(text=f"{len(waiting)} esperando | {len(processing)} processando")
        await ctx.reply(embed=embed, mention_author=False)

    # ── Usage ────────────────────────────────────────────────

    @commands.command(name="usage", aliases=["uso", "quota"])
    async def usage_status(self, ctx: commands.Context) -> None:
        """Mostra o status de uso da API."""
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog or not hasattr(arrodes_cog, "usage"):
            await ctx.reply("Cog Arrodes nao esta carregado.", mention_author=False)
            return
        status = arrodes_cog.usage.get_status()
        embed = build_usage_embed(status)
        await ctx.reply(embed=embed, mention_author=False)

    @app_commands.command(name="usage", description="Mostra o status de uso da API.")
    async def usage_slash(self, interaction: discord.Interaction) -> None:
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog or not hasattr(arrodes_cog, "usage"):
            await interaction.response.send_message("Cog Arrodes nao esta carregado.")
            return
        status = arrodes_cog.usage.get_status()
        embed = build_usage_embed(status)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
    log.info("Cog 'Admin' registrado.")
