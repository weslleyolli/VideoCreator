"""Módulo SPEED — controle de velocidade por clipe (Fase 2).

Posição no pipeline: entre CROP e RENDER. Recebe clipes já cropados (1080x1920,
sem áudio) e devolve novos arquivos com a velocidade aplicada.

Contratos em ARCHITECTURE_PHASE2.md. Regras em AGENT_BRIEF_PHASE2.md.

Funções PRONTAS (não reescreva): parse_speed_tag, resolve_speed.
Funções a implementar: apply_speed, speed_ramp_clips.
Opcional: apply_intra_clip_ramp.
"""

from __future__ import annotations

import re
from pathlib import Path

from .ingest import Clip
from .utils.ffmpeg_helpers import run_ffmpeg
from .utils.logging_config import get_logger

logger = get_logger(__name__)

#: Token de velocidade no nome do arquivo: "@3x", "@2.5x", "@1x", "@0.5x".
_SPEED_TAG_RE = re.compile(r"@(\d+(?:\.\d+)?)x$")

#: Tolerância para considerar a velocidade como "tempo real" (passthrough).
_SPEED_EPS = 1e-3


def parse_speed_tag(path: Path) -> float | None:
    """Extrai o sufixo @<n>x do nome do arquivo (sem extensão).

    JÁ IMPLEMENTADO — referência da convenção (AGENT_BRIEF_PHASE2 §4).

    Returns:
        A velocidade como float, ou None se não houver tag válida.

    Exemplos:
        "01_picar@3x.mp4"     -> 3.0
        "03_montagem@1x.mp4"  -> 1.0
        "02_refogar.mp4"      -> None
    """
    match = _SPEED_TAG_RE.search(path.stem)
    if not match:
        return None
    value = float(match.group(1))
    return value if value > 0 else None


def resolve_speed(clip: Clip, cfg: dict) -> float:
    """Resolve a velocidade efetiva de um clipe pela precedência da convenção.

    JÁ IMPLEMENTADO. Ordem: sufixo @Nx > default_speed do config.

    Args:
        clip: clipe (usa clip.path para ler o sufixo).
        cfg: configuração; usa cfg["speed_ramp"]["default_speed"].

    Returns:
        Velocidade efetiva (> 0).
    """
    tag = parse_speed_tag(clip.path)
    if tag is not None:
        return tag

    default = cfg.get("speed_ramp", {}).get("default_speed", 1.0)
    try:
        default = float(default)
    except (TypeError, ValueError):
        logger.warning("default_speed inválido (%r); usando 1.0.", default)
        return 1.0
    if default <= 0:
        logger.warning("default_speed <= 0 (%r); usando 1.0.", default)
        return 1.0
    return default


def apply_speed(src: Path, speed: float, cfg: dict, out_path: Path) -> Path:
    """Aplica velocidade uniforme a UM clipe.

    Args:
        src: clipe cropado de entrada (1080x1920, sem áudio).
        speed: multiplicador (> 1 acelera, < 1 desacelera).
        cfg: configuração; usa cfg["render"]["preset"] (fps, crf, x264_preset).
        out_path: destino do clipe acelerado.

    Returns:
        Path do arquivo resultante. No caso speed == 1.0, retorna `src` sem
        re-encodar (short-circuit; ver DoD §3).
    """
    # 1. Short-circuit: tempo real não re-encoda (preserva qualidade e tempo).
    if abs(speed - 1.0) < _SPEED_EPS:
        logger.info("SPEED: passthrough (1.0x) %s", src.name)
        return src

    # 2. Parâmetros do preset (mesmos da Fase 1; render.py não muda).
    preset = cfg.get("render", {}).get("preset", {})
    fps = preset.get("fps", 30)
    crf = preset.get("crf", 20)
    x264_preset = preset.get("x264_preset", "medium")
    video_codec = preset.get("video_codec", "libx264")

    # 3. setpts=PTS/speed altera a velocidade do vídeo; fps reamostra para
    #    manter o fps consistente com o preset. -an: clipes já são mudos.
    args = [
        "-y",
        "-i",
        str(src),
        "-filter:v",
        f"setpts=PTS/{speed},fps={fps}",
        "-c:v",
        video_codec,
        "-preset",
        x264_preset,
        "-crf",
        str(crf),
        "-an",
        str(out_path),
    ]
    run_ffmpeg(args)

    logger.info("SPEED: %s -> %s (%.3gx)", src.name, out_path.name, speed)
    return out_path


def speed_ramp_clips(
    clips: list[Clip],
    cropped: list[Path],
    cfg: dict,
    work_dir: Path,
) -> list[Path]:
    """Aplica o speed ramp a todos os clipes, preservando a ordem.

    Args:
        clips: objetos Clip (para resolver a velocidade pelo nome).
        cropped: Paths dos clipes já cropados, pareados por índice com `clips`.
        cfg: configuração.
        work_dir: pasta dos intermediários.

    Returns:
        Lista de Paths (acelerados ou passthrough), na mesma ordem.

    Raises:
        ValueError: se `clips` e `cropped` tiverem tamanhos diferentes.
    """
    if len(clips) != len(cropped):
        raise ValueError(
            "speed_ramp_clips: clips e cropped têm tamanhos diferentes "
            f"({len(clips)} != {len(cropped)})."
        )

    results: list[Path] = []
    n_accel = 0
    n_passthrough = 0

    for clip, cropped_path in zip(clips, cropped):
        speed = resolve_speed(clip, cfg)
        out = work_dir / f"{clip.index:03d}_speed.mp4"
        result = apply_speed(cropped_path, speed, cfg, out)
        results.append(result)

        if abs(speed - 1.0) < _SPEED_EPS:
            n_passthrough += 1
        else:
            n_accel += 1

    logger.info(
        "SPEED: resumo — %d clipe(s) com velocidade aplicada, "
        "%d em tempo real (passthrough).",
        n_accel,
        n_passthrough,
    )
    return results


def apply_intra_clip_ramp(src: Path, cfg: dict, out_path: Path) -> Path:
    """[OPCIONAL] Ramp suave dentro de um clipe (reveal acelerando→tempo real).

    Técnica de referência (por segmentos) em ARCHITECTURE_PHASE2.md.
    Se não for implementar agora, mantenha o NotImplementedError.
    """
    raise NotImplementedError("Ramp intra-clipe: opcional na Fase 2.")
