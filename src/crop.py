"""CROP — normaliza cada clipe para 1080x1920 (vertical 9:16).

Cada clipe é re-encodado com o codec/fps do preset para que o passo de RENDER
possa concatená-los sem surpresas. Dois modos são suportados: `center`
(zoom central, padrão) e `blur_pad` (preenchimento com fundo borrado).
"""

from __future__ import annotations

from pathlib import Path

from .ingest import Clip
from .utils.ffmpeg_helpers import run_ffmpeg
from .utils.logging_config import get_logger

logger = get_logger(__name__)

# Resolução-alvo fixa para Reels/TikTok (vertical 9:16).
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def crop_clip(clip: Clip, cfg: dict, work_dir: Path) -> Path:
    """Normaliza um clipe para 1080x1920 e devolve o arquivo gerado.

    Args:
        clip: Clipe de entrada com metadados (de `scan_clips`).
        cfg: Configuração carregada do YAML. Usa `cfg["crop"]["mode"]` e
            `cfg["render"]["preset"]` (codec/fps/crf).
        work_dir: Pasta para os arquivos intermediários.

    Returns:
        Caminho do arquivo normalizado `f"{clip.index:03d}_cropped.mp4"`.

    Raises:
        NotImplementedError: Se o modo de crop não estiver implementado.
        ValueError: Se o modo de crop for desconhecido.
    """
    mode = cfg.get("crop", {}).get("mode", "center")
    preset = cfg.get("render", {}).get("preset", {})

    fps = preset.get("fps", 30)
    video_codec = preset.get("video_codec", "libx264")
    x264_preset = preset.get("x264_preset", "medium")
    crf = preset.get("crf", 20)

    output_path = work_dir / f"{clip.index:03d}_cropped.mp4"

    logger.info(
        "CROP: [%03d] %s -> %s (modo=%s)",
        clip.index,
        clip.path.name,
        output_path.name,
        mode,
    )

    if mode == "center":
        vf = (
            f"scale=-2:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},setsar=1"
        )
        args = [
            "-y",
            "-i",
            str(clip.path),
            "-vf",
            vf,
            "-r",
            str(fps),
            "-c:v",
            video_codec,
            "-preset",
            x264_preset,
            "-crf",
            str(crf),
            "-an",
            str(output_path),
        ]
        run_ffmpeg(args)

    elif mode == "blur_pad":
        filter_complex = (
            f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:"
            "force_original_aspect_ratio=increase,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},boxblur=40:10[bg];"
            f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:"
            "force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
        args = [
            "-y",
            "-i",
            str(clip.path),
            "-filter_complex",
            filter_complex,
            "-r",
            str(fps),
            "-c:v",
            video_codec,
            "-preset",
            x264_preset,
            "-crf",
            str(crf),
            "-an",
            str(output_path),
        ]
        run_ffmpeg(args)

    else:
        raise ValueError(
            f"Modo de crop desconhecido: {mode!r}. Use 'center' ou 'blur_pad'."
        )

    logger.info("CROP: [%03d] gerado %s", clip.index, output_path)
    return output_path
