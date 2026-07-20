-- Schema do app web (Painel de Conteúdo — leitura para o time).
-- Aplicar no SQL editor do Supabase (Dashboard → SQL) OU via `supabase db push`.
-- Idempotente: pode rodar de novo sem quebrar.

create table if not exists snapshot (
  id              bigserial primary key,
  termo           text        not null,
  extracao_local  int         not null,
  status          text,
  iniciada_em     timestamptz,
  resumo          jsonb,
  pronto          boolean     not null default false,
  sincronizado_em timestamptz not null default now(),
  unique (termo, extracao_local)
);

create table if not exists avaliacao_curso (
  snapshot_id bigint not null references snapshot(id) on delete cascade,
  curso_id    text   not null,
  curso_nome  text,
  autores     text,
  payload     jsonb,
  primary key (snapshot_id, curso_id)
);

create table if not exists pendencia_resumo (
  snapshot_id bigint not null references snapshot(id) on delete cascade,
  severidade  text   not null,
  regra       text   not null,
  abertas     int,
  primary key (snapshot_id, severidade, regra)
);

-- "o snapshot mais recente e 100% sincronizado de cada termo"
create or replace view snapshot_atual as
  select distinct on (termo) *
  from snapshot
  where pronto
  order by termo, extracao_local desc;

-- a view respeita o RLS das tabelas de baixo (não roda como dono)
alter view snapshot_atual set (security_invoker = on);

-- RLS: leitura só para autenticados; escrita só via service_role (ignora RLS)
alter table snapshot         enable row level security;
alter table avaliacao_curso  enable row level security;
alter table pendencia_resumo enable row level security;

drop policy if exists "leitura autenticada" on snapshot;
drop policy if exists "leitura autenticada" on avaliacao_curso;
drop policy if exists "leitura autenticada" on pendencia_resumo;

create policy "leitura autenticada" on snapshot
  for select to authenticated using (true);
create policy "leitura autenticada" on avaliacao_curso
  for select to authenticated using (true);
create policy "leitura autenticada" on pendencia_resumo
  for select to authenticated using (true);

grant select on snapshot, avaliacao_curso, pendencia_resumo to authenticated;
grant select on snapshot_atual to authenticated;
