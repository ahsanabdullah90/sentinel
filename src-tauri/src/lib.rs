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
async fn analyze_gaps(_rfp_id: String) -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![])
}

#[tauri::command]
async fn bootstrap_system(app: tauri::AppHandle) -> Result<String, String> {
    use std::process::Command;
    use std::path::PathBuf;

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
