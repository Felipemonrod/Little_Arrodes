"""
Chunker inteligente com overlap para textos de lore.
Divide textos em pedacos sobrepostos para nao cortar frases no meio.
"""

CHUNK_SIZE = 1000
OVERLAP = 200
MIN_CHUNK_LENGTH = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """
    Divide texto em chunks com sobreposicao.

    Args:
        text: Texto completo para dividir.
        chunk_size: Tamanho maximo de cada chunk em caracteres.
        overlap: Quantidade de caracteres sobrepostos entre chunks.

    Returns:
        Lista de chunks de texto.
    """
    # Limpa quebras de linha excessivas
    text = text.replace("\n\n\n", "\n\n")
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Tenta cortar em um limite natural (fim de frase ou paragrafo)
        if end < len(text):
            # Procura o ultimo ponto final, interrogacao ou exclamacao
            last_sentence_end = max(
                chunk.rfind(". "),
                chunk.rfind("? "),
                chunk.rfind("! "),
                chunk.rfind("\n\n"),
                chunk.rfind("\n"),
            )
            if last_sentence_end > chunk_size // 2:
                chunk = chunk[:last_sentence_end + 1]
                end = start + last_sentence_end + 1

        chunk = chunk.strip()
        if len(chunk) >= MIN_CHUNK_LENGTH:
            chunks.append(chunk)

        # Avanca com overlap
        start = end - overlap if end < len(text) else len(text)

    return chunks
