pub mod commands;
pub mod db;
pub mod errors;
pub mod sidecar;
pub mod ipc;
pub mod telemetry;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn check_ollama_status() -> String {
    use std::net::TcpStream;
    use std::time::Duration;
    
    // Try to connect to Ollama default port
    match TcpStream::connect_timeout(&"127.0.0.1:11434".parse().unwrap(), Duration::from_secs(1)) {
        Ok(_) => "Online".to_string(),
        Err(_) => "Offline".to_string(),
    }
}

#[tauri::command]
async fn generate_chat_response(prompt: String, model: String, url: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let res = client.post(&format!("{}/api/generate", url))
        .json(&serde_json::json!({
            "model": model,
            "prompt": prompt,
            "stream": false
        }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let json: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
    
    if let Some(response) = json.get("response") {
        if let Some(text) = response.as_str() {
            return Ok(text.to_string());
        }
    }
    
    Err("Failed to get response from Ollama".to_string())
}

#[tauri::command]
async fn analyze_gaps(_rfp_id: String) -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![])
}

#[tauri::command]
async fn bootstrap_system() -> Result<String, String> {
    use std::process::Command;
    use std::path::PathBuf;

    let mut script_path = PathBuf::from("scripts/control-unit.sh");
    if !script_path.exists() {
        script_path = PathBuf::from("../scripts/control-unit.sh");
    }

    let output = Command::new("bash")
        .arg(script_path)
        .output()
        .map_err(|e| e.to_string())?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    telemetry::init_telemetry();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_sql::Builder::default().add_migrations("sqlite:sentinel.db", db::init()).build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            check_ollama_status,
            generate_chat_response,
            run_gap_analysis,
            commands::settings::save_settings,
            commands::settings::get_cloud_response,
            commands::credentials::save_portal_credential,
            bootstrap_system,
            commands::hunting::start_hunt_session,
            commands::hunting::stop_hunt_session,
            commands::hunting::get_opportunities,
            commands::hunting::detect_portal,
            commands::drafting::ingest_document,
            commands::drafting::generate_draft,
            commands::knowledge_base::add_to_knowledge_base,
            commands::knowledge_base::search_knowledge_base,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
