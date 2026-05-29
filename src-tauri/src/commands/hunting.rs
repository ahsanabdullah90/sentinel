use tauri::{AppHandle, Manager};
use crate::errors::SentinelError;
use crate::sidecar::{execute_grpc_hunt, execute_grpc_detect, HunterRegistry};
use tracing::info;

#[tauri::command]
pub async fn start_hunt_session(
    app: AppHandle,
    portal_id: String,
    config: String,
) -> Result<String, SentinelError> {
    let session_id = uuid::Uuid::new_v4().to_string();
    info!("Starting gRPC hunt session {} for portal {}", session_id, portal_id);
    
    // Execute streaming gRPC hunt in background
    execute_grpc_hunt(app, portal_id, config, session_id.clone()).await?;
    
    Ok(session_id)
}

#[tauri::command]
pub async fn stop_hunt_session(
    app: AppHandle,
    session_id: String,
) -> Result<(), SentinelError> {
    info!("Stopping hunt session {}...", session_id);
    let registry = app.state::<HunterRegistry>();
    
    let mut guard = registry.active_hunts.lock().unwrap();
    if let Some(cancel_tx) = guard.remove(&session_id) {
        // Trigger cancellation. This drops the gRPC connection, which Python server detects
        let _ = cancel_tx.send(());
        info!("Successfully triggered gRPC cancellation for session {}.", session_id);
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
    execute_grpc_detect(app, url).await?;
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
