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
Runtime: usar Node 22+ (deps do Supabase pedem `>=22` nos engines).

## Mapa

- `middleware.ts` — gate: sem sessão → `/login`
- `app/login` + `app/auth/confirm` — magic-link (convite; templates ajustados no Dashboard)
- `app/route.ts` → `/` (painel, `__DADOS__` injetado) · `app/avaliacao/route.ts` → `/avaliacao`
- `app/api/{cursos,avaliacao}` — mesmos shapes do `painel.py`, lendo `snapshot_atual`/`avaliacao_curso`
- `telas/` — cópias das telas da raiz (fonte da verdade visual continua lá;
  mudou a tela da raiz → replicar aqui as mesmas 3 edições: link sair,
  selo de frescor, estado vazio)

**Convidar alguém:** Dashboard Supabase → Authentication → Users → Invite user.
