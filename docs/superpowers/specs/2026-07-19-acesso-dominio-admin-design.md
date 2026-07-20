# Acesso por domínio + tela de admin — app web (design)

_Data: 2026-07-19 · Autor: Luiz + Claude · Status: aprovado no chat (aguarda review do spec)_

## Objetivo

Hoje o app web só aceita usuários convidados um a um. Regra nova de acesso:

1. **E-mails `@estrategia.com` são pré-aprovados**: digitam o e-mail no login e recebem
   o magic link direto, sem convite prévio (o usuário é criado na primeira tentativa).
2. **E-mails externos** continuam **só por convite** — agora feito numa **tela de admin
   dentro do app** (não mais só pelo Dashboard do Supabase).

De quebra, corrige a armadilha descoberta em produção-teste: usuário convidado que ainda
não clicou no convite recebia `422 signup_disabled` ao pedir magic link pelo formulário
(o Supabase trata OTP de usuário não-confirmado como cadastro novo) — sem mensagem útil.

## Decisões tomadas com o Luiz

- Domínio aprovado: **só `@estrategia.com`**, fixo em código (sem env de lista).
- Mensagem para externo desconhecido: **explicar o convite** ("Acesso por convite —
  fale com o administrador do painel"), não mensagem genérica.
- Tela de admin no v1: **convidar + listar + remover**. Sem promover outros admins,
  sem reenvio em massa.
- **Admin: só o Luiz** por enquanto (`limajrsab@gmail.com`), marcado via
  `app_metadata.role = "admin"` no usuário (gravado por API na implantação).

## Abordagem escolhida (A) — service_role no servidor do Next

A tela de admin exige a service_role de qualquer forma (invite/list/delete são API admin
do GoTrue). Então TODA a regra vive nos server actions do Next, com um cliente admin
server-only. O `disable_signup` do projeto **continua ligado** (defesa em profundidade:
a API pública de cadastro segue bloqueada; só o nosso servidor cria usuário).

Alternativa descartada: Auth Hook `before-user-created` (SQL) — dispara também nos
convites do admin (bloquearia externos), exigiria allowlist paralela e não elimina a
necessidade da service_role para a tela de admin.

## Componentes

### 1. Cliente admin server-only — `web/lib/supabase/admin.ts`

- Lê `SUPABASE_URL` (reusa a `NEXT_PUBLIC_SUPABASE_URL`) + **`SUPABASE_SERVICE_KEY`**
  (env server-only, SEM prefixo `NEXT_PUBLIC_` — nunca chega ao bundle do navegador).
- Exporta `criarClienteAdmin()` (supabase-js com service_role, `autoRefreshToken:false`,
  `persistSession:false`) e helpers finos sobre `auth.admin`:
  `buscarPorEmail(email)`, `criarConfirmado(email)`, `convidar(email)`,
  `listarUsuarios()`, `removerUsuario(id)`.
- **Regra de ouro:** este módulo só pode ser importado de server actions / route
  handlers. Nunca de componente cliente.

### 2. Regra de acesso — `web/app/login/actions.ts` (reescrito)

Fluxo do `enviarLink(email)`:

```
e-mail termina em @estrategia.com?
├── sim → usuário existe?
│         ├── não → criarConfirmado(email)  [admin API, silencioso]
│         └── sim → (se não-confirmado, confirmar via admin update)
│         → signInWithOtp (magic link) → "✅ Link enviado!"
└── não → usuário existe?
          ├── não → "🔒 Acesso por convite — fale com o administrador do painel."
          ├── sim, confirmado → signInWithOtp → "✅ Link enviado!"
          └── sim, NÃO confirmado → "📨 Seu convite ainda não foi aceito — use o link
              do e-mail de convite." + botão "Reenviar convite" (server action separada
              `reenviarConvite`, que chama convidar(email) de novo)
```

Mecânica do reenvio: o redirect leva o e-mail junto (`/login?msg=convite-pendente&email=...`);
a página mostra o botão só nesse caso, com o e-mail num input hidden do form do
`reenviarConvite`. A action revalida no servidor que o usuário existe e está
não-confirmado antes de reenviar (não vira reenviador arbitrário de convites).

Mensagens novas no dicionário `MENSAGENS` da página de login (pt-BR, tom atual).
Validação de e-mail: formato básico + lowercase/trim antes de qualquer decisão.

### 3. Tela de admin — `web/app/admin/page.tsx` + `web/app/admin/actions.ts`

- **Gate**: a página (server component) chama `getUser()`; se
  `app_metadata.role !== "admin"` → `notFound()` (404 — não revela que a rota existe).
  O middleware global continua cobrindo o caso sem sessão.
- **UI** (mesmo visual do login — inline styles, paleta das telas):
  - Campo e-mail + botão **Convidar** (externos; para @estrategia.com avisa que
    não precisa: "esse domínio entra sozinho pelo login").
  - **Tabela de usuários**: e-mail, papel (admin/—), confirmado?, último login
    (data local pt-BR), botão **Remover** por linha (com `confirm()` no cliente).
    Admin não pode remover a si mesmo (botão desabilitado).
- **Server actions** (`admin/actions.ts`): `convidarUsuario`, `removerUsuario` —
  ambas revalidam o gate de admin NO SERVIDOR antes de executar (nunca confiar só
  na página) e devolvem mensagem de sucesso/erro pt-BR via redirect com `?msg=`.
- Link discreto "admin" no rodapé das telas? Não — acesso direto por URL `/admin`
  (YAGNI; só o Luiz usa).

### 4. Implantação (uma vez, na sessão)

- Gravar `app_metadata.role = "admin"` no usuário `limajrsab@gmail.com` via API admin.
- Acrescentar `SUPABASE_SERVICE_KEY` ao `web/.env.local` e (depois) às env vars do
  Vercel — **como env server-only** (sem `NEXT_PUBLIC_`).
- CLAUDE.md: atualizar a regra "nunca usar service_role no `web\`" para "nunca no
  cliente/navegador — só em `web/lib/supabase/admin.ts` (server actions)".

## Segurança

- service_role: server-only, fora do bundle; `.env*` já gitignored; no Vercel entra
  como env normal (não exposta). O RLS das tabelas de dados não muda.
- `disable_signup` permanece `true` — criação de usuário só pelo nosso servidor
  (domínio aprovado) ou convite de admin.
- Ações de admin re-checam o papel no servidor a cada chamada.
- Remoção de usuário revoga o acesso imediatamente (sessões existentes expiram no
  refresh seguinte — TTL do JWT, padrão 1h; aceito no v1).
- A checagem de domínio usa o e-mail normalizado e compara sufixo exato
  `@estrategia.com` (não `contains`).

## Erros e mensagens (pt-BR)

| Caso | Mensagem |
|---|---|
| Link enviado | ✅ Link enviado! Abra seu e-mail e clique no link para entrar. |
| Externo desconhecido | 🔒 Acesso por convite — fale com o administrador do painel. |
| Convidado não-confirmado | 📨 Seu convite ainda não foi aceito — use o link do e-mail de convite (ou reenvie abaixo). |
| Convite reenviado | 📨 Convite reenviado! |
| Falha de envio/serviço | ❌ Não foi possível enviar agora — tente de novo em instantes. |
| Admin: convite ok | ✅ Convite enviado para {email}. |
| Admin: e-mail do domínio | ℹ Esse e-mail é @estrategia.com — entra direto pelo login, sem convite. |
| Admin: remoção ok | ✅ Acesso de {email} removido. |

## Testes / critérios de aceite

1. `@estrategia.com` inexistente → digita e-mail no login → recebe link → entra
   (usuário aparece na tela de admin como confirmado).
2. Externo desconhecido → mensagem de convite, nenhum e-mail sai.
3. Externo convidado não-confirmado → mensagem específica + reenvio funciona.
4. Não-admin acessando `/admin` → 404. Sem sessão → redirect /login (middleware).
5. Convidar externo pela tela → e-mail chega (Resend) → entra pelo convite.
6. Remover usuário → some da lista; login dele volta a cair na regra de externo.
7. `npm run build` limpo; service_role ausente de qualquer chunk do cliente
   (conferir `grep -r service_key .next/static` vazio).

## Fora de escopo (fica para depois)

- Promover/rebaixar admins pela tela; multi-admin.
- Lista de domínios configurável.
- Auditoria de acessos (quem entrou quando) além do "último login".
- Revogação instantânea de sessão ativa (hoje: expira no refresh do JWT).
