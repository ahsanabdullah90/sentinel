use tauri::{AppHandle, Manager};
use crate::errors::SentinelError;
use crate::sidecar::{SidecarRegistry, execute_jsonrpc_method};
use tracing::info;

#[tauri::command]
pub async fn start_hunt_session(
    app: AppHandle,
    portal_id: String,
    config: String,
) -> Result<String, SentinelError> {
    let session_id = uuid::Uuid::new_v4().to_string();
    info!("Starting IPC hunt session {} for portal {}", session_id, portal_id);
    
    // Execute streaming JSON-RPC hunt in background
    let params = serde_json::json!({
        "portal_id": portal_id,
        "mock_config_json": config,
    });
    execute_jsonrpc_method(app, "hunter", "server.py", "hunt", params, &session_id).await?;
    
    Ok(session_id)
}

#[tauri::command]
pub async fn stop_hunt_session(
    app: AppHandle,
    session_id: String,
) -> Result<(), SentinelError> {
    info!("Stopping hunt session {}...", session_id);
    let registry = app.state::<SidecarRegistry>();
    
    let mut guard = registry.active_hunts.lock().unwrap();
    if let Some(cancel_tx) = guard.remove(&session_id) {
        // Trigger cancellation
        let _ = cancel_tx.send(());
        info!("Successfully triggered cancellation for session {}.", session_id);
    } else {
        info!("No active hunt session found for ID {}.", session_id);
    }
    
    Ok(())
}

#[tauri::command]
pub async fn detect_portal(
    app: AppHandle,
    url: String,
) -> Result<(), SentinelError> {
    info!("Detecting portal at URL: {}", url);
    let req_id = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({ "url": url });
    execute_jsonrpc_method(app, "hunter", "server.py", "detect", params, &req_id).await?;
    Ok(())
}

#[tauri::command]
pub async fn get_opportunities(
    _app: AppHandle,
    _portal_id: Option<String>,
    _status: Option<String>,
) -> Result<Vec<serde_json::Value>, SentinelError> {
    // Will be implemented properly when connecting to SQLite
    Ok(vec![])
}
