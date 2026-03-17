"""Interface abstrata para LLM Providers."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface base que todo provider de LLM deve implementar."""

    @abstractmethod
    async def ask(
        self,
        question: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Envia uma pergunta ao LLM e retorna a resposta.

        Args:
            question: Pergunta/prompt do usuario.
            system_prompt: Instrucoes de sistema (persona).
            history: Historico de conversa [{"role": "user|assistant", "content": "..."}].

        Returns:
            Texto da resposta do LLM.
        """
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Retorna nome identificador do provider."""
        ...
