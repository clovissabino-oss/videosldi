# Acesso por domínio + tela de admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** E-mails `@estrategia.com` entram com magic link direto (auto-provisionados); externos só por convite, gerenciado numa tela `/admin` dentro do app (convidar + listar + remover).

**Architecture:** Toda a regra vive nos server actions do Next com um cliente admin server-only (`web/lib/supabase/admin.ts`, service_role via env `SUPABASE_SERVICE_KEY` sem `NEXT_PUBLIC_`). O `enviarLink` decide o caminho pelo domínio e estado do usuário; `/admin` re-checa `app_metadata.role === "admin"` no servidor a cada ação. `disable_signup` do Supabase continua ligado (só o nosso servidor cria usuário). Spec: `docs/superpowers/specs/2026-07-19-acesso-dominio-admin-design.md`.

**Tech Stack:** Next.js 15 (App Router, server actions), `@supabase/supabase-js` (API admin GoTrue), `@supabase/ssr` (sessão, já existente).

## Global Constraints

- **Idioma pt-BR** em código, mensagens e comentários.
- **service_role NUNCA no cliente/navegador**: só em `web/lib/supabase/admin.ts`, importado apenas por server actions / server components. Env `SUPABASE_SERVICE_KEY` **sem** prefixo `NEXT_PUBLIC_`.
- **`disable_signup` permanece `true`** no Supabase — não mexer na config de auth.
- Domínio aprovado fixo: sufixo exato **`@estrategia.com`** sobre e-mail normalizado (trim + lowercase); usar `endsWith`, nunca `includes`.
- **Datas de exibição em pt-BR com `timeZone: "America/Sao_Paulo"`** (o servidor do Vercel roda em UTC — sem o timeZone explícito a data "local" sairia errada).
- **`getUser()`**, nunca `getSession()`.
- Mensagens da tabela do spec, verbatim (seção "Erros e mensagens").
- Admin v1: só o Luiz (`limajrsab@gmail.com`); admin não remove a si mesmo.
- Sem testes JS automatizados (padrão do app web) — verificação por `npm run build`, curls e critérios de aceite manuais do spec.

---

### Task 1: Cliente admin server-only + envs

**Files:**
- Create: `web/lib/supabase/admin.ts`
- Modify: `web/.env.exemplo` (acrescentar `SUPABASE_SERVICE_KEY=`)
- Modify: `web/.env.local` (acrescentar a service key real — **NÃO commitar**; o valor real está no campo `service_key` de `supabase.json` na raiz do repo)

**Interfaces:**
- Consumes: envs `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
- Produces (Tasks 2–3 importam exatamente estes nomes):
  - `criarClienteAdmin(): SupabaseClient`
  - `buscarPorEmail(admin: SupabaseClient, email: string): Promise<User | null>`
  - `listarUsuarios(admin: SupabaseClient): Promise<User[]>`
  (tipos `SupabaseClient` e `User` de `@supabase/supabase-js`)

- [ ] **Step 1: Criar `web/lib/supabase/admin.ts`**

```ts
import { createClient, type SupabaseClient, type User } from "@supabase/supabase-js";

// Cliente com a service_role (API admin do GoTrue). SERVER-ONLY:
// importar apenas de server actions / server components — nunca de
// componente cliente (a chave não pode chegar ao navegador).
export function criarClienteAdmin(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const chave = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !chave) {
    throw new Error("SUPABASE_SERVICE_KEY ausente (env server-only do app).");
  }
  return createClient(url, chave, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

// A API admin não tem busca por e-mail; o time é pequeno (< 1000),
// então listamos uma página cheia e filtramos localmente.
export async function buscarPorEmail(
  admin: SupabaseClient,
  email: string
): Promise<User | null> {
  const usuarios = await listarUsuarios(admin);
  return usuarios.find((u) => (u.email ?? "").toLowerCase() === email) ?? null;
}

export async function listarUsuarios(admin: SupabaseClient): Promise<User[]> {
  const { data, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 });
  if (error) throw new Error(`listar usuários: ${error.message}`);
  return data.users;
}
```

- [ ] **Step 2: Envs**

Em `web/.env.exemplo`, acrescentar ao final:

```
# Server-only (sem NEXT_PUBLIC_): API admin do GoTrue — nunca chega ao navegador
SUPABASE_SERVICE_KEY=COLE_AQUI_A_SERVICE_ROLE_KEY
```

Em `web/.env.local`, acrescentar `SUPABASE_SERVICE_KEY=<valor de service_key do supabase.json da raiz>` (ler o valor com um comando, não digitar à mão):

```bash
cd web && python -c "import json; print('SUPABASE_SERVICE_KEY=' + json.load(open('../supabase.json', encoding='utf-8'))['service_key'])" >> .env.local
```

- [ ] **Step 3: Buildar**

Run: `cd web && npm run build`
Expected: compila limpo (o módulo novo ainda não é importado por ninguém — ok).

- [ ] **Step 4: Commit**

```bash
git add web/lib/supabase/admin.ts web/.env.exemplo
git commit -m "feat(web): cliente admin server-only (service_role) + env SUPABASE_SERVICE_KEY"
```

---

### Task 2: Regra de acesso no login (domínio aprovado + convite pendente)

**Files:**
- Rewrite: `web/app/login/actions.ts`
- Modify: `web/app/login/page.tsx`

**Interfaces:**
- Consumes: `criarClienteAdmin`, `buscarPorEmail` (Task 1); `criarClienteServidor` (já existe em `web/lib/supabase/servidor.ts`).
- Produces: server actions `enviarLink(formData)` e `reenviarConvite(formData)`; mensagens novas `convite`, `convite-pendente` (com `&email=`), `convite-reenviado` na página de login.

- [ ] **Step 1: Reescrever `web/app/login/actions.ts`**

```ts
"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { buscarPorEmail, criarClienteAdmin } from "../../lib/supabase/admin";
import { criarClienteServidor } from "../../lib/supabase/servidor";

const DOMINIO_APROVADO = "@estrategia.com";

// Regra de acesso (spec 2026-07-19):
//   @estrategia.com  -> pré-aprovado: cria/confirma o usuário e envia o link
//   externo          -> só por convite (existente e confirmado)
export async function enviarLink(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) redirect("/login?msg=email");

  const admin = criarClienteAdmin();
  const usuario = await buscarPorEmail(admin, email);

  if (email.endsWith(DOMINIO_APROVADO)) {
    if (!usuario) {
      const { error } = await admin.auth.admin.createUser({ email, email_confirm: true });
      if (error) redirect("/login?msg=erro");
    } else if (!usuario.email_confirmed_at) {
      const { error } = await admin.auth.admin.updateUserById(usuario.id, {
        email_confirm: true,
      });
      if (error) redirect("/login?msg=erro");
    }
  } else {
    if (!usuario) redirect("/login?msg=convite");
    if (!usuario.email_confirmed_at) {
      redirect(`/login?msg=convite-pendente&email=${encodeURIComponent(email)}`);
    }
  }

  // Aqui o usuário existe e está confirmado -> magic link normal.
  const h = await headers();
  const origem = `${h.get("x-forwarded-proto") ?? "http"}://${h.get("host")}`;
  const supabase = await criarClienteServidor();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { shouldCreateUser: false, emailRedirectTo: `${origem}/auth/confirm` },
  });
  redirect(error ? "/login?msg=erro" : "/login?msg=enviado");
}

// Reenvia o convite APENAS para convidado pendente (existe e não confirmou) —
// não vira reenviador arbitrário de convites.
export async function reenviarConvite(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email) redirect("/login?msg=email");

  const admin = criarClienteAdmin();
  const usuario = await buscarPorEmail(admin, email);
  if (!usuario || usuario.email_confirmed_at) redirect("/login?msg=convite");

  const { error } = await admin.auth.admin.inviteUserByEmail(email);
  redirect(error ? "/login?msg=erro" : "/login?msg=convite-reenviado");
}
```

- [ ] **Step 2: Atualizar `web/app/login/page.tsx`**

Substituir o arquivo inteiro por:

```tsx
import { enviarLink, reenviarConvite } from "./actions";

const MENSAGENS: Record<string, string> = {
  enviado: "✅ Link enviado! Abra seu e-mail e clique no link para entrar.",
  erro: "❌ Não foi possível enviar agora — tente de novo em instantes.",
  email: "Informe seu e-mail.",
  "link-invalido": "⚠ Link inválido ou vencido. Peça um novo abaixo.",
  convite: "🔒 Acesso por convite — fale com o administrador do painel.",
  "convite-pendente":
    "📨 Seu convite ainda não foi aceito — use o link do e-mail de convite (ou reenvie abaixo).",
  "convite-reenviado": "📨 Convite reenviado!",
};

export default async function PaginaLogin({
  searchParams,
}: {
  searchParams: Promise<{ msg?: string; email?: string }>;
}) {
  const { msg, email } = await searchParams;
  return (
    <main
      style={{
        minHeight: "100vh", display: "grid", placeItems: "center",
        background: "#fcfcfb", color: "#0b0b0b",
        font: '15px/1.5 "Segoe UI", system-ui, sans-serif',
      }}
    >
      <div
        style={{
          background: "#f4f4f2", border: "1px solid #e3e2dd", borderRadius: 10,
          padding: "28px 32px", width: 360, maxWidth: "90vw",
        }}
      >
        <p style={{
          fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase",
          color: "#2a78d6", fontWeight: 600, margin: "0 0 6px",
        }}>
          Painel de Conteúdo
        </p>
        <h1 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 4px" }}>Entrar</h1>
        <p style={{ color: "#52514e", fontSize: 13, margin: "0 0 16px" }}>
          E-mail @estrategia.com entra direto; externos, por convite.
        </p>
        {msg && MENSAGENS[msg] && (
          <p style={{ fontSize: 13, margin: "0 0 12px" }}>{MENSAGENS[msg]}</p>
        )}
        <form action={enviarLink}>
          <input
            type="email" name="email" required placeholder="seu@email.com"
            defaultValue={email ?? ""}
            style={{
              width: "100%", font: "inherit", padding: "8px 11px",
              border: "1px solid #e3e2dd", borderRadius: 8, marginBottom: 10,
            }}
          />
          <button
            type="submit"
            style={{
              width: "100%", font: "inherit", fontWeight: 600, cursor: "pointer",
              background: "#2a78d6", color: "#fff", border: 0, borderRadius: 8,
              padding: "9px 11px",
            }}
          >
            Enviar link de acesso
          </button>
        </form>
        {msg === "convite-pendente" && email && (
          <form action={reenviarConvite} style={{ marginTop: 10 }}>
            <input type="hidden" name="email" value={email} />
            <button
              type="submit"
              style={{
                width: "100%", font: "inherit", fontWeight: 600, cursor: "pointer",
                background: "transparent", color: "#2a78d6",
                border: "1px solid #2a78d6", borderRadius: 8, padding: "8px 11px",
              }}
            >
              Reenviar convite
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
```

(Mudanças vs anterior: `<form>` principal agora está dentro de um `<div>` contêiner; mensagens novas; `defaultValue` do e-mail; formulário secundário de reenvio.)

- [ ] **Step 3: Buildar e conferir**

Run: `cd web && npm run build`
Expected: limpo.

Run (dev no ar): `curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/login?msg=convite-pendente&email=x%40y.com"`
Expected: `200`.

- [ ] **Step 4: Commit**

```bash
git add web/app/login
git commit -m "feat(web): regra de acesso por domínio no login (+reenvio de convite pendente)"
```

---

### Task 3: Tela `/admin` (convidar + listar + remover)

**Files:**
- Create: `web/app/admin/actions.ts`
- Create: `web/app/admin/form-remover.tsx`
- Create: `web/app/admin/page.tsx`

**Interfaces:**
- Consumes: `criarClienteAdmin`, `buscarPorEmail`, `listarUsuarios` (Task 1); `criarClienteServidor`.
- Produces: rota `/admin` (404 para não-admin), server actions `convidarUsuario`, `removerUsuario`.

- [ ] **Step 1: Criar `web/app/admin/actions.ts`**

```ts
"use server";

import { redirect } from "next/navigation";
import { criarClienteAdmin } from "../../lib/supabase/admin";
import { criarClienteServidor } from "../../lib/supabase/servidor";

const DOMINIO_APROVADO = "@estrategia.com";

// Toda action re-checa o papel NO SERVIDOR — nunca confiar só na página.
async function exigirAdmin() {
  const supabase = await criarClienteServidor();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || user.app_metadata?.role !== "admin") redirect("/login");
  return user;
}

export async function convidarUsuario(formData: FormData) {
  await exigirAdmin();
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) redirect("/admin?msg=email");
  if (email.endsWith(DOMINIO_APROVADO)) redirect("/admin?msg=dominio");

  const admin = criarClienteAdmin();
  const { error } = await admin.auth.admin.inviteUserByEmail(email);
  redirect(error ? "/admin?msg=erro" : `/admin?msg=convidado&email=${encodeURIComponent(email)}`);
}

export async function removerUsuario(formData: FormData) {
  const eu = await exigirAdmin();
  const id = String(formData.get("id") ?? "");
  const email = String(formData.get("email") ?? "");
  if (!id) redirect("/admin?msg=erro");
  if (id === eu.id) redirect("/admin?msg=proprio");

  const admin = criarClienteAdmin();
  const { error } = await admin.auth.admin.deleteUser(id);
  redirect(error ? "/admin?msg=erro" : `/admin?msg=removido&email=${encodeURIComponent(email)}`);
}
```

- [ ] **Step 2: Criar `web/app/admin/form-remover.tsx`** (componente cliente só para o `confirm()`)

```tsx
"use client";

import { removerUsuario } from "./actions";

export function FormRemover({
  id, email, desabilitado,
}: {
  id: string; email: string; desabilitado: boolean;
}) {
  return (
    <form
      action={removerUsuario}
      onSubmit={(e) => {
        if (!confirm(`Remover o acesso de ${email}?`)) e.preventDefault();
      }}
      style={{ display: "inline" }}
    >
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="email" value={email} />
      <button
        type="submit"
        disabled={desabilitado}
        title={desabilitado ? "Você não pode remover a si mesmo" : undefined}
        style={{
          font: "inherit", fontSize: 12.5, cursor: desabilitado ? "not-allowed" : "pointer",
          background: "transparent", color: desabilitado ? "#8a897f" : "#b23230",
          border: "1px solid currentColor", borderRadius: 6, padding: "3px 10px",
        }}
      >
        Remover
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Criar `web/app/admin/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import { listarUsuarios, criarClienteAdmin } from "../../lib/supabase/admin";
import { criarClienteServidor } from "../../lib/supabase/servidor";
import { convidarUsuario } from "./actions";
import { FormRemover } from "./form-remover";

export const dynamic = "force-dynamic";

const MENSAGENS: Record<string, (email?: string) => string> = {
  email: () => "Informe um e-mail válido.",
  dominio: () => "ℹ Esse e-mail é @estrategia.com — entra direto pelo login, sem convite.",
  erro: () => "❌ Não foi possível concluir — tente de novo.",
  proprio: () => "⚠ Você não pode remover a si mesmo.",
  convidado: (e) => `✅ Convite enviado para ${e ?? "o e-mail"}.`,
  removido: (e) => `✅ Acesso de ${e ?? "usuário"} removido.`,
};

// Data local do projeto: pt-BR com fuso explícito (servidor do Vercel é UTC).
const dataLocal = (iso: string | undefined) =>
  iso
    ? new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit", month: "2-digit", year: "2-digit",
        hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo",
      })
    : "—";

export default async function PaginaAdmin({
  searchParams,
}: {
  searchParams: Promise<{ msg?: string; email?: string }>;
}) {
  const { msg, email } = await searchParams;

  const supabase = await criarClienteServidor();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || user.app_metadata?.role !== "admin") notFound();

  const admin = criarClienteAdmin();
  const usuarios = await listarUsuarios(admin);
  usuarios.sort((a, b) => (a.email ?? "").localeCompare(b.email ?? "", "pt-BR"));

  return (
    <main
      style={{
        maxWidth: 760, margin: "0 auto", padding: "32px 24px 64px",
        background: "#fcfcfb", color: "#0b0b0b", minHeight: "100vh",
        font: '14.5px/1.5 "Segoe UI", system-ui, sans-serif',
      }}
    >
      <p style={{
        fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase",
        color: "#2a78d6", fontWeight: 600, margin: "0 0 6px",
      }}>
        <a href="/" style={{ color: "#8a897f", textDecoration: "none" }}>← painel</a>
        {" "}Painel de Conteúdo · administração de acesso
      </p>
      <h1 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 4px" }}>Usuários</h1>
      <p style={{ color: "#52514e", fontSize: 13, margin: "0 0 16px" }}>
        @estrategia.com entra sozinho pelo login. Convide aqui apenas e-mails externos.
      </p>

      {msg && MENSAGENS[msg] && (
        <p style={{ fontSize: 13, margin: "0 0 12px" }}>{MENSAGENS[msg](email)}</p>
      )}

      <form action={convidarUsuario} style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          type="email" name="email" required placeholder="externo@dominio.com"
          style={{
            flex: 1, font: "inherit", padding: "8px 11px",
            border: "1px solid #e3e2dd", borderRadius: 8,
          }}
        />
        <button
          type="submit"
          style={{
            font: "inherit", fontWeight: 600, cursor: "pointer",
            background: "#2a78d6", color: "#fff", border: 0, borderRadius: 8,
            padding: "8px 16px",
          }}
        >
          Convidar
        </button>
      </form>

      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
        <thead>
          <tr>
            {["E-mail", "Papel", "Confirmado", "Último login", ""].map((t) => (
              <th key={t} style={{
                textAlign: "left", padding: "8px 10px", color: "#52514e",
                fontSize: 11, letterSpacing: ".07em", textTransform: "uppercase",
                borderBottom: "1px solid #e3e2dd",
              }}>{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.id}>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {u.email}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {u.app_metadata?.role === "admin" ? "admin" : "—"}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {u.email_confirmed_at ? "✅" : "📨 pendente"}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {dataLocal(u.last_sign_in_at)}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                <FormRemover id={u.id} email={u.email ?? ""} desabilitado={u.id === user.id} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

- [ ] **Step 4: Buildar e conferir o gate**

Run: `cd web && npm run build`
Expected: limpo; rota `/admin` dynamic (ƒ).

Run (dev no ar, sem sessão): `curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://localhost:3000/admin`
Expected: `307 http://localhost:3000/login` (o middleware pega antes do notFound — correto: sem sessão nem revela a rota).

- [ ] **Step 5: Commit**

```bash
git add web/app/admin
git commit -m "feat(web): tela /admin — convidar, listar e remover usuários (só admin)"
```

---

### Task 4: Implantação, CLAUDE.md e verificação de aceite

**Files:**
- Modify: `CLAUDE.md` (regra da service_role)
- Sem código novo — implantação + verificação.

**Interfaces:**
- Consumes: tudo das Tasks 1–3; `supabase.json` (service_key + access_token).

- [ ] **Step 1: Marcar o Luiz como admin (uma vez, via API)**

```bash
cd "/c/Users/Clovis Sabino/Projetos/Estratégia Claude/🎬 EXTRATOR_LDI_VIDEOS" && python - <<'EOF'
import json, requests
cfg = json.load(open("supabase.json", encoding="utf-8"))
h = {"apikey": cfg["service_key"], "Authorization": f"Bearer {cfg['service_key']}",
     "Content-Type": "application/json"}
base = cfg["url"].rstrip("/") + "/auth/v1/admin/users"
users = requests.get(base, headers=h, timeout=30).json()["users"]
luiz = next(u for u in users if u["email"] == "limajrsab@gmail.com")
r = requests.put(f"{base}/{luiz['id']}", headers=h,
                 json={"app_metadata": {"role": "admin"}}, timeout=30)
print("role admin ->", r.status_code, r.json().get("app_metadata"))
EOF
```

Expected: `role admin -> 200 {'provider': 'email', 'providers': ['email'], 'role': 'admin'}`.

- [ ] **Step 2: Service key fora do bundle do cliente (critério do spec)**

```bash
cd web && grep -rl "service_role" .next/static 2>/dev/null; grep -rl "SUPABASE_SERVICE_KEY" .next/static 2>/dev/null; echo "(vazio = ok)"
```

Expected: nenhum arquivo listado.

- [ ] **Step 3: Atualizar o CLAUDE.md**

Na seção "Publicação web", trocar a frase `Nunca usar a service_role no `web\`.` por:

```
Service_role no app: só no módulo server-only `web\lib\supabase\admin.ts` (env
`SUPABASE_SERVICE_KEY`, sem NEXT_PUBLIC_) — nunca em componente cliente/navegador.
Acesso: @estrategia.com entra direto pelo login; externos por convite na tela /admin
(admin = app_metadata.role="admin"; hoje só o Luiz).
```

- [ ] **Step 4: Critérios de aceite manuais (com o Luiz, dev server no ar)**

1. Externo desconhecido (ex.: `teste@gmail.com`) no login → mensagem de convite, sem e-mail.
2. O e-mail do Luiz (convidado pendente) → mensagem "convite pendente" + reenvio funciona **ou** o Luiz aceita o convite original e o magic link passa a chegar.
3. `/admin` logado como Luiz → tabela aparece; convidar um externo → e-mail chega; remover → some.
4. (Quando alguém do Estratégia testar) `@estrategia.com` → link chega direto.

- [ ] **Step 5: Commit + registrar no PROXIMA-SESSAO.md**

```bash
git add CLAUDE.md PROXIMA-SESSAO.md
git commit -m "docs: acesso por domínio + /admin registrados (CLAUDE.md e sessão)"
```

---

## Self-review (feito na escrita)

- **Cobertura do spec:** regra de domínio ✓ (T2) · mensagens da tabela ✓ (T2/T3, verbatim) · reenvio seguro ✓ (T2, revalida pendente no servidor) · /admin convidar+listar+remover ✓ (T3) · admin não remove a si ✓ (T3) · 404 para não-admin ✓ (T3; sem sessão o middleware redireciona antes — comportamento registrado) · service_role server-only + grep no bundle ✓ (T1/T4) · role no usuário do Luiz ✓ (T4) · CLAUDE.md ✓ (T4).
- **Tipos consistentes:** `criarClienteAdmin/buscarPorEmail/listarUsuarios` iguais nas Tasks 1–3; `User.app_metadata?.role` acessado igual em page e actions.
- **Placeholders:** nenhum.
- **Nota:** e-mails de teste do critério 4 dependem de alguém com conta @estrategia.com — fica documentado como pendência de aceite, não bloqueia o merge.
