-- DDL for data.gov.sg collections with versioning support
-- Enables idempotent ingestion and keyword search

create extension if not exists pg_trgm;

create table if not exists data_gov_sg_collection (
  collection_id text not null,
  lastUpdatedAt timestamptz not null,
  name text,
  description text,
  child_dataset_ids text[] not null default '{}',
  payload jsonb not null,
  created_at timestamptz not null default now(),
  primary key (collection_id, lastUpdatedAt)
);

create index if not exists idx_dgsc_collection_id_lastupdated_desc
  on data_gov_sg_collection (collection_id, lastUpdatedAt desc);

create index if not exists idx_dgsc_child_dataset_ids_gin
  on data_gov_sg_collection using gin (child_dataset_ids);

create index if not exists idx_dgsc_name_trgm
  on data_gov_sg_collection using gin (name gin_trgm_ops);

create index if not exists idx_dgsc_description_trgm
  on data_gov_sg_collection using gin (description gin_trgm_ops);

create or replace view data_gov_sg_collection_latest as
select distinct on (collection_id)
  collection_id,
  name,
  description,
  child_dataset_ids,
  lastUpdatedAt,
  payload
from data_gov_sg_collection
order by collection_id, lastUpdatedAt desc;

create or replace function data_gov_sg_collection_search(keyword text, lim int default 50)
returns table (
  collection_id text,
  name text,
  description text,
  child_dataset_ids text[],
  lastUpdatedAt timestamptz
)
language sql
stable
as $$
  select
    collection_id,
    name,
    description,
    child_dataset_ids,
    lastUpdatedAt
  from data_gov_sg_collection_latest
  where keyword is null
     or keyword = ''
     or (name ilike '%' || keyword || '%'
         or description ilike '%' || keyword || '%')
  order by lastUpdatedAt desc
  limit greatest(lim, 1);
$$;
