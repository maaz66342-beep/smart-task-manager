-- ============================================================
-- Smart Task Management System – Database Schema
-- PostgreSQL
-- ============================================================

-- Drop existing tables (for clean re-run)
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE users (
    id          SERIAL       PRIMARY KEY,
    username    VARCHAR(80)  UNIQUE NOT NULL,
    email       VARCHAR(120) UNIQUE NOT NULL,
    password    TEXT         NOT NULL,          -- bcrypt hash
    created_at  TIMESTAMP    DEFAULT NOW()
);

-- ── Tasks ────────────────────────────────────────────────────
CREATE TABLE tasks (
    id           SERIAL      PRIMARY KEY,
    user_id      INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title        VARCHAR(200) NOT NULL,
    description  TEXT,
    priority     VARCHAR(10)  NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
    status       VARCHAR(20)  NOT NULL CHECK (status   IN ('pending', 'in_progress', 'completed')),
    created_at   TIMESTAMP    DEFAULT NOW(),
    updated_at   TIMESTAMP    DEFAULT NOW()
);

-- ── Indexes ──────────────────────────────────────────────────
CREATE INDEX idx_tasks_user_id  ON tasks (user_id);
CREATE INDEX idx_tasks_status   ON tasks (status);
CREATE INDEX idx_tasks_priority ON tasks (priority);

-- ── Auto-update updated_at ────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
