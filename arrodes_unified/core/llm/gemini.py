"""
Provider Google Gemini.
Rapido, free tier, com fallback de modelos e tracking de tokens.
"""

from typing import Any

from google import genai
from google.genai import types

from core.llm.base import LLMProvider
from core.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS
from core.logger import get_logger

log = get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Provider Google Gemini com fallback de modelos."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or GEMINI_API_KEY
        self._model = model or GEMINI_MODEL
        self._client = genai.Client(api_key=self._api_key)
        self._last_prompt_tokens: int = 0
        self._last_completion_tokens: int = 0
        log.info("GeminiProvider inicializado com modelo: %s", self._model)

    def get_name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def last_prompt_tokens(self) -> int:
        return self._last_prompt_tokens

    @property
    def last_completion_tokens(self) -> int:
        return self._last_completion_tokens

    async def ask(
        self,
        question: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        self._last_prompt_tokens = 0
        self._last_completion_tokens = 0

        # Monta historico no formato Gemini
        contents: list[types.Content] = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
                )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=question)])
        )

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1500,
        )

        # Tenta modelo principal e fallbacks
        models_to_try = list(dict.fromkeys([self._model] + GEMINI_FALLBACK_MODELS))
        response = None
        last_error = None

        for model_name in models_to_try:
            try:
                models_api: Any = self._client.aio.models
                response = await models_api.generate_content(
                    model=model_name,
                    contents=contents,
                    config=gen_config,
                )
                if model_name != self._model:
                    log.info("Fallback '%s' usado com sucesso.", model_name)
                break
            except Exception as e:
                last_error = e
                log.warning("Modelo '%s' falhou: %s", model_name, type(e).__name__)

        if response is None:
            if last_error:
                raise last_error
            raise RuntimeError("Nenhum modelo Gemini disponivel")

        answer = response.text or "*O espelho permanece em silencio...*"

        # Extrai tokens usados
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self._last_prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            self._last_completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        # Trunca se necessario
        if len(answer) > 1900:
            answer = answer[:1900] + "\n\n*... (resposta truncada)*"

        return answer
