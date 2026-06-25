"""Testes da Fase 2 (speed ramp).

Os testes de parse_speed_tag e resolve_speed já passam (funções prontas).
Os demais exercitam apply_speed / speed_ramp_clips com ffmpeg real.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.ingest import Clip
from src.speed import parse_speed_tag, resolve_speed


def _clip(name: str, index: int = 0) -> Clip:
    """Cria um Clip fake só para testar a resolução de velocidade."""
    return Clip(
        path=Path(name),
        index=index,
        duration_s=4.0,
        width=1080,
        height=1920,
        fps=30.0,
    )


def _make_clip_file(path: Path, seconds: int = 4, size: str = "1080x1920") -> None:
    """Gera um clipe vertical de teste com ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"testsrc=duration={seconds}:size={size}:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-an",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


# --------------------------------------------------------------------------- #
# Funções PRONTAS — estes testes já devem passar.
# --------------------------------------------------------------------------- #

def test_parse_speed_tag() -> None:
    assert parse_speed_tag(Path("01_picar@3x.mp4")) == 3.0
    assert parse_speed_tag(Path("02_refogar@2.5x.mp4")) == 2.5
    assert parse_speed_tag(Path("03_montagem@1x.mp4")) == 1.0
    assert parse_speed_tag(Path("04_reveal@0.5x.mp4")) == 0.5
    assert parse_speed_tag(Path("05_sem_tag.mp4")) is None
    # valor inválido (zero) não conta como tag
    assert parse_speed_tag(Path("06_zero@0x.mp4")) is None


def test_resolve_speed_precedence() -> None:
    cfg = {"speed_ramp": {"default_speed": 2.0}}
    # sufixo vence o default
    assert resolve_speed(_clip("01_picar@3x.mp4"), cfg) == 3.0
    # sem sufixo cai no default
    assert resolve_speed(_clip("02_refogar.mp4"), cfg) == 2.0
    # default inválido cai em 1.0
    assert resolve_speed(_clip("x.mp4"), {"speed_ramp": {"default_speed": -1}}) == 1.0


# --------------------------------------------------------------------------- #
# apply_speed / speed_ramp_clips (Fase 2 implementada).
# --------------------------------------------------------------------------- #

def test_apply_speed_halves_duration(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg necessário.")
    from src.speed import apply_speed
    from src.utils.ffmpeg_helpers import ffprobe_metadata

    src = tmp_path / "in.mp4"
    _make_clip_file(src, seconds=4)
    cfg = {"render": {"preset": {"fps": 30, "crf": 20, "x264_preset": "ultrafast"}}}
    out = apply_speed(src, 2.0, cfg, tmp_path / "out.mp4")
    # ffprobe_metadata (helper da Fase 1) expõe a duração na chave "duration".
    dur = ffprobe_metadata(out)["duration"]
    assert abs(dur - 2.0) < 0.1  # ~metade


def test_apply_speed_passthrough(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg necessário.")
    from src.speed import apply_speed

    src = tmp_path / "in.mp4"
    _make_clip_file(src, seconds=4)
    cfg = {"render": {"preset": {"fps": 30, "crf": 20, "x264_preset": "ultrafast"}}}
    out = apply_speed(src, 1.0, cfg, tmp_path / "out.mp4")
    # short-circuit: deve retornar o próprio arquivo de entrada, sem re-encode
    assert out == src


def test_speed_ramp_clips_order_and_count(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg necessário.")
    from src.speed import speed_ramp_clips

    work = tmp_path / "work"
    work.mkdir()
    names = ["00_a@2x.mp4", "01_b@1x.mp4", "02_c.mp4"]
    cropped = []
    clips = []
    for i, n in enumerate(names):
        p = tmp_path / n
        _make_clip_file(p, seconds=2)
        cropped.append(p)
        clips.append(_clip(n, index=i))
    cfg = {
        "speed_ramp": {"default_speed": 3.0},
        "render": {"preset": {"fps": 30, "crf": 20, "x264_preset": "ultrafast"}},
    }
    out = speed_ramp_clips(clips, cropped, cfg, work)
    assert len(out) == 3
    # o clipe @1x deve ser passthrough (mesmo path de entrada)
    assert out[1] == cropped[1]
