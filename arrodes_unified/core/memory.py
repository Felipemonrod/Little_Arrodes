"""
Gerenciador de memoria de conversa por canal.
Mantém historico com sliding window para controlar tokens.
"""

from dataclasses import dataclass, field
from core.logger import get_logger

log = get_logger(__name__)

MAX_HISTORY_PER_CHANNEL = 20  # 10 pares user/assistant


@dataclass
class Message:
    role: str  # "user" ou "assistant"
    content: str


class ConversationMemory:
    """Memoria de conversa por canal Discord com sliding window."""

    def __init__(self, max_messages: int = MAX_HISTORY_PER_CHANNEL) -> None:
        self.max_messages = max_messages
        self._histories: dict[int, list[Message]] = {}

    def get_history(self, channel_id: int) -> list[Message]:
        """Retorna o historico do canal."""
        if channel_id not in self._histories:
            self._histories[channel_id] = []
        return self._histories[channel_id]

    def add_message(self, channel_id: int, role: str, content: str) -> None:
        """Adiciona uma mensagem ao historico e aplica sliding window."""
        history = self.get_history(channel_id)
        history.append(Message(role=role, content=content))

        if len(history) > self.max_messages:
            self._histories[channel_id] = history[-self.max_messages:]
            log.debug("Historico do canal %s truncado para %d mensagens", channel_id, self.max_messages)

    def get_history_text(self, channel_id: int) -> str:
        """Retorna o historico como texto formatado para incluir em prompts."""
        history = self.get_history(channel_id)
        if not history:
            return ""
        lines = []
        for msg in history:
            prefix = "Grande Mestre" if msg.role == "user" else "Arrodes"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def clear(self, channel_id: int) -> bool:
        """Limpa o historico de um canal."""
        if channel_id in self._histories:
            del self._histories[channel_id]
            log.info("Historico limpo para canal %s", channel_id)
            return True
        return False

    def clear_all(self) -> int:
        """Limpa todos os historicos. Retorna quantidade."""
        count = len(self._histories)
        self._histories.clear()
        log.info("Todos os historicos limpos (%d sessoes)", count)
        return count
