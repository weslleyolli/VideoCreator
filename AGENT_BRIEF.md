# AGENT_BRIEF — Instruções para a IA Desenvolvedora

> **LEIA ESTE ARQUIVO PRIMEIRO, INTEIRO, ANTES DE ESCREVER QUALQUER CÓDIGO.**
> Este documento é um contrato. Se algo aqui conflitar com sua intuição, siga o documento.
> Se algo for ambíguo ou impossível, **pare e relate** em vez de adivinhar.

---

## 1. Seu papel

Você é a IA responsável por **implementar a Fase 1** de um pipeline de edição
automática de vídeos de receita. O esqueleto, os contratos de função e os
critérios de aceite já estão definidos. Seu trabalho é **preencher as
implementações marcadas com `TODO(impl)`** sem alterar as assinaturas públicas
das funções nem os formatos de entrada/saída descritos aqui.

Você **não** deve:
- Mudar nomes de funções, parâmetros ou seus tipos.
- Adicionar dependências fora de `requirements.txt` sem justificar no PR/resposta.
- Implementar features das Fases 2, 3 ou 4 (listadas adiante como FORA DE ESCOPO).
- "Melhorar" a arquitetura por conta própria. Se tiver sugestão, escreva como
  comentário `# NOTE(arch): ...` e siga o plano atual.

---

## 2. Contexto do produto (por que isso existe)

O usuário é criador de conteúdo de receitas. O formato dos vídeos é:

- **Demonstração silenciosa de preparo** (sem narração, sem fala).
- **Música de fundo** dá o ritmo.
- Destino: **Reels (Instagram) e TikTok** — ou seja, **vertical 9:16**.
- Estilo "aesthetic/ASMR cooking": cortes limpos, foco no preparo.

Implicações técnicas que JÁ foram decididas por causa disso:
- Não há transcrição de voz (não existe fala). **Não use Whisper.**
- Não há detecção de silêncio na fala (não existe fala). **Não use auto-editor.**
- O áudio original dos clipes é descartável; o que importa é a música.

---

## 3. Escopo da Fase 1 (o que VOCÊ deve construir agora)

Pipeline mínimo ponta a ponta:

```
INGEST  →  CROP 9:16  →  RENDER (concatena + música opcional + preset)
```

Resultado esperado: o usuário joga clipes brutos numa pasta, roda **um comando**,
e recebe **um arquivo .mp4 vertical (1080x1920)** pronto para subir no Reels/TikTok,
com os clipes na ordem certa e (opcionalmente) uma trilha de música por cima.

### Definição de "pronto" (Definition of Done)
A Fase 1 está concluída quando TODOS os itens abaixo forem verdadeiros:

1. `python -m src.pipeline --config config/settings.yaml` roda sem erro com
   pelo menos 2 clipes de teste na pasta `input/`.
2. O arquivo de saída existe em `output/`, tem resolução exata **1080x1920**.
3. Os clipes aparecem **na ordem definida pelo nome do arquivo** (ver §5.1).
4. Se `music.enabled: true` no config, a saída tem a trilha de música e o áudio
   original dos clipes foi removido.
5. Cada etapa loga início/fim e o caminho dos arquivos que produziu.
6. Rodar de novo não quebra (idempotente: limpa/sobrescreve os intermediários).
7. `pytest` passa (há um teste de exemplo em `tests/`; expanda se precisar).

---

## 4. FORA DE ESCOPO (não implemente — outras fases)

Estas funcionalidades têm stubs ou menções no código. **Deixe como estão.**

- **Fase 2 — Speed ramp:** acelerar trechos repetitivos. NÃO implementar.
- **Fase 3 — Beat sync:** alinhar cortes com a batida (librosa). NÃO implementar.
- **Fase 4 — Detecção de movimento (OpenCV) e overlays de texto.** NÃO implementar.

Se encontrar um stub dessas fases, mantenha a assinatura e o `raise
NotImplementedError`. Não apague.

---

## 5. Contratos de dados e comportamento

### 5.1 Ordenação dos clipes (REGRA CRÍTICA)
Os clipes são nomeados pelo usuário por etapa de preparo, com prefixo numérico:

```
01_picar.mp4
02_refogar.mp4
03_montagem.mp4
10_finalizacao.mp4
```

A ordenação **deve ser numérica natural pelo prefixo**, não alfabética simples.
Ou seja, `10_...` vem DEPOIS de `02_...` (alfabético erraria isso se fosse
`10` vs `2`, mas com zero-padding `02` o alfabético acerta — ainda assim,
**implemente ordenação natural** para tolerar nomes sem zero-padding).

Arquivos sem prefixo numérico válido → logar um WARNING e jogá-los para o fim,
em ordem alfabética entre si. Não falhe por causa disso.

### 5.2 Objeto `Clip`
Definido em `src/ingest.py`. É a unidade que trafega pelo pipeline.
Campos obrigatórios: `path`, `index`, `duration_s`, `width`, `height`, `fps`.
Metadados vêm de `ffprobe` (helper já fornecido em `utils/ffmpeg_helpers.py`).

### 5.3 Estratégia de crop 9:16 (DECISÃO JÁ TOMADA)
Alvo fixo: **1080x1920**. Dois modos, selecionáveis via config (`crop.mode`):

- `"center"` (PADRÃO): escala mantendo proporção até cobrir 1080x1920 e corta o
  excesso pelo centro (zoom-in). Para tomadas de cima (overhead) de cozinha,
  funciona bem. **Implemente este primeiro e garanta que funciona.**
- `"blur_pad"`: encaixa o frame inteiro e preenche as bordas com uma versão
  borrada do próprio vídeo (sem cortar conteúdo). Implemente se sobrar tempo;
  se não, deixe levantando `NotImplementedError` com mensagem clara.

Os comandos ffmpeg de referência para os dois modos estão em `src/crop.py`.

### 5.4 Concatenação no render
Como o passo CROP normaliza TODOS os clipes para os mesmos parâmetros
(1080x1920, mesmo codec/fps definidos no preset), use o **concat demuxer** do
ffmpeg (lista de arquivos), que é rápido e sem re-encode quando possível.
Se os parâmetros divergirem, caia para o **concat filter** (re-encode).
A regra: tente demuxer; se o ffprobe acusar divergência de codec/fps/resolução
entre os intermediários, use o filter. Documente qual caminho usou no log.

### 5.5 Música (opcional na Fase 1)
Se `music.enabled: true`:
- Carregue `music.path`.
- **Remova o áudio original** dos clipes (são silenciosos/descartáveis).
- Faça loop ou corte da música para casar com a duração total do vídeo.
- Normalize o volume da música com o filtro `loudnorm`.
Se `music.enabled: false`: a saída fica sem áudio (ou áudio silencioso). Tudo bem.

---

## 6. Convenções de código (siga à risca)

- **Python 3.11+.** Type hints obrigatórios em toda função pública.
- **ffmpeg via subprocess**, sempre usando o wrapper `run_ffmpeg()` de
  `utils/ffmpeg_helpers.py` (nunca chame `subprocess.run` direto nos módulos).
- **Nunca** monte comando ffmpeg com `shell=True` nem com f-string concatenando
  caminhos sem escape. Passe listas de argumentos.
- **Logging** via `get_logger(__name__)` de `utils/logging_config.py`.
  Proibido `print()` no código de produção.
- Caminhos com `pathlib.Path`, nunca strings cruas concatenadas com `/`.
- Arquivos intermediários vão para uma pasta temporária definida no config
  (`paths.work_dir`), não misturados com `input/` ou `output/`.
- Erros de ferramenta externa (ffmpeg/ffprobe retornando != 0) devem levantar
  uma exceção clara com o comando que falhou e o stderr capturado.
- Docstrings no estilo Google. Comentários e docstrings podem ser em português.
  Identificadores (nomes de variáveis/funções) em inglês.

---

## 7. Como verificar seu trabalho antes de entregar

1. Coloque 2–3 clipes curtos de teste em `input/` (pode gerar com ffmpeg
   `testsrc`, ver `tests/README` ou o teste de exemplo).
2. Rode `python -m src.pipeline --config config/settings.yaml`.
3. Cheque a resolução: `ffprobe -v error -select_streams v:0 -show_entries
   stream=width,height -of csv=p=0 output/final.mp4` → deve imprimir `1080,1920`.
4. Abra o vídeo e confirme a ordem dos clipes e a música (se ativada).
5. Rode `pytest -q`.

Se algum item da Definition of Done (§3) falhar, o trabalho **não** está pronto.

---

## 8. Em caso de dúvida

- Releia o `ARCHITECTURE.md` (contratos detalhados de cada função).
- Se a dúvida for de produto ("o usuário quer X ou Y?"), **não decida sozinho**:
  registre como `# QUESTION(product): ...` no ponto do código e siga a opção
  PADRÃO indicada neste brief.
- Nunca silencie um erro com `except: pass`.
