"""
Cliente para a API do Google Gemini (gratuita).
Usa o novo SDK google-genai.
Integrado com UsageTracker para monitorar limites da API.
"""

from google import genai
from google.genai import types
from typing import Any

import config
from utils.logger import get_logger
from utils.usage_tracker import UsageTracker

log = get_logger(__name__)


class GeminiClient:
    """Wrapper para o Google Gemini com controle de uso."""

    def __init__(self) -> None:
        log.info("Inicializando cliente Gemini...")

        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL

        # Histórico por canal para manter contexto
        self._histories: dict[int, list[types.Content]] = {}

        # Rastreador de uso da API
        self.usage = UsageTracker(
            minute_request_limit=config.MINUTE_REQUEST_LIMIT,
            hour_request_limit=config.HOUR_REQUEST_LIMIT,
            daily_request_limit=config.DAILY_REQUEST_LIMIT,
            daily_token_limit=config.DAILY_TOKEN_LIMIT,
            threshold=config.USAGE_THRESHOLD,
        )

        log.info("Cliente Gemini inicializado com modelo: %s", self.model)

    def _get_history(self, channel_id: int) -> list[types.Content]:
        """Retorna ou cria o histórico de conversa do canal."""
        if channel_id not in self._histories:
            log.debug("Criando novo histórico para canal %s", channel_id)
            self._histories[channel_id] = []
        return self._histories[channel_id]

    async def ask(self, channel_id: int, question: str) -> str:
        """
        Envia uma pergunta ao Gemini e retorna a resposta.
        Se o limite de uso estiver atingido, retorna uma resposta pronta.
        """
        # Verificar se estamos em modo offline (limite atingido)
        if self.usage.is_offline:
            log.warning(
                "Modo offline ativo — respondendo com fallback [canal=%s, user_question=%s]",
                channel_id,
                question[:60],
            )
            return self.usage.get_fallback_response()

        history = self._get_history(channel_id)
        log.debug("Pergunta [canal=%s]: %s", channel_id, question[:100])

        try:
            # Monta o conteúdo: histórico + nova pergunta
            contents = history + [
                types.Content(role="user", parts=[types.Part.from_text(text=question)])
            ]

            gen_config = types.GenerateContentConfig(
                system_instruction=config.ARRODES_SYSTEM_PROMPT,
                max_output_tokens=1500,
            )

            # Tenta o modelo principal, depois os fallbacks sem duplicar nomes
            models_to_try = list(dict.fromkeys([self.model] + config.GEMINI_FALLBACK_MODELS))
            response = None
            last_error = None

            for model_name in models_to_try:
                try:
                    models_api: Any = self.client.aio.models
                    response = await models_api.generate_content(
                        model=model_name,
                        contents=contents,
                        config=gen_config,
                    )
                    if model_name != self.model:
                        log.info("Modelo fallback '%s' usado com sucesso.", model_name)
                    break
                except Exception as model_err:
                    last_error = model_err
                    log.warning(
                        "Modelo '%s' falhou: %s. Tentando próximo...",
                        model_name,
                        type(model_err).__name__,
                    )
                    continue

            if response is None:
                if last_error is not None:
                    raise last_error
                raise RuntimeError("Nenhum modelo disponível")

            answer = response.text or "*O espelho permanece em silêncio...*"

            # Salvar no histórico (user + model)
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
            history.append(types.Content(role="model", parts=[types.Part.from_text(text=answer)]))

            # Limitar histórico a 20 mensagens (10 pares) para não explodir tokens
            if len(history) > 20:
                self._histories[channel_id] = history[-20:]

            # Registrar uso de tokens a partir do metadata da resposta
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                log.debug(
                    "Tokens usados — prompt: %d, resposta: %d, total: %d",
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens + completion_tokens,
                )

            self.usage.record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            # Truncar se necessário (limite do Discord)
            if len(answer) > 1950:
                answer = answer[:1950] + "\n\n*... (resposta truncada)*"

            log.debug("Resposta [canal=%s]: %s", channel_id, answer[:100])
            return answer

        except Exception as e:
            log.error("Erro ao consultar Gemini: %s", e, exc_info=True)
            return (
                "⚠️ *Os véus entre os mundos se agitaram...* "
                "Arrodes não conseguiu canalizar sua sabedoria neste momento. "
                f"(Erro: {type(e).__name__})"
            )

    def clear_history(self, channel_id: int) -> bool:
        """Limpa o histórico de conversa de um canal."""
        if channel_id in self._histories:
            del self._histories[channel_id]
            log.info("Histórico limpo para canal %s", channel_id)
            return True
        return False

    def clear_all_history(self) -> int:
        """Limpa todos os históricos. Retorna quantidade limpa."""
        count = len(self._histories)
        self._histories.clear()
        log.info("Todos os históricos limpos (%d sessões)", count)
        return count

    def get_quota_status(self) -> dict[str, int | float | str | bool]:
        """Retorna snapshot local de limites para log de teste no Discord."""
        return self.usage.get_status()
