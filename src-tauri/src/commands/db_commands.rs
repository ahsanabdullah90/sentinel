use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::db::queries::{
    self, Portal, Opportunity, Attachment, ProposalDraft, KnowledgeItem
};

#[tauri::command]
pub async fn get_portals(app: AppHandle) -> Result<Vec<Portal>, SentinelError> {
    queries::fetch_portals(&app)
}

#[tauri::command]
pub async fn get_opportunities_list(app: AppHandle) -> Result<Vec<Opportunity>, SentinelError> {
    queries::fetch_opportunities(&app)
}

#[tauri::command]
pub async fn save_portal(app: AppHandle, portal: Portal, is_edit: bool) -> Result<(), SentinelError> {
    if is_edit {
        queries::update_portal(&app, portal)
    } else {
        queries::insert_portal(&app, portal)
    }
}

#[tauri::command]
pub async fn delete_portal(app: AppHandle, id: String) -> Result<(), SentinelError> {
    queries::delete_portal(&app, id)
}

#[tauri::command]
pub async fn toggle_portal_status(app: AppHandle, id: String, current_status: String) -> Result<(), SentinelError> {
    queries::toggle_portal_status(&app, id, current_status)
}

#[tauri::command]
pub async fn finish_active_hunt(
    app: AppHandle,
    portal_id: String,
    duration_ms: i64,
    opp_count: i32,
    rendering_mode: String,
) -> Result<(), SentinelError> {
    let local_date = chrono::Local::now() + chrono::Duration::hours(5); // Map GMT+5
    let timestamp = format!("{} (GMT+5)", local_date.format("%Y-%m-%d %H:%M:%S"));
    queries::finish_portal_run(&app, portal_id, timestamp, duration_ms, opp_count, rendering_mode, "Low Risk".to_string())
}

#[tauri::command]
pub async fn get_scheduler_timestamp(app: AppHandle) -> Result<Option<String>, SentinelError> {
    queries::get_kv(&app, "sentinel_last_auto_hunt_timestamp".to_string())
}

#[tauri::command]
pub async fn set_scheduler_timestamp(app: AppHandle, timestamp: String) -> Result<(), SentinelError> {
    queries::set_kv(&app, "sentinel_last_auto_hunt_timestamp".to_string(), timestamp)
}

// --- NEW UNIFIED DB QUERIES ---

#[tauri::command]
pub async fn delete_opportunity(app: AppHandle, id: String) -> Result<(), SentinelError> {
    crate::db::queries::delete_opportunity(&app, id)
}

#[tauri::command]
pub async fn update_opportunity_status(app: AppHandle, id: String, status: String) -> Result<(), SentinelError> {
    crate::db::queries::update_opportunity_status(&app, id, status)
}

#[tauri::command]
pub async fn get_opportunity_detail(app: AppHandle, id: String) -> Result<Option<Opportunity>, SentinelError> {
    crate::db::queries::get_opportunity_detail(&app, id)
}

#[tauri::command]
pub async fn get_attachments(app: AppHandle, opp_id: String) -> Result<Vec<Attachment>, SentinelError> {
    crate::db::queries::get_attachments(&app, opp_id)
}

#[tauri::command]
pub async fn save_attachment(
    app: AppHandle,
    id: String,
    opp_id: String,
    file_name: String,
    file_type: String,
    file_size: i64,
    file_bytes: Vec<u8>
) -> Result<(), SentinelError> {
    crate::db::queries::save_attachment(&app, id, opp_id, file_name, file_type, file_size, file_bytes)
}

#[tauri::command]
pub async fn delete_attachment(app: AppHandle, id: String) -> Result<(), SentinelError> {
    crate::db::queries::delete_attachment(&app, id)
}

#[tauri::command]
pub async fn update_attachment_text(app: AppHandle, id: String, text: String) -> Result<(), SentinelError> {
    crate::db::queries::update_attachment_text(&app, id, text)
}

#[tauri::command]
pub async fn get_attachment_bytes(app: AppHandle, id: String) -> Result<Option<Vec<u8>>, SentinelError> {
    crate::db::queries::get_attachment_bytes(&app, id)
}

#[tauri::command]
pub async fn get_proposal_drafts(app: AppHandle) -> Result<Vec<ProposalDraft>, SentinelError> {
    crate::db::queries::get_proposal_drafts(&app)
}

#[tauri::command]
pub async fn save_proposal_draft(
    app: AppHandle,
    id: String,
    opp_id: String,
    title: String,
    content: String
) -> Result<(), SentinelError> {
    crate::db::queries::save_proposal_draft(&app, id, opp_id, title, content)
}

#[tauri::command]
pub async fn update_proposal_draft(
    app: AppHandle,
    id: String,
    title: String,
    content: String
) -> Result<(), SentinelError> {
    crate::db::queries::update_proposal_draft(&app, id, title, content)
}

#[tauri::command]
pub async fn delete_proposal_draft(app: AppHandle, id: String) -> Result<(), SentinelError> {
    crate::db::queries::delete_proposal_draft(&app, id)
}

#[tauri::command]
pub async fn get_knowledge_base(app: AppHandle) -> Result<Vec<KnowledgeItem>, SentinelError> {
    crate::db::queries::get_knowledge_base(&app)
}

#[tauri::command]
pub async fn save_knowledge_item(
    app: AppHandle,
    id: String,
    title: String,
    content: String,
    item_type: String,
    tags: Option<String>,
    file_name: Option<String>,
    file_bytes: Option<Vec<u8>>
) -> Result<(), SentinelError> {
    crate::db::queries::save_knowledge_item(&app, id, title, content, item_type, tags, file_name, file_bytes)
}

#[tauri::command]
pub async fn delete_knowledge_item(app: AppHandle, id: String) -> Result<(), SentinelError> {
    crate::db::queries::delete_knowledge_item(&app, id)
}
