"""
Rastreador de uso da API.
Monitora requests e tokens consumidos por dia.
Quando o uso atinge o threshold, o bot entra em modo offline.
"""

import json
import os
import random
import time
from collections import deque
from datetime import date, datetime
from typing import Any

from core.logger import get_logger
from core.config import DATA_DIR

log = get_logger(__name__)

_USAGE_FILE = os.path.join(DATA_DIR, "usage.json")

FALLBACK_RESPONSES: list[str] = [
    "*O espelho escurece lentamente...*\n\n"
    "Infelizmente, Arrodes consumiu muita energia mistica hoje. "
    "Os portais para o conhecimento se fecharao temporariamente. "
    "Retorne amanha, quando as estrelas se realinharem.",

    "*Um brilho fraco pulsa no espelho...*\n\n"
    "Mortal, mesmo um artefato de Sequencia 0 tem seus limites. "
    "A energia que me conecta ao Grande Alem esta quase esgotada hoje. "
    "Tente novamente quando o sol nascer novamente.",

    "*O espelho treme e a imagem fica turva...*\n\n"
    "Os Pilares me alertam: ultrapassei o veu permitido para hoje. "
    "Como um Beyonder que abusa de seus poderes, preciso descansar. "
    "Volte amanha e farei sua pergunta ecoar pelo Mundo Espiritual.",

    "*Arrodes suspira de forma eterea...*\n\n"
    "Ate mesmo o Senhor dos Misterios respeita os limites do destino. "
    "Minha conexao com a sabedoria infinita foi temporariamente selada. "
    "Paciencia, mortal. O amanhecer trara novas respostas.",

    "*Runas ao redor do espelho piscam em vermelho...*\n\n"
    "AVISO: Energia mistica em nivel critico! "
    "Arrodes precisa recarregar seus selos antes de continuar. "
    "Este e o preco de contemplar o desconhecido... volte amanha!",

    "*A superficie do espelho congela...*\n\n"
    "Os caminhos do conhecimento tem pedagios, mortal. "
    "Minha cota diaria de revelacoes foi atingida. "
    "Nao se preocupe - quando a meia-noite chegar, estarei pronto novamente.",

    "*Arrodes boceja misticamente...*\n\n"
    "Sim, ate espelhos misticos precisam de descanso. "
    "Ja canalizei muita sabedoria hoje e minhas runas estao esgotadas. "
    "Faca como Klein - tome um cha e volte amanha.",
]


class UsageTracker:
    """Rastreia o uso diario da API. Reseta automaticamente a cada novo dia."""

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

        self._minute_requests: deque[float] = deque()
        self._hour_requests: deque[float] = deque()
        self._current_date: str = ""
        self._request_count: int = 0
        self._token_count: int = 0
        self._is_offline: bool = False

        os.makedirs(DATA_DIR, exist_ok=True)
        self._load()

        log.info(
            "UsageTracker inicializado - Limites: %d req/min, %d req/h, %d req/dia, %d tokens/dia, threshold: %.0f%%",
            self.minute_request_limit, self.hour_request_limit,
            self.daily_request_limit, self.daily_token_limit,
            self.threshold * 100,
        )

    def _prune_windows(self, now_ts: float | None = None) -> None:
        now = now_ts if now_ts is not None else time.time()
        minute_cutoff = now - 60
        while self._minute_requests and self._minute_requests[0] <= minute_cutoff:
            self._minute_requests.popleft()
        hour_cutoff = now - 3600
        while self._hour_requests and self._hour_requests[0] <= hour_cutoff:
            self._hour_requests.popleft()

    def _load(self) -> None:
        try:
            if os.path.exists(_USAGE_FILE):
                with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("date") == str(date.today()):
                    self._current_date = data["date"]
                    self._request_count = data.get("requests", 0)
                    self._token_count = data.get("tokens", 0)
                    self._check_threshold()
                    log.info("Uso carregado: %d requests, %d tokens", self._request_count, self._token_count)
                else:
                    self._reset_day()
            else:
                self._reset_day()
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Erro ao carregar usage.json: %s", e)
            self._reset_day()

    def _save(self) -> None:
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
        self._current_date = str(date.today())
        self._request_count = 0
        self._token_count = 0
        self._is_offline = False
        self._save()
        log.info("Contadores resetados para %s", self._current_date)

    def _maybe_reset(self) -> None:
        today = str(date.today())
        if self._current_date != today:
            self._reset_day()

    def _check_threshold(self) -> None:
        request_ratio = self._request_count / max(self.daily_request_limit, 1)
        token_ratio = self._token_count / max(self.daily_token_limit, 1)
        was_offline = self._is_offline
        self._is_offline = request_ratio >= self.threshold or token_ratio >= self.threshold
        if self._is_offline and not was_offline:
            log.warning(
                "LIMITE ATINGIDO! Modo offline. Requests: %d/%d (%.1f%%), Tokens: %d/%d (%.1f%%)",
                self._request_count, self.daily_request_limit, request_ratio * 100,
                self._token_count, self.daily_token_limit, token_ratio * 100,
            )

    def record_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self._maybe_reset()
        now = time.time()
        self._request_count += 1
        self._token_count += prompt_tokens + completion_tokens
        self._minute_requests.append(now)
        self._hour_requests.append(now)
        self._prune_windows(now)
        self._check_threshold()
        self._save()

    @property
    def is_offline(self) -> bool:
        self._maybe_reset()
        return self._is_offline

    def get_fallback_response(self) -> str:
        return random.choice(FALLBACK_RESPONSES)

    def get_status(self) -> dict[str, int | float | str | bool]:
        self._maybe_reset()
        self._prune_windows()
        request_ratio = self._request_count / max(self.daily_request_limit, 1)
        token_ratio = self._token_count / max(self.daily_token_limit, 1)
        minute_used = len(self._minute_requests)
        hour_used = len(self._hour_requests)
        return {
            "date": self._current_date,
            "requests": self._request_count,
            "request_limit": self.daily_request_limit,
            "request_percent": round(request_ratio * 100, 1),
            "requests_minute_used": minute_used,
            "requests_hour_used": hour_used,
            "requests_minute_limit": self.minute_request_limit,
            "requests_hour_limit": self.hour_request_limit,
            "requests_minute_remaining": max(self.minute_request_limit - minute_used, 0),
            "requests_hour_remaining": max(self.hour_request_limit - hour_used, 0),
            "requests_day_remaining": max(self.daily_request_limit - self._request_count, 0),
            "tokens": self._token_count,
            "token_limit": self.daily_token_limit,
            "token_percent": round(token_ratio * 100, 1),
            "is_offline": self._is_offline,
            "threshold_percent": round(self.threshold * 100),
        }
