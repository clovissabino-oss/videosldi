# App web no Vercel (vitrine do Painel de Conteúdo) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar as telas aprovadas do Painel de Conteúdo (`painel.html` + `avaliacao.html`) como app web de leitura no Vercel, com login Supabase Auth (magic-link, convite apenas), lendo as tabelas já sincronizadas no Supabase.

**Architecture:** Next.js mínimo (App Router) numa subpasta `web/` deste repo (Vercel com Root Directory = `web`; deploy = `git push`). As telas continuam HTML/JS vanilla, servidas por **route handlers** que injetam dados/config — exatamente como o Flask faz hoje. A sessão fica em **cookies via `@supabase/ssr`** (middleware gate + rotas de API); por isso as telas seguem chamando `/api/...` (agora handlers Next que consultam o Supabase com o JWT do usuário — RLS `authenticated` aplicado). *Desvio consciente do spec:* o spec dizia "supabase-js direto do navegador", mas o cliente UMD do navegador guarda sessão em localStorage enquanto o middleware exige cookie (`@supabase/ssr`) — duas sessões incompatíveis. Servir via handlers resolve isso, mantém as telas com **zero mudança de fetch** e o RLS continua sendo o guarda (o handler usa o token do usuário, não a service_role).

**Tech Stack:** Next.js 15 (App Router, TypeScript), `@supabase/ssr` + `@supabase/supabase-js`, telas em JS vanilla (as mesmas do painel local).

## Global Constraints

- **Idioma pt-BR** em código, comentários, mensagens e docs (nomes de função em português, como no resto do projeto).
- **Não regredir o lado Python**: nada em `painel.py`, `sync_supabase.py`, coletor ou telas locais muda. As telas web são **cópias** em `web/telas/` (o Flask continua servindo as originais da raiz).
- **Datas de exibição = data local** (convenção do projeto, não UTC) — `toLocaleString("pt-BR")`.
- **Segredos nunca no git**: anon key entra por env (`.env.local` local / env vars no Vercel). `.env*` no `.gitignore`. (A anon key é pública por design, mas mantemos o padrão.)
- **Leitura apenas**: o app web não escreve nada no Supabase; nunca usar a service_role key no Next.
- **`getUser()`**, nunca `getSession()`, para checagem de auth (getSession não valida o JWT).
- Supabase do projeto: conta **Estratégia**, ref `zpjsoidxhfwziprjxpqx` (nunca o pessoal do Luiz).

## O que o LUIZ precisa fazer (avisar na hora certa)

1. **Já no início (Task 1):** colar aqui a **anon key** do projeto (Dashboard → Settings → API Keys → `anon` `public`) para o `.env.local` local.
2. **Task 5 (config do Auth no Dashboard):** desligar auto-cadastro, ajustar 2 templates de e-mail, convidar o próprio e-mail (checklist detalhado na task).
3. **Task 5 (Vercel):** criar o projeto Vercel apontando pro repo `videosldi` com Root Directory `web` + 2 env vars, e fazer o push (login interativo).

---

### Task 1: Esqueleto Next.js em `web/`

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/next.config.mjs`
- Create: `web/.gitignore`
- Create: `web/.env.exemplo`
- Create: `web/.env.local` (NÃO versionado — precisa da anon key do Luiz)
- Create: `web/app/layout.tsx`

**Interfaces:**
- Consumes: nada.
- Produces: projeto que builda (`npm run build`); env vars `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` que TODAS as tasks seguintes leem; `outputFileTracingIncludes` que a Task 4 precisa para as telas chegarem ao Vercel.

- [ ] **Step 1: Conferir o Node da máquina**

Run: `node --version && npm --version`
Expected: Node ≥ 18.18 (ideal 20+). Se não houver Node, PARAR e avisar o Luiz (instalar o Node LTS de https://nodejs.org).

- [ ] **Step 2: Criar os arquivos do esqueleto**

Create `web/package.json`:

```json
{
  "name": "painel-conteudo-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "@supabase/ssr": "^0.6.1",
    "@supabase/supabase-js": "^2.47.0",
    "next": "^15.3.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "typescript": "^5.7.0"
  }
}
```

Create `web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Create `web/next.config.mjs`:

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // As telas HTML são lidas do disco em runtime pelos route handlers;
  // sem isto o build do Vercel não as inclui no bundle serverless.
  outputFileTracingIncludes: {
    "/": ["./telas/**"],
    "/avaliacao": ["./telas/**"],
  },
};

export default nextConfig;
```

Create `web/.gitignore`:

```
node_modules/
.next/
next-env.d.ts
.env*
!.env.exemplo
*.tsbuildinfo
```

Create `web/.env.exemplo`:

```
# Copie para .env.local e preencha (Dashboard Supabase -> Settings -> API)
NEXT_PUBLIC_SUPABASE_URL=https://zpjsoidxhfwziprjxpqx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=COLE_AQUI_A_ANON_KEY
```

Create `web/.env.local` (com a anon key que o Luiz colar — **pedir agora se ainda não tiver**):

```
NEXT_PUBLIC_SUPABASE_URL=https://zpjsoidxhfwziprjxpqx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key do Luiz>
```

Create `web/app/layout.tsx`:

```tsx
import type { ReactNode } from "react";

export const metadata = {
  title: "Painel de Conteúdo",
  description: "Auditoria de conteúdo dos cursos LDI — leitura para o time",
};

export default function LayoutRaiz({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: Instalar e buildar**

Run: `cd web && npm install && npm run build`
Expected: build termina sem erro (nenhuma rota ainda — só o layout; Next aceita).

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json web/tsconfig.json web/next.config.mjs web/.gitignore web/.env.exemplo web/app/layout.tsx
git commit -m "feat(web): esqueleto Next.js mínimo do app de leitura (Vercel)"
```

---

### Task 2: Autenticação — cliente servidor, middleware gate, login magic-link

**Files:**
- Create: `web/lib/supabase/servidor.ts`
- Create: `web/middleware.ts`
- Create: `web/app/login/page.tsx`
- Create: `web/app/login/actions.ts`
- Create: `web/app/auth/confirm/route.ts`
- Create: `web/app/auth/sair/route.ts`

**Interfaces:**
- Consumes: env vars da Task 1.
- Produces: `criarClienteServidor(): Promise<SupabaseClient>` (em `web/lib/supabase/servidor.ts`) — TODAS as rotas das Tasks 3–4 usam esta função; gate global: qualquer rota fora de `/login` e `/auth/*` sem sessão redireciona para `/login`.

- [ ] **Step 1: Cliente Supabase de servidor (sessão em cookie)**

Create `web/lib/supabase/servidor.ts`:

```ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Cliente Supabase para route handlers e server actions.
// A sessão vive em cookies (@supabase/ssr) — é o que o middleware valida.
export async function criarClienteServidor() {
  const jarra = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return jarra.getAll();
        },
        setAll(aGravar) {
          try {
            aGravar.forEach(({ name, value, options }) =>
              jarra.set(name, value, options)
            );
          } catch {
            // Chamado de um Server Component: o middleware renova a sessão.
          }
        },
      },
    }
  );
}
```

- [ ] **Step 2: Middleware gate**

Create `web/middleware.ts`:

```ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Gate: sem sessão -> /login. Também renova o token expirado (setAll).
export async function middleware(request: NextRequest) {
  let resposta = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(aGravar) {
          aGravar.forEach(({ name, value }) => request.cookies.set(name, value));
          resposta = NextResponse.next({ request });
          aGravar.forEach(({ name, value, options }) =>
            resposta.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return resposta;
}

export const config = {
  // Tudo passa pelo gate, exceto login, fluxo de auth e estáticos do Next.
  matcher: ["/((?!login|auth/|_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 3: Página de login + server action do magic-link**

Create `web/app/login/actions.ts`:

```ts
"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { criarClienteServidor } from "../../lib/supabase/servidor";

// Envia o magic-link. shouldCreateUser:false = convite apenas
// (e-mail não convidado não cria conta nem recebe link).
export async function enviarLink(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  if (!email) redirect("/login?msg=email");

  const h = await headers();
  const origem = `${h.get("x-forwarded-proto") ?? "http"}://${h.get("host")}`;

  const supabase = await criarClienteServidor();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      shouldCreateUser: false,
      emailRedirectTo: `${origem}/auth/confirm`,
    },
  });

  redirect(error ? "/login?msg=erro" : "/login?msg=enviado");
}
```

Create `web/app/login/page.tsx`:

```tsx
import { enviarLink } from "./actions";

const MENSAGENS: Record<string, string> = {
  enviado: "✅ Link enviado! Abra seu e-mail e clique no link para entrar.",
  erro: "❌ Não foi possível enviar o link. Confira o e-mail — o acesso é por convite.",
  email: "Informe seu e-mail.",
  "link-invalido": "⚠ Link inválido ou vencido. Peça um novo abaixo.",
};

export default async function PaginaLogin({
  searchParams,
}: {
  searchParams: Promise<{ msg?: string }>;
}) {
  const { msg } = await searchParams;
  return (
    <main
      style={{
        minHeight: "100vh", display: "grid", placeItems: "center",
        background: "#fcfcfb", color: "#0b0b0b",
        font: '15px/1.5 "Segoe UI", system-ui, sans-serif',
      }}
    >
      <form
        action={enviarLink}
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
          Acesso por convite. Digite seu e-mail e receba um link de acesso.
        </p>
        {msg && MENSAGENS[msg] && (
          <p style={{ fontSize: 13, margin: "0 0 12px" }}>{MENSAGENS[msg]}</p>
        )}
        <input
          type="email" name="email" required placeholder="seu@email.com"
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
    </main>
  );
}
```

- [ ] **Step 4: Rota que troca o token do e-mail por sessão + rota de sair**

Create `web/app/auth/confirm/route.ts`:

```ts
import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

// O link do e-mail (magic-link OU convite) chega aqui com token_hash + type.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const token_hash = url.searchParams.get("token_hash");
  const type = (url.searchParams.get("type") ?? "email") as EmailOtpType;

  if (token_hash) {
    const supabase = await criarClienteServidor();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) return NextResponse.redirect(new URL("/", url));
  }
  return NextResponse.redirect(new URL("/login?msg=link-invalido", url));
}
```

Create `web/app/auth/sair/route.ts`:

```ts
import { NextResponse } from "next/server";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

export async function GET(request: Request) {
  const supabase = await criarClienteServidor();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/login", request.url));
}
```

- [ ] **Step 5: Buildar e conferir o gate no dev**

Run: `cd web && npm run build`
Expected: build sem erro.

Run (2 terminais ou background): `npm run dev` e depois `curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://localhost:3000/`
Expected: `307 http://localhost:3000/login` (sem sessão → redireciona). `curl http://localhost:3000/login` devolve o HTML do formulário (200).

- [ ] **Step 6: Commit**

```bash
git add web/lib/supabase/servidor.ts web/middleware.ts web/app/login web/app/auth
git commit -m "feat(web): login magic-link (convite) + middleware gate com @supabase/ssr"
```

---

### Task 3: APIs de leitura — `/api/cursos` e `/api/avaliacao`

**Files:**
- Create: `web/lib/dados.ts`
- Create: `web/app/api/cursos/route.ts`
- Create: `web/app/api/avaliacao/route.ts`

**Interfaces:**
- Consumes: `criarClienteServidor()` da Task 2; tabelas `snapshot_atual` / `avaliacao_curso` do Supabase (já populadas pelo sync).
- Produces:
  - `snapshotAtual(supabase)` → `{ id, termo, resumo, sincronizado_em } | null` (usada também pela Task 4).
  - `GET /api/cursos` → `{ data: [{curso_id, nome, autores}], sincronizado_em }` (mesmo shape do Flask + selo).
  - `GET /api/avaliacao?curso_id=X` → `{ data: <payload de dados_avaliacao()> }` (idêntico ao Flask).

- [ ] **Step 1: Função compartilhada do snapshot atual**

Create `web/lib/dados.ts`:

```ts
import type { SupabaseClient } from "@supabase/supabase-js";

// A view snapshot_atual tem 1 linha por termo (só pronto=true).
// v1 = um termo por vez: pega o sincronizado mais recentemente.
export async function snapshotAtual(supabase: SupabaseClient) {
  const { data, error } = await supabase
    .from("snapshot_atual")
    .select("id, termo, resumo, sincronizado_em")
    .order("sincronizado_em", { ascending: false })
    .limit(1);
  if (error) throw new Error(`snapshot_atual: ${error.message}`);
  return data?.[0] ?? null;
}
```

- [ ] **Step 2: Rota /api/cursos**

Create `web/app/api/cursos/route.ts`:

```ts
import { NextResponse } from "next/server";
import { snapshotAtual } from "../../../lib/dados";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

export const dynamic = "force-dynamic";

// Mesmo shape do /api/cursos do painel.py (curso_id, nome, autores)
// + sincronizado_em para o selo de frescor da tela.
export async function GET() {
  const supabase = await criarClienteServidor();
  const snap = await snapshotAtual(supabase);
  if (!snap) return NextResponse.json({ data: [], sincronizado_em: null });

  const { data, error } = await supabase
    .from("avaliacao_curso")
    .select("curso_id, curso_nome, autores")
    .eq("snapshot_id", snap.id)
    .order("curso_nome");
  if (error) {
    return NextResponse.json({ data: null, erro: error.message }, { status: 500 });
  }
  const cursos = (data ?? []).map((c) => ({
    curso_id: c.curso_id,
    nome: c.curso_nome ?? "",
    autores: c.autores ?? "",
  }));
  return NextResponse.json({ data: cursos, sincronizado_em: snap.sincronizado_em });
}
```

- [ ] **Step 3: Rota /api/avaliacao**

Create `web/app/api/avaliacao/route.ts`:

```ts
import { NextResponse } from "next/server";
import { snapshotAtual } from "../../../lib/dados";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

export const dynamic = "force-dynamic";

// Devolve o payload PRONTO de painel.dados_avaliacao() gravado pelo sync —
// mesmo {data: ...} que a tela local consome do Flask.
export async function GET(request: Request) {
  const cursoId = new URL(request.url).searchParams.get("curso_id") ?? "";
  const supabase = await criarClienteServidor();
  const snap = await snapshotAtual(supabase);
  if (!snap) return NextResponse.json({ data: null });

  const { data, error } = await supabase
    .from("avaliacao_curso")
    .select("payload")
    .eq("snapshot_id", snap.id)
    .eq("curso_id", cursoId)
    .maybeSingle();
  if (error) {
    return NextResponse.json({ data: null, erro: error.message }, { status: 500 });
  }
  return NextResponse.json({ data: data?.payload ?? null });
}
```

- [ ] **Step 4: Buildar e conferir que o gate protege as APIs**

Run: `cd web && npm run build`
Expected: build sem erro, rotas `/api/cursos` e `/api/avaliacao` listadas como dynamic (ƒ).

Run (com `npm run dev` no ar): `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/cursos`
Expected: `307` (sem sessão o middleware redireciona antes de tocar o Supabase).

- [ ] **Step 5: Commit**

```bash
git add web/lib/dados.ts web/app/api
git commit -m "feat(web): APIs de leitura /api/cursos e /api/avaliacao (payload pronto do sync)"
```

---

### Task 4: Telas portadas + rotas `/` e `/avaliacao`

**Files:**
- Create: `web/telas/painel.html` (cópia de `painel.html` da raiz + 3 edições abaixo)
- Create: `web/telas/avaliacao.html` (cópia de `avaliacao.html` da raiz + 3 edições abaixo)
- Create: `web/app/route.ts`
- Create: `web/app/avaliacao/route.ts`

**Interfaces:**
- Consumes: `snapshotAtual()` e `criarClienteServidor()`; `web/telas/*.html`.
- Produces: `GET /` (painel com `__DADOS__` injetado, igual ao Flask) e `GET /avaliacao` (tela que consome as APIs da Task 3).

- [ ] **Step 1: Copiar as telas**

```bash
cp painel.html web/telas/painel.html
cp avaliacao.html web/telas/avaliacao.html
```

- [ ] **Step 2: Editar `web/telas/painel.html` (3 edições)**

Edição 1 — link Sair no eyebrow (linha ~98). Trocar:

```html
  <p class="eyebrow">Painel de Conteúdo · Inventário
    &nbsp;·&nbsp; <a href="/avaliacao" style="color:inherit">📋 Avaliação de disciplina</a></p>
```

por:

```html
  <p class="eyebrow">Painel de Conteúdo · Inventário
    &nbsp;·&nbsp; <a href="/avaliacao" style="color:inherit">📋 Avaliação de disciplina</a>
    <a href="/auth/sair" style="color:inherit;float:right">sair ↪</a></p>
```

Edição 2 — texto do subtítulo (fala em rodar coletor; na web é leitura). Trocar:

```html
  <p class="sub">Dados vivos da base <code>conteudo.db</code> — snapshot mais recente.
  Rode o coletor de novo (ou outro concurso) e recarregue a página.</p>
```

por:

```html
  <p class="sub">Snapshot mais recente publicado pelo coletor — leitura para o time.</p>
```

Edição 3 — selo de frescor nos chips (JS, linha ~143). Trocar:

```js
  const dt = (E.iniciada_em || "").replace("T", " ").slice(0, 16);
  document.getElementById("chips").innerHTML = [
    `Snapshot <b>#${E.id}</b>`, `Coletado em <b>${dt}</b>`, `Termo <b>${E.termo}</b>`,
    `Status <b>${E.status}</b> · ${fmt(E.erros)} erro(s)`,
  ].map(c => `<span class="chip">${c}</span>`).join("");
```

por:

```js
  const dt = (E.iniciada_em || "").replace("T", " ").slice(0, 16);
  const sync = D.sincronizado_em ? new Date(D.sincronizado_em).toLocaleString("pt-BR",
    { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : null;
  document.getElementById("chips").innerHTML = [
    `Snapshot <b>#${E.id}</b>`, `Coletado em <b>${dt}</b>`, `Termo <b>${E.termo}</b>`,
    `Status <b>${E.status}</b> · ${fmt(E.erros)} erro(s)`,
    sync ? `Dados de <b>${sync}</b>` : null,
  ].filter(Boolean).map(c => `<span class="chip">${c}</span>`).join("");
```

- [ ] **Step 3: Editar `web/telas/avaliacao.html` (3 edições)**

Edição 1 — link Sair no eyebrow (linha ~69). Trocar:

```html
  <p class="eyebrow"><a href="/">← visão geral</a> Painel de Conteúdo · avaliação de livro/disciplina</p>
```

por:

```html
  <p class="eyebrow"><a href="/">← visão geral</a> Painel de Conteúdo · avaliação de livro/disciplina
    <a href="/auth/sair" style="float:right">sair ↪</a></p>
```

Edição 2 — elemento do selo de frescor. Logo após `<p class="sub" id="autores"></p>` (linha ~71), inserir:

```html
  <p class="sub" id="frescor" style="margin-top:-12px"></p>
```

Edição 3 — `carregarCursos` ganha selo + estado vazio (JS, linha ~117). Trocar:

```js
  async function carregarCursos() {
    const r = await fetch("/api/cursos");
    const cursos = (await r.json()).data;
    const sel = document.getElementById("selCurso");
    sel.innerHTML = '<option value="">— escolha —</option>' + cursos.map(c =>
      `<option value="${c.curso_id}">${c.nome.trim()}</option>`).join("");
    sel.addEventListener("change", () => sel.value && carregarAvaliacao(sel.value));
    if (cursos.length === 1) { sel.value = cursos[0].curso_id; carregarAvaliacao(sel.value); }
  }
```

por:

```js
  async function carregarCursos() {
    const r = await fetch("/api/cursos");
    const j = await r.json();
    const cursos = j.data || [];
    if (j.sincronizado_em) {
      const sync = new Date(j.sincronizado_em).toLocaleString("pt-BR",
        { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
      document.getElementById("frescor").textContent = `Dados de ${sync}`;
    }
    const sel = document.getElementById("selCurso");
    if (!cursos.length) {
      document.getElementById("titulo").textContent = "Nenhum snapshot publicado ainda";
      sel.innerHTML = '<option value="">— sem dados —</option>';
      return;
    }
    sel.innerHTML = '<option value="">— escolha —</option>' + cursos.map(c =>
      `<option value="${c.curso_id}">${c.nome.trim()}</option>`).join("");
    sel.addEventListener("change", () => sel.value && carregarAvaliacao(sel.value));
    if (cursos.length === 1) { sel.value = cursos[0].curso_id; carregarAvaliacao(sel.value); }
  }
```

- [ ] **Step 4: Route handlers que servem as telas**

Create `web/app/route.ts`:

```ts
import { readFile } from "fs/promises";
import { NextResponse } from "next/server";
import path from "path";
import { snapshotAtual } from "../lib/dados";
import { criarClienteServidor } from "../lib/supabase/servidor";

export const dynamic = "force-dynamic";

// GET / — serve o painel com __DADOS__ injetado (mesmo mecanismo do painel.py).
export async function GET() {
  const supabase = await criarClienteServidor();
  const snap = await snapshotAtual(supabase);
  if (!snap) {
    return new NextResponse(
      "<h1>Nenhum snapshot publicado ainda.</h1>" +
      "<p>Assim que o coletor rodar e sincronizar, os dados aparecem aqui.</p>",
      { headers: { "content-type": "text/html; charset=utf-8" } }
    );
  }
  const html = await readFile(
    path.join(process.cwd(), "telas", "painel.html"), "utf-8"
  );
  const dados = { ...snap.resumo, sincronizado_em: snap.sincronizado_em };
  // < evita fechar o <script> se algum nome de curso tiver "</"
  const json = JSON.stringify(dados).replace(/</g, "\\u003c");
  return new NextResponse(html.replace("__DADOS__", json), {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
```

Create `web/app/avaliacao/route.ts`:

```ts
import { readFile } from "fs/promises";
import { NextResponse } from "next/server";
import path from "path";

export const dynamic = "force-dynamic";

// GET /avaliacao — a tela busca tudo em /api/... depois de carregar.
export async function GET() {
  const html = await readFile(
    path.join(process.cwd(), "telas", "avaliacao.html"), "utf-8"
  );
  return new NextResponse(html, {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
```

- [ ] **Step 5: Buildar e conferir**

Run: `cd web && npm run build`
Expected: build sem erro; rotas `/` e `/avaliacao` como dynamic (ƒ).

Run (com `npm run dev` no ar): `curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://localhost:3000/avaliacao`
Expected: `307 http://localhost:3000/login` (gate protege as telas).

- [ ] **Step 6: Commit**

```bash
git add web/telas web/app/route.ts web/app/avaliacao
git commit -m "feat(web): telas do painel e da avaliação servidas pelo Next (selo de frescor + estados vazios)"
```

---

### Task 5: Configuração manual (Luiz) + verificação de paridade + docs

**Files:**
- Create: `web/README.md`
- Modify: `PROXIMA-SESSAO.md` (nota da sessão)

**Interfaces:**
- Consumes: app completo das Tasks 1–4.
- Produces: app no ar no Vercel, login funcionando, números conferidos contra o painel local.

- [ ] **Step 1: Checklist do Dashboard Supabase (Luiz executa, eu oriento)**

No projeto `zpjsoidxhfwziprjxpqx` (conta Estratégia):

1. **Authentication → Sign In / Up → Email**: DESLIGAR "Allow new users to sign up" (acesso só por convite).
2. **Authentication → Emails (templates)**:
   - **Magic Link** → corpo com link: `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email`
   - **Invite user** → corpo com link: `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=invite`
3. **Authentication → URL Configuration**:
   - Site URL: a URL do Vercel (ex.: `https://painel-conteudo.vercel.app`) — preencher após o 1º deploy.
   - Redirect URLs: adicionar `http://localhost:3000/auth/confirm` e `https://<app>.vercel.app/auth/confirm`.
4. **Authentication → Users → Invite user**: convidar o e-mail do Luiz (teste) — depois os do time.

- [ ] **Step 2: Verificação local de paridade (critério de aceite do spec)**

1. `cd web && npm run dev`
2. Navegador em `http://localhost:3000` → deve cair em `/login`.
3. Login com o e-mail convidado → e-mail chega → link → volta logado no painel.
4. Rodar o painel local (`py painel.py --sem-navegador`) e comparar:
   - KPIs da home (cursos, aulas únicas, blocos, questões, textos, vídeos) **idênticos**.
   - `/avaliacao` do mesmo curso (ex.: Direito Penal): todas as colunas **idênticas** às de `http://127.0.0.1:8766/avaliacao`.
   - Selo "Dados de DD/MM HH:MM" aparece nas duas telas web.

- [ ] **Step 3: Vercel (Luiz executa, eu oriento)**

1. `git push` da branch (login interativo do Luiz).
2. vercel.com → Add New Project → importar `clovissabino-oss/videosldi`.
3. **Root Directory: `web`** (Framework: Next.js, detectado sozinho).
4. Environment Variables: `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY` (mesmos valores do `.env.local`).
5. Deploy → copiar a URL → voltar ao Step 1.3 (Site URL + Redirect URLs).
6. Testar o login na URL do Vercel e repetir a comparação de números.

- [ ] **Step 4: README do app web**

Create `web/README.md`:

```markdown
# Painel de Conteúdo — app web (Vercel)

App de **leitura** para o time: serve as telas do Painel de Conteúdo lendo o
Supabase (tabelas publicadas pelo `sync_supabase.py` da raiz do repo).
Login por magic-link (Supabase Auth), acesso **por convite apenas**.

## Rodar local

    cp .env.exemplo .env.local   # e preencha a anon key
    npm install
    npm run dev                  # http://localhost:3000

## Deploy

Projeto Vercel com **Root Directory = `web`**; deploy automático no `git push`.
Env vars no Vercel: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

## Mapa

- `middleware.ts` — gate: sem sessão → `/login`
- `app/login` + `app/auth/confirm` — magic-link (convite; templates ajustados no Dashboard)
- `app/route.ts` → `/` (painel, `__DADOS__` injetado) · `app/avaliacao/route.ts` → `/avaliacao`
- `app/api/{cursos,avaliacao}` — mesmos shapes do `painel.py`, lendo `snapshot_atual`/`avaliacao_curso`
- `telas/` — cópias das telas da raiz (fonte da verdade visual continua lá)

**Convidar alguém:** Dashboard Supabase → Authentication → Users → Invite user.
```

- [ ] **Step 5: Commit final + atualizar PROXIMA-SESSAO.md**

Adicionar ao `PROXIMA-SESSAO.md` (seção da sessão corrente) o resumo: app web no ar,
URL do Vercel, como convidar usuários, e que as telas web são cópias em `web/telas/`
(mudou a tela da raiz → replicar na cópia).

```bash
git add web/README.md PROXIMA-SESSAO.md
git commit -m "docs(web): README do app + registro da sessão"
```

---

## Self-review (feito na escrita)

- **Cobertura do spec:** login magic-link convite ✓ (Task 2 + 5.1) · middleware gate ✓ (2.2) · telas portadas com fetch inalterado ✓ (4) · selo de frescor ✓ (4.2/4.3) · estados vazios ✓ (4.3/4.4) · env por Vercel ✓ (1/5.3) · deploy git push ✓ (5.3). Item do spec "supabase-js direto do navegador" substituído por handlers server-side — justificado no Architecture (incompatibilidade localStorage×cookie com o gate) e sinalizado ao Luiz.
- **Paridade:** payload vem pronto do sync (mesma agregação Python); critério de aceite na Task 5.2.
- **Tipos consistentes:** `criarClienteServidor()` e `snapshotAtual()` usados com os mesmos nomes nas Tasks 2–4.
- **Sem testes JS**: decisão do spec (verificação = visual/paridade); o lado Python já tem o teste de paridade do `montar_payload`.
