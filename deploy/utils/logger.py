"""
Sistema de logging centralizado do Little Arrodes.
Cria logs em console e em arquivo com rotação.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# Diretório de logs
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(name: str = "arrodes") -> logging.Logger:
    """
    Configura e retorna o logger principal.

    Args:
        name: Nome do logger.

    Returns:
        Logger configurado com handlers de console e arquivo.
    """
    logger = logging.getLogger(name)

    # Evita duplicar handlers se chamado mais de uma vez
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Formato ──────────────────────────────────────────
    detailed_fmt = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(name)-20s │ %(funcName)-25s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_fmt = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Console Handler (INFO+) ──────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_fmt)
    logger.addHandler(console_handler)

    # ── Arquivo: log geral (DEBUG+) ──────────────────────
    general_log = os.path.join(LOG_DIR, "arrodes.log")
    file_handler = RotatingFileHandler(
        general_log,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_fmt)
    logger.addHandler(file_handler)

    # ── Arquivo: somente erros (ERROR+) ──────────────────
    error_log = os.path.join(LOG_DIR, "errors.log")
    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_fmt)
    logger.addHandler(error_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Retorna um logger filho do logger principal.
    Use no início de cada módulo: log = get_logger(__name__)

    Args:
        module_name: Normalmente __name__ do módulo.

    Returns:
        Logger filho com o nome do módulo.
    """
    parent = setup_logger()
    return parent.getChild(module_name)
