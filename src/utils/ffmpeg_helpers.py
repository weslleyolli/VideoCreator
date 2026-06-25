"""Wrappers finos sobre ffmpeg/ffprobe.

Centraliza toda a chamada de subprocess para ferramentas externas. Os módulos
do pipeline (ingest/crop/render) devem usar EXCLUSIVAMENTE estas funções e
nunca chamar `subprocess.run` diretamente.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .logging_config import get_logger

logger = get_logger(__name__)


class FFmpegError(RuntimeError):
    """Erro de execução de ffmpeg/ffprobe.

    Carrega o comando que falhou e o stderr capturado para facilitar o debug.
    """


def ensure_ffmpeg_available() -> None:
    """Verifica se `ffmpeg` e `ffprobe` estão disponíveis no PATH.

    Raises:
        FFmpegError: Se qualquer uma das ferramentas não for encontrada.
    """
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise FFmpegError(
            "Ferramentas ausentes no PATH: "
            + ", ".join(missing)
            + ". Instale o ffmpeg (inclui ffprobe) — ver README."
        )


def run_ffmpeg(args: list[str]) -> None:
    """Executa `ffmpeg` com a lista de argumentos fornecida.

    O binário `ffmpeg` é prefixado automaticamente; passe apenas os argumentos
    seguintes (ex.: `["-y", "-i", "in.mp4", ...]`).

    Args:
        args: Argumentos do ffmpeg (sem o nome do binário).

    Raises:
        FFmpegError: Se o ffmpeg retornar código de saída diferente de zero.
    """
    cmd = ["ffmpeg", *args]
    logger.debug("Executando: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise FFmpegError(
            "ffmpeg falhou (código "
            f"{proc.returncode}).\nComando: {' '.join(cmd)}\n"
            f"stderr:\n{proc.stderr.strip()}"
        )


def ffprobe_metadata(path: Path) -> dict:
    """Lê metadados do primeiro stream de vídeo via `ffprobe`.

    Args:
        path: Caminho do arquivo de vídeo.

    Returns:
        Dicionário com as chaves `width` (int), `height` (int),
        `fps` (float) e `duration` (float, em segundos).

    Raises:
        FFmpegError: Se o ffprobe falhar ou não houver stream de vídeo.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    logger.debug("Executando: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise FFmpegError(
            "ffprobe falhou (código "
            f"{proc.returncode}).\nComando: {' '.join(cmd)}\n"
            f"stderr:\n{proc.stderr.strip()}"
        )

    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise FFmpegError(f"Nenhum stream de vídeo encontrado em: {path}")

    stream = streams[0]
    width = int(stream["width"])
    height = int(stream["height"])
    fps = _parse_fraction(stream.get("r_frame_rate", "0/1"))

    # A duração pode vir no stream ou no container (format); usa o que existir.
    duration_raw = stream.get("duration") or data.get("format", {}).get("duration")
    duration = float(duration_raw) if duration_raw not in (None, "N/A") else 0.0

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
    }


def _parse_fraction(value: str) -> float:
    """Converte uma fração `"num/den"` (formato do ffprobe) em float.

    Args:
        value: String no formato `"30000/1001"` ou `"30/1"`.

    Returns:
        Valor em ponto flutuante; `0.0` se o denominador for zero/inválido.
    """
    try:
        num, _, den = value.partition("/")
        den_val = float(den) if den else 1.0
        if den_val == 0:
            return 0.0
        return float(num) / den_val
    except (ValueError, TypeError):
        return 0.0
