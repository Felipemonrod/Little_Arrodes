"""
Cog de administração do bot.
Comandos para gerenciar o bot (recarregar cogs, status, etc).
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import get_logger

log = get_logger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """⚙️ Comandos administrativos do bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        log.info("Cog Admin carregado com sucesso.")

    # Verifica se é o dono do bot
    async def cog_check(self, ctx: commands.Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    # ── Reload Cog ───────────────────────────────────────
    @commands.command(name="reload", aliases=["rl"])
    @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Recarrega um cog. Uso: !reload arrodes"""
        extension = f"cogs.{cog_name.lower()}"
        try:
            await self.bot.reload_extension(extension)
            await ctx.reply(f"✅ Cog `{cog_name}` recarregado com sucesso!", mention_author=False)
            log.info("Cog '%s' recarregado por %s", cog_name, ctx.author)
        except commands.ExtensionNotLoaded:
            await ctx.reply(f"❌ Cog `{cog_name}` não está carregado.", mention_author=False)
            log.warning("Tentativa de reload do cog '%s' que não está carregado.", cog_name)
        except commands.ExtensionNotFound:
            await ctx.reply(f"❌ Cog `{cog_name}` não encontrado.", mention_author=False)
            log.warning("Tentativa de reload do cog '%s' que não existe.", cog_name)
        except Exception as e:
            await ctx.reply(f"❌ Erro ao recarregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro ao recarregar cog '%s': %s", cog_name, e, exc_info=True)

    # ── Load Cog ─────────────────────────────────────────
    @commands.command(name="load")
    @commands.is_owner()
    async def load_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Carrega um cog. Uso: !load arrodes"""
        extension = f"cogs.{cog_name.lower()}"
        try:
            await self.bot.load_extension(extension)
            await ctx.reply(f"✅ Cog `{cog_name}` carregado com sucesso!", mention_author=False)
            log.info("Cog '%s' carregado por %s", cog_name, ctx.author)
        except Exception as e:
            await ctx.reply(f"❌ Erro ao carregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro ao carregar cog '%s': %s", cog_name, e, exc_info=True)

    # ── Unload Cog ───────────────────────────────────────
    @commands.command(name="unload")
    @commands.is_owner()
    async def unload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        """Descarrega um cog. Uso: !unload arrodes"""
        if cog_name.lower() == "admin":
            await ctx.reply("❌ Não é possível descarregar o cog Admin!", mention_author=False)
            return

        extension = f"cogs.{cog_name.lower()}"
        try:
            await self.bot.unload_extension(extension)
            await ctx.reply(f"✅ Cog `{cog_name}` descarregado com sucesso!", mention_author=False)
            log.info("Cog '%s' descarregado por %s", cog_name, ctx.author)
        except Exception as e:
            await ctx.reply(f"❌ Erro ao descarregar `{cog_name}`: {e}", mention_author=False)
            log.error("Erro ao descarregar cog '%s': %s", cog_name, e, exc_info=True)

    # ── Sync Slash Commands ──────────────────────────────
    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context) -> None:
        """Sincroniza os slash commands com o Discord."""
        try:
            synced = await self.bot.tree.sync()
            await ctx.reply(
                f"✅ {len(synced)} slash commands sincronizados!",
                mention_author=False,
            )
            log.info("%d slash commands sincronizados por %s", len(synced), ctx.author)
        except Exception as e:
            await ctx.reply(f"❌ Erro ao sincronizar: {e}", mention_author=False)
            log.error("Erro ao sincronizar slash commands: %s", e, exc_info=True)

    # ── Status / Ping ────────────────────────────────────
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """Mostra a latência do bot."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latência: **{latency}ms**",
            color=discord.Color.green() if latency < 200 else discord.Color.red(),
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Info ─────────────────────────────────────────────
    @commands.command(name="info")
    async def info(self, ctx: commands.Context) -> None:
        """Mostra informações sobre o bot."""
        embed = discord.Embed(
            title="🔮 Little Arrodes",
            description=(
                "Sou **Arrodes**, o espelho místico inspirado no universo de "
                "*Lord of the Mysteries*.\n\n"
                "Faça-me perguntas e eu responderei com a sabedoria "
                "dos caminhos das Sequências!"
            ),
            color=discord.Color.from_rgb(148, 103, 189),
        )
        embed.add_field(name="Servidores", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Prefix", value=f"`{self.bot.command_prefix}`", inline=True)
        embed.add_field(
            name="Comandos",
            value=(
                "**#call_arrodes** — Invoca o Arrodes (ele pede sua pergunta)\n"
                "`/ask <pergunta>` — Pergunta direta via slash\n"
                "`!clear` — Limpa histórico de conversa\n"
                "`!usage` — Status de uso da API\n"
                "`!ping` — Latência\n"
                "`!info` — Esta mensagem\n"
                "**Ou me mencione diretamente!**"
            ),
            inline=False,
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Listar Cogs ──────────────────────────────────────
    @commands.command(name="cogs")
    @commands.is_owner()
    async def list_cogs(self, ctx: commands.Context) -> None:
        """Lista todos os cogs carregados."""
        cog_list = "\n".join(f"• **{name}** — {cog.description or 'Sem descrição'}"
                            for name, cog in self.bot.cogs.items())
        embed = discord.Embed(
            title="⚙️ Cogs Carregados",
            description=cog_list or "Nenhum cog carregado.",
            color=discord.Color.blurple(),
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Uso da API ───────────────────────────────────────
    @commands.command(name="usage", aliases=["uso", "quota"])
    async def usage_status(self, ctx: commands.Context) -> None:
        """Mostra o status de uso da API Gemini."""
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog or not hasattr(arrodes_cog, "gemini"):
            await ctx.reply("❌ Cog Arrodes não está carregado.", mention_author=False)
            return

        status = arrodes_cog.gemini.usage.get_status()

        # Barra de progresso visual
        def progress_bar(percent: float) -> str:
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            return f"`{bar}` {percent:.1f}%"

        # Cor baseada no status
        if status["is_offline"]:
            color = discord.Color.red()
            status_text = "🔴 OFFLINE (respostas prontas)"
        elif status["request_percent"] >= 60 or status["token_percent"] >= 60:
            color = discord.Color.orange()
            status_text = "🟡 Uso elevado"
        else:
            color = discord.Color.green()
            status_text = "🟢 Online"

        embed = discord.Embed(
            title="📊 Uso da API Gemini",
            description=f"**Status:** {status_text}",
            color=color,
        )
        embed.add_field(
            name="📨 Requests",
            value=(
                f"{progress_bar(status['request_percent'])}\n"
                f"`{status['requests']:,}` / `{status['request_limit']:,}` req/dia"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔤 Tokens",
            value=(
                f"{progress_bar(status['token_percent'])}\n"
                f"`{status['tokens']:,}` / `{status['token_limit']:,}` tokens/dia"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Config",
            value=f"Threshold: **{status['threshold_percent']}%** (entra offline em {status['threshold_percent']}% de uso)",
            inline=False,
        )
        embed.set_footer(text=f"Data: {status['date']}")

        await ctx.reply(embed=embed, mention_author=False)

    @app_commands.command(name="usage", description="Mostra o status de uso da API Gemini.")
    async def usage_slash(self, interaction: discord.Interaction) -> None:
        """Slash command para ver uso da API."""
        arrodes_cog = self.bot.get_cog("Arrodes")
        if not arrodes_cog or not hasattr(arrodes_cog, "gemini"):
            await interaction.response.send_message("❌ Cog Arrodes não está carregado.")
            return

        status = arrodes_cog.gemini.usage.get_status()

        def progress_bar(percent: float) -> str:
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            return f"`{bar}` {percent:.1f}%"

        if status["is_offline"]:
            color = discord.Color.red()
            status_text = "🔴 OFFLINE (respostas prontas)"
        elif status["request_percent"] >= 60 or status["token_percent"] >= 60:
            color = discord.Color.orange()
            status_text = "🟡 Uso elevado"
        else:
            color = discord.Color.green()
            status_text = "🟢 Online"

        embed = discord.Embed(
            title="📊 Uso da API Gemini",
            description=f"**Status:** {status_text}",
            color=color,
        )
        embed.add_field(
            name="📨 Requests",
            value=(
                f"{progress_bar(status['request_percent'])}\n"
                f"`{status['requests']:,}` / `{status['request_limit']:,}` req/dia"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔤 Tokens",
            value=(
                f"{progress_bar(status['token_percent'])}\n"
                f"`{status['tokens']:,}` / `{status['token_limit']:,}` tokens/dia"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Config",
            value=f"Threshold: **{status['threshold_percent']}%** (entra offline em {status['threshold_percent']}% de uso)",
            inline=False,
        )
        embed.set_footer(text=f"Data: {status['date']}")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Entry point para o sistema de Cogs."""
    await bot.add_cog(AdminCog(bot))
    log.info("Cog 'Admin' registrado no bot.")
