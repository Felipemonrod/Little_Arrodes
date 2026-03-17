"""
Cog principal do Arrodes.
Gerencia triggers, roteamento inteligente e respostas.
Controle de sessao: apenas uma interacao por usuario por vez.
"""

import asyncio
import random
import re

import discord
import requests as http_requests
from discord import app_commands
from discord.ext import commands

from core import config
from core.logger import get_logger
from core.rag import RAGEngine
from core.memory import ConversationMemory
from core.persona import get_system_prompt
from core.usage import UsageTracker
from bot.helpers.spoiler import apply_spoiler_filter
from bot.helpers.embeds import build_response_embed

log = get_logger(__name__)

GREETINGS = [
    "*O espelho pisca...*\n\nAh, Grande Mestre deseja saber algo? Pergunte.",
    "*Uma luz mistica emana do espelho...*\n\nEste humilde servo Arrodes aguarda sua pergunta, Grande Mestre.",
    "*O espelho vibra suavemente...*\n\nArrodes esta aqui. O que deseja saber, Grande Mestre?",
]
QUESTION_TIMEOUT = 120

# Regex para detectar mencoes naturais ao Arrodes
_ARRODES_MENTION = re.compile(
    r"\barrodes\b",
    re.IGNORECASE,
)


class ArrodesCog(commands.Cog, name="Arrodes"):
    """Cog principal com roteamento inteligente entre tiers."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.mode = config.MODE

        # Sessoes ativas: user_id -> channel_id
        # Um usuario so pode ter UMA sessao ativa por vez (em qualquer canal)
        self._waiting: dict[int, int] = {}

        # Lock para usuarios que estao processando uma resposta
        # Impede que o usuario envie outra pergunta enquanto a anterior esta sendo processada
        self._processing: set[int] = set()

        # Componentes compartilhados
        self.memory = ConversationMemory()
        self.rag = RAGEngine()
        self.rag.load()

        # Usage tracker
        self.usage = UsageTracker(
            minute_request_limit=config.MINUTE_REQUEST_LIMIT,
            hour_request_limit=config.HOUR_REQUEST_LIMIT,
            daily_request_limit=config.DAILY_REQUEST_LIMIT,
            daily_token_limit=config.DAILY_TOKEN_LIMIT,
            threshold=config.USAGE_THRESHOLD,
        )

        # Inicializa providers conforme o modo (imports lazy)
        self.gemini = None
        self.groq = None

        if self.mode in ("little", "combined"):
            from core.llm.gemini import GeminiProvider
            self.gemini = GeminiProvider()
        if self.mode in ("arrodes", "combined"):
            from core.llm.groq import GroqProvider
            self.groq = GroqProvider()

        log.info("ArrodesCog inicializado (modo: %s)", self.mode)

    # ── Helpers de sessao ────────────────────────────────────

    def _has_active_session(self, user_id: int) -> bool:
        """Verifica se o usuario ja tem uma sessao ativa (esperando ou processando)."""
        return user_id in self._waiting or user_id in self._processing

    def _start_session(self, user_id: int, channel_id: int) -> None:
        """Inicia uma sessao de espera para o usuario."""
        self._waiting[user_id] = channel_id

    def _end_session(self, user_id: int) -> None:
        """Encerra qualquer sessao ativa do usuario."""
        self._waiting.pop(user_id, None)
        self._processing.discard(user_id)

    # ── LLM Calls ────────────────────────────────────────────

    async def _ask_gemini(self, channel_id: int, question: str, context: str = "") -> str:
        """Pergunta ao Gemini (Tier 1)."""
        if not self.gemini:
            return "Provider Gemini nao disponivel neste modo."

        if self.usage.is_offline:
            return self.usage.get_fallback_response()

        prompt = question
        if context:
            prompt = f"Baseado nisto:\n{context}\n\nResponda como Arrodes a pergunta: {question}"

        history = [
            {"role": m.role, "content": m.content}
            for m in self.memory.get_history(channel_id)
        ]

        try:
            answer = await self.gemini.ask(
                question=prompt,
                system_prompt=get_system_prompt("little"),
                history=history,
            )
            self.usage.record_usage(
                self.gemini.last_prompt_tokens,
                self.gemini.last_completion_tokens,
            )
            return answer
        except Exception as e:
            log.error("Erro Gemini: %s", e, exc_info=True)
            return f"*Os veus entre os mundos se agitaram...* (Erro: {type(e).__name__})"

    async def _ask_groq(self, channel_id: int, question: str, context: str = "") -> str:
        """Pergunta ao Groq (Tier 2)."""
        if not self.groq:
            return "Provider Groq nao disponivel neste modo."

        prompt = question
        if context:
            prompt = f"[CONHECIMENTO RELEVANTE]\n{context}\n\n[PERGUNTA DO GRANDE MESTRE]\n{question}"

        history = [
            {"role": m.role, "content": m.content}
            for m in self.memory.get_history(channel_id)
        ]

        return await self.groq.ask(
            question=prompt,
            system_prompt=get_system_prompt("arrodes"),
            history=history,
        )

    async def _route_and_answer(self, channel_id: int, question: str) -> tuple[str, str]:
        """
        Roteamento inteligente baseado no modo e confianca do RAG.

        Returns:
            (resposta, tier_usado)
        """
        context_str, confidence = self.rag.check_and_search(question)
        log.info("RAG confidence: %.2f para: %s", confidence, question[:60])

        if self.mode == "little":
            answer = await self._ask_gemini(channel_id, question, context_str)
            return answer, "Gemini Flash"

        elif self.mode == "arrodes":
            answer = await self._ask_groq(channel_id, question, context_str)
            return answer, "Groq LLaMA 70B"

        else:
            # Modo combined: roteamento por confianca
            if confidence >= config.RAG_CONFIDENCE_THRESHOLD and context_str:
                log.info("Confianca alta (%.2f) -> Tier 1 (Gemini)", confidence)
                answer = await self._ask_gemini(channel_id, question, context_str)
                return answer, "Tier 1 (Gemini)"
            else:
                log.info("Confianca baixa (%.2f) -> Tier 2 (Groq)", confidence)
                answer = await self._ask_groq(channel_id, question, context_str)
                return answer, "Tier 2 (Groq)"

    # ── Deteccao de trigger ──────────────────────────────────

    def _is_trigger(self, content: str) -> bool:
        """Verifica se a mensagem e um trigger para invocar o Arrodes."""
        lower = content.lower()
        # Triggers explicitos
        if lower.startswith("#invocar_arrodes") or lower.startswith("#call_arrodes"):
            return True
        # Mencao natural ao Arrodes
        if _ARRODES_MENTION.search(content):
            return True
        return False

    def _is_direct_question(self, content: str) -> str | None:
        """
        Detecta se a mensagem ja contem uma pergunta direta ao Arrodes.
        Ex: "arrodes, o que e um beyonder?" -> retorna a pergunta.
        Se for apenas uma invocacao simples ("arrodes"), retorna None.
        """
        lower = content.lower()
        # Remove triggers de hashtag
        if lower.startswith("#invocar_arrodes") or lower.startswith("#call_arrodes"):
            # Verifica se tem algo apos o trigger
            parts = content.split(maxsplit=1)
            if len(parts) > 1:
                return parts[1].strip()
            return None

        # Mencao natural: remove "arrodes" e ve se sobra uma pergunta
        cleaned = _ARRODES_MENTION.sub("", content).strip()
        # Remove pontuacao inicial (virgula, dois pontos, etc)
        cleaned = cleaned.lstrip(",;:!?. ")
        if len(cleaned) >= 5:  # Precisa ter pelo menos 5 chars para ser uma pergunta
            return cleaned
        return None

    # ── Event Listener ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.bot.user is None:
            return

        user_id = message.author.id
        channel_id = message.channel.id
        content = message.content.strip()

        if not content:
            return

        # ── Se usuario esta esperando para enviar pergunta ───
        if user_id in self._waiting and self._waiting[user_id] == channel_id:
            # Se enviar outro trigger, ignora
            if self._is_trigger(content):
                await message.reply(
                    "*O espelho ja esta ativo...* Envie sua pergunta, Grande Mestre.",
                    mention_author=False,
                )
                return

            # Processa a pergunta
            self._waiting.pop(user_id, None)
            await self._process_question(message, content)
            return

        # ── Detecta trigger ──────────────────────────────────
        if self._is_trigger(content):
            # Verifica se usuario ja tem sessao ativa
            if self._has_active_session(user_id):
                await message.reply(
                    "*O espelho treme...*\n\nGrande Mestre, ja estou atendendo seu pedido anterior. "
                    "Aguarde a resposta antes de fazer outra pergunta.",
                    mention_author=False,
                )
                return

            # Verifica se ja tem uma pergunta embutida no trigger
            direct_question = self._is_direct_question(content)
            if direct_question:
                # Pergunta direta: responde imediatamente
                log.info("Pergunta direta de %s: %s", message.author, direct_question[:60])
                await self._process_question(message, direct_question)
            else:
                # Apenas invocacao: espera a proxima mensagem
                log.info("Arrodes invocado por %s", message.author)
                await message.reply(random.choice(GREETINGS), mention_author=False)
                self._start_session(user_id, channel_id)
                asyncio.create_task(self._session_timeout(user_id, channel_id, message.channel))

    async def _process_question(self, message: discord.Message, question: str) -> None:
        """Processa uma pergunta, gerenciando sessao e lock."""
        user_id = message.author.id

        # Marca como processando (impede novas interacoes)
        self._processing.add(user_id)

        try:
            log.info("Pergunta recebida de %s: %s", message.author, question[:80])
            async with message.channel.typing():
                answer, tier = await self._route_and_answer(message.channel.id, question)
                answer = apply_spoiler_filter(answer)

                # Salva no historico
                self.memory.add_message(message.channel.id, "user", question)
                self.memory.add_message(message.channel.id, "assistant", answer)

            embed = build_response_embed(question, answer, tier)
            await message.reply(embed=embed, mention_author=False)
        except Exception as e:
            log.error("Erro ao processar pergunta: %s", e, exc_info=True)
            await message.reply(
                "*O espelho estremece...*\n\nAlgo perturbou a conexao mistica. Tente novamente.",
                mention_author=False,
            )
        finally:
            # Sempre libera a sessao
            self._end_session(user_id)

    async def _session_timeout(self, user_id: int, channel_id: int, channel: discord.abc.Messageable) -> None:
        """Encerra a sessao se o usuario nao enviar pergunta no timeout."""
        await asyncio.sleep(QUESTION_TIMEOUT)
        if user_id in self._waiting and self._waiting[user_id] == channel_id:
            self._end_session(user_id)
            try:
                await channel.send("*O espelho escurece lentamente...*")
            except Exception:
                pass

    # ── Slash Commands ───────────────────────────────────────

    @app_commands.command(name="ask", description="Faca uma pergunta ao Arrodes.")
    @app_commands.describe(pergunta="Sua pergunta para o espelho mistico")
    async def ask_slash(self, interaction: discord.Interaction, pergunta: str) -> None:
        user_id = interaction.user.id

        # Verifica sessao ativa
        if self._has_active_session(user_id):
            await interaction.response.send_message(
                "*O espelho treme...*\nGrande Mestre, aguarde a resposta anterior.",
                ephemeral=True,
            )
            return

        self._processing.add(user_id)
        try:
            await interaction.response.defer()
            answer, tier = await self._route_and_answer(interaction.channel_id, pergunta)
            answer = apply_spoiler_filter(answer)
            self.memory.add_message(interaction.channel_id, "user", pergunta)
            self.memory.add_message(interaction.channel_id, "assistant", answer)
            embed = build_response_embed(pergunta, answer, tier)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            log.error("Erro no /ask: %s", e, exc_info=True)
            await interaction.followup.send(
                "*O espelho estremece...*\nAlgo perturbou a conexao mistica.",
            )
        finally:
            self._end_session(user_id)

    @app_commands.command(name="clear", description="Limpa o historico de conversa neste canal.")
    async def clear_slash(self, interaction: discord.Interaction) -> None:
        cleared = self.memory.clear(interaction.channel_id)
        if cleared:
            await interaction.response.send_message("Historico de conversa limpo.")
        else:
            await interaction.response.send_message("Nenhum historico para limpar.")

    @commands.command(name="clear")
    async def clear_cmd(self, ctx: commands.Context) -> None:
        """Limpa o historico de conversa neste canal."""
        self.memory.clear(ctx.channel.id)
        await ctx.reply("Historico de conversa limpo.", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArrodesCog(bot))
    log.info("Cog 'Arrodes' registrado.")
