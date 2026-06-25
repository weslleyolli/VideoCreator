# ARCHITECTURE — Contratos dos Módulos (Fase 1)

Este documento descreve, função por função, o que cada módulo recebe e devolve.
A IA desenvolvedora deve respeitar essas assinaturas. O `AGENT_BRIEF.md` tem as
regras gerais; aqui estão os detalhes técnicos.

## Visão geral do fluxo

```
                 input/ (clipes brutos do usuário)
                          │
                          ▼
   ┌──────────────────────────────────────────────┐
   │ ingest.py                                      │
   │  scan_clips(input_dir) -> list[Clip]           │
   │  - lista, ordena (natural), lê metadados       │
   └──────────────────────────────────────────────┘
                          │ list[Clip]
                          ▼
   ┌──────────────────────────────────────────────┐
   │ crop.py                                        │
   │  crop_clip(clip, cfg) -> Path (intermediário)  │
   │  - normaliza cada clipe para 1080x1920         │
   └──────────────────────────────────────────────┘
                          │ list[Path] (clipes 9:16)
                          ▼
   ┌──────────────────────────────────────────────┐
   │ render.py                                      │
   │  render_final(clips, cfg) -> Path (output)     │
   │  - concatena + música opcional + preset        │
   └──────────────────────────────────────────────┘
                          │
                          ▼
                 output/final.mp4 (1080x1920)
```

O orquestrador (`pipeline.py`) chama os três na ordem e cuida de config + logs.

---

## Módulo: `src/ingest.py`

### `@dataclass Clip`
Estrutura imutável que representa um clipe de entrada.

| Campo        | Tipo    | Descrição                                   |
|--------------|---------|---------------------------------------------|
| `path`       | `Path`  | Caminho do arquivo original em `input/`.    |
| `index`      | `int`   | Posição final na timeline (0-based).        |
| `duration_s` | `float` | Duração em segundos (do ffprobe).           |
| `width`      | `int`   | Largura em pixels (do ffprobe).             |
| `height`     | `int`   | Altura em pixels (do ffprobe).              |
| `fps`        | `float` | Frames por segundo (do ffprobe).            |

### `scan_clips(input_dir: Path) -> list[Clip]`
- Varre `input_dir` por extensões de vídeo suportadas (`.mp4`, `.mov`, `.mkv`,
  `.avi` — defina a lista como constante `SUPPORTED_EXT`).
- Ordena por prefixo numérico natural (ver AGENT_BRIEF §5.1).
- Para cada arquivo, chama `ffprobe_metadata()` (helper) e monta um `Clip`.
- Atribui `index` sequencial após ordenar.
- Retorna lista vazia? → é erro de uso: levante `FileNotFoundError` com mensagem
  dizendo que `input/` está vazio.

---

## Módulo: `src/crop.py`

### `crop_clip(clip: Clip, cfg: dict, work_dir: Path) -> Path`
- Lê `cfg["crop"]["mode"]` (`"center"` ou `"blur_pad"`).
- Produz um arquivo normalizado **1080x1920** em `work_dir`, nomeado de forma
  determinística: `f"{clip.index:03d}_cropped.mp4"`.
- Re-encoda com o codec/fps do preset (ver `cfg["render"]["preset"]`) para que o
  render possa concatenar sem surpresas.
- Retorna o `Path` do arquivo gerado.

#### Comando de referência — modo "center"
Fonte horizontal 16:9 → vertical 9:16 com zoom central:
```
ffmpeg -y -i INPUT \
  -vf "scale=-2:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -r 30 -c:v libx264 -preset medium -crf 20 -an OUTPUT
```
Notas:
- `scale=-2:1920` garante altura 1920 mantendo proporção (largura par).
- Se a fonte já for mais "magra" que 9:16, o `force_original_aspect_ratio=increase`
  + `crop` cobre corretamente. Teste com fontes 16:9 e 9:16.
- `-an` remove áudio (música entra só no render).

#### Comando de referência — modo "blur_pad" (opcional na Fase 1)
```
ffmpeg -y -i INPUT -filter_complex \
 "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:10[bg]; \
  [0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg]; \
  [bg][fg]overlay=(W-w)/2:(H-h)/2" \
  -r 30 -c:v libx264 -preset medium -crf 20 -an OUTPUT
```
Se não for implementar agora: `raise NotImplementedError("crop mode blur_pad: Fase 1 opcional")`.

---

## Módulo: `src/render.py`

### `render_final(cropped_clips: list[Path], cfg: dict, work_dir: Path, output_dir: Path) -> Path`
Três sub-passos:

1. **Concatenar** os `cropped_clips` (ver AGENT_BRIEF §5.4).
   - Caminho rápido: concat demuxer.
     ```
     # arquivo de lista (concat.txt):
     file '/abs/path/000_cropped.mp4'
     file '/abs/path/001_cropped.mp4'
     ffmpeg -y -f concat -safe 0 -i concat.txt -c copy work_dir/_concat.mp4
     ```
   - Se `-c copy` falhar/divergir, re-encode com o concat filter.
2. **Música** (se `cfg["music"]["enabled"]`):
   ```
   ffmpeg -y -i _concat.mp4 -stream_loop -1 -i MUSIC \
     -filter:a loudnorm -map 0:v -map 1:a -shortest \
     -c:v copy -c:a aac -b:a 192k OUTPUT
   ```
   - `-shortest` corta a música no fim do vídeo.
   - `-stream_loop -1` na música cobre vídeos mais longos que a faixa.
3. **Saída**: grava em `output_dir / cfg["render"]["output_name"]` (ex.: `final.mp4`).
   Retorna o `Path`.

### Stubs de fases futuras (NÃO IMPLEMENTAR)
- `apply_speed_ramp(...)` — Fase 2.
- `sync_to_beat(...)` — Fase 3.
- `detect_dead_time(...)` / `add_text_overlay(...)` — Fase 4.
Mantenha-os com `raise NotImplementedError`.

---

## Módulo: `src/pipeline.py` (orquestrador)

### `run(config_path: Path) -> Path`
1. Carrega config (YAML) → dict.
2. Prepara `work_dir` (cria/limpa) e `output_dir`.
3. `clips = scan_clips(input_dir)`.
4. `cropped = [crop_clip(c, cfg, work_dir) for c in clips]`.
5. `final = render_final(cropped, cfg, work_dir, output_dir)`.
6. Loga o caminho final e retorna.

### CLI
`python -m src.pipeline --config config/settings.yaml`
Usar `argparse`. `--config` default = `config/settings.yaml`.

---

## Utilitários já fornecidos (use, não reescreva)

- `utils/ffmpeg_helpers.py`
  - `run_ffmpeg(args: list[str]) -> None` — roda ffmpeg, levanta erro com stderr.
  - `ffprobe_metadata(path: Path) -> dict` — devolve width/height/fps/duration.
  - `ensure_ffmpeg_available() -> None` — checa se ffmpeg/ffprobe existem no PATH.
- `utils/logging_config.py`
  - `get_logger(name: str) -> logging.Logger` — logger padronizado.
