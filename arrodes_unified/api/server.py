"""
Servidor API REST para o modo combined.
Expoe endpoints para o Tier 1 delegar perguntas ao Tier 2.
"""

import threading

from flask import Flask, request, jsonify

from core import config
from core.llm.groq import GroqProvider
from core.rag import RAGEngine
from core.persona import get_system_prompt
from core.logger import get_logger

log = get_logger(__name__)

app = Flask(__name__)

# Inicializa componentes
_groq = GroqProvider()
_rag = RAGEngine()
_rag.load()


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de health check."""
    return jsonify({"status": "ok", "mode": config.MODE})


@app.route("/ask", methods=["POST"])
def ask_arrodes():
    """
    Endpoint principal para perguntas delegadas do Tier 1.

    Body JSON:
        query: Pergunta do usuario (obrigatorio)
        context: Contexto adicional (opcional)
        history: Historico de conversa em texto (opcional)
    """
    data = request.json
    if not data or not data.get("query"):
        return jsonify({"error": "No query provided"}), 400

    query = data["query"]
    context = data.get("context", "")
    history_text = data.get("history", "")

    # Se nao tem contexto, busca no RAG local
    if not context or context == "Contexto delegado do Tier 1.":
        rag_context, _ = _rag.check_and_search(query)
        if rag_context:
            context = rag_context

    # Monta prompt
    prompt = query
    if context:
        prompt = (
            f"[CONHECIMENTO RELEVANTE DO MUNDO ESPIRITUAL]\n{context}\n\n"
            f"[HISTORICO DA CONVERSA]\n{history_text}\n\n"
            f"[A PERGUNTA DO GRANDE MESTRE]\n{query}"
        )

    # Chama Groq sincronamente (Flask e sincrono)
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        answer = loop.run_until_complete(
            _groq.ask(
                question=prompt,
                system_prompt=get_system_prompt("arrodes"),
            )
        )
        loop.close()
    except Exception as e:
        log.error("Erro na API /ask: %s", e, exc_info=True)
        answer = "Grande Mestre, as brumas estao densas demais para responder agora..."

    return jsonify({"answer": answer})


def start_api_server(port: int | None = None) -> threading.Thread:
    """Inicia o servidor Flask em uma thread separada."""
    _port = port or config.TIER2_API_PORT

    def _run():
        log.info("API Tier 2 iniciando na porta %d...", _port)
        app.run(host="0.0.0.0", port=_port, debug=False, use_reloader=False)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    log.info("API Tier 2 rodando em background na porta %d.", _port)
    return thread
