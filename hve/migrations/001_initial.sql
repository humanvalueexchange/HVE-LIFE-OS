CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    checksum    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    domain      TEXT NOT NULL CHECK (domain IN (
                    'time_wealth','physical_wealth','mental_wealth',
                    'social_wealth','financial_wealth'
                )),
    checksum    TEXT NOT NULL,
    content     TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_knowledge_domain ON knowledge(domain);

CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY,
    domain      TEXT NOT NULL CHECK (domain IN (
                    'time_wealth','physical_wealth','mental_wealth',
                    'social_wealth','financial_wealth'
                )),
    category    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    value_type  TEXT NOT NULL CHECK (value_type IN ('text','number','bool','enum')),
    value       TEXT NOT NULL,
    source      TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    valid_from  TEXT,
    valid_to    TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_domain ON facts(domain, category);
CREATE INDEX IF NOT EXISTS idx_facts_valid  ON facts(valid_from, valid_to);

CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    response    TEXT,
    latency_ms  INTEGER,
    model       TEXT,
    context_len INTEGER,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS health_log (
    id          INTEGER PRIMARY KEY,
    component   TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ok','warn','fail')),
    detail      TEXT,
    checked_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
