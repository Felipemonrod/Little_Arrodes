"""
Cog principal: Arrodes — o espelho místico que responde perguntas.
Integra o bot Discord com o Google Gemini.

Fluxo principal:
  1. Usuário envia "#call_arrodes" no canal
  2. Arrodes acorda e pede a pergunta (estilo místico)
  3. Usuário envia a pergunta
  4. Arrodes consulta a IA e responde
"""

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.gemini_client import GeminiClient
from utils.logger import get_logger

log = get_logger(__name__)

# Mensagens de "despertar" quando o usuário envia #
GREETINGS = [
    "🔮 *O espelho brilha intensamente e uma voz ecoa...*\n\n"
    "Ah, um mortal ousa despertar **Arrodes**! Muito bem... "
    "Qual é a sua pergunta, curioso caminhante dos Caminhos?",

    "🔮 *Runas antigas se iluminam ao redor do espelho...*\n\n"
    "Sua Excelência, **Arrodes**, foi convocado! "
    "Fale, mortal — que mistério deseja desvendar?",

    "🔮 *Uma névoa prateada emana do espelho...*\n\n"
    "O véu entre os mundos se abre... **Arrodes** escuta. "
    "Faça sua pergunta, antes que o destino mude de ideia.",

    "🔮 *O espelho pulsa com energia mística...*\n\n"
    "Hmm? Alguém me invoca? Pois bem! "
    "**Arrodes** está à disposição. Qual é o enigma que te aflige, mortal?",

    "🔮 *Um brilho roxo surge das profundezas do espelho...*\n\n"
    "Saudações, viajante! Sua Excelência **Arrodes** desperta. "
    "Pergunte-me o que desejar... mas esteja preparado para a resposta.",

    "🔮 *O espelho vibra e uma risada suave ecoa...*\n\n"
    "Ora, ora... mais um Beyonder curioso? "
    "**Arrodes** aceita seu chamado. Diga-me, qual é a sua questão?",
]

# Timeout em segundos para esperar a pergunta
QUESTION_TIMEOUT = 120  # 2 minutos


class ArrodesCog(commands.Cog, name="Arrodes"):
    """🔮 O espelho místico responde às suas perguntas."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.gemini = GeminiClient()
        # Set de (user_id, channel_id) aguardando pergunta
        self._waiting: set[tuple[int, int]] = set()
        log.info("Cog Arrodes carregado com sucesso.")

    # ── Listener principal: # e perguntas ────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Fluxo principal:
        1. '#call_arrodes' → Arrodes acorda e pede a pergunta
        2. Próxima mensagem do mesmo user/canal → envia pra IA
        Também responde quando o bot é mencionado.
        """
        if message.author.bot:
            return

        if self.bot.user is None:
            return

        user_key = (message.author.id, message.channel.id)
        content = message.content.strip()

        # ── Passo 2: Usuário está respondendo com a pergunta ──
        if user_key in self._waiting:
            self._waiting.discard(user_key)

            # Se mandou #call_arrodes de novo, ignora (já está esperando)
            if content.lower() == "#call_arrodes":
                return

            # Se mandou mensagem vazia ou só espaço
            if not content:
                await message.reply(
                    "🔮 *O espelho aguarda...* Envie sua pergunta, mortal.",
                    mention_author=False,
                )
                self._waiting.add(user_key)
                return

            log.info("Pergunta de %s (canal=%s): %s", message.author, message.channel.id, content[:80])

            async with message.channel.typing():
                answer = await self.gemini.ask(message.channel.id, content)

            quota_log = self._build_quota_test_log()
            embed = self._build_embed(content, answer, message.author, quota_log)
            await message.reply(embed=embed, mention_author=False)
            return

        # ── Passo 1: Usuário envia '#call_arrodes' para invocar ──
        if content.lower() == "#call_arrodes":
            log.info("Arrodes invocado por %s (canal=%s)", message.author, message.channel.id)

            greeting = random.choice(GREETINGS)
            await message.reply(greeting, mention_author=False)

            # Marca que estamos esperando a pergunta
            self._waiting.add(user_key)

            # Timeout: remove da espera após 2 minutos
            await self._start_timeout(user_key, message.channel)
            return

        # ── Menção direta ao bot ─────────────────────────
        if self.bot.user in message.mentions:
            clean = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            clean = clean.replace(f"<@!{self.bot.user.id}>", "").strip()

            if not clean:
                await message.reply(
                    "🔮 *O espelho brilha suavemente...* "
                    "Envie **#call_arrodes** para me invocar, ou me mencione com sua pergunta!",
                    mention_author=False,
                )
                return

            log.info("Menção de %s (canal=%s): %s", message.author, message.channel.id, clean[:80])

            async with message.channel.typing():
                answer = await self.gemini.ask(message.channel.id, clean)

            quota_log = self._build_quota_test_log()
            embed = self._build_embed(clean, answer, message.author, quota_log)
            await message.reply(embed=embed, mention_author=False)

    async def _start_timeout(self, user_key: tuple[int, int], channel: discord.abc.Messageable) -> None:
        """Remove o usuário da fila de espera após o timeout."""
        await asyncio.sleep(QUESTION_TIMEOUT)
        if user_key in self._waiting:
            self._waiting.discard(user_key)
            log.debug("Timeout de pergunta para user=%s canal=%s", user_key[0], user_key[1])
            try:
                await channel.send(
                    f"🔮 *O espelho escurece lentamente...*\n\n"
                    f"<@{user_key[0]}>, Arrodes esperou, mas nenhuma pergunta veio. "
                    f"O portal se fecha... Envie **#call_arrodes** novamente quando estiver pronto.",
                )
            except discord.HTTPException:
                pass

    # ── Slash Command: /ask (atalho direto) ──────────────
    @app_commands.command(name="ask", description="Faça uma pergunta ao Arrodes, o espelho místico.")
    @app_commands.describe(pergunta="Sua pergunta para Arrodes")
    async def ask_slash(self, interaction: discord.Interaction, pergunta: str) -> None:
        """Slash command para perguntar ao Arrodes (sem precisar do #)."""
        log.info(
            "Slash /ask de %s (canal=%s): %s",
            interaction.user,
            interaction.channel_id,
            pergunta[:80],
        )

        await interaction.response.defer(thinking=True)

        if interaction.channel_id is None:
            await interaction.followup.send("❌ Não consegui identificar o canal desta interação.")
            return

        answer = await self.gemini.ask(interaction.channel_id, pergunta)

        quota_log = self._build_quota_test_log()
        embed = self._build_embed(pergunta, answer, interaction.user, quota_log)
        await interaction.followup.send(embed=embed)

    # ── Comando: limpar histórico ────────────────────────
    @commands.command(name="clear", aliases=["limpar"])
    async def clear_history(self, ctx: commands.Context[commands.Bot]) -> None:
        """Limpa o histórico de conversa do Arrodes neste canal."""
        cleared = self.gemini.clear_history(ctx.channel.id)
        if cleared:
            await ctx.reply(
                "🔮 *O espelho se limpa...* Minha memória deste canal foi purificada.",
                mention_author=False,
            )
        else:
            await ctx.reply(
                "🔮 *O espelho já estava límpido.* Não há memórias para purificar.",
                mention_author=False,
            )

    @app_commands.command(name="clear", description="Limpa o histórico de conversa do Arrodes neste canal.")
    async def clear_slash(self, interaction: discord.Interaction) -> None:
        """Slash command para limpar histórico."""
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ Não consegui identificar o canal desta interação.")
            return

        cleared = self.gemini.clear_history(interaction.channel_id)
        if cleared:
            await interaction.response.send_message(
                "🔮 *O espelho se limpa...* Minha memória deste canal foi purificada."
            )
        else:
            await interaction.response.send_message(
                "🔮 *O espelho já estava límpido.* Não há memórias para purificar."
            )

    # ── Helper: embed bonito ─────────────────────────────
    def _build_quota_test_log(self) -> str | None:
        """Monta log de teste com requests restantes por minuto/hora/dia."""
        if not config.DISCORD_TEST_QUOTA_LOG:
            return None

        status = self.gemini.get_quota_status()
        return (
            "`TEST QUOTA` "
            f"min: **{status['requests_minute_remaining']}**/{status['requests_minute_limit']} | "
            f"hora: **{status['requests_hour_remaining']}**/{status['requests_hour_limit']} | "
            f"dia: **{status['requests_day_remaining']}**/{status['request_limit']}"
        )

    @staticmethod
    def _build_embed(
        question: str,
        answer: str,
        user: discord.User | discord.Member,
        quota_log: str | None = None,
    ) -> discord.Embed:
        """Cria um embed formatado para a resposta do Arrodes."""
        embed = discord.Embed(
            title="🔮 Arrodes Responde",
            color=discord.Color.from_rgb(148, 103, 189),
        )
        embed.add_field(
            name="📜 Pergunta",
            value=question[:1024],
            inline=False,
        )
        embed.add_field(
            name="✨ Resposta",
            value=answer[:1024],
            inline=False,
        )

        if len(answer) > 1024:
            embed.add_field(
                name="✨ Continuação",
                value=answer[1024:2048],
                inline=False,
            )

        if quota_log:
            embed.add_field(
                name="🧪 Limites (teste)",
                value=quota_log,
                inline=False,
            )

        embed.set_footer(
            text=f"Consultado por {user.display_name}",
            icon_url=user.display_avatar.url if user.display_avatar else None,
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    """Entry point para o sistema de Cogs."""
    await bot.add_cog(ArrodesCog(bot))
    log.info("Cog 'Arrodes' registrado no bot.")
