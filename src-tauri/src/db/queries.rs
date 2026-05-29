use tauri::AppHandle;
use crate::errors::SentinelError;
use rusqlite::{Connection, params};

#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct Portal {
    pub id: String,
    pub name: String,
    pub url: Option<String>,
    pub scraper_module: Option<String>,
    pub keywords: Option<String>,
    pub status: Option<String>,
    pub selector_config: Option<String>,
    pub last_run_at: Option<String>,
    pub last_run_duration_ms: Option<i64>,
    pub opportunities_count: Option<i32>,
    pub rendering_mode: Option<String>,
    pub cloudflare_bypass_score: Option<String>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct Opportunity {
    pub id: String,
    pub title: String,
    pub issuing_org: Option<String>,
    pub date: Option<String>,
    pub status: Option<String>,
    pub portal: String,
}

pub fn get_db_connection(app: &AppHandle) -> Result<Connection, SentinelError> {
    use tauri::Manager;
    let mut db_path = app.path().app_data_dir()
        .map_err(|e| SentinelError::Database(format!("Failed to get app data dir: {}", e)))?;
    
    // Ensure parent directory exists
    std::fs::create_dir_all(&db_path)
        .map_err(|e| SentinelError::Database(format!("Failed to create DB directory: {}", e)))?;
        
    db_path.push("sentinel.db");
    
    let conn = Connection::open(&db_path)
        .map_err(|e| SentinelError::Database(format!("Failed to open database at {:?}: {}", db_path, e)))?;
        
    Ok(conn)
}

pub fn fetch_portals(app: &AppHandle) -> Result<Vec<Portal>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT id, name, base_url, scraper_module, keywords, status, selector_config, last_run_at, last_run_duration_ms, opportunities_count, rendering_mode, cloudflare_bypass_score FROM portals"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map([], |row| {
        Ok(Portal {
            id: row.get(0)?,
            name: row.get(1)?,
            url: row.get(2)?,
            scraper_module: row.get(3)?,
            keywords: row.get(4)?,
            status: row.get(5)?,
            selector_config: row.get(6)?,
            last_run_at: row.get(7)?,
            last_run_duration_ms: row.get(8)?,
            opportunities_count: row.get(9)?,
            rendering_mode: row.get(10)?,
            cloudflare_bypass_score: row.get(11)?,
        })
    }).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut result = Vec::new();
    for row in rows {
        if let Ok(p) = row {
            result.push(p);
        }
    }
    Ok(result)
}

pub fn fetch_opportunities(app: &AppHandle) -> Result<Vec<Opportunity>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT o.id, o.title, o.issuing_org, o.deadline_at, o.status, p.name FROM opportunities o JOIN portals p ON o.portal_id = p.id ORDER BY o.created_at DESC"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map([], |row| {
        Ok(Opportunity {
            id: row.get(0)?,
            title: row.get(1)?,
            issuing_org: row.get(2)?,
            date: row.get(3)?,
            status: row.get(4)?,
            portal: row.get(5)?,
        })
    }).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut result = Vec::new();
    for row in rows {
        if let Ok(o) = row {
            result.push(o);
        }
    }
    Ok(result)
}

pub fn insert_portal(app: &AppHandle, portal: Portal) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "INSERT INTO portals (id, name, base_url, keywords, status, auth_method, scraper_module) VALUES (?, ?, ?, ?, ?, ?, ?)",
        params![
            portal.id,
            portal.name,
            portal.url.unwrap_or_default(),
            portal.keywords.unwrap_or_default(),
            portal.status.unwrap_or_else(|| "Active".to_string()),
            "public",
            portal.scraper_module.unwrap_or_else(|| "generic_search".to_string()),
        ]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn update_portal(app: &AppHandle, portal: Portal) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "UPDATE portals SET name = ?, base_url = ?, keywords = ?, status = ? WHERE id = ?",
        params![
            portal.name,
            portal.url.unwrap_or_default(),
            portal.keywords.unwrap_or_default(),
            portal.status.unwrap_or_else(|| "Active".to_string()),
            portal.id,
        ]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn delete_portal(app: &AppHandle, id: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute("DELETE FROM portals WHERE id = ?", params![id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn toggle_portal_status(app: &AppHandle, id: String, current_status: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    let next_status = if current_status == "Active" { "Inactive" } else { "Active" };
    conn.execute("UPDATE portals SET status = ? WHERE id = ?", params![next_status, id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn finish_portal_run(
    app: &AppHandle,
    portal_id: String,
    timestamp: String,
    duration: i64,
    opp_count: i32,
    rendering_mode: String,
    guard_score: String,
) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "UPDATE portals SET last_run_at = ?, last_run_duration_ms = ?, opportunities_count = ?, rendering_mode = ?, cloudflare_bypass_score = ? WHERE id = ?",
        params![timestamp, duration, opp_count, rendering_mode, guard_score, portal_id]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn record_opportunity(
    app: &AppHandle,
    id: String,
    portal_id: String,
    title: String,
    agency: String,
    due_date: String,
) -> Result<bool, SentinelError> {
    let conn = get_db_connection(app)?;
    
    // Check duplication natively in SQLite (O(log N) index-backed search)
    let normalized_input = title.trim().to_lowercase();
    let mut stmt = conn.prepare("SELECT EXISTS(SELECT 1 FROM opportunities WHERE LOWER(TRIM(title)) = ?)")
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    let exists: i32 = stmt.query_row(params![normalized_input], |row| row.get(0))
        .map_err(|e| SentinelError::Database(e.to_string()))?;
        
    if exists == 1 {
        // Duplicate found
        return Ok(false);
    }
    
    // Insert new opportunity
    conn.execute(
        "INSERT INTO opportunities (id, portal_id, title, issuing_org, deadline_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        params![id, portal_id, title, agency, due_date, "discovered"]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    
    // Increment opportunity count in portals
    conn.execute(
        "UPDATE portals SET opportunities_count = COALESCE(opportunities_count, 0) + 1 WHERE id = ?",
        params![portal_id]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    
    Ok(true)
}

pub fn update_portal_selector(app: &AppHandle, base_url: String, config_json: String, rendering_mode: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    let sanitized_url = base_url.trim_end_matches('/').to_string();
    let sanitized_with_slash = format!("{}/", sanitized_url);
    let like_pattern = format!("%{}%", sanitized_url);
    
    conn.execute(
        "UPDATE portals SET selector_config = ?, rendering_mode = ? WHERE base_url = ? OR base_url = ? OR base_url LIKE ?",
        params![config_json, rendering_mode, sanitized_url, sanitized_with_slash, like_pattern]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    
    Ok(())
}

pub fn get_kv(app: &AppHandle, key: String) -> Result<Option<String>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare("SELECT value FROM key_value_store WHERE key = ?")
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    
    let mut rows = stmt.query(params![key]).map_err(|e| SentinelError::Database(e.to_string()))?;
    if let Some(row) = rows.next().map_err(|e| SentinelError::Database(e.to_string()))? {
        let value: String = row.get(0).map_err(|e| SentinelError::Database(e.to_string()))?;
        Ok(Some(value))
    } else {
        Ok(None)
    }
}

pub fn set_kv(app: &AppHandle, key: String, value: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "INSERT INTO key_value_store (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![key, value]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}
