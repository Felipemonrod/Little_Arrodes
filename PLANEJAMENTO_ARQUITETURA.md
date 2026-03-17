# PLANEJAMENTO E ARQUITETURA DO SISTEMA V2 (HARMONIZAÇÃO ARRODES)

A arquitetura foi redesenhada para um modelo de **Roteamento Inteligente (Agentic Routing)**. O objetivo é garantir que o bot rode no servidor VPS KVM2 da Hostinger (com pouca RAM), abolindo definitivamente o uso do Google Colab, dividindo a carga e mantendo a Inteligência em alto nível.

## 1. Melhorias Base na Inteligência Artificial
Para deixar o Arrodes mais inteligente e responsivo, implementaremos as seguintes mecânicas no núcleo:
- **Chunking com Overlap (Sobreposição):** A leitura dos arquivos anexados de Lore não corta mais frases no meio por acidente. Textos são mastigados com uma "margem" de sobreposição (ex: pedaços de 1000 tokens com 200 sobrepostos), retendo o sentido semântico total.
- **Memória de Conversa (Contexto de Sessão):** Fim da "amnésia". O bot terá um cache rápido em memória das últimas 5 mensagens enviadas pelo usuário, permitindo fluxo de conversa contínuo e contextual.
- **Prompting Restrito e Otimizado:** Refinaremos radicalmente o sistema de instruções ao LLM. Inseriremos bloqueios absolutos ("nunca confesse ser uma IA"), tom de deboche, lealdade à imagem de um espelho mágico contida no Lord of the Mysteries.

## 2. Abordagem de Indexação Offline (FAISS + Gemini)
O grande gargalo de servidor (RAM) era injetar e processar IA de embeddings (Sentence-Transformers/PyTorch) em runtime. Solução implementada:
- **Indexador Offline (uild_index.py):** Esse script é rodado manualmente quando se insere arquivo novo. Ele processa todos os txt usando a API externa do Gemini (google.genai text-embedding-004).
- **Banco FAISS Estático:** Os vetores gerados pelo Google viram um snapshot binário super compactado chamado index.faiss e um mapeamento via BM25 (m25_index.pkl).
- **Zero Custo de RAM no KVM2:** Quando rodar o Deploy, o bot sobe instanteamente lendo o pequeno arquivo .faiss congelado da memória ram, caindo o custo do microserviço para menos de 50MB.

## 3. Os Dois Níveis de Agência (Tiers)

### Tier 1: Little Arrodes (O Bot Roteador Front-End)
A interface primária, ligada ao Discord. Faz varreduras supersônicas nos índices FAISS/BM25 offline.
- **Trigger de Teste Isolada:** Responderá restritamente a mensagens que contenham gatilhos manuais (ex: #invocar_arrodes ou "arrodes tenho uma pergunta"), previnindo conflitos bizarros contra o bot base atualmente online lá no seu servidor produtivo.
- **Filtro Estrito de Spoiler:** Ele analisa obrigatoriamente e aplica as tags do discord || spoiler || mascarando textos associados às Sequências críticas do livro (ex: Caminhos do nível 7 até o nível 0).
- **Gatilho de Delegação (Anti-Alucinação):** Ele analisa a semelhança do texto local. Se a taxa de aprovação da busca do FAISS não exibir clareza ou a respostá não for "Pronta", ele não responde; ele silencia e repassa (via POST) toda a dúvida do usuário pra máquina mais inteligente lidar (Bot 2).

### Tier 2: Klein AI (O Master Cérebro Profundo)
Para perguntas que exigem interligar conceitos da Lore pesada quando o Bot 1 hesita.
- Deixa de acessar o Discord por si próprio e vira uma **API Flask/Backend** assíncrona. 
- Processa inferências pesadas invocando os prompts em cima da requisição do Tier 1, e faz a solicitação ao LLaMA 3 70B (Groq). Ele entrega a resposta inteligente já redigida de volta para o *Little Arrodes* realizar a devolutiva no chat do usuário.

## 4. Estratégia de Deploy no Servidor (Hostinger)
Os dois bots operarão dentro do mesmo VPS através de um Container docker-compose. Comunicando-se apenas via rede virtual do Docker. Nenhum servidor Google Colab de repescagem será empenhado: as lógicas RAG ocorrendo sobre a Base FB FAISS binária e o LLM Cloud Groq eliminam integralmente estrangulamentos do KVM2.