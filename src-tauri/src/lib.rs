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
async fn check_ollama_status(url: String) -> String {
    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(1))
        .build() {
            Ok(c) => c,
            Err(_) => return "Offline".to_string(),
        };

    match client.get(&format!("{}/api/tags", url)).send().await {
        Ok(res) if res.status().is_success() => "Online".to_string(),
        _ => "Offline".to_string(),
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
async fn generate_vision_description(
    image_bytes: Vec<u8>,
    model: String,
    url: String,
) -> Result<String, String> {
    use base64::{Engine as _, engine::general_purpose};

    let base64_image = general_purpose::STANDARD.encode(image_bytes);
    
    let client = reqwest::Client::new();
    let prompt = "Analyze this technical diagram. Provide a detailed structured description including: 1. Core components/nodes, 2. The connections, arrows, or relationships between them, 3. The directional sequence or flow of data.";

    let res = client.post(&format!("{}/api/generate", url))
        .json(&serde_json::json!({
            "model": model,
            "prompt": prompt,
            "images": vec![base64_image],
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
    
    Err("Failed to get visual description from local Ollama model".to_string())
}

#[tauri::command]
async fn extract_pdf_text_from_bytes(bytes: Vec<u8>) -> Result<String, String> {
    use std::process::Command;
    use std::io::Write;
    use tempfile::NamedTempFile;

    // Create an OS-managed temporary file that gets auto-deleted when dropped
    let mut temp_file = NamedTempFile::new().map_err(|e| e.to_string())?;
    temp_file.write_all(&bytes).map_err(|e| e.to_string())?;
    
    let temp_path = temp_file.path();

    // Extract text using pdftotext
    let output = Command::new("pdftotext")
        .arg(temp_path)
        .arg("-")
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("pdftotext failed: {}", stderr));
    }

    let text = String::from_utf8_lossy(&output.stdout).into_owned();
    Ok(text)
}

#[tauri::command]
async fn get_ollama_models(url: String) -> Result<Vec<String>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .map_err(|e| e.to_string())?;

    let res = client.get(&format!("{}/api/tags", url))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let json: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
    
    let mut models = Vec::new();
    if let Some(models_array) = json.get("models") {
        if let Some(arr) = models_array.as_array() {
            for item in arr {
                if let Some(name) = item.get("name") {
                    if let Some(name_str) = name.as_str() {
                        models.push(name_str.to_string());
                    }
                }
            }
        }
    }
    
    models.sort();
    Ok(models)
}

#[tauri::command]
async fn analyze_gaps(rfp_id: String) -> Result<Vec<serde_json::Value>, String> {
    use std::process::Command;
    use std::path::PathBuf;

    let python_exec = if cfg!(windows) { "python.exe" } else { "python3" };
    let mut script_path = PathBuf::from("sidecars/gap-engine/src_py/gap_engine.py");
    if !script_path.exists() {
        script_path = PathBuf::from("../sidecars/gap-engine/src_py/gap_engine.py");
    }

    if !script_path.exists() {
        return Err("Gap Engine script not found".to_string());
    }

    let output = Command::new(python_exec)
        .arg(script_path)
        .arg(&rfp_id)
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(format!("Gap Engine execution failed: {}", err_msg));
    }

    let stdout_str = String::from_utf8_lossy(&output.stdout).to_string();
    
    // Find the JSON line in the stdout
    for line in stdout_str.lines() {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
            if let Some(event) = val.get("event").and_then(|e| e.as_str()) {
                if event == "gap_report_generated" {
                    if let Some(gaps) = val.get("data").and_then(|d| d.get("gaps")).and_then(|g| g.as_array()) {
                        return Ok(gaps.clone());
                    }
                }
            }
        }
    }

    Err("Failed to parse gaps from Gap Engine output".to_string())
}

#[tauri::command]
async fn bootstrap_system(app: tauri::AppHandle) -> Result<String, String> {
    use std::process::Command;
    use std::net::TcpStream;
    use std::time::Duration;
    use std::thread::sleep;

    // Run database bootstrap cleanup natively in Rust
    if let Ok(conn) = crate::db::queries::get_db_connection(&app) {
        let _ = conn.execute("DELETE FROM opportunities WHERE id IN ('101', '102')", []);
        let _ = conn.execute("DELETE FROM opportunities WHERE title LIKE 'Found result for %'", []);
        let _ = conn.execute("DELETE FROM portals WHERE id = '1'", []);

        let mut presets_to_update = Vec::new();
        if let Ok(mut stmt) = conn.prepare("SELECT id, base_url, selector_config FROM portals") {
            if let Ok(mut rows) = stmt.query([]) {
                while let Ok(Some(row)) = rows.next() {
                    let id: String = row.get(0).unwrap_or_default();
                    let base_url: String = row.get(1).unwrap_or_default();
                    let selector_config: Option<String> = row.get(2).unwrap_or(None);
                    if base_url.contains("resume.brightspyre.com") && selector_config.is_none() {
                        presets_to_update.push(id);
                    }
                }
            }
        }

        for id in presets_to_update {
            let config_preset = serde_json::json!({ "searchSelector": "input#query-data" }).to_string();
            let _ = conn.execute(
                "UPDATE portals SET selector_config = ?, rendering_mode = ? WHERE id = ?",
                rusqlite::params![config_preset, "Browser (Playwright)".to_string(), id],
            );
        }
    }

    // 1. Bring up Docker compose infrastructure securely and platform-independently
    let mut compose_status = Command::new("docker")
        .args(["compose", "up", "-d"])
        .status();

    if compose_status.is_err() {
        // Fallback to older docker-compose command
        compose_status = Command::new("docker-compose")
            .args(["up", "-d"])
            .status();
    }

    if let Err(e) = compose_status {
        return Err(format!("Failed to bring up Docker infrastructure: {}", e));
    }

    // 2. Poll health natively via TcpStream socket checks to avoid calling external binaries (curl, nc)
    let poll_timeout = Duration::from_secs(2);
    let mut logs = vec![String::from("Sentinel Bootstrapped Natively in Rust:")];

    // Wait for Ollama
    let mut ollama_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:11434".parse().unwrap(), poll_timeout).is_ok() {
            ollama_ok = true;
            break;
        }
        sleep(Duration::from_secs(2));
    }
    if ollama_ok {
        logs.push(String::from("[✓] Ollama is ONLINE"));
    } else {
        logs.push(String::from("[-] Ollama check timed out"));
    }

    // Wait for ChromaDB
    let mut chroma_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:8000".parse().unwrap(), poll_timeout).is_ok() {
            chroma_ok = true;
            break;
        }
        sleep(Duration::from_secs(2));
    }
    if chroma_ok {
        logs.push(String::from("[✓] ChromaDB is ONLINE"));
    } else {
        logs.push(String::from("[-] ChromaDB check timed out"));
    }

    // Wait for Hunter sidecar
    let mut hunter_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:50051".parse().unwrap(), poll_timeout).is_ok() {
            hunter_ok = true;
            break;
        }
        sleep(Duration::from_secs(2));
    }
    if hunter_ok {
        logs.push(String::from("[✓] Hunter Engine is ONLINE"));
    } else {
        logs.push(String::from("[-] Hunter check timed out"));
    }

    // Wait for RAG sidecar
    let mut rag_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:50052".parse().unwrap(), poll_timeout).is_ok() {
            rag_ok = true;
            break;
        }
        sleep(Duration::from_secs(2));
    }
    if rag_ok {
        logs.push(String::from("[✓] RAG Engine is ONLINE"));
    } else {
        logs.push(String::from("[-] RAG check timed out"));
    }

    Ok(logs.join("\n"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    telemetry::init_telemetry();

    tauri::Builder::default()
        .manage(crate::sidecar::HunterRegistry::new())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_sql::Builder::default().add_migrations("sqlite:sentinel.db", db::init()).build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            check_ollama_status,
            get_ollama_models,
            generate_chat_response,
            generate_vision_description,
            extract_pdf_text_from_bytes,
            analyze_gaps,
            bootstrap_system,
            commands::hunting::start_hunt_session,
            commands::hunting::stop_hunt_session,
            commands::hunting::get_opportunities,
            commands::hunting::detect_portal,
            commands::drafting::ingest_document,
            commands::drafting::generate_draft,
            commands::knowledge_base::add_to_knowledge_base,
            commands::knowledge_base::search_knowledge_base,
            commands::db_commands::get_portals,
            commands::db_commands::get_opportunities_list,
            commands::db_commands::save_portal,
            commands::db_commands::delete_portal,
            commands::db_commands::toggle_portal_status,
            commands::db_commands::finish_active_hunt,
            commands::db_commands::get_scheduler_timestamp,
            commands::db_commands::set_scheduler_timestamp,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
