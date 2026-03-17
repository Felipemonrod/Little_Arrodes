"""
Arrodes Unified - Entry Point.

Uso:
    python main.py --mode little     # So Gemini (leve)
    python main.py --mode arrodes    # So Groq (potente)
    python main.py --mode combined   # Ambos com roteamento

Ou defina MODE no .env.
"""

import argparse
import asyncio
import os
import sys

# Garante que o diretorio do projeto esta no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Arrodes Unified Bot")
    parser.add_argument(
        "--mode",
        choices=["little", "arrodes", "combined"],
        default=None,
        help="Modo de execucao (default: valor do .env ou 'combined')",
    )
    args = parser.parse_args()

    # Se --mode foi passado, sobrescreve a env
    if args.mode:
        os.environ["MODE"] = args.mode

    # Importa apos definir MODE para que config.py leia o valor correto
    from core import config
    from core.logger import setup_logger

    log = setup_logger()
    mode = config.MODE

    log.info("=" * 50)
    log.info("Arrodes Unified - Modo: %s", mode.upper())
    log.info("=" * 50)

    # Valida config
    errors = config.validate_config(mode)
    if errors:
        for err in errors:
            log.critical("CONFIG ERROR: %s", err)
        log.critical("Corrija o .env e tente novamente.")
        sys.exit(1)

    # No modo combined, inicia a API do Tier 2 em background
    if mode == "combined":
        from api.server import start_api_server
        start_api_server()
        log.info("API Tier 2 iniciada em background.")

    # Inicia o bot Discord
    from bot.client import run_bot

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log.info("Bot encerrado pelo usuario (Ctrl+C).")
    except Exception as e:
        log.critical("Erro fatal: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
