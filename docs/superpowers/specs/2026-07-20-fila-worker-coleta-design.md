# Fila de coleta + worker no VPS (Fase 3) — design

_Data: 2026-07-20 · Autor: Luiz + Claude · Status: aprovado no chat (aguarda review do spec)_

## Objetivo

Permitir que a coleta de um concurso seja **disparada pela web** e executada **no servidor**
(VPS), sem depender da máquina do Luiz. Esta fase entrega o **backend**: a fila no Supabase,
o worker que a processa no VPS, o armazenamento/validade do cookie e os avisos. A **tela**
(formulário de disparo, campo de cookie, banner, painel de status, papel `operador`) é a
**Fase 4**, logo depois.

Preserva a amarra de sempre: o Vercel não roda o coletor; ele só **enfileira**. O worker no
VPS (onde o cookie vive) observa a fila e executa. O Supabase é o "correio".

## Decisões tomadas com o Luiz
- **Worker = serviço Python systemd** no host do VPS (Ubuntu 24.04, acesso SSH completo).
  Reusa `coletor_ldi.coletar()` + o sync existentes. **n8n fica fora do caminho crítico**
  agora ("systemd agora, n8n depois" — futuro painel/alertas em cima destas tabelas).
- **Cookie renovado pela tela /admin** (Fase 4) → gravado no Supabase (`config_ldi`, secreto,
  só service_role lê) → o worker usa. **Só admin seta o cookie**; operador só dispara.
- **Disparar coleta:** admin + operador (papel novo, Fase 4). Equipes só visualizam.
- **Avisos:** e-mail (Resend, já integrado) + banner no app.
- **Controles de fila (admin):** cancelar pendente · retentar erro/aguardando-cookie ·
  cancelar coleta em andamento (worker checa sinal de cancelamento no batch). Remover
  concurso publicado: fora de escopo por ora.

## Modelo de dados (Supabase — novo `supabase/schema_coleta.sql`)

**`coleta_pedido`** — a fila
| coluna | tipo | nota |
|---|---|---|
| id | bigserial PK | |
| tipo | text | `termo` \| `ids` |
| alvo | text | o termo de busca, ou a lista de IDs (CSV) |
| rotulo | text | nome do concurso (obrigatório quando `tipo=ids`; vira o `termo` do snapshot) |
| status | text | `pendente`→`rodando`→(`concluida`\|`erro`\|`aguardando_cookie`\|`cancelada`); `cancelando` = pedido de aborto de um `rodando` |
| progresso | text | ex.: "120/122 aulas" (worker atualiza) |
| mensagem | text | erro/detalhe legível |
| extracao_id | int | id do snapshot local resultante (rastreio) |
| pedido_por | text | e-mail de quem pediu |
| criado_em / iniciado_em / concluido_em | timestamptz | |

RLS: `SELECT` para `authenticated`; escrita só service_role (worker e server actions do app).

**`config_ldi`** — o cookie atual (linha única)
| coluna | tipo | nota |
|---|---|---|
| id | int PK (fixo=1) | |
| cookie | text | o valor do `__Secure-SID` (segredo) |
| atualizado_em | timestamptz | |
| atualizado_por | text | e-mail do admin |

RLS: **nenhuma política de leitura para `authenticated`** — só service_role acessa. É o
único dado sensível persistido; protegido por RLS (como a service_role já é hoje). O campo
do /admin grava aqui via server action com o cliente admin.

**`cookie_status`** — validade derivada (linha única, sem segredo)
| coluna | tipo |
|---|---|
| id | int PK (fixo=1) |
| email | text |
| expira_em | timestamptz |
| dias_restantes | int |
| valido | boolean |
| atualizado_em | timestamptz |

RLS: `SELECT` para `authenticated` (alimenta o banner). Escrita só service_role (worker).

## Worker (`worker_coleta.py`, novo — roda no VPS)

Laço principal (serviço systemd, reinício automático):
1. A cada ~20s, publica/atualiza `cookie_status` (validade do cookie de `config_ldi`).
2. `SELECT` o `coleta_pedido` mais antigo com `status='pendente'` (um por vez — o coletor
   assume single-flight). Se nenhum, dorme e volta ao passo 1.
3. Marca `rodando` (+`iniciado_em`, `pedido_por` preservado).
4. Carrega o cookie de `config_ldi`; monta a sessão (`extrator_ldi.montar_sessao`).
5. Roda `coletar(cfg, sessao, termo, caminho_banco, ids=..., progresso=cb)`:
   - `termo` = `alvo` (tipo termo) ou `rotulo` (tipo ids); `ids` = parse do `alvo`.
   - `cb(feito, total)` atualiza `coleta_pedido.progresso` e **checa cancelamento**: relê
     `status`; se `cancelando`, levanta `ColetaCancelada` → o batch para (aulas já baixadas
     ficam salvas/retomáveis), worker marca `cancelada`.
   - O sync ao fim de `coletar` já publica no Supabase (gancho existente).
6. Sucesso → `concluida` (+`extracao_id`, `concluido_em`).
7. `CookieVencido` (401/403) → `aguardando_cookie` + `cookie_status.valido=false` + **e-mail
   Resend** ao admin. Ao renovar o cookie (via /admin), o admin usa "retentar" (status volta
   a `pendente`) e o worker reprocessa.
8. Erro qualquer → `erro` + `mensagem`.

Config no VPS: `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` + `RESEND_API_KEY` (env ou
`supabase.json` local ao worker). E-mail via API REST do Resend (`requests`, sem dep nova).

## Adições ao código existente (mínimas, sem regressão)

- **`coletor_ldi.coletar(...)`** ganha um kwarg opcional **`progresso=None`** (callback
  `(feito, total)`), chamado dentro de `_baixar_lote` a cada N aulas. Sem callback (uso
  local de hoje), nada muda. O callback pode levantar `ColetaCancelada` para abortar limpo.
- **Novo `cookie_status.py`** (ou seção em módulo compartilhado): extrai
  `_decodifica_sid` / `_status_cookie` que hoje vivem em `visualizador.py`, para o worker e
  o Visualizador reusarem a mesma lógica (DRY). O `visualizador.py` passa a importar dali.
- **`ColetaCancelada(Exception)`** em `coletor_ldi` (ou `extrator_ldi`), tratada no worker.

## Segurança
- `config_ldi.cookie` é o único segredo novo persistido: RLS bloqueia `authenticated`; só a
  service_role (worker no VPS, server action de admin) lê. Cookie setado só por admin.
- service_role key **só no servidor** (VPS worker) e nas server actions server-only do app —
  nunca no navegador (regra já vigente).
- O worker valida env/credenciais e a presença do cookie antes de rodar; sem cookie válido,
  não tenta coletar (marca `aguardando_cookie`).

## Entrega e testes (critérios de aceite)
1. `supabase/schema_coleta.sql` aplicado (idempotente); 3 tabelas + RLS conferidas.
2. Cookie gravado em `config_ldi` (por script nesta fase; pela tela na Fase 4).
3. Worker sobe como systemd no VPS; `cookie_status` aparece atualizado no Supabase.
4. Enfileirar um pedido `tipo=ids` (por script) → worker processa → `concluida` + o concurso
   aparece no seletor do app (Fase 1) com paridade vs. o painel local.
5. Enfileirar e, no meio, marcar `cancelando` → worker aborta → `cancelada`; retomar depois
   funciona.
6. Simular cookie inválido → `aguardando_cookie` + `cookie_status.valido=false` + e-mail chega;
   "retentar" após renovar reprocessa.
7. Sem worker rodando, enfileirar não quebra nada (fica `pendente`); a coleta local por
   comando (BACEN/PRF/por-ID) continua intacta.

## Fora de escopo (Fase 4, spec próprio)
- Tela: formulário de disparo (termo × IDs+rótulo, colando URL do admin), campo de cookie no
  /admin, banner de cookie, painel de status da fila, botões cancelar/retentar, papel `operador`.
- Remover concurso publicado pela tela.
- n8n como painel/alertas.

## Armadilhas a respeitar
- **De→para do Metabase no VPS:** o cache `saida/metabase_depara.json.gz` (que dá o "ano de
  gravação real" dos vídeos) é gerado localmente e exige Warp/Metabase — **não estará no VPS**.
  A coleta e o sync funcionam sem ele; só as colunas de ano de gravação ficam vazias para os
  vídeos coletados no servidor (degradação aceita). Se quiser preencher, o cache pode ser
  copiado para o VPS periodicamente (fora de escopo).
- Coletor/sync/telas locais **não regridem** — worker e callback só adicionam.
- Datas de exibição = data local (convenção do projeto).
- Cookie e service_role **nunca** no git nem no navegador.
- Single-flight: um pedido por vez (o coletor assume; retomada via `--continuar`/status).
