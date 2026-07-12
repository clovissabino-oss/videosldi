# Publicação web do Painel de Conteúdo — Supabase + Vercel (design)

_Data: 2026-07-12 · Autor: Luiz + Claude · Status: aprovado seção a seção (aguarda review final do spec)_

## Objetivo

Tirar o Painel de Conteúdo da máquina do Luiz e publicá-lo como **app web de leitura
para o time interno da Estratégia**, sem instalação, reusando o stack que o Luiz já
domina (**git + Supabase + Vercel**). A coleta continua na mão do Luiz (com cookie/Warp);
o time só consome pelo navegador.

Decisões de escopo tomadas com o Luiz:
- **Time = só leitura.** Ninguém do time edita no v1. O Luiz segue sendo o único editor
  (localmente). Sem escrita multiusuário nesta fase.
- **Login com Supabase Auth** (magic-link, convite apenas) — mais robusto que senha única
  e já pavimenta o multiusuário real depois.
- **A coleta não vai pro serverless.** O coletor é um batch Python demorado e com estado
  (cookie ~30 dias, Warp pro Metabase, ~540 mil linhas do de→para) — incompatível com
  funções do Vercel. Ele continua rodando na máquina do Luiz (infosab só quando/se houver
  agendamento) e apenas **empurra** o resultado pro Supabase.

## Abordagem escolhida (Opção A) — "Supabase é a fonte, Vercel é a vitrine"

Não tocar no que já funciona (coletor provado e retomável); só adicionar as pontes.

```
VOCÊ (máquina local / infosab no futuro):
  coletor_ldi.py ─► conteudo.db (SQLite, intacto)
                         │
  sync_supabase.py ──────┤  importa painel.py, roda a agregação JÁ VALIDADA
       │                 ▼
       │        Supabase (Postgres): tabelas com o JSON PRONTO
       │           • snapshot          (cabeça: resumo/KPIs, flag `pronto`)
       │           • avaliacao_curso   (curso_id → payload jsonb da planilha; também alimenta o seletor)
       │           • pendencia_resumo  (severidade/regra → abertas)
       ▼
TIME (navegador):
  App Next.js no Vercel  ─►  login (Supabase Auth)  ─►  lê o Supabase (RLS authenticated)  ─►  telas
```

### Sacada central: agregação materializada no sync

A agregação da planilha (`painel.dados_avaliacao`) é lógica Python de verdade (banca por
capítulo, faixas de ano crítico/atenção/novo, cruzamento de duração, ano real de gravação
via cache do de→para). Como o time é **só leitura** e os dados só mudam quando o Luiz roda
uma coleta, **não reimplementamos nada em SQL/TS**: o `sync_supabase.py` roda a própria
agregação Python existente e sobe o **resultado já mastigado**. O Vercel só lê linhas prontas.

Consequências:
- **Zero divergência** do mockup v6 — o número na web é literalmente o do `painel.py`.
- **Frontend quase não muda** — as telas já consomem `{data: ...}`; o Vercel devolve o mesmo
  formato, só que lendo do Supabase.
- **De→para fica na mão do Luiz** — o ano de gravação é resolvido no momento do sync; o
  Vercel nunca precisa do Metabase nem do Warp.
- **Custo:** a web mostra só o que foi pré-agregado. Fatias novas exigem agregar mais no
  sync (barato). Filtros client-side atuais (destaque de banca-alvo) seguem funcionando
  porque o payload traz a contagem de todas as bancas.

## Modelo de dados no Supabase

Três tabelas + uma view. Cada tabela guarda o JSON agregado que a tela consome, versionado
por snapshot (histórico mantido — pavimenta a fase de "evolução no tempo" sem trabalho extra).

**`snapshot`** — registro de cada coleta sincronizada (a cabeça)
| coluna | tipo | nota |
|---|---|---|
| id | bigserial PK | |
| termo | text | 'BACEN', 'PRF'… |
| extracao_local | int | o `extracoes.id` do SQLite (upsert idempotente) |
| status | text | completa / parcial |
| iniciada_em | timestamptz | |
| resumo | jsonb | saída de `dados_do_snapshot()`: kpis, achados, tipos, cursos |
| pronto | boolean | default false; vira true só ao fim do sync |
| sincronizado_em | timestamptz | default now() |

`UNIQUE(termo, extracao_local)`

**`avaliacao_curso`** — a planilha pronta, 1 linha por curso/snapshot
| coluna | tipo |
|---|---|
| snapshot_id | bigint FK → snapshot(id) |
| curso_id | text |
| curso_nome | text |
| autores | text |
| payload | jsonb — saída de `dados_avaliacao()`: `{curso, autores, capitulos[...]}` |

`PRIMARY KEY(snapshot_id, curso_id)`

> O **seletor de disciplina** lê direto daqui (`SELECT curso_id, curso_nome FROM avaliacao_curso
> WHERE snapshot_id = atual`) — não há tabela `curso` separada (seria redundante, mesma chave e
> mesmos campos).

**`pendencia_resumo`** — resumo por regra/severidade
| coluna | tipo |
|---|---|
| snapshot_id | bigint FK → snapshot(id) |
| severidade | text |
| regra | text |
| abertas | int |

`PRIMARY KEY(snapshot_id, severidade, regra)`

**View `snapshot_atual`** — `DISTINCT ON (termo) … WHERE pronto ORDER BY termo, extracao_local DESC`.
O Vercel sempre lê o snapshot certo (mais recente e 100% sincronizado) sem lógica no cliente.

**Segurança dos dados:** só metadados (contagens, banca, ano, duração) — nunca texto de
questão nem cookie. **RLS ligado**, política de `SELECT` apenas para o papel `authenticated`
(sem sessão = 0 linhas). Escrita só pelo `sync_supabase.py` via `service_role key` (ignora RLS).

## A ponte `sync_supabase.py`

Separa a parte pura (testável) da parte de I/O — mesmo princípio do `parse_blocos.py`.

```
montar_payload(con, termo)  → dict de linhas   [PURO, testável com fixture]
    • painel.dados_do_snapshot(con)              → resumo
    • painel.dados_avaliacao(con, curso, depara) → 1 payload por curso
    • resumo de pendências (mesma query do /api/pendencias/resumo)
    • devolve {snapshot, avaliacoes[], pendencias[]}

enviar(rows)                → upsert no Supabase   [I/O]
    • POST no PostgREST com header Prefer: resolution=merge-duplicates
```

**Decisões:**
- **Transporte: `requests` puro contra a API REST (PostgREST) do Supabase** — zero
  dependência nova (o projeto já vive de `requests`). Volume minúsculo (~265 linhas por
  snapshot). Alternativa descartada: `supabase-py` (não compensa a dependência).
- **Segredos por variável de ambiente:** `SUPABASE_URL` e `SUPABASE_SERVICE_KEY`. A
  service_role key ignora o RLS (é o que permite escrever) → secreta, nunca no git. Fallback
  opcional num `supabase.json` local, adicionado ao `.gitignore` (padrão do `cookie.txt`).
- **Idempotência + visibilidade atômica:** chaves naturais → re-rodar atualiza no lugar,
  nunca duplica. A flag `pronto` garante que o time nunca veja dado pela metade: grava
  `pronto=false`, sobe os filhos, e só no fim vira `pronto=true`; a view filtra `WHERE pronto`.
- **Deleções se resolvem sozinhas:** cada coleta é um `snapshot_id` novo; curso que sumiu
  não aparece no snapshot novo. Sem órfãos, sem limpeza manual.
- **Acionamento:** roda ao fim do `coletor_ldi.py` (uma linha, como as regras de qualidade
  já fazem) e avulso: `py sync_supabase.py [--termo BACEN]` (sem arg = snapshot mais recente).

## App no Vercel

Reaproveita a UI aprovada quase intacta. As telas (`avaliacao.html`, `painel.html`) são
páginas únicas em JS vanilla que já fazem `fetch` e renderizam; só trocamos a **fronteira de
dados**: onde hoje chamam `/api/...` do Flask, passam a consultar o Supabase via `supabase-js`.

```
Projeto Next.js (mínimo) no Vercel
├─ /public
│   ├─ avaliacao.html   ← mesma tela, fetch trocado p/ supabase-js
│   └─ painel.html      ← idem; deixa de receber __DADOS__ injetado e busca o resumo no load
├─ middleware           ← gate: sem sessão → /login
├─ /login               ← Supabase Auth (magic-link)
└─ env: NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY
```

**Decisões:**
- **Next.js mínimo, não rewrite.** Ele hospeda as telas validadas (servidas de `/public`),
  injeta a config do Supabase por env, dá o `middleware` do gate e faz deploy no `git push`.
  Quando as features de escrita chegarem, o Next já é a casa natural.
- **`supabase-js` direto do navegador.** A anon key é pública por design; o RLS
  `authenticated` protege. Uma linha de mudança em cada `fetch`:
  `supabase.from('avaliacao_curso').select('payload')…` devolvendo o mesmo `{data}`.
- **Supabase Auth (magic-link, convite apenas):** auto-cadastro desligado; o Luiz convida os
  e-mails do time. Sem senha pra gerenciar; controle exato de quem entra. As chamadas usam o
  JWT da sessão.
- **Deploy = `git push`** (fluxo atual do Luiz nos outros apps).

## Operação, erros e testes

**Novo ciclo:**
```
VOCÊ:  py coletor_ldi.py --termo BACEN   → coleta + regras + sync (automático no fim)
       (avulso:  py sync_supabase.py --termo BACEN)
TIME:  abre o app no Vercel → login → vê o snapshot atual
```

**Tratamento de erro (fiel ao "aborta claro" do coletor):**
- **Sync falha no meio:** `pronto=false` segura tudo — a view ignora o snapshot incompleto e
  o time continua vendo o último snapshot bom. Loga o erro, sai ≠ 0; re-rodar retoma.
- **Env/credencial errada:** valida env vars + ping ANTES de agregar; falha na cara, sem lixo.
- **Frescor visível:** as telas mostram "dados de DD/MM HH:MM" (`sincronizado_em`), porque o
  sync é manual/periódico.
- **Sem dados / sem sessão:** mensagem amigável (como o `painel.py` já faz no "sem coletas").

**Testes (padrão TDD do projeto):**
- `montar_payload` → unit test contra um `conteudo.db` de fixture, afirmando **paridade com o
  `painel.py`** (garantia de que a web mostra o mesmo número da tela aprovada).
- `enviar` → smoke test contra projeto Supabase descartável.
- **RLS** → checagem manual: sem sessão = 0 linhas; autenticado = dados.
- **Frontend** → verificação visual no navegador contra os mesmos dados do BACEN que o painel
  local mostra — os números têm que bater (critério de aceite).

## Escopo

**v1 (esta entrega):**
- `sync_supabase.py` (`montar_payload` puro + `enviar`).
- Schema Supabase (3 tabelas + view + RLS authenticated).
- App Next.js mínimo no Vercel com Supabase Auth (magic-link, convite) + middleware.
- Port do `avaliacao.html` e `painel.html` (troca do fetch → supabase-js) + selo de frescor
  + estados vazios.
- Teste de paridade do `montar_payload`.

**Fica pra depois (fundação já pronta):**
- Visualizador de vídeos na web (tem edição — entra com as features de escrita).
- Escrita multiusuário (propostas/pendências na tela) → RLS de escrita + identidade.
- Tela rica de Pendências (fase 2.1, já no backlog).
- Evolução no tempo (diff de snapshots — histórico já guardado).
- Seletor de concurso quando houver >1 termo (schema já preparado).
- Coleta agendada autônoma no infosab.

## Itens abertos (confirmar no review)

1. **Projeto Supabase novo e dedicado** a este app (isolado dos outros do Luiz) — assumido: sim.
2. **infosab fica pra fase de agendamento;** no v1 a coleta roda onde o Luiz já roda (máquina
   local). Confirmar.
3. **Domínio/lista de e-mails** do time pro convite magic-link (ex: @estrategia.com) — a
   preencher; placeholder até lá.
4. **`painel.html` deixa de receber `__DADOS__` injetado** e passa a buscar no load — mudança
   pequena, confirmar.

## Armadilhas a respeitar (do CLAUDE.md / PROXIMA-SESSAO.md)

- Coletor e agregação **não devem regredir** — o sync só lê e reusa; não altera a coleta.
- Datas de exibição usam **data local** (convenção do projeto, não UTC).
- O de→para (`metabase_depara.json.gz`) permanece o insumo do ano de gravação — carregado
  pelo `painel._depara()` no momento do sync.
- Segredos (cookie do LDI, service_role key) **nunca** no git.
