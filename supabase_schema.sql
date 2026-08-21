create extension if not exists pgcrypto;

create table if not exists public.programs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  area text not null default 'GENERACION',
  source_filename text,
  uploaded_by text,
  uploaded_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.programs(id) on delete cascade,
  area text not null default 'GENERACION',
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
  event_date date,
  created_at timestamptz not null default now()
);

alter table public.programs add column if not exists area text not null default 'GENERACION';
alter table public.tasks add column if not exists area text not null default 'GENERACION';
alter table public.advances add column if not exists event_date date;
update public.programs set area = 'GENERACION' where area is null or trim(area) = '';
update public.tasks set area = 'GENERACION' where area is null or trim(area) = '';

create index if not exists idx_tasks_program on public.tasks(program_id);
create index if not exists idx_programs_area_active on public.programs(area, active);
create index if not exists idx_tasks_area_program on public.tasks(area, program_id);
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
