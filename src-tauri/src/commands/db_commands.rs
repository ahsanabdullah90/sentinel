use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::db::queries::{self, Portal, Opportunity};

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
