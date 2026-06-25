# QUICKSTART — Como rodar o pipeline na sua máquina

Guia prático para gerar um vídeo vertical 9:16 (Reels/TikTok) a partir dos seus
clipes brutos. Cobre Fase 1 (ingest → crop → render) e Fase 2 (speed ramp).

## 1. Pré-requisito de sistema: ffmpeg

O pipeline usa `ffmpeg` e `ffprobe` (precisam estar no PATH).

```bash
# Ubuntu/Debian
sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows (winget) ou baixe de https://ffmpeg.org/download.html
winget install Gyan.FFmpeg
```

Confirme:

```bash
ffmpeg -version
ffprobe -version
```

## 2. Clonar e preparar o ambiente Python (3.11+)

```bash
git clone https://github.com/weslleyolli/VideoCreator.git
cd VideoCreator

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 3. Escolher um config

Copie um dos exemplos para `config/settings.yaml` (este arquivo é ignorado pelo
git, então suas escolhas locais não vão pro repositório):

```bash
# Sem speed ramp (comportamento da Fase 1):
cp config/settings.example.yaml config/settings.yaml

# Com speed ramp ativado (Fase 2):
cp config/settings.phase2.example.yaml config/settings.yaml
```

## 4. Colocar os clipes em `input/`

Nomeie por etapa de preparo, com prefixo numérico (define a ORDEM na timeline):

```
input/01_picar.mp4
input/02_refogar.mp4
input/03_montagem.mp4
```

### Controlar a velocidade por clipe (Fase 2)

Duas formas, em ordem de prioridade:

1. **Sufixo `@Nx` no nome do arquivo** (vence o config):
   ```
   input/01_picar@3x.mp4       # 3x mais rápido
   input/02_refogar@2.5x.mp4   # 2.5x
   input/03_montagem@1x.mp4    # tempo real (o "money shot") — passa sem re-encode
   ```
2. **`default_speed` no config** — aplicado a qualquer clipe SEM sufixo.

No `config/settings.yaml`:

```yaml
speed_ramp:
  enabled: true        # false = pipeline se comporta como a Fase 1
  default_speed: 2.0   # velocidade dos clipes sem @Nx
```

### (Opcional) Música

```yaml
music:
  enabled: true
  path: "input/music.mp3"
```

A música é loopada/cortada automaticamente para casar com a duração final do
vídeo (inclusive depois do speed ramp).

## 5. Rodar

```bash
python -m src.pipeline --config config/settings.yaml
```

Resultado em `output/final.mp4` (1080x1920). Rodar de novo sobrescreve os
intermediários (idempotente).

## 6. Conferir o resultado

```bash
# Deve imprimir 1080,1920
ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
  -of csv=p=0 output/final.mp4

# Duração final
ffprobe -v error -show_entries format=duration -of csv=p=0 output/final.mp4
```

## 7. Rodar os testes (opcional)

```bash
pytest -q
```

---

### Dicas / problemas comuns

- **"ffmpeg não encontrado"**: instale o ffmpeg (passo 1) e reabra o terminal.
- **"Nenhum clipe suportado em input/"**: extensões aceitas são `.mp4`, `.mov`,
  `.mkv`, `.avi`. Confira se os arquivos estão em `input/`.
- **Ordem errada dos clipes**: a ordem vem do prefixo numérico do nome
  (`01_`, `02_`, `10_`). O sufixo `@Nx` não interfere na ordenação.
- **Quer só testar sem clipes reais**: dá para gerar clipes sintéticos com
  `ffmpeg -f lavfi -i testsrc=duration=4:size=1280x720:rate=30 input/01_teste.mp4`.
