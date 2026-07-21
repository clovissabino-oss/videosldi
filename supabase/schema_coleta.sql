-- Fila de coleta + cookie do LDI + status do cookie (Fase 3).
-- Idempotente. Aplicar no SQL editor do Supabase ou via Management API.

create table if not exists coleta_pedido (
  id           bigserial primary key,
  tipo         text        not null check (tipo in ('termo','ids')),
  alvo         text        not null,
  rotulo       text,
  status       text        not null default 'pendente'
               check (status in ('pendente','rodando','cancelando',
                                  'cancelada','concluida','erro','aguardando_cookie')),
  progresso    text,
  mensagem     text,
  extracao_id  int,
  pedido_por   text,
  criado_em    timestamptz not null default now(),
  iniciado_em  timestamptz,
  concluido_em timestamptz
);
create index if not exists ix_coleta_pedido_fila
  on coleta_pedido (status, criado_em);

create table if not exists config_ldi (
  id             int primary key default 1 check (id = 1),
  cookie         text,
  atualizado_em  timestamptz not null default now(),
  atualizado_por text
);

create table if not exists cookie_status (
  id             int primary key default 1 check (id = 1),
  email          text,
  expira_em      timestamptz,
  dias_restantes numeric,
  valido         boolean not null default false,
  atualizado_em  timestamptz not null default now()
);

alter table coleta_pedido enable row level security;
alter table config_ldi    enable row level security;
alter table cookie_status enable row level security;

-- coleta_pedido: leitura autenticada; escrita só service_role (sem policy de escrita)
drop policy if exists "leitura autenticada" on coleta_pedido;
create policy "leitura autenticada" on coleta_pedido
  for select to authenticated using (true);

-- cookie_status: leitura autenticada (para o banner)
drop policy if exists "leitura autenticada" on cookie_status;
create policy "leitura autenticada" on cookie_status
  for select to authenticated using (true);

-- config_ldi: SEM policy nenhuma → authenticated não lê nem escreve; só service_role acessa.

grant select on coleta_pedido, cookie_status to authenticated;
