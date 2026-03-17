import asyncio
import random
import requests
import json
import re

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.gemini_client import GeminiClient
from utils.logger import get_logger
from utils.fast_rag import check_confidence_and_search

log = get_logger(__name__)

GREETINGS = [
    "🔮 *O espelho pisca...*\n\nAh, Grande Mestre deseja saber algo? Pergunte.",
]

QUESTION_TIMEOUT = 120

class ArrodesCog(commands.Cog, name="Arrodes"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.gemini = GeminiClient()
        self._waiting: set[tuple[int, int]] = set()

    def processar_spoiler(self, texto: str) -> str:
        # Tudo que fala de "Sequencia [0-7]" no lore é critico.
        # Envolvemos em || spoiler || se houver mencoes a sequencia 7 pra baixo
        if re.search(r"sequ[êe]ncia [0-7]", texto, re.IGNORECASE):
            return f"|| {texto} ||"
        return texto

    async def chamar_tier_2(self, pergunta: str, history: str) -> str:
        url = "http://127.0.0.1:8080/ask_arrodes" # Localhost API do klein_ai
        payload = {
            "query": pergunta,
            "context": "Contexto delegado do Tier 1. Busque no seu RAG.",
            "history": history
        }
        try:
            # Em producao (docker), mudar 127.0.0.1 pelo nome do container 'klein_ai'
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                answer = resp.json().get("answer", "")
                return self.processar_spoiler(answer)
        except Exception as e:
            log.error(f"Erro ao chamar Tier 2: {e}")
        return "As brumas estão muito densas para o meu irmão maior responder agora..."

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.bot.user is None:
            return

        user_key = (message.author.id, message.channel.id)
        content = message.content.strip()
        lower_content = content.lower()

        # #invocar_arrodes ou frase natural de trigger (NOVO!)
        trigger_ativada = lower_content.startswith("#invocar_arrodes") or "arrodes tenho uma pergunta" in lower_content

        if user_key in self._waiting:
            self._waiting.discard(user_key)
            if trigger_ativada:
                return

            if not content:
                await message.reply("🔮 *O espelho aguarda...* Envie sua pergunta.", mention_author=False)
                self._waiting.add(user_key)
                return

            log.info("Pergunta recebida: %s", content[:80])
            async with message.channel.typing():
                # Roteamento Inteligente (Agentic Routing)
                context_str, confidence = check_confidence_and_search(content)
                hist_str = "\n".join([c.parts[0].text for c in self.gemini._get_history(message.channel.id)])
                
                if confidence < 0.6 or not context_str:
                    log.info("Confianca baixa (%.2f). Delegando ao Tier 2 (Klein AI)...", confidence)
                    final_answer = await self.chamar_tier_2(content, hist_str)
                else:
                    log.info("Confianca alta (%.2f). Respondendo via Tier 1 (Gemini Flash).", confidence)
                    # Adiciona contexto na frente
                    prompt_enriquecido = f"Baseado nisto:\n{context_str}\n\nResponda como Arrodes a pergunta: {content}"
                    raw_answer = await self.gemini.ask(message.channel.id, prompt_enriquecido)
                    final_answer = self.processar_spoiler(raw_answer)

            embed = self._build_embed(content, final_answer, message.author, "ROUTED")
            await message.reply(embed=embed, mention_author=False)
            return

        if trigger_ativada:
            log.info("Arrodes invocado!")
            await message.reply(random.choice(GREETINGS), mention_author=False)
            self._waiting.add(user_key)
            await self._start_timeout(user_key, message.channel)

    async def _start_timeout(self, user_key: tuple[int, int], channel: discord.abc.Messageable) -> None:
        await asyncio.sleep(QUESTION_TIMEOUT)
        if user_key in self._waiting:
            self._waiting.discard(user_key)
            try:
                await channel.send("🔮 *O espelho escurece lentamente...*")
            except:
                pass

    @staticmethod
    def _build_embed(question: str, answer: str, user, quota_log: str) -> discord.Embed:
        embed = discord.Embed(title="🔮 Arrodes Responde", color=discord.Color.from_rgb(148, 103, 189))
        embed.add_field(name="📜 Pergunta", value=question[:1024], inline=False)
        embed.add_field(name="👁️ Resposta", value=answer[:1024], inline=False)
        return embed