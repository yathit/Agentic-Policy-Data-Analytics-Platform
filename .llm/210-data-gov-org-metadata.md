# data-gov-org-metadata.md

## Goal

Ingest **data.gov.sg Collections** (paged) into Postgres with versioning (idempotent), and provide **latest view + keyword search**.

## Source

`GET https://api-production.data.gov.sg/v2/public/api/collections?page={page}`
Loop `page=1..pages` where `pages` comes from response `data.pages`.

## Postgres

### DDL

```sql
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
```

### Idempotency

* PK `(collection_id, lastUpdatedAt)`:

  * same version re-run → ignored
  * updated collection → new row (new `lastUpdatedAt`)

## Backend implementation

### Files

```
/backend/app/connectors/data_gov_sg.py
/backend/app/workers/data_gov_sg_collections.py
/backend/app/db/repo_data_gov_sg_collection.py
/backend/app/db/sql/ddl_data_gov_sg_collection.sql
```

### Connector

`fetch_collections_page(page: int) -> { pages: int, collections: list[dict] }`
Validate `data.pages` + `data.collections`.

### Repo

`insert_many_ignore_conflicts(rows) -> int`
SQL: `insert ... on conflict (collection_id, lastUpdatedAt) do nothing`.

### Worker

`run_data_gov_sg_collections_ingest() -> dict`
Loop pages, map each collection to row:

* `collection_id = collection["collectionId"]`
* `lastUpdatedAt = parse_ts(collection["lastUpdatedAt"])`
* `name = collection.get("name")`
* `description = collection.get("description")`
* `child_dataset_ids = collection.get("childDatasets") or []`
* `payload = collection`

Return summary: `pages_fetched`, `collections_seen`, `rows_inserted`, `errors` (optional).


### DDL migration 

Mount the DDL sql file into /docker-entrypoint-initdb.d/. as a one-shot migrate for postgres service in docker-compose file. 

## Worker task

### Contract

**Module:** `app/workers/data_gov_sg_collections.py`

* `run_data_gov_sg_collections_ingest() -> dict`

Algorithm:

1. Fetch page 1; read `pages`.
2. Persist page 1.
3. For page `2..pages`: fetch + persist.
4. Return summary: `pages_fetched`, `collections_seen`, `rows_inserted`, `errors[]` (optional)

Mapping:

* `collection_id` = `collection["collectionId"]`
* `lastUpdatedAt` = parse `collection["lastUpdatedAt"]`
* `name` = `collection.get("name")`
* `description` = `collection.get("description")`
* `payload` = raw dict

---

## Error handling & retries

* Retry transient failures (timeouts, 429, 5xx) with exponential backoff.
* Hard-fail on response shape drift (missing `data.pages` / `data.collections`).
* Record-level skip if missing `collectionId` or `lastUpdatedAt` (track in `errors[]`).

---

## Acceptance criteria

* Worker fetches `page=1..pages` and persists all collections.
* Idempotency holds on `(collection_id, lastUpdatedAt)`—no duplicates on re-run.
* `data_gov_sg_collection_latest` returns exactly one row per `collection_id` (latest).
* `data_gov_sg_collection_search(keyword, lim)` returns keyword matches over latest rows efficiently (indexes present).
