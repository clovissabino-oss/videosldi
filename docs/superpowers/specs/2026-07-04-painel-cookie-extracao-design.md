# Design — Painel "Colar cookie e extrair" (Visualizador LDI)

_Data: 2026-07-04 · Status: aprovado para plano de implementação_

## 1. Contexto e problema

Hoje, para gerar os dados de vídeos do LDI, o usuário (Luiz) faz um vaivém manual:
abre o admin no Chrome → **F12 → Network → copia o header `cookie:`** → cola no
`cookie.txt` (ou no popover 🍪) → depois clica separadamente para extrair → espera →
os resultados carregam na árvore. São passos desconexos, e o gerenciamento de
credencial ainda mistura arquivos e (para o Metabase) a pasta de *outro* aplicativo.

O objetivo desta etapa é **ampliar o projeto a nível de aplicação** começando pelo ponto
de entrada: transformar o "colar o cookie do F12" no gatilho único que já traz todos os
vídeos. Sem nenhuma integração externa nova nesta fase.

## 2. Objetivo da v1 (escopo)

Um painel no Visualizador onde o usuário **cola o cookie do LDI (o que sai do F12),
opcionalmente ajusta o concurso, e clica um botão que salva, valida, extrai do zero e
abre a árvore de vídeos** — tudo em um fluxo.

### Não-objetivos (v1)
- **Não** capturar o cookie automaticamente do browser (sem extensão, sem ler o cofre do
  Chrome). O usuário continua colando o cookie do F12 — só que num lugar só e com um clique.
- **Não** gerenciar o cookie do Metabase pela tela nesta fase — o cartão do Metabase fica
  **oculto**. O de→para (`depara_metabase.py`) continua funcionando pelo `.bat` como hoje.
- **Não** implementar nada da futura API do Metabase (ver §8).

## 3. Decisões tomadas (brainstorming)

| Tema | Decisão |
|---|---|
| Como o cookie chega ao app | Colar manualmente num painel único (sem captura automática) |
| Cookie-alvo da v1 | Só LDI; Metabase oculto |
| Ação do botão Salvar | **Sempre extrai do zero** e abre a árvore ao final |
| Concurso/termo | **Campo na tela**, pré-preenchido com o valor atual do config (ex.: `PRF`) |
| API oficial do Metabase | Incerta/sem prazo → apenas nota de arquitetura, nada construído |

## 4. Arquitetura e componentes

Tudo dentro do que já existe — sem framework novo, sem página nova.

### Frontend (`ui.html`)
- O popover do cookie (hoje `#modalCookie`) vira o painel **"🔑 Cookie e extração"**, com
  um único cartão (LDI):
  - Faixa de **status** (verde/amarelo) reaproveitando `/api/cookie/status` (e-mail,
    validade por JWT, "atualizado em").
  - **Textarea** para colar o cookie (aceita com/sem prefixo `cookie:`, como hoje).
  - **Campo "Concurso"** (input de texto) pré-preenchido com o `termo_busca` atual.
  - Botão **"💾 Salvar e extrair"** que orquestra o fluxo da §5.
  - Barra de progresso reutilizando o padrão já existente da extração pela tela.
- Nota discreta no rodapé do painel: "📊 Metabase (data real de gravação) — em breve;
  hoje roda pelo `.bat`".

### Backend (`visualizador.py`)
Reutiliza os endpoints existentes; a orquestração fica no frontend:
- `GET  /api/cookie/status` — já existe.
- `POST /api/cookie` — já existe (salva + testa). Passa a **também aceitar/gravar o termo**
  de concurso quando enviado, persistindo no `config.json` (campo `termo_busca`).
- `POST /api/extrair` — já existe (dispara extração). Aceita o termo como parâmetro
  (sobrepõe o config na chamada, como o `extrator_ldi.py --termo` já suporta).
- `GET  /api/extrair/status` — já existe (progresso).
- `GET  /api/dados` — já existe (carrega a árvore extraída).

Nenhum endpoint novo é estritamente necessário para a v1; o trabalho é de **orquestração no
frontend** + pequenos ajustes para o termo trafegar.

### Metabase (mantido, apenas oculto na UI)
O caminho atual continua intacto: `depara_metabase.py` segue autenticando via
`experimento_metabase` da pasta da Limpeza. Não removemos nada — só não expomos o cartão do
Metabase na tela nesta fase. (A extração/decisão de mover a auth do Metabase para dentro do
projeto — Abordagem A do brainstorming — fica para a fase que reativar esse cartão.)

## 5. Fluxo do usuário e comportamento

1. Usuário abre o Visualizador → painel **🔑 Cookie e extração**.
2. Cola o cookie do F12 no textarea; ajusta o **Concurso** se quiser (padrão = valor do config).
3. Clica **"💾 Salvar e extrair"**. O frontend então:
   a. `POST /api/cookie` com o cookie **e o termo** → grava `cookie.txt`, atualiza
      `termo_busca` no `config.json`, e retorna o status testado.
   b. Se o status **não** for válido (cookie vencido/errado) → mostra o aviso e **para aqui**,
      sem extrair.
   c. Se válido → `POST /api/extrair` (com o termo) e passa a **exibir a barra de progresso**,
      fazendo *polling* de `/api/extrair/status`.
   d. Ao terminar a extração → chama `/api/dados` e **renderiza a árvore** de vídeos
      (mesma visão de sempre), fechando o painel.
4. Resultado: colar → um clique → todos os vídeos do concurso na tela.

## 6. Tratamento de erros e casos de borda

- **Cookie inválido ao colar** (curto demais, sem `=`): a validação atual de `/api/cookie`
  rejeita com mensagem clara; o fluxo não avança para a extração.
- **Cookie vencido** (status HTTP 401 no teste): o painel avisa "cookie vencido — cole um
  novo" e **não** dispara a extração (evita rodar um ciclo longo fadado a falhar).
- **Extração falha no meio** (rede/429/5xx): o `extrator_ldi` já tem retry; erros por aula
  viram linhas com coluna `erro`. A barra conclui e a árvore abre mostrando o que veio; o
  painel informa quantas falhas de download ocorreram.
- **Termo vazio**: se o campo Concurso ficar vazio, cai no valor atual do config; se o config
  também estiver vazio, o backend responde com aviso ("informe um concurso") em vez de extrair
  0 cursos silenciosamente.
- **Salvar sem extrair**: não há botão separado na v1 — o fluxo é sempre "salvar e extrair".
  (Se no futuro fizer falta, um "só salvar" é trivial de adicionar.)

## 7. Testes

O projeto não tem suíte automatizada. Para esta v1:

- **Teste manual (roteiro no PR):** colar um cookie válido + termo → ver status ✅ → barra de
  progresso → árvore carregada; repetir com cookie vencido → ver que **não** extrai e mostra o
  aviso; repetir com termo inexistente → ver aviso "nenhum curso encontrado".
- **Teste leve e testável sem rede:** a passagem do **termo** ponta a ponta — que
  `POST /api/cookie` persiste `termo_busca` no `config.json` e que `POST /api/extrair` usa o
  termo recebido em vez do config. Isolar a leitura/gravação de config para permitir asserção.
- A UI e o teste de sessão ao vivo ficam de verificação manual.

## 8. Fase futura (registro, não implementar agora)

- **Integração com a API oficial do Metabase** (quando/se a empresa liberar): reativar o
  cartão do Metabase e, mais importante, permitir **buscar vídeos por nome direto na tela** e
  receber os resultados já cruzados (data real de gravação, regravações), sem depender da
  extração crua + cookie. Nesse momento vale mover a autenticação do Metabase para dentro do
  projeto (Abordagem A do brainstorming: store local + fallback), dando casa ao token de API.
- **Captura automática do cookie** (extensão Chrome ou leitura do cofre) permanece possível,
  mas fora de escopo enquanto o colar-manual atender.

## 9. Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `ui.html` | Popover do cookie → painel "Cookie e extração"; campo de concurso; botão fundido; orquestração salvar→validar→extrair→árvore; ocultar Metabase |
| `visualizador.py` | `POST /api/cookie` passa a persistir o termo no `config.json`; garantir que `/api/extrair` use o termo recebido |
| `config.json` | `termo_busca` passa a ser gravado pela tela (estrutura inalterada) |
| `VisualizadorLDI.exe` | Reempacotar após mexer em `ui.html`/`visualizador.py` (a UI vai embutida via `--add-data`) |

Sem mudança em `extrator_ldi.py` (já aceita `--termo`) nem em `depara_metabase.py` (Metabase
intacto, só oculto na UI).
