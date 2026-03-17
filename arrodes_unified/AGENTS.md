# Arrodes Unified - Guia de Agentes

Este documento descreve os agentes/componentes do sistema e como eles interagem entre si.
Use este guia para entender a arquitetura ao retomar o trabalho no projeto.

---

## Agente 1: Little Arrodes (Tier 1 - Frontend Rapido)

### Responsabilidades
- Interface direta com o Discord (recebe mensagens, envia embeds)
- Busca rapida no RAG local (FAISS + BM25)
- Responde perguntas simples usando Gemini Flash (free tier)
- Filtra spoilers automaticamente (Sequencias 0-7)
- Monitora quota de uso da API

### Triggers
- `#invocar_arrodes` ou `#call_arrodes` no chat
- `"arrodes tenho uma pergunta"` em linguagem natural
- Mencao direta ao bot (@Arrodes)

### Fluxo
1. Usuario envia trigger -> Bot responde com saudacao
2. Usuario envia pergunta -> Bot busca no RAG
3. Se confianca >= 0.6 -> Responde via Gemini Flash
4. Se confianca < 0.6 -> Delega para Agente 2 (modo combined) ou responde com Gemini mesmo (modo little)

### Arquivos Chave
- `bot/cogs/arrodes.py` - Logica principal
- `core/llm/gemini.py` - Provider Gemini
- `core/rag/engine.py` - Busca hibrida
- `bot/helpers/spoiler.py` - Filtro de spoiler

---

## Agente 2: Klein AI / Arrodes Full (Tier 2 - Cerebro Profundo)

### Responsabilidades
- Processar perguntas complexas que exigem raciocinio profundo
- Usar LLaMA 3.3 70B via Groq para respostas mais inteligentes
- Servir como API REST no modo combined
- Pode rodar como bot Discord independente no modo arrodes

### Endpoint API (modo combined)
```
POST /ask
{
    "query": "pergunta do usuario",
    "context": "contexto do RAG",
    "history": "historico de conversa"
}
-> {"answer": "resposta do Arrodes"}
```

### Arquivos Chave
- `api/server.py` - Servidor Flask
- `core/llm/groq.py` - Provider Groq
- `core/persona.py` - Prompts especificos do Arrodes full

---

## Agente 3: RAG Engine (Agente de Conhecimento)

### Responsabilidades
- Indexar offline os arquivos de lore (data/lore/*.txt)
- Gerar embeddings via Gemini text-embedding-004
- Manter indices FAISS e BM25 em disco
- Busca hibrida com score ponderado

### Pipeline de Indexacao
```
data/lore/*.txt
    -> Chunker (1000 chars, 200 overlap)
    -> Gemini Embeddings (text-embedding-004)
    -> FAISS Index (IndexFlatL2) -> data/index.faiss
    -> BM25 Index (BM25Okapi) -> data/bm25_index.pkl
    -> Chunks metadata -> data/chunks.json
```

### Pipeline de Busca
```
Query do usuario
    -> Embedding da query (Gemini)
    -> FAISS search (top 5, score normalizado)
    -> BM25 search (top 5, score normalizado)
    -> Hybrid score = 0.7 * faiss + 0.3 * bm25
    -> Retorna top 5 chunks + confianca
```

### Arquivos Chave
- `core/rag/engine.py` - Motor de busca
- `core/rag/indexer.py` - Gerador de indices
- `core/rag/chunker.py` - Divisor de texto

---

## Fluxo de Comunicacao entre Agentes

### Modo `little` (Somente Tier 1)
```
Discord -> Little Arrodes -> RAG -> Gemini -> Discord
```

### Modo `arrodes` (Somente Tier 2)
```
Discord -> Arrodes Full -> RAG -> Groq -> Discord
```

### Modo `combined` (Ambos)
```
Discord -> Little Arrodes -> RAG -> Confianca?
    |                                    |
    |  >= 0.6: Gemini responde       < 0.6: Delega
    |       |                              |
    v       v                              v
Discord <- Resposta            POST /ask -> Klein AI API
                                              |
                               Groq LLaMA 70B + RAG
                                              |
                               Discord <- Resposta
```

---

## Tabela de Modos vs Componentes Ativos

| Componente | `little` | `arrodes` | `combined` |
|------------|----------|-----------|------------|
| Discord Bot | Sim | Sim | Sim |
| Gemini LLM | Sim | Nao | Sim |
| Groq LLM | Nao | Sim | Sim |
| RAG Engine | Sim | Sim | Sim |
| API Flask | Nao | Nao | Sim (interno) |
| Usage Tracker | Sim | Sim | Sim |
| Spoiler Filter | Sim | Sim | Sim |

---

## Tarefas Pendentes / Roadmap

### Fase 1 - Core (Prioridade Alta)
- [x] Estrutura de pastas unificada
- [x] Config unificado com .env
- [x] Logger centralizado
- [x] LLM Provider abstrato (Gemini + Groq)
- [x] RAG Engine hibrida (FAISS + BM25)
- [x] Chunker com overlap
- [x] Indexer offline
- [x] Usage Tracker com persistencia
- [x] Persona do Arrodes (prompts)
- [x] Memoria de conversa (sliding window)

### Fase 2 - Bot Discord
- [x] Client Discord com cog loader
- [x] Cog Arrodes (roteamento inteligente)
- [x] Cog Admin (reload, usage, ping, info)
- [x] Embed builder
- [x] Spoiler filter

### Fase 3 - API e Integracao
- [x] Servidor Flask para modo combined
- [x] Entry point com --mode flag

### Fase 4 - Deploy
- [x] Dockerfile
- [x] docker-compose.yml com profiles
- [x] .env.example completo

### Fase 5 - Melhorias Futuras
- [ ] Testes unitarios (RAG, spoiler, usage, LLM providers)
- [ ] Reranking com LLM dos resultados do RAG
- [ ] Sliding window com resumo (comprimir historico antigo)
- [ ] Comando /spoiler_level (usuario define ate onde leu)
- [ ] Metricas de latencia por request
- [ ] Log estruturado (JSON) para observabilidade
- [ ] CI/CD pipeline
- [ ] Rate limiting mais sofisticado (token bucket)

---

## Troubleshooting Comum

### "Indice nao encontrado"
Rode `python -m core.rag.indexer` para gerar os indices FAISS/BM25.

### "GOOGLE_API_KEY nao encontrada"
Verifique se o `.env` tem `GEMINI_API_KEY` preenchido.

### "Quota excedida"
O bot entra em modo offline automaticamente em 80% de uso.
Reseta a meia-noite. Ajuste `USAGE_THRESHOLD` no `.env` se necessario.

### "Erro ao conectar ao Tier 2"
No modo combined, o Flask sobe na porta definida em `TIER2_API_PORT` (default 8080).
Verifique se a porta nao esta ocupada.

### "Bot nao responde a mensagens"
Verifique se a intent `message_content` esta habilitada no Discord Developer Portal.
