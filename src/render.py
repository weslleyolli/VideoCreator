"""RENDER — concatena os clipes, aplica música opcional e exporta.

Recebe os clipes já normalizados (1080x1920) do passo CROP, concatena-os
(preferindo o concat demuxer, com fallback para o concat filter em caso de
divergência), aplica trilha de música opcional e grava o `.mp4` final.

Funções das fases futuras (2–4) ficam como stubs que levantam
`NotImplementedError`. NÃO implementar nesta fase.
"""

from __future__ import annotations

from pathlib import Path

from .utils.ffmpeg_helpers import FFmpegError, ffprobe_metadata, run_ffmpeg
from .utils.logging_config import get_logger

logger = get_logger(__name__)


def render_final(
    cropped_clips: list[Path],
    cfg: dict,
    work_dir: Path,
    output_dir: Path,
) -> Path:
    """Concatena os clipes, aplica música opcional e grava o vídeo final.

    Args:
        cropped_clips: Caminhos dos clipes normalizados (na ordem da timeline).
        cfg: Configuração carregada do YAML.
        work_dir: Pasta para arquivos intermediários.
        output_dir: Pasta de saída do vídeo final.

    Returns:
        Caminho do arquivo final gravado em `output_dir`.

    Raises:
        ValueError: Se a lista de clipes estiver vazia.
    """
    if not cropped_clips:
        raise ValueError("render_final recebeu lista de clipes vazia.")

    render_cfg = cfg.get("render", {})
    preset = render_cfg.get("preset", {})
    output_name = render_cfg.get("output_name", "final.mp4")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    logger.info("RENDER: concatenando %d clipe(s).", len(cropped_clips))
    concat_path = _concat_clips(cropped_clips, work_dir, preset)

    music_cfg = cfg.get("music", {})
    if music_cfg.get("enabled"):
        music_path = Path(music_cfg["path"])
        if not music_path.exists():
            raise FileNotFoundError(
                f"music.enabled=true mas o arquivo não existe: {music_path}"
            )
        logger.info("RENDER: aplicando música %s", music_path)
        _mux_music(concat_path, music_path, output_path, preset)
    else:
        logger.info("RENDER: sem música; saída ficará sem áudio.")
        _finalize_no_music(concat_path, output_path)

    logger.info("RENDER: vídeo final gravado em %s", output_path)
    return output_path


def _clips_are_uniform(clips: list[Path]) -> bool:
    """Verifica se todos os clipes têm mesma resolução e fps.

    Args:
        clips: Caminhos dos clipes a comparar.

    Returns:
        True se resolução e fps coincidirem em todos; False caso contrário.
    """
    reference: tuple[int, int, int] | None = None
    for clip in clips:
        meta = ffprobe_metadata(clip)
        # Arredonda o fps para evitar ruído de ponto flutuante (29.97 vs 30).
        signature = (meta["width"], meta["height"], round(meta["fps"]))
        if reference is None:
            reference = signature
        elif signature != reference:
            logger.warning(
                "RENDER: divergência de parâmetros em %s (%s != %s).",
                clip.name,
                signature,
                reference,
            )
            return False
    return True


def _write_concat_list(clips: list[Path], work_dir: Path) -> Path:
    """Escreve o arquivo de lista usado pelo concat demuxer.

    Args:
        clips: Caminhos dos clipes na ordem desejada.
        work_dir: Pasta onde o `concat.txt` será gravado.

    Returns:
        Caminho do arquivo de lista gerado.
    """
    list_path = work_dir / "concat.txt"
    lines = []
    for clip in clips:
        # Usa caminho absoluto e escapa aspas simples conforme o demuxer exige.
        abs_path = str(clip.resolve()).replace("'", "'\\''")
        lines.append(f"file '{abs_path}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return list_path


def _concat_clips(clips: list[Path], work_dir: Path, preset: dict) -> Path:
    """Concatena os clipes, escolhendo demuxer (rápido) ou filter (re-encode).

    Tenta o concat demuxer com `-c copy` quando os clipes são uniformes; em
    caso de divergência ou falha do copy, cai para o concat filter.

    Args:
        clips: Clipes normalizados na ordem da timeline.
        work_dir: Pasta para intermediários.
        preset: Preset de codec/fps/crf (usado no fallback com re-encode).

    Returns:
        Caminho do vídeo concatenado (`_concat.mp4`).
    """
    concat_path = work_dir / "_concat.mp4"
    list_path = _write_concat_list(clips, work_dir)

    uniform = _clips_are_uniform(clips)
    if uniform:
        try:
            logger.info("RENDER: tentando concat demuxer (-c copy, sem re-encode).")
            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_path),
                    "-c",
                    "copy",
                    str(concat_path),
                ]
            )
            logger.info("RENDER: concat via demuxer concluído.")
            return concat_path
        except FFmpegError as exc:
            logger.warning(
                "RENDER: concat demuxer falhou, caindo para concat filter. %s",
                exc,
            )
    else:
        logger.info("RENDER: clipes divergem; usando concat filter (re-encode).")

    _concat_with_filter(clips, concat_path, preset)
    return concat_path


def _concat_with_filter(clips: list[Path], output: Path, preset: dict) -> None:
    """Concatena via concat filter, re-encodando o resultado.

    Args:
        clips: Clipes na ordem da timeline.
        output: Caminho do vídeo concatenado de saída.
        preset: Preset de codec/fps/crf.
    """
    fps = preset.get("fps", 30)
    video_codec = preset.get("video_codec", "libx264")
    x264_preset = preset.get("x264_preset", "medium")
    crf = preset.get("crf", 20)

    args: list[str] = ["-y"]
    for clip in clips:
        args += ["-i", str(clip)]

    n = len(clips)
    # Normaliza o SAR de cada entrada antes do concat: o concat filter exige
    # que todos os links tenham os mesmos parâmetros (resolução E SAR).
    prep = "".join(f"[{i}:v]setsar=1[v{i}];" for i in range(n))
    streams = "".join(f"[v{i}]" for i in range(n))
    filter_complex = f"{prep}{streams}concat=n={n}:v=1:a=0[outv]"

    args += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-r",
        str(fps),
        "-c:v",
        video_codec,
        "-preset",
        x264_preset,
        "-crf",
        str(crf),
        "-an",
        str(output),
    ]
    run_ffmpeg(args)
    logger.info("RENDER: concat via filter concluído.")


def _mux_music(
    concat_path: Path,
    music_path: Path,
    output_path: Path,
    preset: dict,
) -> None:
    """Aplica a trilha de música ao vídeo concatenado.

    A música é loopada para cobrir vídeos mais longos, normalizada com
    `loudnorm` e cortada no fim do vídeo (`-shortest`). O áudio original dos
    clipes já foi removido no passo CROP (`-an`).

    Args:
        concat_path: Vídeo concatenado (sem áudio).
        music_path: Arquivo de música.
        output_path: Caminho do vídeo final.
        preset: Preset com `audio_codec` e `audio_bitrate`.
    """
    audio_codec = preset.get("audio_codec", "aac")
    audio_bitrate = preset.get("audio_bitrate", "192k")

    run_ffmpeg(
        [
            "-y",
            "-i",
            str(concat_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter:a",
            "loudnorm",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            audio_codec,
            "-b:a",
            audio_bitrate,
            str(output_path),
        ]
    )


def _finalize_no_music(concat_path: Path, output_path: Path) -> None:
    """Grava a saída final sem áudio (copiando o vídeo concatenado).

    Args:
        concat_path: Vídeo concatenado.
        output_path: Caminho do vídeo final.
    """
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(concat_path),
            "-c:v",
            "copy",
            "-an",
            str(output_path),
        ]
    )


# ---------------------------------------------------------------------------
# Stubs de fases futuras — NÃO IMPLEMENTAR (ver AGENT_BRIEF §4).
# Mantenha as assinaturas e o `raise NotImplementedError`.
# ---------------------------------------------------------------------------


def apply_speed_ramp(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    """Fase 2 — acelera trechos repetitivos de preparo. NÃO implementado."""
    raise NotImplementedError("apply_speed_ramp: Fase 2 (fora de escopo).")


def sync_to_beat(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    """Fase 3 — alinha cortes com a batida (librosa). NÃO implementado."""
    raise NotImplementedError("sync_to_beat: Fase 3 (fora de escopo).")


def detect_dead_time(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    """Fase 4 — detecta tempo morto (OpenCV). NÃO implementado."""
    raise NotImplementedError("detect_dead_time: Fase 4 (fora de escopo).")


def add_text_overlay(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    """Fase 4 — adiciona overlays de texto. NÃO implementado."""
    raise NotImplementedError("add_text_overlay: Fase 4 (fora de escopo).")
