-- De→para de vídeos do Metabase (question 19885): data real de gravação por
-- video_id_antigo, para a web/VPS casarem sem o cache gz local.
-- Idempotente. Aplicar no SQL editor do Supabase (Dashboard → SQL) → Run.

create table if not exists depara_video (
  video_id      text primary key,   -- = video_id_antigo (chave do gz)
  data          text,               -- data/hora de gravação (ISO, como no gz)
  status        text,
  titulo        text,
  raiz          text,               -- professor
  path          text,               -- árvore antiga
  dur           text,               -- "HH:MM:SS"
  n             int,
  atualizado_em timestamptz not null default now()
);

alter table depara_video enable row level security;

-- leitura autenticada; escrita só service_role (sem policy de escrita)
drop policy if exists "leitura autenticada" on depara_video;
create policy "leitura autenticada" on depara_video
  for select to authenticated using (true);

grant select on depara_video to authenticated;
