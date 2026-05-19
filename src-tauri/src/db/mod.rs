use tauri_plugin_sql::{Migration, MigrationKind};

pub fn init() -> Vec<Migration> {
    let schema = include_str!("schema.sql");
    
    vec![
        Migration {
            version: 1,
            description: "initial_schema",
            sql: schema,
            kind: MigrationKind::Up,
        },
        Migration {
            version: 2,
            description: "dummy_data",
            sql: "INSERT OR IGNORE INTO portals (id, name, base_url, auth_method, scraper_module) VALUES ('1', 'SAM.gov', 'https://sam.gov', 'public', 'sam_gov');
                  INSERT OR IGNORE INTO opportunities (id, portal_id, title, issuing_org, deadline_at) VALUES ('101', '1', 'Cybersecurity Upgrades', 'DoD', '2026-06-01');
                  INSERT OR IGNORE INTO opportunities (id, portal_id, title, issuing_org, deadline_at) VALUES ('102', '1', 'Cloud Infrastructure Maintenance', 'NASA', '2026-06-15');",
            kind: MigrationKind::Up,
        },
        Migration {
            version: 3,
            description: "add_keywords_and_status_to_portals",
            sql: "ALTER TABLE portals ADD COLUMN keywords TEXT;
                  ALTER TABLE portals ADD COLUMN status TEXT;",
            kind: MigrationKind::Up,
        },
        Migration {
            version: 4,
            description: "add_selector_config_to_portals",
            sql: "ALTER TABLE portals ADD COLUMN selector_config TEXT;",
            kind: MigrationKind::Up,
        },
        Migration {
            version: 5,
            description: "add_diagnostic_columns_to_portals",
            sql: "ALTER TABLE portals ADD COLUMN last_run_at TEXT;
                  ALTER TABLE portals ADD COLUMN last_run_duration_ms INTEGER;
                  ALTER TABLE portals ADD COLUMN opportunities_count INTEGER DEFAULT 0;
                  ALTER TABLE portals ADD COLUMN rendering_mode TEXT DEFAULT 'Static HTML';
                  ALTER TABLE portals ADD COLUMN cloudflare_bypass_score TEXT DEFAULT 'Low Risk';",
            kind: MigrationKind::Up,
        }
    ]
}
