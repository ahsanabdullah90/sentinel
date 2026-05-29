use std::collections::HashMap;
use std::sync::Mutex;
use serde::Deserialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::{ShellExt, process::CommandEvent};
use tracing::{error, info, warn};
use tokio::sync::oneshot;

pub mod proto {
    pub mod hunter {
        tonic::include_proto!("hunter");
    }
    pub mod health {
        tonic::include_proto!("grpc.health.v1");
    }
}

use proto::hunter::hunter_service_client::HunterServiceClient;
use proto::hunter::{HuntRequest, DetectRequest};

// Thread-safe registry for sidecar subprocesses and active streams
pub struct HunterRegistry {
    pub server_child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
    pub active_hunts: Mutex<HashMap<String, oneshot::Sender<()>>>,
}

impl HunterRegistry {
    pub fn new() -> Self {
        Self {
            server_child: Mutex::new(None),
            active_hunts: Mutex::new(HashMap::new()),
        }
    }
}

impl Default for HunterRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Deserialize, Debug)]
struct SidecarEvent {
    event: String,
    #[serde(flatten)]
    payload: serde_json::Value,
}

fn find_sidecar_script(sidecar_name: &str) -> Option<String> {
    if let Ok(mut dir) = std::env::current_dir() {
        loop {
            let test_path = dir.join("sidecars").join(sidecar_name).join("dist/index.js");
            if test_path.exists() {
                return Some(test_path.to_string_lossy().into_owned());
            }
            if let Some(parent) = dir.parent() {
                dir = parent.to_path_buf();
            } else {
                break;
            }
        }
    }
    None
}

// Spawns old-style Node/CLI sidecars (e.g. RAG sidecar)
pub async fn spawn_sidecar(app: AppHandle, sidecar_name: &str, args: Vec<String>) -> Result<(), crate::errors::SentinelError> {
    let app_clone = app.clone();
    let sidecar_name_owned = sidecar_name.to_string();
    
    tauri::async_runtime::spawn(async move {
        let mut retries = 0;
        let max_retries = 3;

        loop {
            info!("Spawning sidecar: {}", sidecar_name_owned);
            
            let script_path = find_sidecar_script(&sidecar_name_owned)
                .unwrap_or_else(|| format!("sidecars/{}/dist/index.js", sidecar_name_owned));
                
            info!("Resolved sidecar script path to: {}", script_path);
            
            let cmd = app_clone.shell().command("node")
                .args(vec![script_path])
                .args(args.clone());

            let (mut rx, _child) = match cmd.spawn() {
                Ok(child) => child,
                Err(e) => {
                    error!("Failed to spawn sidecar {}: {}", sidecar_name_owned, e);
                    break;
                }
            };

            let mut crashed = false;

            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line) => {
                        let line_str = String::from_utf8_lossy(&line);
                        for l in line_str.lines() {
                            if l.trim().is_empty() { continue; }
                            
                            match serde_json::from_str::<SidecarEvent>(l) {
                                Ok(se) => {
                                    let event_name = format!("sentinel://{}/{}", sidecar_name_owned, se.event.replace('_', "-"));
                                    let final_payload = if let Some(data_val) = se.payload.get("data") {
                                        data_val.clone()
                                    } else {
                                        se.payload
                                    };

                                    if let Err(e) = app_clone.emit(&event_name, final_payload) {
                                        error!("Failed to emit event {}: {}", event_name, e);
                                    }
                                }
                                Err(_) => {
                                    info!("[{}] {}", sidecar_name_owned, l);
                                }
                            }
                        }
                    }
                    CommandEvent::Stderr(line) => {
                        let line_str = String::from_utf8_lossy(&line);
                        warn!("[{}] STDERR: {}", sidecar_name_owned, line_str);
                    }
                    CommandEvent::Terminated(payload) => {
                        info!("Sidecar {} terminated with {:?}", sidecar_name_owned, payload);
                        if let Some(code) = payload.code {
                            if code != 0 {
                                error!("Sidecar {} exited with error code: {}", sidecar_name_owned, code);
                                crashed = true;
                            }
                        } else {
                            error!("Sidecar {} terminated without exit code (possibly signal)", sidecar_name_owned);
                            crashed = true;
                        }
                        break;
                    }
                    CommandEvent::Error(err) => {
                        error!("Sidecar {} IO error: {}", sidecar_name_owned, err);
                        crashed = true;
                        break;
                    }
                    _ => {}
                }
            }

            if crashed {
                retries += 1;
                if retries >= max_retries {
                    error!("Sidecar {} exceeded max retries, giving up.", sidecar_name_owned);
                    let _ = app_clone.emit("sentinel://system/error", serde_json::json!({
                        "code": "SIDECAR_CRASHED",
                        "message": format!("Sidecar {} crashed permanently.", sidecar_name_owned)
                    }));
                    break;
                }
                
                let delay = std::time::Duration::from_secs(2u64.pow(retries));
                warn!("Restarting sidecar {} in {} seconds (retry {}/{})", sidecar_name_owned, delay.as_secs(), retries, max_retries);
                tokio::time::sleep(delay).await;
            } else {
                info!("Sidecar {} exited cleanly.", sidecar_name_owned);
                break;
            }
        }
    });

    Ok(())
}

// Heuristic Python script finder
fn find_python_script(app: &AppHandle, script_name: &str) -> Option<String> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let test_path = resource_dir.join("sidecars").join("hunter").join("src_py").join(script_name);
        if test_path.exists() {
            return Some(test_path.to_string_lossy().into_owned());
        }
        let alt_path = resource_dir.join("hunter").join("src_py").join(script_name);
        if alt_path.exists() {
            return Some(alt_path.to_string_lossy().into_owned());
        }
    }

    if let Ok(mut dir) = std::env::current_dir() {
        loop {
            let test_path = dir.join("sidecars").join("hunter").join("src_py").join(script_name);
            if test_path.exists() {
                return Some(test_path.to_string_lossy().into_owned());
            }
            if let Some(parent) = dir.parent() {
                dir = parent.to_path_buf();
            } else {
                break;
            }
        }
    }
    None
}

// Standard gRPC healthcheck using grpc.health.v1
async fn is_grpc_service_healthy(port: u16) -> bool {
    use proto::health::health_client::HealthClient;
    use proto::health::HealthCheckRequest;

    let channel_res = tonic::transport::Endpoint::from_shared(format!("http://127.0.0.1:{}", port))
        .map(|e| e.connect_timeout(std::time::Duration::from_millis(150)))
        .map(|e| e.connect_lazy());

    if let Ok(channel) = channel_res {
        let mut client = HealthClient::new(channel);
        let request = HealthCheckRequest { service: "".to_string() };
        if let Ok(response) = client.check(request).await {
            return response.into_inner().status == 1; // ServingStatus::Serving is 1
        }
    }
    false
}

fn find_available_port() -> Option<u16> {
    std::net::TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .ok()
}

// Dynamic server auto-launcher
pub async fn ensure_hunter_grpc_server_running(app: AppHandle) -> Result<(), crate::errors::SentinelError> {
    let current_port = crate::ipc::HUNTER_PORT.load(std::sync::atomic::Ordering::SeqCst);
    if is_grpc_service_healthy(current_port).await {
        info!("Hunter gRPC server is already running and listening on port {}.", current_port);
        return Ok(());
    }

    info!("Hunter gRPC server not running. Launching Python subprocess...");

    let port = find_available_port().unwrap_or(50051);
    crate::ipc::HUNTER_PORT.store(port, std::sync::atomic::Ordering::SeqCst);
    info!("Allocated dynamic port {} for Hunter gRPC service", port);

    let script_path = find_python_script(&app, "server.py")
        .unwrap_or_else(|| "sidecars/hunter/src_py/server.py".to_string());
        
    info!("Resolved Python server script path to: {}", script_path);

    let registry = app.state::<HunterRegistry>();

    // --- Failproof PYTHONPATH construction ---
    //
    // PROBLEM: std::env::current_dir() returns the Rust binary's cwd, which during
    // `tauri dev` is `src-tauri/` — NOT the workspace root. Building PYTHONPATH from
    // that gives wrong paths like `src-tauri/proto/` which does not exist.
    //
    // SOLUTION: Derive the workspace root from the *resolved* script_path, which
    // find_python_script() guarantees is an absolute path. The path structure is:
    //   <workspace>/sidecars/hunter/src_py/server.py
    // So the workspace root is exactly 4 parent levels up from server.py.
    // This is deterministic regardless of cwd, launch context, or OS.
    //
    // FALLBACK CHAIN (in order of preference):
    //   1. Workspace root derived from script path (primary — works in dev & CI)
    //   2. std::env::current_dir() parent traversal (secondary — handles edge cases)
    //   3. App resource_dir (tertiary — for packaged/bundled builds)
    let python_path: String = {
        // Strategy 1: Walk 4 parents up from server.py -> workspace root
        let workspace_from_script = std::path::Path::new(&script_path)
            .parent()               // .../src_py/
            .and_then(|p| p.parent()) // .../hunter/
            .and_then(|p| p.parent()) // .../sidecars/
            .and_then(|p| p.parent()) // .../sentinel/ (workspace root)
            .map(|p| p.to_path_buf());

        if let Some(workspace) = workspace_from_script {
            let proto = workspace.join("proto");
            if proto.exists() {
                let path = format!("{}:{}", workspace.display(), proto.display());
                info!("PYTHONPATH (from script path): {}", path);
                path
            } else {
                // proto dir not adjacent to workspace root (edge case: packaged build layout)
                let path = workspace.display().to_string();
                info!("PYTHONPATH (workspace only, no proto adjacent): {}", path);
                path
            }
        } else {
            // Strategy 2: Walk current_dir() tree upward searching for sidecars/hunter
            let fallback = std::env::current_dir().ok().and_then(|mut dir| {
                loop {
                    if dir.join("sidecars").join("hunter").exists() {
                        let proto = dir.join("proto");
                        let p = if proto.exists() {
                            format!("{}:{}", dir.display(), proto.display())
                        } else {
                            dir.display().to_string()
                        };
                        return Some(p);
                    }
                    match dir.parent() {
                        Some(parent) => dir = parent.to_path_buf(),
                        None => break,
                    }
                }
                None
            });

            // Strategy 3: App resource_dir (packaged bundles)
            let resource_fallback = app.path().resource_dir().ok().map(|d| d.display().to_string());

            let path = fallback
                .or(resource_fallback)
                .unwrap_or_default();
            if !path.is_empty() {
                info!("PYTHONPATH (fallback): {}", path);
            } else {
                warn!("Could not determine PYTHONPATH — imports may fail.");
            }
            path
        }
    };

    // Launch Python server with dynamic PORT and PYTHONPATH environment variables
    let mut cmd = app.shell().command("python3")
        .args(vec![script_path])
        .env("PORT", port.to_string());

    if !python_path.is_empty() {
        cmd = cmd.env("PYTHONPATH", python_path);
    }

    let (mut rx, child) = match cmd.spawn() {
        Ok(res) => res,
        Err(e) => {
            error!("Failed to spawn Python gRPC server subprocess: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "Failed to spawn Python gRPC server subprocess: {}", e
            )));
        }
    };

    // Store child process handle in registry
    {
        let mut guard = registry.server_child.lock().unwrap();
        *guard = Some(child);
    }

    // Monitor stdout/stderr logs in a background task
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    info!("[Hunter Python Server] {}", text.trim());
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line);
                    warn!("[Hunter Python Server STDERR] {}", text.trim());
                }
                CommandEvent::Terminated(payload) => {
                    info!("Hunter Python Server terminated: {:?}", payload);
                    break;
                }
                _ => {}
            }
        }
    });

    // Wait for the port to open and service to be healthy (up to 5 seconds)
    for i in 0..25 {
        tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        if is_grpc_service_healthy(port).await {
            info!("Hunter gRPC server launched and verified healthy on port {} after {}ms.", port, i * 200);
            return Ok(());
        }
    }

    error!("Hunter gRPC server failed to start listening on port {} within 5 seconds.", port);
    Err(crate::errors::SentinelError::Sidecar(
        "Hunter gRPC server failed to respond within timeout.".to_string()
    ))
}

// gRPC Hunt RPC Stream Mapping
pub async fn execute_grpc_hunt(
    app: AppHandle,
    portal_id: String,
    config_json: String,
    session_id: String,
) -> Result<(), crate::errors::SentinelError> {
    // 1. Ensure server is active
    ensure_hunter_grpc_server_running(app.clone()).await?;

    // 2. Setup Tonic connection with timeouts
    let hunter_port = crate::ipc::HUNTER_PORT.load(std::sync::atomic::Ordering::SeqCst);
    let endpoint = match tonic::transport::Endpoint::from_shared(format!("http://127.0.0.1:{}", hunter_port)) {
        Ok(ep) => ep
            .connect_timeout(std::time::Duration::from_secs(5))
            .timeout(std::time::Duration::from_secs(120)), // Maximum 2 minutes for the entire hunt lifecycle
        Err(e) => {
            error!("Failed to construct Hunter gRPC endpoint: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "Failed to construct Hunter gRPC endpoint: {}", e
            )));
        }
    };

    let channel = match endpoint.connect().await {
        Ok(ch) => ch,
        Err(e) => {
            error!("Failed to connect to Hunter gRPC service: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "Failed to connect to Hunter gRPC service: {}", e
            )));
        }
    };

    let mut client = HunterServiceClient::new(channel);

    // 3. Create active cancellation channel
    let (cancel_tx, cancel_rx) = oneshot::channel::<()>();
    let registry = app.state::<HunterRegistry>();
    {
        let mut guard = registry.active_hunts.lock().unwrap();
        guard.insert(session_id.clone(), cancel_tx);
    }

    // 4. Request the Hunt stream
    let request = crate::ipc::get_api_request(HuntRequest {
        portal_id: portal_id.clone(),
        mock_config_json: config_json,
    });

    let mut stream = match client.hunt(request).await {
        Ok(response) => response.into_inner(),
        Err(e) => {
            error!("gRPC Hunt call failed: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "gRPC Hunt call failed: {}", e
            )));
        }
    };

    let app_clone = app.clone();
    let session_id_clone = session_id.clone();

    // 5. Process the stream in a background task
    tauri::async_runtime::spawn(async move {
        tokio::select! {
            _ = cancel_rx => {
                info!("Hunt session {} was cancelled by user.", session_id_clone);
            }
            _res = async {
                loop {
                    match stream.message().await {
                        Ok(Some(message)) => {
                            let event_name = format!("sentinel://hunter/{}", message.event.replace('_', "-"));
                            
                            let payload_value = if message.payload_type == 0 { // PayloadType::Json
                                serde_json::from_str::<serde_json::Value>(&message.json_payload)
                                    .unwrap_or_else(|_| serde_json::Value::String(message.json_payload.clone()))
                            } else {
                                serde_json::Value::String(message.json_payload.clone())
                            };
                            
                            info!("Received from gRPC stream: {} -> {}", event_name, payload_value);

                            // Auto-persist to SQLite on Rust side
                            if message.event == "opportunity_found" {
                                if let Ok(opp) = serde_json::from_str::<serde_json::Value>(&message.json_payload) {
                            let opp_id = opp.get("id").and_then(|v| v.as_str()).map(|s| s.to_string())
                                .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
                            let portal_id = opp.get("portalId").and_then(|v| v.as_str()).map(|s| s.to_string())
                                .unwrap_or_else(|| "1".to_string());
                            let title = opp.get("title").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                            let agency = opp.get("agency").and_then(|v| v.as_str()).map(|s| s.to_string())
                                .unwrap_or_else(|| "Unknown Agency".to_string());
                            let due_date = opp.get("dueDate").and_then(|v| v.as_str()).map(|s| s.to_string())
                                .unwrap_or_else(|| "2026-06-30".to_string());
                            let url = opp.get("url").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                            let description = opp.get("description").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
                            
                            if let Err(e) = crate::db::queries::record_opportunity(
                                &app_clone,
                                opp_id,
                                portal_id,
                                title,
                                agency,
                                due_date,
                                url,
                                description,
                            ) {
                                error!("Failed to auto-persist opportunity to SQLite in Rust: {}", e);
                            }
                        }
                    }

                            if let Err(e) = app_clone.emit(&event_name, payload_value) {
                                error!("Failed to emit hunt event {}: {}", event_name, e);
                            }
                        }
                        Ok(None) => {
                            info!("Hunt stream ended naturally for session {}", session_id_clone);
                            break;
                        }
                        Err(e) => {
                            error!("Hunt stream error for session {}: {:?}", session_id_clone, e);
                            let _ = app_clone.emit("sentinel://hunter/error", serde_json::json!({
                                "message": format!("gRPC Stream Error: {}", e)
                            }));
                            break;
                        }
                    }
                }
            } => {}
        }

        // Clean up registry entry when done
        let registry = app_clone.state::<HunterRegistry>();
        let mut guard = registry.active_hunts.lock().unwrap();
        guard.remove(&session_id_clone);
    });

    Ok(())
}

// gRPC Detect RPC Stream Mapping
pub async fn execute_grpc_detect(
    app: AppHandle,
    url: String,
) -> Result<(), crate::errors::SentinelError> {
    ensure_hunter_grpc_server_running(app.clone()).await?;

    let hunter_port = crate::ipc::HUNTER_PORT.load(std::sync::atomic::Ordering::SeqCst);
    let endpoint = match tonic::transport::Endpoint::from_shared(format!("http://127.0.0.1:{}", hunter_port)) {
        Ok(ep) => ep
            .connect_timeout(std::time::Duration::from_secs(5))
            .timeout(std::time::Duration::from_secs(60)), // Maximum 60 seconds for portal detection
        Err(e) => {
            error!("Failed to construct Hunter gRPC endpoint for detect: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "Failed to construct Hunter gRPC endpoint: {}", e
            )));
        }
    };

    let channel = match endpoint.connect().await {
        Ok(ch) => ch,
        Err(e) => {
            error!("Failed to connect to Hunter gRPC service for detect: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "Failed to connect to Hunter gRPC service: {}", e
            )));
        }
    };

    let mut client = HunterServiceClient::new(channel);

    let request = crate::ipc::get_api_request(DetectRequest { url });
    let mut stream = match client.detect(request).await {
        Ok(response) => response.into_inner(),
        Err(e) => {
            error!("gRPC Detect call failed: {}", e);
            return Err(crate::errors::SentinelError::Sidecar(format!(
                "gRPC Detect call failed: {}", e
            )));
        }
    };

    let app_clone = app.clone();

    tauri::async_runtime::spawn(async move {
        while let Some(message) = stream.message().await.ok().flatten() {
            let event_name = format!("sentinel://hunter/{}", message.event.replace('_', "-"));
            
            // Auto-persist detection to SQLite
            if message.event == "portal_detected" {
                if let Ok(report) = serde_json::from_str::<serde_json::Value>(&message.json_payload) {
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
                        error!("Failed to auto-persist portal detection to SQLite in Rust: {}", e);
                    }
                }
            }

            if let Ok(parsed_payload) = serde_json::from_str::<serde_json::Value>(&message.json_payload) {
                if let Err(e) = app_clone.emit(&event_name, parsed_payload) {
                    error!("Failed to emit detect event {}: {}", event_name, e);
                }
            } else {
                if let Err(e) = app_clone.emit(&event_name, message.json_payload.clone()) {
                    error!("Failed to emit raw detect event {}: {}", event_name, e);
                }
            }
        }
        info!("gRPC Detect stream completed.");
    });

    Ok(())
}
