# AGENT_BRIEF — FASE 2 (Speed Ramp)

> **LEIA ESTE ARQUIVO INTEIRO ANTES DE ESCREVER QUALQUER CÓDIGO.**
> A Fase 1 já está implementada, testada e mergeada. Esta fase é ADITIVA.
> Se algo aqui conflitar com sua intuição, siga o documento. Se algo for
> ambíguo ou impossível, **pare e relate** em vez de adivinhar.

---

## 1. Seu papel

Implementar a **Fase 2** do Recipe Reels Pipeline: o **speed ramp** (controle de
velocidade por clipe). O esqueleto, os contratos e os critérios de aceite estão
definidos aqui e em `ARCHITECTURE_PHASE2.md`. Preencha os `TODO(impl)` do módulo
novo `src/speed.py` e faça a ÚNICA alteração permitida no `pipeline.py`.

Você **não** deve:
- Alterar `ingest.py`, `crop.py`, `render.py` nem os utilitários. **Nenhuma linha.**
- Mudar assinaturas públicas existentes da Fase 1.
- Implementar Fases 3 (beat sync) ou 4 (movimento/overlays).
- Quebrar o comportamento da Fase 1 quando o speed ramp estiver desligado.

---

## 2. Contexto e decisões já tomadas

Formato dos vídeos: demonstração silenciosa de preparo, com música, vertical 9:16.
O objetivo do speed ramp no nosso caso é: **acelerar o preparo repetitivo**
(picar, mexer, refogar) e **segurar em tempo real o momento do prato pronto**
(o "money shot").

Decisões de arquitetura (NÃO reabrir):

- **Posição no pipeline:** entre CROP e RENDER → `ingest → crop → speed → render`.
  O módulo de speed recebe os caminhos dos clipes JÁ cropados (1080x1920) e
  devolve novos caminhos com a velocidade aplicada.
- **A velocidade é DECLARADA, não detectada.** Detecção automática de tempo morto
  é Fase 4. Aqui o usuário declara a velocidade (ver §4).
- **Áudio:** os clipes cropados já vêm sem áudio (`-an` na Fase 1). O speed mexe
  só no vídeo (`setpts`). Nada de `atempo`.
- **RENDER NÃO MUDA.** O render já usa `-stream_loop -1` + `-shortest` na música,
  então a mudança de duração dos clipes é absorvida automaticamente. **Não toque
  no render.py.** Se você sentir vontade de mexer lá, pare — está errado.

---

## 3. Escopo da Fase 2

### Obrigatório
- Novo módulo `src/speed.py` com aplicação de **velocidade uniforme por clipe**.
- Resolução da velocidade de cada clipe por: (a) sufixo no nome do arquivo, senão
  (b) `default_speed` do config (ver §4).
- Short-circuit: clipe com velocidade efetiva **1.0 passa direto, sem re-encode**
  (preserva qualidade e tempo).
- Integração no `pipeline.py` guardada por flag `speed_ramp.enabled`.
- Bloco de config novo `speed_ramp` (ver §6).
- Testes novos em `tests/test_speed.py` (alguns já escritos; remova os `@skip`).

### Opcional (dentro da Fase 2, só se sobrar tempo)
- **Ramp intra-clipe**: dentro de UM clipe, acelerar e desacelerar suavemente até
  o tempo real no fim (efeito cinematográfico de reveal). Contrato e técnica de
  referência em `ARCHITECTURE_PHASE2.md`. Se não for implementar, deixe a função
  `apply_intra_clip_ramp` levantando `NotImplementedError` com mensagem clara.

### FORA DE ESCOPO
- Fase 3 (beat sync / librosa) e Fase 4 (OpenCV / overlays). Não tocar.
- Slow motion suave com interpolação de frames (`minterpolate`). Velocidades < 1.0
  são permitidas mas podem ficar "picotadas"; interpolação fica para depois.

---

## 4. Convenção de velocidade (REGRA CRÍTICA)

A velocidade efetiva de cada clipe é resolvida nesta ordem de precedência:

1. **Sufixo no nome do arquivo** (maior prioridade): um token `@<n>x` antes da
   extensão. Exemplos:
   - `01_picar@3x.mp4`   → 3.0x (3x mais rápido)
   - `02_refogar@2.5x.mp4` → 2.5x
   - `03_montagem@1x.mp4` → 1.0x (tempo real — o money shot)
   - `04_reveal@0.5x.mp4` → 0.5x (slow, pode picotar — ver §3)
   O parser é `parse_speed_tag()` em `src/speed.py` (JÁ IMPLEMENTADO como referência
   — use, não reescreva).
2. **`default_speed`** do config, aplicado a qualquer clipe sem sufixo.

Notas:
- O sufixo `@Nx` NÃO interfere na ordenação da Fase 1 (que olha o prefixo numérico).
- Velocidade deve ser > 0. Valor inválido → logar WARNING e cair no `default_speed`.

---

## 5. Definition of Done (todos verdadeiros)

1. `speed_ramp.enabled: true`, `default_speed: 2.0`: um clipe cropado de ~4s vira
   ~2s no arquivo de saída do speed (tolerância de ±1 frame).
2. Um clipe nomeado `...@3x.mp4` fica ~3x mais rápido, ignorando o `default_speed`.
3. Clipe com velocidade efetiva 1.0 **passa sem re-encode** (mesma duração; o
   caminho retornado pode ser o próprio arquivo de entrada).
4. `speed_ramp.enabled: false`: o pipeline se comporta EXATAMENTE como a Fase 1
   (a etapa de speed é pulada por completo; mesma duração final).
5. A saída final continua **1080x1920** e com `fps` igual ao do preset.
6. Com música ligada, ela mapeia para a nova duração total — **sem nenhuma
   alteração no render.py** (validação de que a Fase 1 absorve a mudança).
7. Idempotente: rodar de novo limpa/sobrescreve os intermediários do speed.
8. `pytest` verde: os testes novos da Fase 2 passam E os da Fase 1 continuam passando.

---

## 6. A ÚNICA alteração em arquivo existente

### 6.1 `pipeline.py` — inserir a etapa de speed entre crop e render

Localize, dentro de `run()`, o trecho equivalente a:

```python
cropped = [crop_clip(c, cfg, work_dir) for c in clips]
final = render_final(cropped, cfg, work_dir, output_dir)
```

Insira a etapa de speed ENTRE as duas linhas, guardada por flag:

```python
cropped = [crop_clip(c, cfg, work_dir) for c in clips]

# --- FASE 2: speed ramp (aditivo, desligável) ---
if cfg.get("speed_ramp", {}).get("enabled", False):
    from .speed import speed_ramp_clips
    cropped = speed_ramp_clips(clips, cropped, cfg, work_dir)
# -------------------------------------------------

final = render_final(cropped, cfg, work_dir, output_dir)
```

Regras:
- Quando `enabled` for ausente/false, NADA muda (import nem acontece).
- `speed_ramp_clips` recebe os `clips` (objetos Clip, p/ ler o nome do arquivo e
  resolver `@Nx`) E os `cropped` (Paths já normalizados, que serão acelerados).
  Retorna a nova lista de Paths, na mesma ordem.

### 6.2 `config/settings.example.yaml` — adicionar o bloco abaixo

```yaml
speed_ramp:
  enabled: true
  # Velocidade padrão para clipes sem sufixo @Nx no nome.
  default_speed: 2.0
```

(Um exemplo completo está em `config/settings.phase2.example.yaml`.)

---

## 7. Convenções de código

Idênticas à Fase 1: Python 3.11+, type hints, ffmpeg via `run_ffmpeg()`, logging
via `get_logger()`, `pathlib.Path`, sem `print()`, sem `shell=True`. Intermediários
do speed vão para `work_dir`, nomeados de forma determinística:
`f"{clip.index:03d}_speed.mp4"`.

---

## 8. Em caso de dúvida

- Detalhes de cada função: `ARCHITECTURE_PHASE2.md`.
- Dúvida de produto ("qual velocidade default?"): use o PADRÃO do config e
  registre `# QUESTION(product): ...`. Não decida sozinho mudando contrato.
- Nunca silencie erro com `except: pass`. Nunca toque em render.py/crop.py/ingest.py.
