-- Migration 001: Document collections + collection files
-- Run manually: psql $DATABASE_URL -f db/migrations/001_collections.sql

CREATE TABLE IF NOT EXISTS collections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    file_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collections_user ON collections(user_id);
CREATE INDEX IF NOT EXISTS idx_collections_conversation ON collections(conversation_id);

CREATE TABLE IF NOT EXISTS collection_files (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id     UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    original_path     TEXT NOT NULL,
    markdown_path     TEXT,
    file_size         BIGINT NOT NULL DEFAULT 0,
    file_ext          TEXT,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'processing', 'done', 'error')),
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_collection_files_collection ON collection_files(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_files_user ON collection_files(user_id);

CREATE TRIGGER trg_collections_updated_at BEFORE UPDATE ON collections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
