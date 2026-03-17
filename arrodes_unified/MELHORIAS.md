# Analise de Melhorias - Arrodes Unified

Analise tecnica do estado atual do projeto e melhorias priorizadas por impacto.

---

## Problemas Atuais (Prioridade Alta)

### 1. Spoiler Filter muito simples

**Problema:** O filtro atual envolve a resposta INTEIRA em spoiler se mencionar qualquer
Sequencia de 0 a 7. Isso esconde tudo, inclusive partes sem spoiler.

**Impacto:** Ruim para usabilidade - usuario precisa clicar para ver qualquer resposta
que mencione sequencias, mesmo que seja informacao basica.

**Solucao proposta:**
- Envolver apenas o TRECHO especifico em spoiler, nao a resposta inteira
- Permitir que o usuario defina ate onde leu: `/spoiler_level 5` significaria
  que Sequencias 0-4 sao spoiler, mas 5-9 podem ser mostradas

```python
# Exemplo: em vez de || resposta inteira ||
# Fazer: "O Vidente comeca na Sequencia 9 e pode chegar a ||Sequencia 0 - O Louco||"
```

---

### 2. Historico de conversa nao persiste entre restarts

**Problema:** O `ConversationMemory` guarda tudo em memoria (dicionario Python).
Quando o bot reinicia, todo o historico de conversa e perdido.

**Impacto:** Apos reiniciar, o Arrodes "esquece" todas as conversas anteriores.

**Solucao proposta:**
- Salvar historicos em `data/conversations.json` (similar ao usage.json)
- Ou usar SQLite para historicos mais robustos
- Limpar conversas com mais de 24h automaticamente

---

### 3. Sem testes automatizados

**Problema:** Zero testes no projeto. Qualquer mudanca pode quebrar algo sem aviso.

**Impacto:** Risco alto de regressao a cada alteracao.

**Solucao proposta:**
Testes unitarios para os componentes criticos:
- `core/rag/chunker.py` - Verificar que chunks respeitam tamanho e overlap
- `bot/helpers/spoiler.py` - Verificar deteccao de sequencias
- `core/usage.py` - Verificar threshold, reset diario, persistencia
- `core/memory.py` - Verificar sliding window, clear
- `core/rag/engine.py` - Verificar hybrid score, normalizacao

---

## Melhorias de Media Prioridade

### 4. Chunking por caracteres, nao por tokens

**Problema:** O chunker divide texto por contagem de caracteres (1000 chars).
Mas os LLMs contam tokens, nao caracteres. Um chunk de 1000 chars pode ter
entre 200-400 tokens dependendo do idioma.

**Impacto:** Chunks podem ser maiores que o necessario para Portugues
(que tende a ter mais tokens por caractere que Ingles).

**Solucao proposta:**
- Usar `tiktoken` ou a contagem do proprio Gemini para chunk por tokens
- Ou ajustar CHUNK_SIZE para ~600 chars (mais seguro para PT-BR)

---

### 5. Confianca do RAG nao considera BM25 no threshold

**Problema:** A funcao `check_and_search` usa o hybrid score como confianca,
mas esse score pode ser inflado pelo BM25 quando o texto contem as mesmas
palavras mas o significado e diferente.

**Impacto:** Pode rotear perguntas para o Gemini quando deveria ir pro Groq
(falso positivo de confianca alta).

**Solucao proposta:**
- Usar apenas o score FAISS para decisao de roteamento
- Ou implementar um reranker: apos buscar top-K, usar o LLM para avaliar
  se o contexto realmente responde a pergunta

---

### 6. Rate limiting reativo, nao preventivo

**Problema:** O UsageTracker conta requests APOS elas acontecerem.
Se 10 usuarios mandarem perguntas ao mesmo tempo e faltarem apenas
5 requests para o limite, todas as 10 vao tentar e so as ultimas falham.

**Impacto:** Desperdicio de requests perto do limite.

**Solucao proposta:**
- Implementar semaforo asyncio com limite de requests simultaneas
- Verificar limites ANTES de fazer a chamada (e nao so apos)
- Implementar fila com prioridade

---

### 7. Persona do Arrodes nao usa os exemplos de dialogo

**Problema:** O arquivo `arrodes_persona.txt` tem dezenas de exemplos
excelentes de como o Arrodes fala, mas o system prompt nao os inclui
(sao apenas usados como contexto do RAG, nao como few-shot examples).

**Impacto:** O LLM as vezes responde de forma generica, sem capturar
bem o tom do personagem.

**Solucao proposta:**
- Incluir 3-5 exemplos de dialogo direto no system prompt (few-shot)
- Rotacionar exemplos aleatorios para variedade
- Separar `arrodes_persona.txt` em dois: persona (system prompt) + dialogos (RAG)

---

## Melhorias de Baixa Prioridade (Futuro)

### 8. Sliding window com resumo

**Problema:** Quando o historico passa de 20 mensagens, as antigas sao
simplesmente descartadas. O bot perde contexto de conversas longas.

**Solucao proposta:**
- Quando o historico atingir 20 mensagens, usar o LLM para resumir
  as 10 mais antigas em 2-3 frases
- Manter: resumo + ultimas 10 mensagens
- Resultado: contexto comprimido mas sem perda de informacao importante

---

### 9. Metricas e observabilidade

**Problema:** Sem metricas de performance. Nao sabemos latencia media,
taxa de erro, distribuicao de roteamento, etc.

**Solucao proposta:**
- Log estruturado (JSON) para facilitar parsing
- Registrar por request: latencia, tier usado, confianca RAG, tokens
- Comando `!stats` com metricas agregadas (media, p95, distribuicao)
- Opcional: exportar para Grafana/Prometheus

---

### 10. Suporte a imagens e arquivos

**Problema:** O bot so processa texto. Se um usuario enviar uma imagem
ou arquivo, o bot ignora.

**Solucao proposta:**
- Detectar anexos na mensagem
- Para imagens: usar Gemini Vision para descrever/analisar
- Para arquivos .txt: ler conteudo e usar como contexto adicional

---

### 11. Cache de respostas

**Problema:** Perguntas frequentes (ex: "o que e um beyonder?") sempre
fazem uma nova busca RAG + chamada LLM, gastando quota.

**Solucao proposta:**
- Cache LRU em memoria para pares (pergunta_normalizada -> resposta)
- TTL de 1 hora para evitar respostas stale
- Apenas para perguntas com confianca RAG alta (respostas factuais)

---

### 12. Melhorar base de conhecimento

**Problema:** Alguns arquivos de lore sao muito curtos (1 chunk apenas).
`faccoes.txt`, `artefatos_tchola.txt`, `worldbuilding.txt` e
`deuses_deuses_externos.txt` tem pouco conteudo.

**Solucao proposta:**
- Expandir cada arquivo com mais detalhes
- Adicionar novos arquivos: personagens principais, eventos importantes,
  sistema de magia detalhado, localizacoes
- Considerar adicionar conteudo de Circle of Inevitability (sequencia)

---

## Tabela Resumo

| # | Melhoria | Impacto | Esforco | Prioridade |
|---|----------|---------|---------|------------|
| 1 | Spoiler filter granular | Alto | Baixo | Alta |
| 2 | Persistir historico | Medio | Baixo | Alta |
| 3 | Testes automatizados | Alto | Medio | Alta |
| 4 | Chunk por tokens | Medio | Baixo | Media |
| 5 | Confianca RAG melhor | Medio | Medio | Media |
| 6 | Rate limiting preventivo | Medio | Medio | Media |
| 7 | Few-shot no system prompt | Alto | Baixo | Media |
| 8 | Sliding window com resumo | Baixo | Alto | Baixa |
| 9 | Metricas/observabilidade | Baixo | Alto | Baixa |
| 10 | Suporte a imagens | Baixo | Medio | Baixa |
| 11 | Cache de respostas | Medio | Medio | Baixa |
| 12 | Expandir lore | Alto | Alto | Baixa |

**Recomendacao de ordem de implementacao:**
1. Few-shot no system prompt (#7) - maior impacto na qualidade com menor esforco
2. Spoiler filter granular (#1) - melhora usabilidade rapido
3. Persistir historico (#2) - evita frustracao de usuarios
4. Testes (#3) - protege contra regressoes antes de mais mudanças
5. Chunk por tokens (#4) - melhora qualidade do RAG
