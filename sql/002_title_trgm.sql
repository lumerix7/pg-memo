CREATE INDEX IF NOT EXISTS idx_memory_items_title_trgm
  ON memory_items USING GIN(title gin_trgm_ops);
