"""Testes da Fase 1 do pipeline.

Cobrem ordenação natural no INGEST, normalização 9:16 no CROP, concatenação/
música no RENDER, idempotência do orquestrador e os stubs das fases futuras.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from src import render
from src.crop import TARGET_HEIGHT, TARGET_WIDTH, crop_clip
from src.ingest import Clip, scan_clips
from src.pipeline import run

from .conftest import ffmpeg_required, make_test_audio, make_test_clip


def _probe_resolution(path: Path) -> tuple[int, int]:
    """Lê (width, height) de um arquivo de vídeo via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    w, h = out.split(",")
    return int(w), int(h)


def _has_audio(path: Path) -> bool:
    """Indica se o arquivo possui ao menos um stream de áudio."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return bool(out)


# --------------------------------------------------------------------------- #
# INGEST
# --------------------------------------------------------------------------- #


@ffmpeg_required
def test_scan_clips_natural_order(tmp_path: Path) -> None:
    """Os clipes devem ser ordenados numericamente, não alfabeticamente."""
    input_dir = tmp_path / "input"
    # Cria fora de ordem; 10_ deve vir DEPOIS de 2_ (natural, não alfabético).
    make_test_clip(input_dir / "10_finalizacao.mp4", seconds=0.5)
    make_test_clip(input_dir / "2_refogar.mp4", seconds=0.5)
    make_test_clip(input_dir / "01_picar.mp4", seconds=0.5)

    clips = scan_clips(input_dir)
    names = [c.path.name for c in clips]
    assert names == ["01_picar.mp4", "2_refogar.mp4", "10_finalizacao.mp4"]
    assert [c.index for c in clips] == [0, 1, 2]


@ffmpeg_required
def test_scan_clips_no_prefix_goes_last(tmp_path: Path) -> None:
    """Arquivos sem prefixo numérico vão para o fim, sem quebrar o pipeline."""
    input_dir = tmp_path / "input"
    make_test_clip(input_dir / "01_picar.mp4", seconds=0.5)
    make_test_clip(input_dir / "outro.mp4", seconds=0.5)

    clips = scan_clips(input_dir)
    assert clips[-1].path.name == "outro.mp4"


def test_scan_clips_empty_raises(tmp_path: Path) -> None:
    """Pasta de entrada vazia deve levantar FileNotFoundError."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        scan_clips(input_dir)


# --------------------------------------------------------------------------- #
# CROP
# --------------------------------------------------------------------------- #


@ffmpeg_required
def test_crop_center_produces_vertical(tmp_path: Path, base_cfg: dict) -> None:
    """Modo center deve produzir um arquivo exatamente 1080x1920."""
    src = make_test_clip(tmp_path / "in.mp4", seconds=0.5, width=1280, height=720)
    clip = Clip(path=src, index=0, duration_s=0.5, width=1280, height=720, fps=30)
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    out = crop_clip(clip, base_cfg, work_dir)
    assert out.name == "000_cropped.mp4"
    assert _probe_resolution(out) == (TARGET_WIDTH, TARGET_HEIGHT)


@ffmpeg_required
def test_crop_center_from_vertical_source(tmp_path: Path, base_cfg: dict) -> None:
    """Fonte já vertical (9:16) também deve sair 1080x1920."""
    src = make_test_clip(tmp_path / "in.mp4", seconds=0.5, width=720, height=1280)
    clip = Clip(path=src, index=1, duration_s=0.5, width=720, height=1280, fps=30)
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    out = crop_clip(clip, base_cfg, work_dir)
    assert _probe_resolution(out) == (TARGET_WIDTH, TARGET_HEIGHT)


def test_crop_unknown_mode_raises(tmp_path: Path, base_cfg: dict) -> None:
    """Modo de crop desconhecido deve levantar ValueError."""
    base_cfg["crop"]["mode"] = "diagonal"
    clip = Clip(
        path=tmp_path / "x.mp4", index=0, duration_s=1, width=10, height=10, fps=30
    )
    with pytest.raises(ValueError):
        crop_clip(clip, base_cfg, tmp_path)


# --------------------------------------------------------------------------- #
# RENDER / PIPELINE ponta a ponta
# --------------------------------------------------------------------------- #


def _write_config(tmp_path: Path, cfg: dict) -> Path:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return config_path


@ffmpeg_required
def test_pipeline_end_to_end_no_music(tmp_path: Path, base_cfg: dict) -> None:
    """Pipeline completo sem música: saída 1080x1920 e sem áudio."""
    input_dir = Path(base_cfg["paths"]["input_dir"])
    make_test_clip(input_dir / "01_a.mp4", seconds=0.5)
    make_test_clip(input_dir / "02_b.mp4", seconds=0.5)

    config_path = _write_config(tmp_path, base_cfg)
    final = run(config_path)

    assert final.exists()
    assert _probe_resolution(final) == (TARGET_WIDTH, TARGET_HEIGHT)
    assert not _has_audio(final)


@ffmpeg_required
def test_pipeline_idempotent(tmp_path: Path, base_cfg: dict) -> None:
    """Rodar duas vezes não deve quebrar (limpa/sobrescreve intermediários)."""
    input_dir = Path(base_cfg["paths"]["input_dir"])
    make_test_clip(input_dir / "01_a.mp4", seconds=0.5)
    make_test_clip(input_dir / "02_b.mp4", seconds=0.5)

    config_path = _write_config(tmp_path, base_cfg)
    final1 = run(config_path)
    final2 = run(config_path)
    assert final1 == final2
    assert final2.exists()


@ffmpeg_required
def test_pipeline_with_music(tmp_path: Path, base_cfg: dict) -> None:
    """Com música ativada, a saída deve conter trilha de áudio."""
    input_dir = Path(base_cfg["paths"]["input_dir"])
    make_test_clip(input_dir / "01_a.mp4", seconds=0.5)
    make_test_clip(input_dir / "02_b.mp4", seconds=0.5)
    music = make_test_audio(input_dir / "music.mp3", seconds=3.0)

    base_cfg["music"] = {"enabled": True, "path": str(music)}
    config_path = _write_config(tmp_path, base_cfg)
    final = run(config_path)

    assert _probe_resolution(final) == (TARGET_WIDTH, TARGET_HEIGHT)
    assert _has_audio(final)


@ffmpeg_required
def test_render_concat_filter_fallback(tmp_path: Path, base_cfg: dict) -> None:
    """O fallback por concat filter deve gerar 1080x1920 (re-encode)."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    cropped = []
    for i, (w, h) in enumerate([(1280, 720), (1920, 1080), (640, 480)]):
        src = make_test_clip(tmp_path / f"in{i}.mp4", seconds=0.5, width=w, height=h)
        clip = Clip(path=src, index=i, duration_s=0.5, width=w, height=h, fps=30)
        cropped.append(crop_clip(clip, base_cfg, work_dir))

    out = work_dir / "_filter.mp4"
    render._concat_with_filter(cropped, out, base_cfg["render"]["preset"])
    assert _probe_resolution(out) == (TARGET_WIDTH, TARGET_HEIGHT)


# --------------------------------------------------------------------------- #
# Stubs das fases futuras (devem permanecer não implementados)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "func",
    [
        render.apply_speed_ramp,
        render.sync_to_beat,
        render.detect_dead_time,
        render.add_text_overlay,
    ],
)
def test_future_phase_stubs_raise(func) -> None:
    """Funções das Fases 2–4 devem permanecer levantando NotImplementedError."""
    with pytest.raises(NotImplementedError):
        func()
