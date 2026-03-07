CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS memory_items (
  id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'main',
  title TEXT,
  content TEXT NOT NULL,
  summary TEXT,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_path TEXT,
  source_ref TEXT,
  source_date DATE,
  related_session TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fts tsvector
);

CREATE OR REPLACE FUNCTION memory_items_set_timestamps() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.created_at := COALESCE(NEW.created_at, NOW());
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION memory_items_fts_update() RETURNS trigger AS $$
BEGIN
  NEW.fts :=
    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(NEW.summary, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'C');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_memory_items_set_timestamps ON memory_items;
CREATE TRIGGER trg_memory_items_set_timestamps
BEFORE INSERT OR UPDATE ON memory_items
FOR EACH ROW EXECUTE FUNCTION memory_items_set_timestamps();

DROP TRIGGER IF EXISTS trg_memory_items_fts_update ON memory_items;
CREATE TRIGGER trg_memory_items_fts_update
BEFORE INSERT OR UPDATE ON memory_items
FOR EACH ROW EXECUTE FUNCTION memory_items_fts_update();

CREATE INDEX IF NOT EXISTS idx_memory_items_scope
  ON memory_items(scope);

CREATE INDEX IF NOT EXISTS idx_memory_items_kind
  ON memory_items(kind);

CREATE INDEX IF NOT EXISTS idx_memory_items_source_date
  ON memory_items(source_date);

CREATE INDEX IF NOT EXISTS idx_memory_items_tags
  ON memory_items USING GIN(tags);

CREATE INDEX IF NOT EXISTS idx_memory_items_fts
  ON memory_items USING GIN(fts);

CREATE INDEX IF NOT EXISTS idx_memory_items_content_trgm
  ON memory_items USING GIN(content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_memory_items_summary_trgm
  ON memory_items USING GIN(summary gin_trgm_ops);
