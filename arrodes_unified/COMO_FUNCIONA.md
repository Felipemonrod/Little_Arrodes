# Como o Arrodes Unified Funciona

Guia completo explicando o funcionamento interno do bot, passo a passo.

---

## 1. Inicializacao (o que acontece ao rodar `python run.py little`)

### 1.1 Launcher (`run.py`)

```
Voce executa: python run.py little
         |
         v
run.py detecta o argumento "little"
         |
         v
Cria um subprocesso: python main.py --mode little
         |
         v
Mostra toda a saida do bot no terminal
         |
         v
Fica esperando ENTER ou Ctrl+C para matar o subprocesso
```

### 1.2 Entry Point (`main.py`)

```
main.py recebe --mode little
         |
         v
Define os.environ["MODE"] = "little"
         |
         v
Importa core.config (que le o .env e as variaveis de ambiente)
         |
         v
Valida a configuracao:
  - DISCORD_TOKEN existe? (obrigatorio sempre)
  - GEMINI_API_KEY existe? (obrigatorio para modo little e combined)
  - GROQ_KEY_1 existe? (obrigatorio para modo arrodes e combined)
         |
         v
Se modo == "combined": inicia API Flask em thread daemon (porta 8080)
         |
         v
Chama bot.client.run_bot()
```

### 1.3 Bot Discord (`bot/client.py`)

```
run_bot() cria o bot Discord com:
  - Prefixo: ! (ou o que estiver no .env)
  - Intents: message_content habilitada
         |
         v
Carrega os Cogs (modulos de comando):
  1. bot.cogs.arrodes  -> ArrodesCog (logica principal)
  2. bot.cogs.admin    -> AdminCog (comandos admin)
         |
         v
Conecta ao Discord via websocket
         |
         v
Evento on_ready() dispara:
  - Loga informacoes (nome do bot, servidores, modo)
  - Define status: "Assistindo: atraves do espelho | #call_arrodes"
         |
         v
Bot fica ouvindo eventos do Discord (mensagens, interacoes)
```

### 1.4 Inicializacao do ArrodesCog (`bot/cogs/arrodes.py`)

Quando o cog Arrodes e carregado, ele inicializa todos os componentes:

```
ArrodesCog.__init__()
         |
         +-- ConversationMemory() -> dicionario vazio de historicos por canal
         |
         +-- RAGEngine().load() -> carrega os 3 arquivos de indice do disco:
         |     - data/index.faiss (vetores FAISS, ~24MB)
         |     - data/bm25_index.pkl (indice BM25, ~2MB)
         |     - data/chunks.json (2067 chunks de texto)
         |
         +-- UsageTracker() -> carrega data/usage.json (ou cria novo se dia mudou)
         |     - Monitora requests e tokens gastos no dia
         |     - Se >= 80% do limite: ativa modo offline
         |
         +-- Se modo "little" ou "combined":
         |     GeminiProvider() -> conecta ao Google Gemini API
         |
         +-- Se modo "arrodes" ou "combined":
               GroqProvider() -> prepara chaves Groq para rotacao
```

---

## 2. Fluxo de uma Pergunta (passo a passo)

### 2.1 Usuario envia mensagem no Discord

Exemplo: usuario digita `arrodes, o que e um beyonder?`

```
Discord envia evento on_message()
         |
         v
Verificacoes iniciais:
  - Autor e bot? -> ignora
  - Mensagem vazia? -> ignora
  - Usuario ja tem sessao ativa? (perguntando ou processando)
    -> Se sim: "ja estou atendendo seu pedido anterior"
         |
         v
Detecta trigger: a palavra "arrodes" esta na mensagem?
  -> Sim! Regex \barrodes\b encontrou match
         |
         v
Tem pergunta embutida? Remove "arrodes" e ve o que sobra:
  "arrodes, o que e um beyonder?" -> "o que e um beyonder?"
  -> Sobrou >= 5 caracteres, entao e uma pergunta direta
         |
         v
Vai direto para _process_question()
```

Se o usuario tivesse enviado apenas `arrodes`:
```
Sobra "" apos remover "arrodes" (< 5 chars)
         |
         v
Nao e pergunta direta -> entra em modo de espera
         |
         v
Bot responde: "*O espelho pisca...*  Ah, Grande Mestre deseja saber algo?"
         |
         v
Inicia timeout de 120 segundos
         |
         v
Proxima mensagem do mesmo usuario naquele canal sera a pergunta
```

### 2.2 Processamento da Pergunta (`_process_question`)

```
Marca usuario como "processando" (bloqueia novas interacoes)
         |
         v
Ativa indicador "digitando..." no Discord
         |
         v
Chama _route_and_answer(channel_id, pergunta)
```

### 2.3 Roteamento Inteligente (`_route_and_answer`)

#### Passo 1: Busca no RAG

```
RAGEngine.check_and_search("o que e um beyonder?")
         |
         v
Gera embedding da pergunta via Gemini API:
  - Envia texto para modelo gemini-embedding-001
  - Recebe vetor de ~768 dimensoes
         |
         v
Busca FAISS (semantica):
  - Compara vetor da pergunta com todos os 2067 vetores do indice
  - Retorna os 5 mais similares com distancias L2
  - Normaliza distancias para scores [0, 1]: score = 1 / (1 + distancia)
         |
         v
Busca BM25 (palavras-chave):
  - Tokeniza a pergunta: ["o", "que", "e", "um", "beyonder"]
  - Calcula relevancia por frequencia de termos em cada chunk
  - Retorna os 5 mais relevantes
  - Normaliza scores para [0, 1]
         |
         v
Combina scores (Hybrid):
  - Para cada chunk encontrado (FAISS ou BM25):
    score_final = 0.7 * score_faiss + 0.3 * score_bm25
  - Ordena por score_final decrescente
  - Retorna top 5 chunks + confianca (score do melhor resultado)
         |
         v
Retorna: (contexto_string, confianca)
  - contexto_string = chunks concatenados (ou "" se confianca < 0.6)
  - confianca = 0.0 a 1.0
```

#### Passo 2: Escolha do LLM

```
confianca = 0.82 (exemplo)
         |
         v
Modo "little":
  -> Sempre usa Gemini, independente da confianca
  -> Passa o contexto do RAG se disponivel

Modo "arrodes":
  -> Sempre usa Groq, independente da confianca
  -> Passa o contexto do RAG se disponivel

Modo "combined":
  -> confianca >= 0.6 E tem contexto? -> Gemini (rapido)
  -> confianca < 0.6 OU sem contexto? -> Groq (profundo)
```

#### Passo 3: Chamada ao LLM

**Se Gemini (Tier 1):**

```
Verifica se esta offline (quota >= 80%)
  -> Se sim: retorna mensagem de fallback tematica
         |
         v
Monta o prompt:
  "Baseado nisto:
   [contexto do RAG - chunks relevantes]

   Responda como Arrodes a pergunta: o que e um beyonder?"
         |
         v
Monta historico de conversa do canal (ultimas 20 mensagens)
         |
         v
Envia para Google Gemini API:
  - System prompt: persona do Little Arrodes (conciso, mistico)
  - Historico + prompt enriquecido
  - Max tokens: 1500
         |
         v
Se modelo principal falha: tenta modelos fallback (gemini-2.0-flash)
         |
         v
Extrai tokens usados da resposta (usage_metadata)
         |
         v
Registra uso no UsageTracker:
  - Incrementa contador de requests do dia
  - Soma tokens (prompt + resposta)
  - Verifica se atingiu 80% do limite
  - Salva em data/usage.json
```

**Se Groq (Tier 2):**

```
Monta o prompt:
  "[CONHECIMENTO RELEVANTE]
   [contexto do RAG]

   [PERGUNTA DO GRANDE MESTRE]
   o que e um beyonder?"
         |
         v
Monta mensagens no formato OpenAI:
  - {"role": "system", "content": persona do Arrodes Full}
  - {"role": "user/assistant", ...}  (historico)
  - {"role": "user", "content": prompt}
         |
         v
Embaralha as API keys disponíveis (GROQ_KEY_1, _2, _3)
         |
         v
Tenta cada key:
  - Se retorna 429 (rate limit): tenta proxima key
  - Se funciona: retorna resposta
  - Se todas falham: mensagem de erro tematica
         |
         v
Chamada e feita em thread separada (asyncio.to_thread)
para nao bloquear o event loop do Discord
```

### 2.4 Pos-processamento

```
Resposta do LLM recebida
         |
         v
Filtro de Spoiler:
  - Regex procura "sequencia [0-7]" (case insensitive)
  - Se encontra: envolve TODA a resposta em || spoiler ||
         |
         v
Salva no historico de conversa:
  - memory.add_message(canal, "user", pergunta)
  - memory.add_message(canal, "assistant", resposta)
  - Se historico > 20 mensagens: descarta as mais antigas (sliding window)
         |
         v
Monta embed Discord:
  - Titulo: "Arrodes Responde"
  - Campo "Pergunta": a pergunta do usuario (max 1024 chars)
  - Campo "Resposta": a resposta do Arrodes (max 1024 chars)
  - Footer: tier que respondeu (ex: "via Gemini Flash")
  - Cor: roxo (148, 103, 189)
         |
         v
Envia embed como reply da mensagem do usuario
         |
         v
Libera a sessao do usuario (remove de _processing)
  -> Usuario pode fazer nova pergunta
```

---

## 3. Sistema RAG em Detalhe

### 3.1 O que e RAG?

RAG = Retrieval Augmented Generation.
Em vez de o LLM inventar respostas, primeiro buscamos informacao relevante
nos arquivos de lore e passamos como contexto para o LLM responder com base em fatos.

### 3.2 Indexacao Offline (`python -m core.rag.indexer`)

Este processo roda uma unica vez (ou quando os arquivos de lore mudam):

```
data/lore/*.txt (8 arquivos de conhecimento)
         |
         v
Chunker (core/rag/chunker.py):
  - Le cada arquivo
  - Divide em pedacos de ~1000 caracteres
  - Sobreposicao de 200 caracteres entre pedacos
  - Tenta cortar em limites de frase (ponto, interrogacao, paragrafo)
  - Ignora pedacos com menos de 50 caracteres
  - Total: ~2067 chunks
         |
         v
Embedding (Gemini API):
  - Para cada chunk, envia ao modelo gemini-embedding-001
  - Recebe um vetor numerico que representa o significado do texto
  - ~2067 chamadas a API (leva alguns minutos)
         |
         v
Indice FAISS:
  - Cria IndexFlatL2 com todos os vetores
  - Salva em data/index.faiss (~24MB)
  - Permite busca por similaridade semantica ultrarapida
         |
         v
Indice BM25:
  - Tokeniza cada chunk (split por espacos)
  - Cria indice BM25Okapi
  - Salva em data/bm25_index.pkl (~2MB)
  - Permite busca por palavras-chave
         |
         v
Metadados:
  - Salva a lista de chunks em data/chunks.json (~2MB)
  - Permite recuperar o texto original dado um indice
```

### 3.3 Por que dois indices?

- **FAISS (semantico):** Entende que "poção mistica" e "bebida sobrenatural" sao similares,
  mesmo sem compartilhar palavras. Bom para perguntas conceituais.

- **BM25 (keywords):** Encontra documentos que contem exatamente as palavras da busca.
  Bom para nomes proprios (ex: "Klein Moretti", "Audrey Hall").

- **Hybrid:** Combina os dois com peso 70% FAISS + 30% BM25 para ter o melhor dos dois mundos.

---

## 4. Sistema de Memoria

### 4.1 Memoria de Conversa (`core/memory.py`)

```
Canal #geral:
  [user]      "o que e um beyonder?"
  [assistant] "Grande Mestre, um Beyonder e alguem que..."
  [user]      "e como eles ganham poder?"
  [assistant] "Atraves das pocoes misticas, Grande Mestre..."
  ... (max 20 mensagens = 10 pares)
```

- Cada canal Discord tem seu proprio historico
- Historico e passado ao LLM para manter contexto de conversa
- Quando passa de 20 mensagens, as mais antigas sao descartadas (sliding window)
- Comando `!clear` ou `/clear` limpa o historico do canal

### 4.2 Persistencia de Uso (`core/usage.py`)

```
data/usage.json:
{
  "date": "2026-03-16",
  "requests": 42,
  "tokens": 15000,
  "is_offline": false
}
```

- Salvo em disco apos cada request (sobrevive a restarts)
- Reseta automaticamente quando detecta um novo dia
- Quando requests ou tokens atingem 80% do limite diario:
  - Bot entra em "modo offline"
  - Retorna mensagens tematicas pre-escritas em vez de chamar a API
  - Reseta automaticamente a meia-noite

---

## 5. Controle de Sessao

### 5.1 Como funciona

O bot mantem dois registros:

```
_waiting = {user_id: channel_id}     # Usuarios esperando para enviar pergunta
_processing = {user_id}              # Usuarios cuja pergunta esta sendo processada
```

### 5.2 Regras

1. Um usuario so pode ter **uma sessao ativa** por vez (em qualquer canal)
2. Se tentar invocar de novo enquanto espera ou processa: recebe aviso
3. A sessao expira apos **120 segundos** de inatividade (timeout)
4. A sessao e **sempre liberada** apos a resposta (mesmo se der erro)
5. Admin pode ver sessoes com `!sessions` e limpar com `!reset`

### 5.3 Ciclo de vida de uma sessao

```
[LIVRE] -> usuario invoca arrodes -> [ESPERANDO] (max 120s)
                                          |
                                    usuario envia pergunta
                                          |
                                          v
                                    [PROCESSANDO]
                                          |
                                    resposta enviada (ou erro)
                                          |
                                          v
                                       [LIVRE]
```

---

## 6. Providers de LLM

### 6.1 Interface Abstrata (`core/llm/base.py`)

Todos os providers implementam o mesmo metodo:

```python
async def ask(question, system_prompt, history) -> str
```

Isso permite trocar o LLM sem mudar o codigo do bot.

### 6.2 GeminiProvider (`core/llm/gemini.py`)

- **API:** Google Gemini (google-genai SDK)
- **Modelo:** gemini-2.5-flash (fallback: gemini-2.0-flash)
- **Limite free tier:** 1500 req/dia, 15 req/min
- **Historico:** Formato Content/Part nativo do Gemini
- **Fallback:** Se modelo principal falha, tenta modelos alternativos
- **Tokens:** Extrai usage_metadata da resposta para tracking

### 6.3 GroqProvider (`core/llm/groq.py`)

- **API:** Groq Cloud (SDK groq)
- **Modelo:** llama-3.3-70b-versatile
- **Key rotation:** Ate 3 chaves, embaralhadas a cada request
- **Rate limit:** Se recebe 429, tenta a proxima chave automaticamente
- **Async:** Roda em thread separada (asyncio.to_thread) pois o SDK e sincrono

---

## 7. API REST (Modo Combined)

Quando roda em modo `combined`, o `main.py` inicia um servidor Flask em background:

```
Thread daemon -> Flask na porta 8080

Endpoints:
  GET  /health  -> {"status": "ok", "mode": "combined"}
  POST /ask     -> Recebe pergunta, busca no RAG, chama Groq, retorna resposta
```

No modo combined, o ArrodesCog pode delegar perguntas para este endpoint
quando a confianca do RAG e baixa, usando a funcao `_ask_tier2_api()`.

Porem, na implementacao atual, o modo combined chama o GroqProvider diretamente
(sem passar pela API HTTP), o que e mais eficiente.

---

## 8. Filtro de Spoiler

```python
# Regex: sequ[eê]ncia [0-7]  (case insensitive)

"O caminho do Vidente vai da Sequencia 9 ate a Sequencia 0"
                                                  ^^^^^^^^^
                                           Match! Sequencia 0

-> Resposta inteira envolvida em || spoiler ||
-> Aparece escondida no Discord, usuario clica para ver
```

Protege conteudo sensivel do lore (Sequencias de nivel alto sao spoilers do livro).

---

## 9. Diagrama Completo do Fluxo

```
                    DISCORD
                       |
                 [Mensagem do Usuario]
                       |
                       v
              +------------------+
              |   on_message()   |
              +------------------+
                       |
            +----------+----------+
            |                     |
     Tem sessao ativa?     Detecta trigger?
     "ja estou atendendo"  (arrodes, #call, etc)
            |                     |
            x              +------+------+
                           |             |
                    Tem pergunta?   So invocacao
                    embutida?       "arrodes"
                           |             |
                           v             v
                   Responde       Saudacao +
                   direto         espera pergunta
                           |             |
                           v             v
                  +-------------------+
                  | _process_question |
                  +-------------------+
                           |
                           v
                  +-------------------+
                  |  RAG Engine       |
                  |  (FAISS + BM25)   |
                  +-------------------+
                           |
                    contexto + confianca
                           |
              +------------+------------+
              |            |            |
        modo little   modo combined  modo arrodes
              |            |            |
              v      confianca?         v
           Gemini    >= 0.6  < 0.6    Groq
              |        |       |        |
              v        v       v        v
           Gemini   Gemini   Groq     Groq
              |        |       |        |
              +--------+-------+--------+
                           |
                           v
                  +-------------------+
                  | Spoiler Filter    |
                  +-------------------+
                           |
                           v
                  +-------------------+
                  | Salva historico   |
                  +-------------------+
                           |
                           v
                  +-------------------+
                  | Monta Embed       |
                  +-------------------+
                           |
                           v
                      DISCORD
                  (reply com embed)
```

---

## 10. Arquivos de Lore (Base de Conhecimento)

Os arquivos em `data/lore/` sao a fonte de conhecimento do Arrodes:

| Arquivo | Conteudo | Chunks |
|---------|----------|--------|
| `arrodes_persona.txt` | Personalidade, exemplos de dialogo, estilo de fala | ~17 |
| `caminhos_beyonder.txt` | 22 caminhos com todas as Sequencias (9 a 0) | ~2031 |
| `conceitos.txt` | Beyonder, Sequencias, Digestao de Pocao, Loucura | ~13 |
| `tarot_club_pt.txt` | Membros do Clube do Taro, caminhos, caracteristicas | ~2 |
| `deuses_deuses_externos.txt` | Deuses ortodoxos e Grandes Antigos | ~1 |
| `faccoes.txt` | Igrejas, organizacoes secretas, familias antigas | ~1 |
| `artefatos_tchola.txt` | Artefatos selados, classificacao, exemplos | ~1 |
| `worldbuilding.txt` | 5 epocas da historia do mundo | ~1 |

Para adicionar novo conhecimento:
1. Crie um arquivo `.txt` em `data/lore/`
2. Rode `python -m core.rag.indexer` para reindexar
3. Reinicie o bot
