# Como Executar o Arrodes Unified

## Pre-requisitos

- Python 3.11+
- Token de bot Discord (https://discord.com/developers/applications)
- API Key do Google Gemini (https://aistudio.google.com/app/apikey)
- (Opcional) API Key(s) do Groq (https://console.groq.com/keys) - necessario para modo `arrodes` e `combined`

---

## 1. Instalar dependencias

```bash
cd arrodes_unified
pip install -r requirements.txt
```

Dependencias principais: `discord.py`, `google-genai`, `groq`, `faiss-cpu`, `rank-bm25`, `numpy`, `flask`, `python-dotenv`, `requests`

---

## 2. Configurar ambiente

Copie o template e preencha com suas chaves:

```bash
cp .env.example .env
```

Edite o `.env` com no minimo:

```env
DISCORD_TOKEN=seu_token_discord
GEMINI_API_KEY=sua_chave_gemini
```

Para modo `arrodes` ou `combined`, adicione tambem:

```env
GROQ_KEY_1=sua_chave_groq
```

---

## 3. Gerar indices RAG (primeira vez ou ao atualizar lore)

Este passo le todos os `.txt` de `data/lore/`, gera embeddings e salva os indices em `data/`.

```bash
python -m core.rag.indexer
```

Saida esperada:
```
Encontrados 8 arquivos de lore.
  arrodes_persona.txt: 17 chunks
  caminhos_beyonder.txt: 2031 chunks
  ...
Total: 2067 chunks gerados.
Gerando embeddings via Gemini API...
  Processado: [50/2067]
  ...
SUCESSO! Indices salvos em data/
```

**Obs:** Este processo leva alguns minutos pois faz ~2000 chamadas a API de embeddings do Gemini. Rode apenas quando adicionar/alterar arquivos de lore.

Arquivos gerados:
- `data/index.faiss` - Indice vetorial FAISS
- `data/bm25_index.pkl` - Indice de palavras-chave BM25
- `data/chunks.json` - Metadata dos chunks de texto

---

## 4. Rodar o bot

Use o **launcher (`run.py`)** para iniciar e parar o bot facilmente pelo terminal.

### Iniciar

```bash
python run.py              # modo definido no .env (ou combined)
python run.py little       # modo little (Gemini only)
python run.py arrodes      # modo arrodes (Groq only)
python run.py combined     # modo combined (roteamento inteligente)
```

### Parar

Pressione **ENTER** ou **Ctrl+C** no terminal onde o bot esta rodando.

O launcher mostra toda a saida do bot em tempo real e encerra o processo de forma limpa.

### Modo direto (sem launcher)

Se preferir rodar sem o launcher:

```bash
python main.py --mode little
python main.py --mode arrodes
python main.py --mode combined
```

Neste caso, pare apenas com **Ctrl+C**.

### Sobre os modos

| Modo | LLM | Requer | Ideal para |
|------|-----|--------|------------|
| `little` | Gemini Flash (free tier) | `DISCORD_TOKEN` + `GEMINI_API_KEY` | VPS com pouca RAM, respostas rapidas |
| `arrodes` | Groq LLaMA 3.3 70B | `DISCORD_TOKEN` + `GROQ_KEY_1` | Respostas profundas e elaboradas |
| `combined` | Ambos (roteamento) | `DISCORD_TOKEN` + `GEMINI_API_KEY` + `GROQ_KEY_1` | Melhor qualidade, triagem automatica |

No modo `combined`, o RAG avalia a confianca da busca:
- Confianca >= 0.6 -> Gemini responde (rapido)
- Confianca < 0.6 -> Groq responde (profundo)

**Tambem pode definir o modo via `.env`:**
```env
MODE=little
```

---

## 5. Usar o bot no Discord

### Invocar o Arrodes

Existem varias formas de chamar o Arrodes:

| Forma | Exemplo | Comportamento |
|-------|---------|---------------|
| Mencionar pelo nome | `arrodes` | Saudacao + espera pergunta |
| Pergunta direta | `arrodes, o que e um beyonder?` | Responde imediatamente |
| Hashtag | `#call_arrodes` | Saudacao + espera pergunta |
| Hashtag com pergunta | `#call_arrodes o que e sequencia 0` | Responde imediatamente |
| Slash command | `/ask o que e o clube do taro` | Responde imediatamente |

Quando o bot entra em modo de espera, voce tem **120 segundos** para enviar a pergunta.

**Controle de sessao:** Cada usuario so pode ter **uma interacao ativa** por vez. Se tentar invocar novamente enquanto ja tem uma sessao aberta, o bot avisa para aguardar.

### Slash Commands
- `/ask <pergunta>` - Pergunta direta ao Arrodes
- `/clear` - Limpa historico de conversa do canal
- `/usage` - Status de uso da API

### Comandos de prefixo
- `!ping` - Latencia do bot
- `!info` - Informacoes sobre o bot
- `!usage` - Status de uso da API
- `!clear` - Limpa historico

### Comandos admin (apenas dono do bot)
- `!reload arrodes` - Recarrega o cog Arrodes
- `!load <cog>` / `!unload <cog>` - Carrega/descarrega cogs
- `!sync` - Sincroniza slash commands com o Discord
- `!cogs` - Lista cogs carregados
- `!sessions` (`!ss`) - Lista sessoes ativas dos usuarios
- `!reset` (`!rs`) - Limpa todas as sessoes ativas (destravar usuarios)

**Importante:** Na primeira vez, rode `!sync` no Discord para registrar os slash commands.

---

## 6. Deploy com Docker

```bash
# Build
docker compose build

# Rodar (modo combined por padrao)
docker compose up -d

# Rodar em modo especifico
MODE=little docker compose up -d

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

---

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| `ModuleNotFoundError: No module named 'groq'` | Dependencia nao instalada | `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'faiss'` | Dependencia nao instalada | `pip install faiss-cpu` |
| `Indices RAG nao encontrados` | Indexer nao foi executado | `python -m core.rag.indexer` |
| `DISCORD_TOKEN nao definido` | .env nao configurado | Copie `.env.example` para `.env` e preencha |
| `GEMINI_API_KEY necessaria` | Chave Gemini faltando | Adicione `GEMINI_API_KEY` no `.env` |
| `models/text-embedding-004 not found` | Modelo de embedding descontinuado | Ja corrigido para `gemini-embedding-001` |
| `Bot nao responde a mensagens` | Intent message_content desabilitada | Habilite no Discord Developer Portal > Bot > Privileged Gateway Intents |
| `Slash commands nao aparecem` | Nao sincronizados | Rode `!sync` no Discord |
| `Quota excedida / modo offline` | 80% do free tier usado | Espere resetar a meia-noite ou ajuste `USAGE_THRESHOLD` |

---

## Estrutura de Arquivos Importante

```
arrodes_unified/
├── run.py               <- LAUNCHER (iniciar/parar com ENTER)
├── main.py              <- Entry point direto (parar com Ctrl+C)
├── .env                 <- SUAS CHAVES (nao committar!)
├── data/
│   ├── lore/            <- Arquivos .txt de conhecimento
│   ├── index.faiss      <- Gerado pelo indexer
│   ├── bm25_index.pkl   <- Gerado pelo indexer
│   └── chunks.json      <- Gerado pelo indexer
├── core/                <- Logica de negocio
├── bot/                 <- Interface Discord
└── api/                 <- API REST (modo combined)
```
