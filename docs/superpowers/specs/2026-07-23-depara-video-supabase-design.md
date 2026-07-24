# De→para de vídeos no Supabase (data real de gravação na web) — design

_Data: 2026-07-23 · Autor: Clovis + Claude · Status: aprovado no chat_

## Objetivo

Fazer a **data real de gravação** dos vídeos aparecer nas coletas feitas pelo VPS (e na web
do time). Hoje o cruzamento com o Metabase (question 19885) roda em `painel.dados_avaliacao`
lendo o cache local `saida\metabase_depara.json.gz`; o VPS **não tem esse cache**, então toda
coleta de lá mostra "0 de N com data real" (bug percebido no curso "Língua Portuguesa para
DMAE Uberlândia": 132 vídeos, 123 com ID antigo, 0 com data). O de→para passa a morar no
Supabase; o VPS/web casam as datas de lá.

## Diagnóstico (confirmado com dados reais)

- Os vídeos são coletados corretamente (132 vídeos, 123 com `video_id_antigo`, durações OK).
- `v_com_data=0` porque o VPS não tem `metabase_depara.json.gz` (ausente — confirmado por SSH).
- A data de gravação **só** existe no Metabase (question 19885); nenhuma API do LDI a entrega.

## Decisão de arquitetura (à prova de futuro)

A **tabela `depara_video` + o consumo (VPS/web lêem dela)** são o núcleo durável. O
**publicador** (o que enche a tabela) é intencionalmente isolado num script próprio, para
que — se um dia o time de dados provisionar um **token de API do Metabase** — a gente troque
só o publicador (de upload manual para busca automática) sem tocar no consumo. Enquanto isso,
o refresh é manual (o preço da auth Warp+Metabase, que já é manual hoje).

## Componentes

### 1. Tabela `depara_video` (Supabase)

Schema versionado em `supabase\schema_depara.sql` (padrão do `schema_coleta.sql`, idempotente):

```
depara_video(
  video_id      text primary key,   -- = video_id_antigo (chave do gz)
  data          text,               -- data/hora de gravação (ISO, como no gz)
  status        text,
  titulo        text,
  raiz          text,               -- professor
  path          text,               -- árvore antiga
  dur           text,               -- "HH:MM:SS"
  n             int,
  atualizado_em timestamptz not null default now()
)
```

RLS: leitura `authenticated`, escrita só `service_role` (mesmo padrão das demais). ~283 mil
linhas. Registro completo (decisão do Clovis — espaço para análises futuras).

### 2. Publicador `sync_depara_supabase.py` (roda no LOCAL, manual/periódico)

Lê `saida\metabase_depara.json.gz` (mesmo caminho do `painel._depara`) e faz **upsert em
lotes** (~5 mil/req, `Prefer: resolution=merge-duplicates`, `on_conflict=video_id`) na
`depara_video`. Reusa `sync_supabase._config`/`_headers`. CLI:
`py sync_depara_supabase.py [--gz CAMINHO]`. Ping de credencial antes de escrever (como
`sync_supabase.enviar`). Loga progresso (lote X de Y). Idempotente (re-run só atualiza).

### 3. Consumo — `sync_supabase.montar_payload` monta o de→para do Supabase

Nova função (em `sync_supabase.py`) `depara_do_supabase(rest, key, con, extracao_id) -> dict`:
- pega os `video_id_antigo` distintos e não-vazios dos `blocos` do snapshot;
- consulta `depara_video` só por esses ids, em lotes (`video_id=in.(...)`);
- devolve `{video_id: {"data": ..., "dur": ..., ...}}` — **mesmo shape** que o gz, para
  `painel.dados_avaliacao` casar sem alteração.

`montar_payload` passa a usar esse dict no lugar de `painel._depara()`. Assim a coleta do VPS
(e a local, se rodar o sync) ganha a "% por ano de gravação". O **Visualizador e o painel
local (Flask)** continuam usando o gz local — sem mudança (fonte rápida offline).

Fallback: se a `depara_video` estiver vazia/inacessível, o de→para volta vazio (comportamento
atual — "sem data"), nunca derruba a coleta.

### 4. Fluxo prático (a orientação pedida)

Ritual periódico do Clovis (ex.: semanal — a data de gravação não muda, só entram vídeos
novos):
1. Warp ativo + renovar o cookie do Metabase (pasta da Limpeza).
2. `py depara_metabase.py --refresh` — atualiza o gz local (~1 min).
3. `py sync_depara_supabase.py` — sobe pro Supabase (~poucos min).

Documentar isso no `TUTORIAL.md`/`PROXIMA-SESSAO.md` e no `deploy\README-vps.md` (o VPS não
precisa de nada — só consome).

## Não-regressão

- Não muda o gz nem o `depara_metabase.py` nem o painel local.
- `montar_payload` já é a fonte única do payload web (paridade preservada).
- Custo no sync do VPS: 1 consulta em lote a `depara_video` por coleta (barata).
- Schema Supabase: aditivo (tabela nova); nada nas tabelas existentes.

## Testes / aceite

1. **Unit (Python)**: o publicador transforma um gz de exemplo nas linhas de upsert
   corretas (chunking); `depara_do_supabase` monta o dict `{video_id: {data,...}}` a partir
   de linhas mockadas do PostgREST (shape idêntico ao gz).
2. **Real**: `py sync_depara_supabase.py` sobe o de→para; recoletar (ou re-sincronizar) o
   curso "Língua Portuguesa DMAE" → a coluna "% por ano de gravação" deixa de ser 0 (os 123
   vídeos com ID antigo passam a casar). Conferir na web.
3. Snapshot sem `depara_video` (tabela vazia) → "sem data", sem erro.

## Fora de escopo (depois)

- Token de API do Metabase / refresh automático (troca só o publicador — núcleo intacto).
- Buscar data por vídeo sob demanda (exigiria question parametrizada no Metabase).
- Expor os outros campos do de→para (titulo/raiz/path) em telas — só armazenados por ora.
