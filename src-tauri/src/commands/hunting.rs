use tauri::{AppHandle, Manager};
use crate::errors::SentinelError;
use crate::sidecar::{SidecarRegistry, execute_jsonrpc_method};
use crate::db::queries;
use tracing::info;
use tokio::sync::oneshot;

#[tauri::command]
pub async fn start_hunt_session(
    app: AppHandle,
    portal_id: String,
    config: String,
) -> Result<String, SentinelError> {
    let session_id = uuid::Uuid::new_v4().to_string();
    info!("Starting IPC hunt session {} for portal {}", session_id, portal_id);
    
    let (tx, rx) = oneshot::channel();
    let registry = app.state::<SidecarRegistry>();
    registry.active_hunts.lock().unwrap().insert(session_id.clone(), tx);

    let session_id_clone = session_id.clone();
    // Spawn a cancellation monitor that will kill the hunter sidecar process if a stop request arrives
    let app_handle = app.clone();
    tokio::spawn(async move {
        // Wait for the cancellation signal
        let _ = rx.await;
        // Retrieve the hunter sidecar child process and terminate it
        if let Some(child_arc) = app_handle.state::<SidecarRegistry>().processes.lock().unwrap().get("hunter") {
            if let Ok(mut guard) = child_arc.lock() {
                if let Some(child) = guard.take() {
                    let _ = child.kill();
                    info!("Hunt session {} cancelled: hunter sidecar process terminated.", session_id_clone);
                }
            }
        }
    });

    // Execute streaming JSON-RPC hunt in background
    let params = serde_json::json!({
        "portal_id": portal_id,
        "mock_config_json": config,
    });
    execute_jsonrpc_method(app, "hunter", "hunt", params, &session_id).await?;
    
    Ok(session_id)
}

#[tauri::command]
pub async fn stop_hunt_session(
    app: AppHandle,
    session_id: String,
) -> Result<(), SentinelError> {
    info!("Stopping hunt session {}...", session_id);
    let registry = app.state::<SidecarRegistry>();
    
    let mut guard = registry.active_hunts.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
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
    execute_jsonrpc_method(app, "hunter", "detect", params, &req_id).await?;
    Ok(())
}

#[tauri::command]
pub async fn get_opportunities(
    app: AppHandle,
    _portal_id: Option<String>,
    _status: Option<String>,
) -> Result<Vec<serde_json::Value>, SentinelError> {
    // Retrieve all opportunities from the SQLite database
    let opportunities = queries::fetch_opportunities(&app)?;
    // Convert each Opportunity struct into a serde_json::Value for Tauri front‑end compatibility
    let json_vals: Vec<serde_json::Value> = opportunities
        .into_iter()
        .map(|opp| serde_json::to_value(opp).unwrap_or_else(|_| serde_json::json!({})))
        .collect();
    Ok(json_vals)
}
