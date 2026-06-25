"""Fixtures compartilhadas dos testes.

Gera clipes sintéticos com `ffmpeg testsrc` para exercitar o pipeline ponta a
ponta sem precisar de arquivos de vídeo reais no repositório.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# Marca para pular testes quando o ffmpeg não estiver disponível.
ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe não disponíveis no PATH.",
)


def make_test_clip(
    path: Path,
    seconds: float = 1.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
) -> Path:
    """Gera um clipe de teste com `testsrc` na resolução informada.

    Args:
        path: Caminho de saída do clipe.
        seconds: Duração do clipe.
        width: Largura da fonte.
        height: Altura da fonte.
        fps: Frames por segundo.

    Returns:
        O caminho do clipe gerado.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={seconds}:size={width}x{height}:rate={fps}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return path


def make_test_audio(path: Path, seconds: float = 5.0) -> Path:
    """Gera um arquivo de áudio de teste (tom senoidal).

    Args:
        path: Caminho de saída do áudio.
        seconds: Duração do áudio.

    Returns:
        O caminho do áudio gerado.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}",
        "-c:a",
        "mp3",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return path


@pytest.fixture
def base_cfg(tmp_path: Path) -> dict:
    """Configuração base apontando para pastas temporárias do teste."""
    return {
        "paths": {
            "input_dir": str(tmp_path / "input"),
            "work_dir": str(tmp_path / "work"),
            "output_dir": str(tmp_path / "output"),
        },
        "crop": {"mode": "center"},
        "render": {
            "output_name": "final.mp4",
            "preset": {
                "fps": 30,
                "video_codec": "libx264",
                "x264_preset": "ultrafast",
                "crf": 23,
                "audio_codec": "aac",
                "audio_bitrate": "192k",
            },
        },
        "music": {"enabled": False, "path": ""},
    }
