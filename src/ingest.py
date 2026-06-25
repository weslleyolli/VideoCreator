"""INGEST — lista, ordena e lê metadados dos clipes de entrada.

Responsável por varrer `input/`, ordenar os clipes por etapa de preparo
(ordenação numérica natural pelo prefixo do nome) e produzir objetos `Clip`
com os metadados lidos via ffprobe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .utils.ffmpeg_helpers import ffprobe_metadata
from .utils.logging_config import get_logger

logger = get_logger(__name__)

# Extensões de vídeo suportadas na entrada.
SUPPORTED_EXT: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".avi")


@dataclass(frozen=True)
class Clip:
    """Representa um clipe de entrada e seus metadados.

    Attributes:
        path: Caminho do arquivo original em `input/`.
        index: Posição final na timeline (0-based).
        duration_s: Duração em segundos (do ffprobe).
        width: Largura em pixels (do ffprobe).
        height: Altura em pixels (do ffprobe).
        fps: Frames por segundo (do ffprobe).
    """

    path: Path
    index: int
    duration_s: float
    width: int
    height: int
    fps: float


# Captura um prefixo numérico no começo do nome do arquivo (ex.: "01_picar").
_PREFIX_RE = re.compile(r"^(\d+)")


def _sort_key(path: Path) -> tuple[int, float, str]:
    """Gera a chave de ordenação natural para um arquivo de clipe.

    Arquivos com prefixo numérico vêm primeiro, ordenados pelo valor do número.
    Arquivos sem prefixo válido são jogados para o fim e ordenados
    alfabeticamente entre si.

    Args:
        path: Caminho do arquivo.

    Returns:
        Tupla `(grupo, valor_numerico, nome)` usada como chave de `sorted`.
        `grupo` 0 = tem prefixo, 1 = sem prefixo (vai para o fim).
    """
    match = _PREFIX_RE.match(path.name)
    name_lower = path.name.lower()
    if match:
        return (0, float(int(match.group(1))), name_lower)
    logger.warning(
        "Clipe sem prefixo numérico, jogado para o fim: %s", path.name
    )
    return (1, float("inf"), name_lower)


def scan_clips(input_dir: Path) -> list[Clip]:
    """Varre o diretório de entrada e devolve os clipes ordenados.

    Args:
        input_dir: Diretório com os clipes brutos do usuário.

    Returns:
        Lista de `Clip` ordenada pela etapa de preparo (prefixo natural),
        com `index` sequencial atribuído após a ordenação.

    Raises:
        FileNotFoundError: Se `input_dir` não existir ou não houver clipes
            suportados nele.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Diretório de entrada não existe: {input_dir}")

    logger.info("INGEST: varrendo clipes em %s", input_dir)

    files = [
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
    ]

    if not files:
        raise FileNotFoundError(
            f"Nenhum clipe suportado em {input_dir} "
            f"(extensões aceitas: {', '.join(SUPPORTED_EXT)}). "
            "Coloque os clipes brutos na pasta input/."
        )

    ordered = sorted(files, key=_sort_key)

    clips: list[Clip] = []
    for index, path in enumerate(ordered):
        meta = ffprobe_metadata(path)
        clip = Clip(
            path=path,
            index=index,
            duration_s=meta["duration"],
            width=meta["width"],
            height=meta["height"],
            fps=meta["fps"],
        )
        clips.append(clip)
        logger.info(
            "INGEST: [%03d] %s (%dx%d, %.2fs, %.2ffps)",
            clip.index,
            path.name,
            clip.width,
            clip.height,
            clip.duration_s,
            clip.fps,
        )

    logger.info("INGEST: %d clipe(s) prontos para processamento.", len(clips))
    return clips
