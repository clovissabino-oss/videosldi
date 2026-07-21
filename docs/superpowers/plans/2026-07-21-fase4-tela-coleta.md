# Fase 4 — Tela de coleta, cookie e fila — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Passos com checkbox. Idioma pt-BR. Comece numa branch nova a partir da `main` atualizada: `git checkout main && git pull && git checkout -b feat/fase4-tela-coleta`.

**Goal:** Disparar coletas, renovar o cookie e gerir a fila pela interface web (app `web/`), consumindo as tabelas da Fase 3 (`coleta_pedido`, `config_ldi`, `cookie_status`) que já estão no ar.

**Architecture:** Só front no Next.js. Server actions com cliente **service_role** (server-only, `web/lib/supabase/admin.ts`) para escrever na fila / cookie / papéis; leitura via `criarClienteServidor` (RLS `authenticated`). Papel novo `operador` além de `admin`. O worker no VPS já reage às transições de status.

**Tech Stack:** Next.js 15 (App Router, server actions), `@supabase/ssr`/`@supabase/supabase-js` (já no projeto). Sem dep nova. Sem testes JS (padrão do app web — verificação por build + aceite manual).

## Global Constraints
- pt-BR. service_role **nunca** no cliente. Papéis re-checados no servidor a cada ação.
- Reusar padrões existentes: `web/app/admin/{actions.ts,page.tsx}`, `web/lib/supabase/{admin.ts,servidor.ts}`, `web/lib/dados.ts`, envelope `{data}`/`{data:null,erro}` das rotas.
- `config_ldi` sem leitura para `authenticated` — o valor do cookie nunca vai ao cliente.
- Spec: `docs/superpowers/specs/2026-07-21-fase4-tela-coleta-design.md`.

---

### Task 1: Papel `operador` — gate + concessão no /admin
**Files:** Modify `web/app/admin/actions.ts` (add `exigirPapel`/`exigirOperador`, action `definirPapel`); Modify `web/app/admin/page.tsx` (seletor de papel por usuário) e `web/app/admin/form-remover.tsx`/novo componente cliente se preciso.
**Interfaces produced:** `exigirOperador(): Promise<User>` (aceita role `admin`|`operador`, senão `notFound()`/redirect); `exigirAdmin()` continua; `definirPapel(formData)` (só admin, grava `app_metadata.role`).
- Deliverable: admin consegue marcar um usuário como `operador`/`admin`/`—` na tela; gate reutilizável pronto para as Tasks 3–5.
- Verificação: build limpo; admin muda papel de um usuário de teste e a tabela reflete; não-admin não vê a ação.

### Task 2: Cookie no /admin (só admin) + rota de status
**Files:** Modify `web/app/admin/actions.ts` (`atualizarCookie(formData)` → upsert `config_ldi` via admin client, `exigirAdmin`); Modify `web/app/admin/page.tsx` (campo colar cookie + exibição do `cookie_status`); Create `web/app/api/cookie-status/route.ts` (`GET` → `{data: cookie_status}` via `criarClienteServidor`).
**Interfaces produced:** `atualizarCookie`; `GET /api/cookie-status`.
- Chave: `config_ldi` upsert `{id:1, cookie, atualizado_por, atualizado_em}` com `on_conflict=id` (mesmo padrão do worker/`_publicar_cookie_status`). A tela mostra estado lendo `cookie_status` (nunca o cookie em si).
- Verificação: admin cola o `__Secure-SID` → `config_ldi` atualiza → worker no VPS passa a usar; `cookie_status` reflete em segundos. Conferir que o valor do cookie não aparece no HTML/JS do cliente.

### Task 3: Banner de cookie
**Files:** Create `web/components/BannerCookie.tsx` (server component: lê `cookie_status`, renderiza vermelho se `!valido`, amarelo se `dias_restantes<=3`, nada senão); Incluir em `web/app/admin/page.tsx` e na futura `web/app/coleta/page.tsx`; para as telas vanilla, um trecho de fetch a `/api/cookie-status` que injeta o aviso no topo de `web/telas/{painel,avaliacao}.html` (edição pequena, mesma lógica de data local).
- Verificação: forçar `cookie_status.valido=false`/`dias_restantes=2` no Supabase e ver o banner mudar nas telas.

### Task 4: `web/lib/coleta.ts` — helpers da fila (porta de `extrair_ids`)
**Files:** Create `web/lib/coleta.ts`.
**Interfaces produced:** `extrairIds(texto): string[]` (regex UUID; pega `[?&]id=<uuid>`, senão UUID solto; ignora `team_id=`; lança em token inválido — porta fiel de `coletor_ldi.extrair_ids`); `enfileirar(admin, {tipo, alvo, rotulo, pedido_por})`; `listarFila(supabase, limite)`; `mudarStatus(admin, id, status, extra?)`.
- Verificação: um teste manual/Node de `extrairIds` com a URL do admin (deve pegar o `id=`, nunca o `team_id=`) — ou um teste unit se decidirem adicionar Vitest (opcional; hoje o app não tem testes JS).

### Task 5: Tela `/coleta` — disparo + painel de status
**Files:** Create `web/app/coleta/page.tsx` (server component, `exigirOperador()` senão `notFound()`; form de disparo + lista da fila + BannerCookie); Create `web/app/coleta/actions.ts` (`disparar(formData)` com `exigirOperador`; `cancelar`/`retentar`/`cancelarEmAndamento` com `exigirAdmin`); Create `web/app/api/fila/route.ts` (`GET` → `{data: coleta_pedido[]}` recente, para o auto-refresh); componente cliente para o polling (~5s) e os botões.
- Deliverable: operador dispara (termo OU IDs+rótulo, colando a URL do admin) → pedido na fila → worker processa (VPS) → concurso no seletor. Admin cancela/retenta/cancela-em-andamento.
- Verificação (aceite do spec): itens 1–4; `/coleta` dá 404 para não-operador.

### Task 6: Docs + fecho
**Files:** Modify `CLAUDE.md`/`PROXIMA-SESSAO.md` (registrar Fase 4 e o papel operador); atualizar `deploy/README-vps.md` se algo do fluxo mudar. Commit.

## Ordem e revisão
Subagente por task + revisão (spec+qualidade) a cada uma; revisão final de branch antes do PR → `main` (fluxo enxuto: `feat/fase4-tela-coleta` → PR → merge → Vercel deploya). Cada task fecha com build limpo e o aceite manual correspondente. As Tasks 4–5 têm o miolo de segurança (gate `operador`, service_role só no servidor, `config_ldi` fora do cliente) — revisar com lupa, como na Fase auth.

## Nota de execução
As decisões já estão fixadas no spec; a próxima sessão pode expandir o código verbatim por task ao despachar cada subagente (este plano fixa arquivos, interfaces e os pontos sensíveis). Reusar sempre os padrões de `web/app/admin/*` (gate, server actions, service_role) e de `web/lib/dados.ts` (leitura).
