CREATE TABLE IF NOT EXISTS portals (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  auth_method TEXT NOT NULL CHECK(auth_method IN ('api_key','credential','public','oauth')),
  scraper_module TEXT NOT NULL,
  active_window_start TEXT NOT NULL DEFAULT '02:00',
  active_window_end TEXT NOT NULL DEFAULT '06:00',
  requests_per_minute INTEGER NOT NULL DEFAULT 15 CHECK(requests_per_minute BETWEEN 1 AND 20),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  portal_id TEXT NOT NULL REFERENCES portals(id),
  title TEXT NOT NULL,
  issuing_org TEXT NOT NULL,
  deadline_at TEXT NOT NULL,
  url TEXT,
  description TEXT,
  downloaded_pdf_path TEXT,
  status TEXT NOT NULL DEFAULT 'discovered'
    CHECK(status IN ('discovered','downloaded','ingested','drafted','submitted')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS requirements (
  id TEXT PRIMARY KEY,
  rfp_id TEXT NOT NULL REFERENCES opportunities(id),
  section TEXT NOT NULL,
  requirement_text TEXT NOT NULL,
  requirement_type TEXT NOT NULL CHECK(requirement_type IN ('mandatory','scored','informational')),
  is_satisfied INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gap_items (
  id TEXT PRIMARY KEY,
  requirement_id TEXT NOT NULL REFERENCES requirements(id),
  severity TEXT NOT NULL CHECK(severity IN ('blocking','advisory')),
  description TEXT NOT NULL,
  suggestion TEXT NOT NULL
);

-- Dummy Data
INSERT OR IGNORE INTO portals (id, name, base_url, auth_method, scraper_module) VALUES ('1', 'SAM.gov', 'https://sam.gov', 'public', 'sam_gov');

INSERT OR IGNORE INTO opportunities (id, portal_id, title, issuing_org, deadline_at) VALUES ('101', '1', 'Cybersecurity Upgrades', 'DoD', '2026-06-01');
INSERT OR IGNORE INTO opportunities (id, portal_id, title, issuing_org, deadline_at) VALUES ('102', '1', 'Cloud Infrastructure Maintenance', 'NASA', '2026-06-15');
