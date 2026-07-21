# Fase 4 — Tela de coleta, cookie e gestão da fila (design)

_Data: 2026-07-21 · Autor: Clovis + Claude · Status: aprovado no chat (decisões tomadas na sessão)_

## Objetivo

Tirar Clovis da linha de comando: disparar coletas, renovar o cookie e gerir a fila **pela
interface web**. O backend (Fase 3) já está no ar (worker no VPS observando `coleta_pedido`,
lendo o cookie de `config_ldi`, publicando `cookie_status`). Esta fase é **só o front** no
app Next.js (`web/`) — consome as tabelas que já existem.

## Decisões (tomadas nesta sessão)
- **Disparar coleta:** papel `admin` **ou** `operador` (papel novo). Equipes só veem.
- **Setar/renovar o cookie:** **só admin** (é a credencial-mestra).
- **Aviso de cookie:** e-mail (Resend, já feito pelo worker) + **banner no app** lendo `cookie_status`.
- **Controles da fila (admin):** cancelar pendente · retentar (erro/aguardando_cookie) ·
  cancelar em andamento (worker já honra `cancelando`). "Remover concurso publicado": fora de escopo.
- **Disparo por termo OU por IDs+rótulo:** aceitar colar a **URL inteira do admin** e extrair
  o `id=` (nunca o `team_id=`) — reusa a lógica de `coletor_ldi.extrair_ids` (portar p/ TS).

## Componentes (tudo em `web/`)

### 1. Papel `operador` — generalizar o gate
- `web/app/admin/actions.ts` tem `exigirAdmin()`. Criar `exigirPapel(...papeis)` /
  `exigirOperador()` (aceita `admin` ou `operador`) reusando `criarClienteServidor().auth.getUser()`
  e `app_metadata.role`. `exigirAdmin` continua para o que é só-admin (cookie, conceder papéis).
- Conceder papel pela tela `/admin` (estender a gestão de usuários já existente): além de
  convidar/remover, um seletor de papel (`—`/`operador`/`admin`) que grava `app_metadata.role`
  via `admin.auth.admin.updateUserById` (só admin faz isso).

### 2. Cookie no /admin (só admin)
- Campo para colar o novo `__Secure-SID` + botão "Atualizar cookie". Server action
  `atualizarCookie(formData)`: `exigirAdmin()` → upsert em `config_ldi` (id=1, cookie,
  atualizado_por=email) via cliente **service_role** (server-only, `web/lib/supabase/admin.ts`).
- Mostrar o estado atual lendo `cookie_status` (email, dias_restantes, válido, atualizado_em).
- **Segurança:** `config_ldi` não tem policy de leitura para `authenticated` (RLS) — o valor do
  cookie nunca volta ao cliente; a tela só lê `cookie_status` (derivado, sem segredo).

### 3. Banner de cookie
- Componente servidor que lê `cookie_status` (via `criarClienteServidor`, RLS `authenticated`):
  se `!valido` → banner vermelho "Cookie do LDI vencido — coletas estão paradas"; se
  `dias_restantes <= 3` → banner amarelo "Cookie vence em N dias". Sem problema → nada.
- Aparece nas telas React (`/admin`, `/coleta`). Para as telas vanilla (`painel.html`,
  `avaliacao.html`), uma nova rota `GET /api/cookie-status` (envelope `{data}`) + um trecho
  de fetch que injeta o aviso no topo (mudança pequena nas telas-cópia).

### 4. Tela de coleta `/coleta` (admin + operador)
- Gate `exigirOperador()` no server component; não-autorizado → `notFound()`.
- Formulário: modo **Termo** (um campo de busca) OU modo **IDs+Rótulo** (textarea de URLs/UUIDs
  + campo rótulo). Server action `disparar(formData)`: `exigirOperador()` → valida → insere em
  `coleta_pedido` (`tipo`, `alvo`, `rotulo`, `pedido_por=email`) via service_role.
- `web/lib/coleta.ts`: `extrairIds(texto): string[]` (porta de `extrair_ids` — regex UUID,
  pega `id=`, ignora `team_id=`), + helpers de insert/list/patch da fila.

### 5. Painel de status da fila (na `/coleta`)
- Lista `coleta_pedido` recente (status, progresso, rótulo/alvo, pedido_por, timestamps),
  atualizando a cada ~5s (client fetch a uma rota `GET /api/fila`).
- Ações (só admin): **Cancelar** (pendente→`cancelada`), **Retentar** (erro/aguardando_cookie→
  `pendente`), **Cancelar em andamento** (rodando→`cancelando`). Server actions com gate,
  service_role. (O worker já trata `cancelando`/`pendente`.)

## Não-regressão / segurança
- service_role só nas server actions/route handlers server-only (regra vigente); nunca no cliente.
- Papéis re-checados **no servidor** a cada ação (nunca confiar só na página) — padrão da Fase auth.
- Nada muda no worker nem no schema (as tabelas/transições já existem). Se faltar algo no schema,
  é aditivo e vira uma task própria.

## Testes / aceite
1. Não-operador não vê `/coleta` (404); operador vê e dispara; o pedido entra na fila e o worker
   (VPS) processa → concurso aparece no seletor.
2. Admin cola um cookie novo no /admin → `config_ldi` atualiza → `cookie_status` reflete;
   operador dispara e a coleta anda.
3. Banner aparece amarelo/vermelho conforme `cookie_status` (simular dias_restantes/valido).
4. Cancelar pendente / retentar / cancelar em andamento mudam o status e o worker reage.
5. `config_ldi` nunca chega ao cliente (conferir que a tela só lê `cookie_status`).

## Fora de escopo (depois)
- Remover concurso publicado pela tela; histórico/relatório da fila; n8n como painel/alertas.
