"""
Provider Groq (LLaMA 3.3 70B).
Potente, com rotacao de API keys para contornar rate limits.
"""

import asyncio
import random

from groq import Groq

from core.llm.base import LLMProvider
from core.config import GROQ_KEYS, GROQ_MODEL
from core.logger import get_logger

log = get_logger(__name__)


class GroqProvider(LLMProvider):
    """Provider Groq com key rotation."""

    def __init__(self, keys: list[str] | None = None, model: str | None = None) -> None:
        self._keys = keys or GROQ_KEYS
        self._model = model or GROQ_MODEL
        if not self._keys:
            log.warning("Nenhuma GROQ_KEY configurada.")
        else:
            log.info("GroqProvider inicializado com %d keys, modelo: %s", len(self._keys), self._model)

    def get_name(self) -> str:
        return f"groq:{self._model}"

    async def ask(
        self,
        question: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        if not self._keys:
            return "Grande Mestre, as fontes de energia espiritual nao estao configuradas..."

        # Monta mensagens no formato OpenAI (que Groq usa)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        # Tenta cada key com shuffle para distribuir carga
        keys_shuffled = list(self._keys)
        random.shuffle(keys_shuffled)

        last_error: Exception | None = None
        for key in keys_shuffled:
            try:
                # Groq SDK e sincrono, roda em thread para nao bloquear
                answer = await asyncio.to_thread(
                    self._sync_call, key, messages
                )
                return answer
            except Exception as e:
                last_error = e
                if "429" in str(e):
                    log.warning("Groq key rate limited, tentando proxima...")
                else:
                    log.warning("Groq erro: %s", e)

        log.error("Todas as Groq keys falharam. Ultimo erro: %s", last_error)
        return "Grande Mestre, todas as fontes de energia espiritual estao esgotadas no momento..."

    def _sync_call(self, api_key: str, messages: list[dict[str, str]]) -> str:
        """Chamada sincrona ao Groq SDK."""
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=500,
            temperature=0.6,
        )
        answer = completion.choices[0].message.content or ""

        # Trunca se necessario
        if len(answer) > 1900:
            answer = answer[:1900] + "\n\n*... (resposta truncada)*"

        return answer
