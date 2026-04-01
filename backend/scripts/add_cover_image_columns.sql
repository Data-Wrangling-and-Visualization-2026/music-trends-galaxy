-- Run once on existing PostgreSQL DBs after pulling models with ``cover_image_id``.
-- New installs can rely on ``init_db.py`` (create_all) instead.

ALTER TABLE dim_albums ADD COLUMN IF NOT EXISTS cover_image_id INTEGER;
ALTER TABLE dim_artists ADD COLUMN IF NOT EXISTS cover_image_id INTEGER;
