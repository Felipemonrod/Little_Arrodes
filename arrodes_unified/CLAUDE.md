# Arrodes Unified - Guia para Claude Code

## Visao Geral do Projeto

Bot Discord baseado no personagem **Arrodes** de *Lord of the Mysteries*. O projeto unifica dois bots anteriores (Little Arrodes + Klein AI) em uma arquitetura modular com 3 modos de execucao.

## Arquitetura

```
arrodes_unified/
├── main.py              # Entry point unico (--mode little|arrodes|combined)
├── core/                # Nucleo compartilhado (config, RAG, LLM, persona)
│   ├── config.py        # Configuracao unificada via .env
│   ├── logger.py        # Logging centralizado com rotacao
│   ├── persona.py       # System prompts do Arrodes (little vs full)
│   ├── memory.py        # Memoria de conversa por canal com sliding window
│   ├── usage.py         # Tracker de quota (requests/tokens por dia)
│   ├── rag/             # RAG Engine (FAISS + BM25 hybrid)
│   │   ├── engine.py    # Busca hibrida com score ponderado
│   │   ├── indexer.py   # Script offline para gerar indices
│   │   └── chunker.py   # Chunking com overlap inteligente
│   └── llm/             # LLM Providers abstratos
│       ├── base.py      # Interface abstrata (LLMProvider)
│       ├── gemini.py    # Google Gemini (rapido/barato)
│       └── groq.py      # Groq LLaMA 70B (potente)
├── bot/                 # Interface Discord
│   ├── client.py        # Bot Discord (discord.py)
│   └── cogs/            # Comandos
│       ├── arrodes.py   # Cog principal (roteamento inteligente)
│       └── admin.py     # Comandos admin (reload, usage, ping)
│   └── helpers/         # Utilidades do bot
│       ├── embeds.py    # Formatacao de embeds Discord
│       └── spoiler.py   # Filtro de spoiler por Sequencia
├── api/                 # API REST (modo combined/arrodes)
│   └── server.py        # Flask endpoints (/ask, /health)
└── data/lore/           # Base de conhecimento (arquivos .txt)
```

## Modos de Execucao

| Modo | Comando | LLM | Descricao |
|------|---------|-----|-----------|
| `little` | `python main.py --mode little` | Gemini Flash | Leve, rapido, free tier |
| `arrodes` | `python main.py --mode arrodes` | Groq LLaMA 70B | Bot Discord potente |
| `combined` | `python main.py --mode combined` | Ambos | Little faz triagem, delega pro Arrodes |

## Convencoes de Codigo

- **Linguagem**: Python 3.11+
- **Async**: Todo I/O Discord e LLM usa async/await
- **Logging**: Sempre use `from core.logger import get_logger; log = get_logger(__name__)`
- **Config**: Tudo via `core.config` (nunca hardcode valores)
- **Tipos**: Type hints em todas as assinaturas de funcao
- **Imports**: Absolutos a partir da raiz do projeto (ex: `from core.config import settings`)
- **Idioma do codigo**: Ingles para nomes de variaveis/funcoes, Portugues para strings de usuario
- **Idioma dos comentarios**: Portugues

## Dependencias Principais

- `discord.py>=2.3.2` - Framework Discord
- `google-genai>=0.2.0` - Google Gemini SDK
- `groq` - Groq API client
- `faiss-cpu` - Busca vetorial
- `rank-bm25` - Busca por palavras-chave
- `flask` - API REST (modo combined)
- `numpy` - Operacoes com arrays de embeddings
- `python-dotenv` - Variaveis de ambiente

## Como Rodar

```bash
# Instalar deps
pip install -r requirements.txt

# Copiar e preencher .env
cp .env.example .env

# Gerar indices (primeira vez)
python -m core.rag.indexer

# Rodar em modo especifico
python main.py --mode little
python main.py --mode arrodes
python main.py --mode combined
```

## RAG Engine

O sistema RAG usa busca hibrida:
- **FAISS**: Busca semantica por embeddings (text-embedding-004 do Gemini)
- **BM25**: Busca por palavras-chave
- **Hybrid Score**: `alpha * faiss_score + (1 - alpha) * bm25_score` (alpha=0.7 default)
- **Indices gerados offline** pelo `core/rag/indexer.py` e salvos em `data/`
- **Arquivos de lore** ficam em `data/lore/*.txt`

## LLM Providers

Interface abstrata `LLMProvider` em `core/llm/base.py`. Implementacoes:
- `GeminiProvider`: Rapido, free tier, fallback models
- `GroqProvider`: LLaMA 70B, key rotation, potente

O roteamento no modo `combined` usa a confianca do RAG:
- Confianca >= 0.6 -> Gemini responde direto
- Confianca < 0.6 -> Delega pro Groq

## Regras Importantes

1. **Nunca commitar .env** - Contem secrets (tokens, API keys)
2. **Indices sao gerados offline** - Nao gerar no runtime do bot
3. **Respostas max 1900 chars** - Limite do Discord
4. **Spoiler filter obrigatorio** - Sequencias 0-7 devem ser mascaradas
5. **Usage tracking** - Monitorar quota do free tier Gemini
6. **Fallback responses** - Quando offline, responder com mensagens tematicas

## Pontos de Atencao

- O arquivo `caminhos_beyonder.txt` e muito grande (~1.5MB) - o chunker divide em pedacos
- Rate limiting do Gemini: 15 req/min, 300 req/h, 1500 req/dia
- Groq tem key rotation (ate 3 chaves) para contornar rate limits
- O bot precisa da intent `message_content` habilitada no Discord Developer Portal
