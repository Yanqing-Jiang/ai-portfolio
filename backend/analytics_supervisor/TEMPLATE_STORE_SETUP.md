# Analytics Config → Supabase Tables

This guide turns the existing YAML configs under `backend/config/schemas/` into first-class tables inside your Supabase Postgres instance. Keeping the data in SQL makes it easier to join, version, and expose to downstream services (RAG, dashboards, admin tooling, etc.). All statements below are safe to rerun thanks to `IF NOT EXISTS` guards.

Before running anything:
- Set `DATABASE_URL` to your Supabase connection string.
- Enable the `pgvector` extension one time (`CREATE EXTENSION IF NOT EXISTS vector;`).
- Install `yq` or be ready to run a short Python script when you bulk-load from YAML.

---

## 1. `queries.yaml` → SQL template catalog

`queries.yaml` defines reusable SQL plans (used today by the supervisor fallback path). Persist them in two tables: one for the template metadata itself and one for keyword tags.

```sql
CREATE TABLE IF NOT EXISTS sql_templates (
    intent_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT[] DEFAULT '{}',
    sql_template TEXT NOT NULL,
    parameters JSONB DEFAULT '{}'::jsonb,
    example_utterances TEXT[] DEFAULT '{}',
    embedding vector(1536),            -- optional: populated when you call seed_from_queries_yaml
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sql_template_targets (
    intent_key TEXT REFERENCES sql_templates(intent_key) ON DELETE CASCADE,
    placeholder TEXT NOT NULL,          -- e.g. years_back, target_ticker
    default_value TEXT,
    description TEXT,
    PRIMARY KEY (intent_key, placeholder)
);
```

To ingest the current YAML, run either `seed_from_queries_yaml` (which already writes into `sql_templates`) or export with `yq` and use `psql`:

```bash
# one-off export
yq '.query_patterns | to_entries[] | {
  intent_key: .key,
  name: .value.name,
  description: .value.description,
  keywords: (.value.keywords // []),
  sql_template: .value.sql_template
}' backend/config/schemas/queries.yaml \
  | jq -c '.' \
  | psql "$DATABASE_URL" -c "COPY sql_templates (intent_key, name, description, keywords, sql_template) FROM STDIN WITH (FORMAT json)";
```

> The existing helper `backend/analytics_supervisor/template_store.py::seed_from_queries_yaml` already handles embeddings + inserts. Use it when you want semantic search via pgvector.

---

## 2. `metrics.yaml` → Metric dictionary

Create dedicated tables for categories, base metrics, derived metrics, and synonyms.

```sql
CREATE TABLE IF NOT EXISTS metric_categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    derived BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS metrics (
    metric_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    database_name TEXT,
    aliases TEXT[] DEFAULT '{}',
    category_id TEXT REFERENCES metric_categories(category_id),
    unit TEXT,
    aggregation TEXT,
    description TEXT,
    format TEXT,
    importance TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS derived_metrics (
    metric_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    formula TEXT NOT NULL,
    dependencies TEXT[] NOT NULL,
    unit TEXT,
    description TEXT,
    format TEXT,
    category_id TEXT REFERENCES metric_categories(category_id),
    importance TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS metric_synonyms (
    alias TEXT PRIMARY KEY,
    target JSONB NOT NULL           -- stores single metric_id OR array of metric_ids
);
```

Bulk load idea (Python):

```python
import yaml, psycopg
from pathlib import Path
cfg = yaml.safe_load(Path('backend/config/schemas/metrics.yaml').read_text())
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.transaction():
        for key, body in (cfg.get('categories') or {}).items():
            conn.execute(
                """
                INSERT INTO metric_categories (category_id, name, description, derived)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (category_id) DO UPDATE
                SET name = EXCLUDED.name, description = EXCLUDED.description, derived = EXCLUDED.derived
                """,
                (key, body.get('name'), body.get('description'), body.get('derived', False))
            )
        # Repeat for metrics, derived_metrics, synonyms ...
```

---

## 3. `companies.yaml` → Company registry

Maintain industries, companies, aliases, peer groups, and display preferences.

```sql
CREATE TABLE IF NOT EXISTS industries (
    industry_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    sector TEXT,
    industry TEXT,
    description TEXT,
    market_cap_tier TEXT,
    default_selection BOOLEAN DEFAULT FALSE,
    priority INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS company_aliases (
    ticker TEXT REFERENCES companies(ticker) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    PRIMARY KEY (ticker, alias)
);

CREATE TABLE IF NOT EXISTS peer_groups (
    group_id TEXT PRIMARY KEY,
    tickers TEXT[] NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS company_display_colors (
    ticker TEXT PRIMARY KEY,
    hex_color TEXT NOT NULL
);
```

Selection rules like `default_companies` can be stored in JSON or as a view:

```sql
CREATE TABLE IF NOT EXISTS company_selection_rules (
    rule_id TEXT PRIMARY KEY,
    tickers TEXT[] NOT NULL,
    reason TEXT
);
```

Populate using a similar Python loader or `yq` pipelines.

---

## 4. `charts.yaml` → Visualization presets

This file is nested; using JSONB columns keeps the schema manageable.

```sql
CREATE TABLE IF NOT EXISTS chart_themes (
    theme_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    colors JSONB NOT NULL,
    chart_colors JSONB
);

CREATE TABLE IF NOT EXISTS chart_types (
    type_id TEXT PRIMARY KEY,
    echarts_type TEXT NOT NULL,
    name TEXT,
    description TEXT,
    default_options JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS chart_layouts (
    layout_id TEXT PRIMARY KEY,
    layout JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS chart_formatting (
    format_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    axis_formatter TEXT,
    tooltip_formatter TEXT
);

CREATE TABLE IF NOT EXISTS chart_title_patterns (
    pattern_group TEXT,
    pattern_key TEXT,
    template TEXT NOT NULL,
    PRIMARY KEY (pattern_group, pattern_key)
);

CREATE TABLE IF NOT EXISTS chart_animations (
    animation_id TEXT PRIMARY KEY,
    settings JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS chart_interactivity (
    feature_id TEXT PRIMARY KEY,
    settings JSONB NOT NULL
);
```

When ingesting, keep the original structure in JSON to preserve future options.

---

## 5. `database.yaml` → Physical data catalog

Capture table schemas, indexes, and global query defaults.

```sql
CREATE TABLE IF NOT EXISTS table_schemas (
    table_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    table_type TEXT,
    value_column TEXT,
    entity_column TEXT,
    metric_column TEXT,
    time_columns JSONB,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS table_columns (
    table_id TEXT REFERENCES table_schemas(table_id) ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    data_type TEXT,
    description TEXT,
    required BOOLEAN DEFAULT FALSE,
    nullable BOOLEAN DEFAULT TRUE,
    indexed BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (table_id, column_name)
);

CREATE TABLE IF NOT EXISTS table_indexes (
    table_id TEXT REFERENCES table_schemas(table_id) ON DELETE CASCADE,
    index_name TEXT NOT NULL,
    columns TEXT[] NOT NULL,
    index_type TEXT,
    PRIMARY KEY (table_id, index_name)
);

CREATE TABLE IF NOT EXISTS query_defaults (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    defaults JSONB NOT NULL,
    data_validation JSONB,
    aggregation JSONB
);
```

---

## Loading workflow summary

1. Run the `CREATE TABLE` statements above.
2. Use quick scripts (Python + `psycopg`, or `yq` + `psql`) to transform each YAML into inserts.
3. For `sql_templates`, optionally run `seed_from_queries_yaml` to compute embeddings for pgvector search.
4. Build views as needed (e.g., join companies with colors for dashboards).

Once the configs live inside Supabase, the supervisor (and any new services) can query them directly, power admin UIs, and enrich RAG pipelines without reinventing YAML parsers.
