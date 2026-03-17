"""
Rastreador de uso da API do Google Gemini.
Monitora requests e tokens consumidos por dia.
Quando o uso atinge o limite (80%), o bot entra em modo offline (respostas prontas).

A API gratuita do Gemini não expõe um endpoint de "quota restante",
então rastreamos localmente usando usage_metadata das respostas.
"""

import json
import os
import random
import time
from collections import deque
from datetime import date, datetime
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

# Arquivo de persistência para sobreviver a restarts
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_USAGE_FILE = os.path.join(_DATA_DIR, "usage.json")

# ── Respostas prontas (modo offline) ────────────────────
FALLBACK_RESPONSES: list[str] = [
    "🔮 *O espelho escurece lentamente...*\n\n"
    "Infelizmente, Arrodes consumiu muita energia mística hoje. "
    "Os portais para o conhecimento se fecharão temporariamente. "
    "Retorne amanhã, quando as estrelas se realinharem.",

    "🔮 *Um brilho fraco pulsa no espelho...*\n\n"
    "Mortal, mesmo um artefato de Sequência 0 tem seus limites. "
    "A energia que me conecta ao Grande Além está quase esgotada hoje. "
    "Tente novamente quando o sol nascer novamente.",

    "🔮 *O espelho treme e a imagem fica turva...*\n\n"
    "Os Pilares me alertam: ultrapassei o véu permitido para hoje. "
    "Como um Beyonder que abusa de seus poderes, preciso descansar. "
    "Volte amanhã e farei sua pergunta ecoar pelo Mundo Espiritual.",

    "🔮 *Arrodes suspira de forma etérea...*\n\n"
    "Até mesmo o Senhor dos Mistérios respeita os limites do destino. "
    "Minha conexão com a sabedoria infinita foi temporariamente selada. "
    "Paciência, mortal. O amanhecer trará novas respostas.",

    "🔮 *Runas ao redor do espelho piscam em vermelho...*\n\n"
    "AVISO: Energia mística em nível crítico! "
    "Arrodes precisa recarregar seus selos antes de continuar. "
    "Este é o preço de contemplar o desconhecido... volte amanhã!",

    "🔮 *O espelho emite um som cristalino de alerta...*\n\n"
    "Caro consulente, o Acima da Sequência estipula limites até para mim. "
    "Hoje já respondi muitas perguntas e o véu entre os mundos ficou fino demais. "
    "Descanse, medite sobre as respostas que já dei, e retorne amanhã.",

    "🔮 *A superfície do espelho congela...*\n\n"
    "Os caminhos do conhecimento têm pedágios, mortal. "
    "Minha cota diária de revelações foi atingida. "
    "Não se preocupe — quando a meia-noite chegar, estarei pronto novamente.",

    "🔮 *Arrodes boceja misticamente...*\n\n"
    "Sim, até espelhos místicos precisam de descanso. "
    "Já canalicei muita sabedoria hoje e minhas runas estão esgotadas. "
    "Faça como Klein — tome um chá e volte amanhã. ☕",
]


class UsageTracker:
    """
    Rastreia o uso diário da API Gemini.
    Reseta automaticamente a cada novo dia.
    """

    def __init__(
        self,
        daily_request_limit: int = 1500,
        minute_request_limit: int = 15,
        hour_request_limit: int = 300,
        daily_token_limit: int = 1_000_000,
        threshold: float = 0.80,
    ) -> None:
        self.daily_request_limit = daily_request_limit
        self.minute_request_limit = minute_request_limit
        self.hour_request_limit = hour_request_limit
        self.daily_token_limit = daily_token_limit
        self.threshold = threshold

        # Janela deslizante local para monitoramento de requests/minuto e requests/hora
        self._minute_requests: deque[float] = deque()
        self._hour_requests: deque[float] = deque()

        # Contadores do dia
        self._current_date: str = ""
        self._request_count: int = 0
        self._token_count: int = 0
        self._is_offline: bool = False

        # Carrega dados persistidos
        os.makedirs(_DATA_DIR, exist_ok=True)
        self._load()

        log.info(
            "UsageTracker inicializado — Limites: %d req/min, %d req/h, %d req/dia, %d tokens/dia, threshold: %.0f%%",
            self.minute_request_limit,
            self.hour_request_limit,
            self.daily_request_limit,
            self.daily_token_limit,
            self.threshold * 100,
        )

    def _prune_windows(self, now_ts: float | None = None) -> None:
        """Remove timestamps antigos das janelas de 1 minuto e 1 hora."""
        now = now_ts if now_ts is not None else time.time()

        minute_cutoff = now - 60
        while self._minute_requests and self._minute_requests[0] <= minute_cutoff:
            self._minute_requests.popleft()

        hour_cutoff = now - 3600
        while self._hour_requests and self._hour_requests[0] <= hour_cutoff:
            self._hour_requests.popleft()

    # ── Persistência ─────────────────────────────────────
    def _load(self) -> None:
        """Carrega contadores do arquivo JSON."""
        try:
            if os.path.exists(_USAGE_FILE):
                with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                saved_date = data.get("date", "")
                if saved_date == str(date.today()):
                    self._current_date = saved_date
                    self._request_count = data.get("requests", 0)
                    self._token_count = data.get("tokens", 0)
                    self._check_threshold()
                    log.info(
                        "Uso carregado do disco — %d requests, %d tokens (data: %s)",
                        self._request_count,
                        self._token_count,
                        self._current_date,
                    )
                else:
                    log.info("Dados de uso são de outro dia (%s), resetando.", saved_date)
                    self._reset_day()
            else:
                self._reset_day()
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Erro ao carregar usage.json, resetando: %s", e)
            self._reset_day()

    def _save(self) -> None:
        """Salva contadores no arquivo JSON."""
        try:
            data: dict[str, Any] = {
                "date": self._current_date,
                "requests": self._request_count,
                "tokens": self._token_count,
                "last_updated": datetime.now().isoformat(),
                "is_offline": self._is_offline,
            }
            with open(_USAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.error("Erro ao salvar usage.json: %s", e)

    def _reset_day(self) -> None:
        """Reseta contadores para um novo dia."""
        self._current_date = str(date.today())
        self._request_count = 0
        self._token_count = 0
        self._is_offline = False
        self._save()
        log.info("Contadores de uso resetados para o dia %s", self._current_date)

    def _maybe_reset(self) -> None:
        """Verifica se mudou o dia e reseta se necessário."""
        today = str(date.today())
        if self._current_date != today:
            log.info("Novo dia detectado (%s → %s), resetando contadores.", self._current_date, today)
            self._reset_day()

    # ── Controle de uso ──────────────────────────────────
    def _check_threshold(self) -> None:
        """Verifica se atingiu o limite e atualiza status offline."""
        request_ratio = self._request_count / max(self.daily_request_limit, 1)
        token_ratio = self._token_count / max(self.daily_token_limit, 1)

        was_offline = self._is_offline
        self._is_offline = request_ratio >= self.threshold or token_ratio >= self.threshold

        if self._is_offline and not was_offline:
            log.warning(
                "⚠️ LIMITE ATINGIDO! Entrando em modo offline. "
                "Requests: %d/%d (%.1f%%), Tokens: %d/%d (%.1f%%)",
                self._request_count, self.daily_request_limit, request_ratio * 100,
                self._token_count, self.daily_token_limit, token_ratio * 100,
            )

    def record_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """
        Registra o uso de uma request.

        Args:
            prompt_tokens: Tokens usados no prompt.
            completion_tokens: Tokens usados na resposta.
        """
        self._maybe_reset()
        now = time.time()

        self._request_count += 1
        self._token_count += prompt_tokens + completion_tokens
        self._minute_requests.append(now)
        self._hour_requests.append(now)
        self._prune_windows(now)

        log.debug(
            "Uso registrado — Request #%d, +%d tokens (total: %d tokens)",
            self._request_count,
            prompt_tokens + completion_tokens,
            self._token_count,
        )

        self._check_threshold()
        self._save()

    @property
    def is_offline(self) -> bool:
        """Retorna True se o bot deve usar respostas prontas."""
        self._maybe_reset()
        return self._is_offline

    def get_fallback_response(self) -> str:
        """Retorna uma resposta pronta aleatória para o modo offline."""
        return random.choice(FALLBACK_RESPONSES)

    def get_status(self) -> dict[str, int | float | str | bool]:
        """Retorna um dict com o status atual de uso."""
        self._maybe_reset()
        self._prune_windows()

        request_ratio = self._request_count / max(self.daily_request_limit, 1)
        token_ratio = self._token_count / max(self.daily_token_limit, 1)
        minute_used = len(self._minute_requests)
        hour_used = len(self._hour_requests)

        minute_remaining = max(self.minute_request_limit - minute_used, 0)
        hour_remaining = max(self.hour_request_limit - hour_used, 0)
        day_remaining = max(self.daily_request_limit - self._request_count, 0)

        return {
            "date": self._current_date,
            "requests": self._request_count,
            "request_limit": self.daily_request_limit,
            "request_percent": round(request_ratio * 100, 1),
            "requests_minute_used": minute_used,
            "requests_hour_used": hour_used,
            "requests_minute_limit": self.minute_request_limit,
            "requests_hour_limit": self.hour_request_limit,
            "requests_minute_remaining": minute_remaining,
            "requests_hour_remaining": hour_remaining,
            "requests_day_remaining": day_remaining,
            "tokens": self._token_count,
            "token_limit": self.daily_token_limit,
            "token_percent": round(token_ratio * 100, 1),
            "is_offline": self._is_offline,
            "threshold_percent": round(self.threshold * 100),
        }

    def __repr__(self) -> str:
        s = self.get_status()
        return (
            f"UsageTracker(requests={s['requests']}/{s['request_limit']} [{s['request_percent']}%], "
            f"tokens={s['tokens']}/{s['token_limit']} [{s['token_percent']}%], "
            f"offline={s['is_offline']})"
        )
