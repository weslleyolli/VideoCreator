"""Configuração padronizada de logging para o pipeline.

Fornece `get_logger` para que todos os módulos compartilhem o mesmo formato
de saída. Use sempre este helper em vez de `print()` no código de produção.
"""

from __future__ import annotations

import logging
import sys

# Formato único para todo o pipeline: hora, nível, módulo e mensagem.
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# Garante que a configuração de handlers aconteça apenas uma vez.
_CONFIGURED = False


def _configure_root() -> None:
    """Configura o handler raiz uma única vez (idempotente)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Evita handlers duplicados se algo já tiver configurado o root.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger padronizado para o módulo informado.

    Args:
        name: Normalmente `__name__` do módulo chamador.

    Returns:
        Logger configurado com o formato padrão do pipeline.
    """
    _configure_root()
    return logging.getLogger(name)
