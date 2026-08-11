create extension if not exists pgcrypto;

create table if not exists public.programs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  source_filename text,
  uploaded_by text,
  uploaded_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs(id) on delete cascade,
  row_hash text,
  nro_ot text,
  tarea text,
  empresa text,
  sector text,
  cuadrilla text,
  fecha_inicio date,
  fecha_fin date,
  duracion integer,
  estado_programa text,
  ubicacion_tecnica text,
  kks_tag text,
  raw jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.advances (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs(id) on delete cascade,
  task_id uuid not null references public.tasks(id) on delete cascade,
  action text not null,
  reason text,
  observation text,
  reporter_name text not null,
  reporter_company text,
  reporter_sector text,
  created_at timestamptz not null default now()
);

create index if not exists idx_tasks_program on public.tasks(program_id);
create index if not exists idx_tasks_filters on public.tasks(program_id, empresa, sector, cuadrilla, fecha_inicio);
create index if not exists idx_advances_program on public.advances(program_id, created_at desc);
create index if not exists idx_advances_task on public.advances(task_id, created_at desc);

alter table public.programs disable row level security;
alter table public.tasks disable row level security;
alter table public.advances disable row level security;

grant usage on schema public to anon;
grant select, insert, update, delete on public.programs to anon;
grant select, insert, update, delete on public.tasks to anon;
grant select, insert, update, delete on public.advances to anon;
