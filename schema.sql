-- ============================================================
-- FIRE Engine — PostgreSQL Schema
-- ============================================================

-- 1. Офисы
CREATE TABLE IF NOT EXISTS offices (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    address     TEXT,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 2. Менеджеры
CREATE TABLE IF NOT EXISTS managers (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    position    VARCHAR(100),
    office_id   INTEGER REFERENCES offices(id),
    skills      TEXT[],
    load        INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 3. Исходные обращения
CREATE TABLE IF NOT EXISTS tickets (
    id          SERIAL PRIMARY KEY,
    guid        VARCHAR(100) NOT NULL UNIQUE,
    gender      VARCHAR(20),
    birth_date  DATE,
    description TEXT,
    attachment  VARCHAR(255),
    segment     VARCHAR(50),
    country     VARCHAR(100),
    region      VARCHAR(100),
    city        VARCHAR(100),
    street      VARCHAR(150),
    house       VARCHAR(20),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 4. AI-анализ
CREATE TABLE IF NOT EXISTS ai_analysis (
    id              SERIAL PRIMARY KEY,
    ticket_id       INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    ai_type         VARCHAR(100),
    ai_lang         VARCHAR(10),
    sentiment       VARCHAR(10),
    priority        SMALLINT,
    summary         TEXT,
    recommendation  TEXT,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. Итоговое распределение
CREATE TABLE IF NOT EXISTS assignments (
    id              SERIAL PRIMARY KEY,
    ticket_id       INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    ai_analysis_id  INTEGER REFERENCES ai_analysis(id),
    manager_id      INTEGER REFERENCES managers(id),
    office_id       INTEGER REFERENCES offices(id),
    office_reason   VARCHAR(50),
    distance_km     DOUBLE PRECISION,
    is_escalation   BOOLEAN DEFAULT FALSE,
    trace           JSONB,
    assigned_at     TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_tickets_guid        ON tickets(guid);
CREATE INDEX IF NOT EXISTS idx_ai_type             ON ai_analysis(ai_type);
CREATE INDEX IF NOT EXISTS idx_ai_sentiment        ON ai_analysis(sentiment);
CREATE INDEX IF NOT EXISTS idx_assignments_manager ON assignments(manager_id);
CREATE INDEX IF NOT EXISTS idx_assignments_office  ON assignments(office_id);
CREATE INDEX IF NOT EXISTS idx_assignments_escalat ON assignments(is_escalation);

-- VIEW для дашборда
CREATE OR REPLACE VIEW v_assignments_full AS
SELECT
    t.guid,
    t.segment,
    t.country,
    t.city,
    a.ai_type,
    a.ai_lang,
    a.sentiment,
    a.priority,
    a.summary,
    a.recommendation,
    o.name          AS office,
    asgn.office_reason,
    asgn.distance_km,
    asgn.is_escalation,
    m.name          AS manager,
    m.position      AS manager_position,
    m.skills        AS manager_skills,
    asgn.assigned_at,
    asgn.trace
FROM assignments asgn
JOIN tickets     t    ON t.id  = asgn.ticket_id
JOIN ai_analysis a    ON a.id  = asgn.ai_analysis_id
LEFT JOIN offices  o  ON o.id  = asgn.office_id
LEFT JOIN managers m  ON m.id  = asgn.manager_id;
