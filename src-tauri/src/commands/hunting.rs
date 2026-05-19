use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::sidecar::spawn_sidecar;

#[tauri::command]
pub async fn start_hunt_session(app: AppHandle, portal_id: String, config: String) -> Result<String, SentinelError> {
    let session_id = uuid::Uuid::new_v4().to_string();
    
    // Spawn sidecar with args
    spawn_sidecar(app, "hunter", vec![
        "hunt".to_string(), 
        "--portal".to_string(), portal_id,
        "--session".to_string(), session_id.clone(),
        "--config".to_string(), config
    ]).await?;
    
    Ok(session_id)
}

#[tauri::command]
pub async fn stop_hunt_session(_app: AppHandle, _session_id: String) -> Result<(), SentinelError> {
    // Sprint 2: Proper process management to send SIGTERM to specific session
    Ok(())
}

#[tauri::command]
pub async fn detect_portal(app: AppHandle, url: String) -> Result<(), SentinelError> {
    spawn_sidecar(app, "hunter", vec![
        "detect".to_string(),
        "--url".to_string(), url
    ]).await?;
    Ok(())
}

#[tauri::command]
pub async fn get_opportunities(_app: AppHandle, _portal_id: Option<String>, _status: Option<String>) -> Result<Vec<serde_json::Value>, SentinelError> {
    // Will be implemented properly when connecting to SQLite
    Ok(vec![])
}
