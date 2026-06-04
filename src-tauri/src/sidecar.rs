use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::{ShellExt, process::{CommandEvent, CommandChild}};
use tracing::{error, info, warn};
use tokio::sync::oneshot;

pub struct SidecarRegistry {
    pub processes: Mutex<HashMap<String, Arc<Mutex<Option<CommandChild>>>>>,
    pub active_hunts: Mutex<HashMap<String, oneshot::Sender<()>>>,
    pub responses: Mutex<HashMap<String, oneshot::Sender<serde_json::Value>>>,
}

impl SidecarRegistry {
    pub fn new() -> Self {
        Self {
            processes: Mutex::new(HashMap::new()),
            active_hunts: Mutex::new(HashMap::new()),
            responses: Mutex::new(HashMap::new()),
        }
    }
}

impl Default for SidecarRegistry {
    fn default() -> Self {
        Self::new()
    }
}

pub async fn spawn_python_sidecar(
    app: AppHandle,
    sidecar_name: &str,
) -> Result<Arc<Mutex<Option<CommandChild>>>, crate::errors::SentinelError> {
    let child_opt = {
        let registry = app.state::<SidecarRegistry>();
        let child = registry.processes.lock().unwrap_or_else(|p| p.into_inner()).get(sidecar_name).cloned();
        child
    };
    if let Some(child) = child_opt {
        return Ok(child);
    }

    let (mut rx, child) = match app.shell().sidecar(sidecar_name) {
        Ok(sidecar_cmd) => {
            info!("Spawning sidecar as compiled binary: {}", sidecar_name);
            sidecar_cmd.spawn().map_err(|e| crate::errors::SentinelError::Sidecar(e.to_string()))?
        }
        Err(err) => {
            // If the compiled sidecar binary is not available, this is a critical error in production.
            // We return an explicit error to avoid falling back to a system Python interpreter, which would break portability.
            error!("Compiled sidecar '{}' not found or failed to load: {}", sidecar_name, err);
            return Err(crate::errors::SentinelError::Sidecar(format!("Compiled sidecar '{}' missing", sidecar_name)));
        }
    };

    let child_arc = Arc::new(Mutex::new(Some(child)));
    
    {
        let registry = app.state::<SidecarRegistry>();
        registry.processes.lock().unwrap_or_else(|p| p.into_inner()).insert(sidecar_name.to_string(), child_arc.clone());
    }

    let (ready_tx, ready_rx) = oneshot::channel::<()>();
    let ready_tx_opt = Some(ready_tx);

    let sidecar_name_owned = sidecar_name.to_string();
    let app_clone = app.clone();
    
    tauri::async_runtime::spawn(async move {
        let mut ready_tx_opt = ready_tx_opt;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    for l in text.lines() {
                        if l.trim().is_empty() { continue; }
                        info!("[{} STDOUT] Raw line received: {}", sidecar_name_owned, l);
                        if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(l) {
                            if let Some(event_str) = parsed.get("event").and_then(|v| v.as_str()).map(|s| s.to_string()) {
                                if event_str == "ready" {
                                    if let Some(tx) = ready_tx_opt.take() {
                                        let _ = tx.send(());
                                    }
                                }

                                let tauri_event = format!("sentinel://{}/{}", sidecar_name_owned, event_str.replace('_', "-"));
                                info!("[{} STDOUT] Parsed event: {}, emitting to: {}", sidecar_name_owned, event_str, tauri_event);

                                
                                if event_str == "portal_detected" {
                                    if let Some(payload_str) = parsed.get("json_payload").and_then(|v| v.as_str()) {
                                        if let Ok(report) = serde_json::from_str::<serde_json::Value>(payload_str) {
                                            let url = report.get("url").and_then(|v| v.as_str()).unwrap_or_default().to_string();
                                            let mut search_selector = report.get("searchSelector").and_then(|v| v.as_str()).unwrap_or_default().to_string();
                                            if search_selector.is_empty() {
                                                if let Some(opts) = report.get("scrapingOptions").and_then(|v| v.as_array()) {
                                                    if let Some(first_opt) = opts.first() {
                                                        if let Some(desc) = first_opt.get("description").and_then(|v| v.as_str()) {
                                                            if desc.contains(": ") {
                                                                search_selector = desc.split(": ").nth(1).unwrap_or_default().to_string();
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            let config_json = serde_json::json!({ "searchSelector": search_selector }).to_string();
                                            if let Err(e) = crate::db::queries::update_portal_selector(
                                                &app_clone,
                                                url,
                                                config_json,
                                                "Browser (Playwright)".to_string(),
                                            ) {
                                                error!("Failed to auto-persist portal detection: {}", e);
                                            }
                                        }
                                    }
                                } else if event_str == "opportunity_found" {
                                    if let Some(payload_str) = parsed.get("json_payload").and_then(|v| v.as_str()) {
                                        if let Ok(opp) = serde_json::from_str::<serde_json::Value>(payload_str) {
                                            let opp_id = opp.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
                                            let portal_id = opp.get("portalId").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_else(|| "1".to_string());
                                            let title = opp.get("title").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                                            let agency = opp.get("agency").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_else(|| "Unknown Agency".to_string());
                                            let due_date = opp.get("dueDate").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                                            let url = opp.get("url").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                                            let description = opp.get("description").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                                            
                                            if let Err(e) = crate::db::queries::record_opportunity(&app_clone, opp_id, portal_id, title, agency, due_date, url, description) {
                                                error!("Failed to auto-persist opportunity: {}", e);
                                            }
                                        }
                                    }
                                } else if event_str == "opportunity_updated" {
                                    if let Some(payload_str) = parsed.get("json_payload").and_then(|v| v.as_str()) {
                                        if let Ok(opp) = serde_json::from_str::<serde_json::Value>(payload_str) {
                                            if let Some(id) = opp.get("id").and_then(|v| v.as_str()) {
                                                if let Some(description) = opp.get("description").and_then(|v| v.as_str()) {
                                                    if let Err(e) = crate::db::queries::update_opportunity_description(&app_clone, id.to_string(), description.to_string()) {
                                                        error!("Failed to update opportunity description: {}", e);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                } else if event_str == "attachment_downloaded" {
                                    if let Some(payload_str) = parsed.get("json_payload").and_then(|v| v.as_str()) {
                                        if let Ok(payload) = serde_json::from_str::<serde_json::Value>(payload_str) {
                                            if let (Some(opp_id), Some(filename), Some(temp_path)) = (
                                                payload.get("opportunityId").and_then(|v| v.as_str()),
                                                payload.get("fileName").and_then(|v| v.as_str()),
                                                payload.get("filePath").and_then(|v| v.as_str())
                                            ) {
                                                use tauri::Manager;
                                                if let Ok(mut attach_dir) = app_clone.path().app_config_dir() {
                                                    attach_dir.push("attachments");
                                                    let _ = std::fs::create_dir_all(&attach_dir);
                                                    
                                                    let mut target_path = attach_dir.clone();
                                                    target_path.push(filename);
                                                    
                                                    if let Ok(bytes) = std::fs::read(temp_path) {
                                                        let size = bytes.len() as i64;
                                                        let ext = std::path::Path::new(filename)
                                                            .extension()
                                                            .and_then(|e| e.to_str())
                                                            .unwrap_or("unknown")
                                                            .to_string();
                                                        
                                                        // Copy to persistent storage
                                                        let _ = std::fs::write(&target_path, &bytes);
                                                        
                                                        // Store in DB
                                                        let id = uuid::Uuid::new_v4().to_string();
                                                        if let Err(e) = crate::db::queries::save_attachment(
                                                            &app_clone, id, opp_id.to_string(), filename.to_string(), ext, size, bytes
                                                        ) {
                                                            error!("Failed to insert attachment into DB: {}", e);
                                                        }
                                                        
                                                        // Clean up temp file
                                                        let _ = std::fs::remove_file(temp_path);
                                                    } else {
                                                        error!("Failed to read attachment temp file: {}", temp_path);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
// Isolate payload parsing to avoid mutating `parsed`
let mut emit_payload = parsed.clone();
if let Some(payload_str) = parsed.get("json_payload").and_then(|v| v.as_str()) {
    if let Ok(inner_json) = serde_json::from_str::<serde_json::Value>(payload_str) {
        if let (Some(obj), Some(inner_obj)) = (emit_payload.as_object_mut(), inner_json.as_object()) {
            // Merge inner fields into the top‑level payload for the frontend
            for (k, v) in inner_obj.iter() {
                obj.insert(k.clone(), v.clone());
            }
        }
    }
}
let _ = app_clone.emit(&tauri_event, emit_payload);
                            } else if let Some(req_id) = parsed.get("req_id").and_then(|v| v.as_str()) {
                                let registry = app_clone.state::<SidecarRegistry>();
                                let mut guard = registry.responses.lock().unwrap_or_else(|p| p.into_inner());
                                if let Some(tx) = guard.remove(req_id) {
                                    let _ = tx.send(parsed.clone());
                                } else {
                                    let _ = app_clone.emit(&format!("sentinel://{}/rpc-response", sidecar_name_owned), parsed);
                                }
                            } else {
                                let _ = app_clone.emit(&format!("sentinel://{}/rpc-response", sidecar_name_owned), parsed);
                            }
                        } else {
                            warn!("[{} STDOUT/Non-JSON] {}", sidecar_name_owned, l);
                        }
                    }
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line);
                    warn!("[{} STDERR] {}", sidecar_name_owned, text.trim());
                }
                CommandEvent::Terminated(payload) => {
                    info!("Sidecar {} terminated: {:?}", sidecar_name_owned, payload);
                    let registry = app_clone.state::<SidecarRegistry>();
                    registry.processes.lock().unwrap_or_else(|p| p.into_inner()).remove(&sidecar_name_owned);
                    break;
                }
                CommandEvent::Error(err) => {
                    error!("Sidecar {} error: {}", sidecar_name_owned, err);
                    let registry = app_clone.state::<SidecarRegistry>();
                    registry.processes.lock().unwrap_or_else(|p| p.into_inner()).remove(&sidecar_name_owned);
                    break;
                }
                _ => {}
            }
        }
    });
    // Wait for the sidecar to signal that it is ready
    match tokio::time::timeout(std::time::Duration::from_secs(60), ready_rx).await {
        Ok(_) => info!("Sidecar {} is ready for IPC commands.", sidecar_name),
        Err(_) => warn!("Timed out waiting 60s for sidecar {} to signal ready. Proceeding anyway...", sidecar_name),
    }

    Ok(child_arc)
}

pub async fn execute_jsonrpc_method(
    app: AppHandle,
    sidecar_name: &str,
    method: &str,
    params: serde_json::Value,
    req_id: &str,
) -> Result<(), crate::errors::SentinelError> {
    let child_arc = spawn_python_sidecar(app.clone(), sidecar_name).await?;
    
    let req = serde_json::json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": req_id,
    });
    
    let req_str = format!("{}\n", req.to_string());
    
    let mut guard = child_arc.lock().unwrap_or_else(|p| p.into_inner());
    if let Some(ref mut child) = *guard {
        child.write(req_str.as_bytes()).map_err(|e| crate::errors::SentinelError::Sidecar(e.to_string()))?;
    } else {
        return Err(crate::errors::SentinelError::Sidecar("Process has been terminated".to_string()));
    }
    
    Ok(())
}

pub async fn execute_jsonrpc_method_await(
    app: AppHandle,
    sidecar_name: &str,
    method: &str,
    params: serde_json::Value,
    req_id: &str,
) -> Result<serde_json::Value, crate::errors::SentinelError> {
    let child_arc = spawn_python_sidecar(app.clone(), sidecar_name).await?;
    
    let (tx, rx) = oneshot::channel();
    {
        let registry = app.state::<SidecarRegistry>();
        registry.responses.lock().unwrap_or_else(|p| p.into_inner()).insert(req_id.to_string(), tx);
    }
    
    let req = serde_json::json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": req_id,
    });
    
    let req_str = format!("{}\n", req.to_string());
    
    {
        let mut guard = child_arc.lock().unwrap_or_else(|p| p.into_inner());
        if let Some(ref mut child) = *guard {
            child.write(req_str.as_bytes()).map_err(|e| crate::errors::SentinelError::Sidecar(e.to_string()))?;
        } else {
            return Err(crate::errors::SentinelError::Sidecar("Process has been terminated".to_string()));
        }
    }
    
    let response = tokio::time::timeout(std::time::Duration::from_secs(60), rx)
        .await
        .map_err(|_| crate::errors::SentinelError::Sidecar("JSON-RPC request timed out".to_string()))?
        .map_err(|_| crate::errors::SentinelError::Sidecar("JSON-RPC response channel closed".to_string()))?;
        
    Ok(response)
}
