"""
Sistema de logging centralizado do Arrodes Unified.
Cria logs em console e em arquivo com rotacao.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from core.config import LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(name: str = "arrodes") -> logging.Logger:
    """Configura e retorna o logger principal."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    detailed_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console (INFO+)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(simple_fmt)
    logger.addHandler(console)

    # Arquivo geral (DEBUG+, 5MB, 5 backups)
    general_log = os.path.join(LOG_DIR, "arrodes.log")
    file_handler = RotatingFileHandler(
        general_log, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_fmt)
    logger.addHandler(file_handler)

    # Arquivo de erros (ERROR+, 2MB, 3 backups)
    error_log = os.path.join(LOG_DIR, "errors.log")
    error_handler = RotatingFileHandler(
        error_log, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_fmt)
    logger.addHandler(error_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Retorna um logger filho do logger principal."""
    parent = setup_logger()
    return parent.getChild(module_name)
