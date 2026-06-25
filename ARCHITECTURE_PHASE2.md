# ARCHITECTURE — FASE 2 (Speed Ramp)

Contratos do módulo novo `src/speed.py`. Regras gerais no `AGENT_BRIEF_PHASE2.md`.

## Posição no fluxo

```
ingest → crop → [SPEED]  → render
                  ▲ nova etapa da Fase 2 (desligável via config)
```

A etapa de speed recebe os clipes JÁ cropados (1080x1920, sem áudio) e devolve
novos arquivos com a velocidade aplicada, prontos para o render concatenar.

---

## Módulo: `src/speed.py`

### `parse_speed_tag(path: Path) -> float | None`  [JÁ IMPLEMENTADO]
Extrai o sufixo `@<n>x` do nome do arquivo. Use, não reescreva.
- `01_picar@3x.mp4` → `3.0`
- `03_montagem@1x.mp4` → `1.0`
- `02_refogar.mp4` → `None` (sem tag)

### `resolve_speed(clip: Clip, cfg: dict) -> float`  [JÁ IMPLEMENTADO]
Aplica a precedência da convenção (AGENT_BRIEF §4):
1. `parse_speed_tag(clip.path)` se houver e for válido (> 0).
2. senão `cfg["speed_ramp"]["default_speed"]`.
Valida e cai no default com WARNING se a tag for inválida.

### `apply_speed(src: Path, speed: float, cfg: dict, out_path: Path) -> Path`  [TODO(impl)]
Aplica velocidade uniforme a UM clipe via ffmpeg.

- Se `speed == 1.0` (use tolerância, ex.: `abs(speed-1.0) < 1e-3`):
  **NÃO re-encodar.** Retorne `src` diretamente (short-circuit, DoD §3).
- Caso contrário, re-encode com `setpts` mantendo o preset:

  Comando de referência (traduzir para list[str] de args; `run_ffmpeg` já põe o
  "ffmpeg" inicial):

```
  -y -i <src>
  -filter:v "setpts=PTS/<speed>,fps=<preset_fps>"
  -c:v libx264 -preset <x264_preset> -crf <crf> -an
  <out_path>
```

  - `setpts=PTS/speed`: speed=3 → 3x mais rápido. speed=0.5 → 2x mais lento.
  - `fps=<preset_fps>`: reamostra para manter o fps consistente (use o fps do
    `cfg["render"]["preset"]`, default 30).
  - `-an`: os clipes cropados já são mudos; mantém assim.
  - crf / x264_preset vêm de `cfg["render"]["preset"]`.
- Logar `src (dur Xs) → out (speed Nx)`.
- Retornar `out_path` (ou `src` no caso short-circuit).

### `speed_ramp_clips(clips: list[Clip], cropped: list[Path], cfg: dict, work_dir: Path) -> list[Path]`  [TODO(impl)]
Orquestra a etapa para todos os clipes.

- Pré-condição: `len(clips) == len(cropped)`, pareados por índice (mesma ordem).
- Para cada par `(clip, cropped_path)`:
  - `speed = resolve_speed(clip, cfg)`
  - `out = work_dir / f"{clip.index:03d}_speed.mp4"`
  - `result = apply_speed(cropped_path, speed, cfg, out)`
  - acumula `result` (pode ser o próprio `cropped_path` no short-circuit).
- Retornar a lista de Paths resultante, NA MESMA ORDEM.
- Logar um resumo (quantos acelerados, quantos passaram em 1.0).

### `apply_intra_clip_ramp(src: Path, cfg: dict, out_path: Path) -> Path`  [OPCIONAL — pode ficar como NotImplementedError]
Efeito de reveal: acelerado no corpo do clipe, desacelerando até tempo real no fim.

Técnica de referência (abordagem por segmentos, sem filtros exóticos):
1. Definir N segmentos no clipe (ex.: 4). Atribuir velocidades decrescentes
   (ex.: 4x, 3x, 2x, 1x) do início para o fim.
2. Recortar cada segmento (`-ss`/`-to`), aplicar `setpts` por segmento.
3. Concatenar os segmentos (mesmo padrão do render: concat demuxer).
4. Opcional: um leve crossfade entre segmentos para suavizar.

Parâmetros (segmentos, curva) deveriam vir de `cfg["speed_ramp"]["intra_clip"]`.
Se não implementar: `raise NotImplementedError("Ramp intra-clipe: opcional na Fase 2")`.

---

## Interações que NÃO devem mudar

- `render_final` permanece intacto. A música (`-stream_loop -1` + `-shortest`)
  absorve a nova duração total automaticamente.
- `crop_clip` permanece intacto: continua produzindo `{index:03d}_cropped.mp4`.
- `scan_clips`/`Clip` permanecem intactos: o `clip.path` original (com o sufixo
  `@Nx`) é o que `resolve_speed` lê.
