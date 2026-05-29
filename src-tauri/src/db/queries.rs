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
    pub url: Option<String>,
    pub portal_base_url: Option<String>,
    pub description: Option<String>,
}

pub fn get_db_connection(app: &AppHandle) -> Result<Connection, SentinelError> {
    use tauri::Manager;
    let mut db_path = app.path().app_config_dir()
        .map_err(|e| SentinelError::Database(format!("Failed to get app config dir: {}", e)))?;
    
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
        "SELECT o.id, o.title, o.issuing_org, o.deadline_at, o.status, p.name, o.url, p.base_url, o.description FROM opportunities o JOIN portals p ON o.portal_id = p.id ORDER BY o.created_at DESC"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map([], |row| {
        Ok(Opportunity {
            id: row.get(0)?,
            title: row.get(1)?,
            issuing_org: row.get(2)?,
            date: row.get(3)?,
            status: row.get(4)?,
            portal: row.get(5)?,
            url: row.get(6)?,
            portal_base_url: row.get(7)?,
            description: row.get(8)?,
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
    url: String,
    description: String,
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
        "INSERT INTO opportunities (id, portal_id, title, issuing_org, deadline_at, status, url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        params![id, portal_id, title, agency, due_date, "discovered", url, description]
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


// --- NEW UNIFIED DB QUERIES ---

#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct Attachment {
    pub id: String,
    pub opportunity_id: String,
    pub file_name: String,
    pub file_type: String,
    pub file_size: Option<i64>,
    pub extracted_text: Option<String>,
    pub created_at: Option<String>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct ProposalDraft {
    pub id: String,
    pub opportunity_id: String,
    pub title: String,
    pub content: String,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub opp_title: Option<String>,
    pub opp_portal: Option<String>,
    pub opp_org: Option<String>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct KnowledgeItem {
    pub id: String,
    pub title: String,
    pub content: String,
    pub item_type: String,
    pub tags: Option<String>,
    pub file_name: Option<String>,
    pub created_at: Option<String>,
}

// -- Opportunities --

pub fn delete_opportunity(app: &AppHandle, id: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    // Due to ON DELETE CASCADE, attachments and drafts should be deleted automatically if schema defines it,
    // but we can also explicitly delete just in case
    conn.execute("DELETE FROM opportunity_attachments WHERE opportunity_id = ?", params![&id]).ok();
    conn.execute("DELETE FROM proposal_drafts WHERE opportunity_id = ?", params![&id]).ok();
    conn.execute("DELETE FROM opportunities WHERE id = ?", params![id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn update_opportunity_status(app: &AppHandle, id: String, status: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "UPDATE opportunities SET status = ? WHERE id = ?",
        params![status, id]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn get_opportunity_detail(app: &AppHandle, id: String) -> Result<Option<Opportunity>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT o.id, o.title, o.issuing_org, o.deadline_at, o.status, p.name, o.url, p.base_url, o.description 
         FROM opportunities o JOIN portals p ON o.portal_id = p.id WHERE o.id = ?"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut rows = stmt.query(params![id]).map_err(|e| SentinelError::Database(e.to_string()))?;
    
    if let Some(row) = rows.next().map_err(|e| SentinelError::Database(e.to_string()))? {
        Ok(Some(Opportunity {
            id: row.get(0).map_err(|e| SentinelError::Database(e.to_string()))?,
            title: row.get(1).map_err(|e| SentinelError::Database(e.to_string()))?,
            issuing_org: row.get(2).map_err(|e| SentinelError::Database(e.to_string()))?,
            date: row.get(3).map_err(|e| SentinelError::Database(e.to_string()))?,
            status: row.get(4).map_err(|e| SentinelError::Database(e.to_string()))?,
            portal: row.get(5).map_err(|e| SentinelError::Database(e.to_string()))?,
            url: row.get(6).map_err(|e| SentinelError::Database(e.to_string()))?,
            portal_base_url: row.get(7).map_err(|e| SentinelError::Database(e.to_string()))?,
            description: row.get(8).map_err(|e| SentinelError::Database(e.to_string()))?,
        }))
    } else {
        Ok(None)
    }
}

// -- Attachments --

pub fn get_attachments(app: &AppHandle, opp_id: String) -> Result<Vec<Attachment>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT id, opportunity_id, file_name, file_type, file_size, extracted_text, created_at 
         FROM opportunity_attachments WHERE opportunity_id = ? ORDER BY created_at DESC"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map(params![opp_id], |row| {
        Ok(Attachment {
            id: row.get(0)?,
            opportunity_id: row.get(1)?,
            file_name: row.get(2)?,
            file_type: row.get(3)?,
            file_size: row.get(4)?,
            extracted_text: row.get(5)?,
            created_at: row.get(6)?,
        })
    }).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut result = Vec::new();
    for row in rows {
        if let Ok(a) = row { result.push(a); }
    }
    Ok(result)
}

pub fn save_attachment(
    app: &AppHandle, 
    id: String, 
    opp_id: String, 
    file_name: String, 
    file_type: String, 
    file_size: i64, 
    file_bytes: Vec<u8>
) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "INSERT INTO opportunity_attachments (id, opportunity_id, file_name, file_type, file_size, file_bytes) 
         VALUES (?, ?, ?, ?, ?, ?)",
        params![id, opp_id, file_name, file_type, file_size, file_bytes]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn delete_attachment(app: &AppHandle, id: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute("DELETE FROM opportunity_attachments WHERE id = ?", params![id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn update_attachment_text(app: &AppHandle, id: String, text: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "UPDATE opportunity_attachments SET extracted_text = ? WHERE id = ?",
        params![text, id]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn get_attachment_bytes(app: &AppHandle, id: String) -> Result<Option<Vec<u8>>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare("SELECT file_bytes FROM opportunity_attachments WHERE id = ?")
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    let mut rows = stmt.query(params![id]).map_err(|e| SentinelError::Database(e.to_string()))?;
    
    if let Some(row) = rows.next().map_err(|e| SentinelError::Database(e.to_string()))? {
        let bytes: Vec<u8> = row.get(0).map_err(|e| SentinelError::Database(e.to_string()))?;
        Ok(Some(bytes))
    } else {
        Ok(None)
    }
}

// -- Proposal Drafts --

pub fn get_proposal_drafts(app: &AppHandle) -> Result<Vec<ProposalDraft>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT d.id, d.opportunity_id, d.title, d.content, d.created_at, d.updated_at, 
                o.title, p.name, o.issuing_org 
         FROM proposal_drafts d 
         LEFT JOIN opportunities o ON d.opportunity_id = o.id 
         LEFT JOIN portals p ON o.portal_id = p.id 
         ORDER BY COALESCE(d.updated_at, d.created_at) DESC"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map([], |row| {
        Ok(ProposalDraft {
            id: row.get(0)?,
            opportunity_id: row.get(1)?,
            title: row.get(2)?,
            content: row.get(3)?,
            created_at: row.get(4)?,
            updated_at: row.get(5)?,
            opp_title: row.get(6)?,
            opp_portal: row.get(7)?,
            opp_org: row.get(8)?,
        })
    }).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut result = Vec::new();
    for row in rows {
        if let Ok(d) = row { result.push(d); }
    }
    Ok(result)
}

pub fn save_proposal_draft(app: &AppHandle, id: String, opp_id: String, title: String, content: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "INSERT INTO proposal_drafts (id, opportunity_id, title, content) VALUES (?, ?, ?, ?)",
        params![id, opp_id, title, content]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn update_proposal_draft(app: &AppHandle, id: String, title: String, content: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "UPDATE proposal_drafts SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        params![title, content, id]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn delete_proposal_draft(app: &AppHandle, id: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute("DELETE FROM proposal_drafts WHERE id = ?", params![id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

// -- Knowledge Base --

pub fn get_knowledge_base(app: &AppHandle) -> Result<Vec<KnowledgeItem>, SentinelError> {
    let conn = get_db_connection(app)?;
    let mut stmt = conn.prepare(
        "SELECT id, title, content, type, tags, file_name, created_at 
         FROM knowledge_base ORDER BY created_at DESC"
    ).map_err(|e| SentinelError::Database(e.to_string()))?;

    let rows = stmt.query_map([], |row| {
        Ok(KnowledgeItem {
            id: row.get(0)?,
            title: row.get(1)?,
            content: row.get(2)?,
            item_type: row.get(3)?,
            tags: row.get(4)?,
            file_name: row.get(5)?,
            created_at: row.get(6)?,
        })
    }).map_err(|e| SentinelError::Database(e.to_string()))?;

    let mut result = Vec::new();
    for row in rows {
        if let Ok(i) = row { result.push(i); }
    }
    Ok(result)
}

pub fn save_knowledge_item(
    app: &AppHandle, 
    id: String, 
    title: String, 
    content: String, 
    item_type: String, 
    tags: Option<String>, 
    file_name: Option<String>, 
    file_bytes: Option<Vec<u8>>
) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute(
        "INSERT INTO knowledge_base (id, title, content, type, tags, file_name, file_bytes) 
         VALUES (?, ?, ?, ?, ?, ?, ?)",
        params![id, title, content, item_type, tags, file_name, file_bytes]
    ).map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}

pub fn delete_knowledge_item(app: &AppHandle, id: String) -> Result<(), SentinelError> {
    let conn = get_db_connection(app)?;
    conn.execute("DELETE FROM knowledge_base WHERE id = ?", params![id])
        .map_err(|e| SentinelError::Database(e.to_string()))?;
    Ok(())
}
