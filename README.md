# Recipe Reels Pipeline — Fase 1

Pipeline de edição automática para vídeos de receita no formato **demonstração
silenciosa com música**, destino **Reels (Instagram) e TikTok** (vertical 9:16).

Você joga os clipes brutos numa pasta, roda um comando, e recebe um `.mp4`
vertical pronto, com os clipes na ordem certa e (opcionalmente) música por cima.

> **Status:** este repositório é um ESQUELETO. As implementações estão marcadas
> com `TODO(impl)`. A documentação de handoff para quem vai desenvolver está em
> **`AGENT_BRIEF.md`** (leia primeiro) e **`ARCHITECTURE.md`** (contratos).

---

## Para a IA / dev que vai implementar

1. Leia **`AGENT_BRIEF.md`** inteiro. Ele define escopo, regras e o que NÃO fazer.
2. Consulte **`ARCHITECTURE.md`** para os contratos de cada função.
3. Implemente apenas os `TODO(impl)`. Não mexa nas assinaturas públicas.
4. Não implemente as Fases 2–4 (stubs em `src/render.py` devem continuar levantando
   `NotImplementedError`).
5. Valide com `pytest` e com a Definition of Done do brief (§3).

---

## O fluxo (Fase 1)

```
input/ (clipes brutos)  →  INGEST  →  CROP 9:16  →  RENDER  →  output/final.mp4
```

- **INGEST** (`src/ingest.py`): lista e ordena clipes por etapa, lê metadados.
- **CROP** (`src/crop.py`): normaliza cada clipe para 1080x1920.
- **RENDER** (`src/render.py`): concatena, aplica música opcional, exporta.
- **Orquestrador** (`src/pipeline.py`): encadeia tudo + CLI.

---

## Setup

Pré-requisito de sistema: **ffmpeg** e **ffprobe** no PATH.

```bash
# Ubuntu/Debian
sudo apt install ffmpeg
# macOS
brew install ffmpeg
```

Ambiente Python (3.11+):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/settings.example.yaml config/settings.yaml
```

---

## Como rodar

1. Coloque os clipes em `input/`, nomeados por etapa de preparo:
   ```
   input/01_picar.mp4
   input/02_refogar.mp4
   input/03_montagem.mp4
   ```
2. (Opcional) Para música, ponha o arquivo e ative no config:
   ```yaml
   music:
     enabled: true
     path: "input/music.mp3"
   ```
3. Execute:
   ```bash
   python -m src.pipeline --config config/settings.yaml
   ```
4. Resultado em `output/final.mp4` (1080x1920).

---

## Mapa dos arquivos

```
recipe-reels-pipeline/
├── AGENT_BRIEF.md          ← LEIA PRIMEIRO: instruções para quem desenvolve
├── ARCHITECTURE.md         ← contratos detalhados de cada função
├── README.md               ← este arquivo
├── requirements.txt
├── config/
│   └── settings.example.yaml
├── src/
│   ├── pipeline.py         ← orquestrador + CLI            [TODO(impl)]
│   ├── ingest.py           ← lista/ordena/metadados        [TODO(impl)]
│   ├── crop.py             ← normaliza p/ 1080x1920         [TODO(impl)]
│   ├── render.py           ← concat + música + export      [TODO(impl)]
│   └── utils/
│       ├── ffmpeg_helpers.py   ← PRONTO (use, não reescreva)
│       └── logging_config.py   ← PRONTO
├── input/                  ← seus clipes brutos
├── output/                 ← saída final
└── tests/
    └── test_pipeline.py    ← testes (removha os @skip ao implementar)
```

---

## Roadmap (fases futuras — fora do escopo agora)

- **Fase 2:** speed ramp (acelerar preparo repetitivo).
- **Fase 3:** beat sync com librosa (cortes na batida).
- **Fase 4:** detecção de tempo morto (OpenCV) + overlays de texto.
