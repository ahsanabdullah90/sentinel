use serde::Deserialize;
use tauri::{AppHandle, Emitter};
use tauri_plugin_shell::{ShellExt, process::CommandEvent};
use tracing::{error, info, warn};

#[derive(Deserialize, Debug)]
struct SidecarEvent {
    event: String,
    #[serde(flatten)]
    payload: serde_json::Value,
}

fn find_sidecar_script(sidecar_name: &str) -> Option<String> {
    // 1. Try starting from current working directory
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

    // 2. Try starting from executable directory
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(mut dir) = exe_path.parent() {
            loop {
                let test_path = dir.join("sidecars").join(sidecar_name).join("dist/index.js");
                if test_path.exists() {
                    return Some(test_path.to_string_lossy().into_owned());
                }
                if let Some(parent) = dir.parent() {
                    dir = parent;
                } else {
                    break;
                }
            }
        }
    }

    None
}

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
                        // Parse JSON lines from stdout
                        for l in line_str.lines() {
                            if l.trim().is_empty() { continue; }
                            
                            match serde_json::from_str::<SidecarEvent>(l) {
                                Ok(se) => {
                                    // Emit to frontend
                                    let event_name = format!("sentinel://{}/{}", sidecar_name_owned, se.event.replace('_', "-"));
                                    
                                    // If payload contains "data", emit that nested value directly.
                                    // Otherwise, emit the flattened payload.
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
                                    // Not JSON, just info log
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
                            // If signal is None and code is None, or signal is present, check if it's normal clean-up
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
                    // Emit crash event to frontend
                    let _ = app_clone.emit("sentinel://system/error", serde_json::json!({
                        "code": "SIDECAR_CRASHED",
                        "message": format!("Sidecar {} crashed permanently.", sidecar_name_owned)
                    }));
                    break;
                }
                
                // Exponential backoff
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
