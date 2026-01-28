# Task 210 — Data.gov.sg Collection Metadata Ingestion

## Objective
Extract all collection metadata from data.gov.sg Collection APIs, paginate across all pages, and persist records into PostgreSQL table `data_gov_sg_collection` with raw payload plus key fields.

## References
- Collection listing endpoint: `GET https://api-production.data.gov.sg/v2/public/api/collections`.
- Pagination: response includes `data.pages`, and `page` query parameter selects page number (>= 1).
- Collection fields include `name`, `description`, and `lastUpdatedAt`.

## Target Table
Create (if missing) a table named `data_gov_sg_collection` with the required columns:

```
CREATE TABLE IF NOT EXISTS data_gov_sg_collection (
  name text PRIMARY KEY,
  description text,
  "lastUpdatedAt" timestamptz,
  payload jsonb NOT NULL
);
```

## Execution Plan
1. Request page 1 from the collections listing API.
2. Read `data.pages` from the response to determine total pages.
3. For each page from 1..pages:
   - Fetch the page.
   - Iterate through `data.collections`.
   - Insert/update each collection into `data_gov_sg_collection`:
     - `name` from `collection.name`
     - `description` from `collection.description`
     - `lastUpdatedAt` from `collection.lastUpdatedAt`
     - `payload` as the full raw collection object
4. Use an UPSERT to keep the table in sync on re-runs.

## Standalone Script
Create a standalone Python script at:
- `backend/scripts/collect_data_gov_sg_collections.py`

Expected usage:
```
python backend/scripts/collect_data_gov_sg_collections.py --database-url "postgresql://user:pass@host:5432/db"
```
Or set `DATABASE_URL` in the environment.

## Acceptance Criteria
- Script paginates from page 1 to `data.pages` and collects all collections.
- Table `data_gov_sg_collection` exists with columns: `payload`, `name`, `description`, `lastUpdatedAt`.
- Each collection is stored with raw payload and key fields.
- Script can be re-run safely (idempotent upsert).

## Verification
- Run the script once, then verify row count:
  - `SELECT COUNT(*) FROM data_gov_sg_collection;`
- Spot-check one row to ensure `payload`, `name`, `description`, `lastUpdatedAt` are populated.
