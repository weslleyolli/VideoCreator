"""Orquestrador do pipeline (Fase 1) + CLI.

Encadeia INGEST -> CROP -> RENDER, cuidando da configuração, da preparação
das pastas de trabalho/saída e dos logs de cada etapa.

Uso:
    python -m src.pipeline --config config/settings.yaml
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

from .crop import crop_clip
from .ingest import scan_clips
from .render import render_final
from .utils.ffmpeg_helpers import ensure_ffmpeg_available
from .utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


def _load_config(config_path: Path) -> dict:
    """Carrega o arquivo de configuração YAML em um dicionário.

    Args:
        config_path: Caminho do arquivo de configuração.

    Returns:
        Configuração como dicionário.

    Raises:
        FileNotFoundError: Se o arquivo de config não existir.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config não encontrado: {config_path}. "
            "Copie config/settings.example.yaml para config/settings.yaml."
        )
    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg


def _prepare_work_dir(work_dir: Path) -> None:
    """Cria a pasta de trabalho do zero (idempotente: limpa o que houver).

    Args:
        work_dir: Pasta de arquivos intermediários.
    """
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)


def run(config_path: Path) -> Path:
    """Executa o pipeline completo da Fase 1 e devolve o caminho final.

    Args:
        config_path: Caminho do arquivo de configuração YAML.

    Returns:
        Caminho do vídeo final gerado.
    """
    logger.info("PIPELINE: iniciando com config %s", config_path)
    ensure_ffmpeg_available()

    cfg = _load_config(config_path)
    paths_cfg = cfg.get("paths", {})

    input_dir = Path(paths_cfg.get("input_dir", "input"))
    work_dir = Path(paths_cfg.get("work_dir", "work"))
    output_dir = Path(paths_cfg.get("output_dir", "output"))

    _prepare_work_dir(work_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # INGEST
    clips = scan_clips(input_dir)

    # CROP
    cropped = [crop_clip(clip, cfg, work_dir) for clip in clips]

    # RENDER
    final = render_final(cropped, cfg, work_dir, output_dir)

    logger.info("PIPELINE: concluído. Saída em %s", final)
    return final


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Faz o parsing dos argumentos de linha de comando.

    Args:
        argv: Lista de argumentos (default: `sys.argv`).

    Returns:
        Namespace com o atributo `config`.
    """
    parser = argparse.ArgumentParser(
        prog="recipe-reels-pipeline",
        description="Pipeline de edição automática de vídeos de receita (Fase 1).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Caminho do arquivo de configuração YAML "
        f"(default: {DEFAULT_CONFIG_PATH}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da CLI.

    Args:
        argv: Argumentos de linha de comando (default: `sys.argv`).
    """
    args = _parse_args(argv)
    final = run(args.config)
    logger.info("Saída final: %s", final)


if __name__ == "__main__":
    main()
