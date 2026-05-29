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
    pdf_extract::extract_text_from_mem(&bytes)
        .map_err(|e| format!("Failed to extract PDF text natively: {}", e))
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
    // C-4: Validate/sanitize rfp_id via uuid::Uuid prior to executing commands in Tauri backend
    if uuid::Uuid::parse_str(&rfp_id).is_err() {
        return Err("Invalid rfp_id format. Must be a valid UUID.".to_string());
    }

    let mut client = crate::ipc::get_gap_engine_client()
        .await
        .map_err(|e| format!("Failed to connect to Gap Engine gRPC service: {}", e))?;

    let payload = crate::ipc::gap_engine::GapRequest {
        rfp_id: rfp_id.clone(),
    };
    let request = crate::ipc::get_api_request(payload);

    let response = client
        .analyze_gaps(request)
        .await
        .map_err(|e| format!("Gap Engine gRPC execution failed: {}", e))?
        .into_inner();

    let mut list = Vec::new();
    for gap in response.gaps {
        list.push(serde_json::json!({
            "area": gap.area,
            "description": gap.description,
        }));
    }

    Ok(list)
}

#[tauri::command]
async fn bootstrap_system(app: tauri::AppHandle) -> Result<String, String> {
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

    // 1. We poll and verify all services running inside the Docker compose network or host-based sidecars.
    // Decoupled docker compose lifecycle from Tauri boot runtime per C-9.
    let poll_timeout = Duration::from_secs(2);
    let mut logs = vec![String::from("Sentinel Bootstrapped Natively in Rust:")];

    // Wait for Ollama
    let ollama_port = std::env::var("OLLAMA_PORT").unwrap_or_else(|_| "11434".to_string());
    let ollama_addr_str = format!("127.0.0.1:{}", ollama_port);
    let ollama_addr = ollama_addr_str.parse().unwrap_or_else(|_| "127.0.0.1:11434".parse().unwrap());
    let mut ollama_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&ollama_addr, poll_timeout).is_ok() {
            ollama_ok = true;
            break;
        }
        sleep(Duration::from_secs(1));
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
        sleep(Duration::from_secs(1));
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
        sleep(Duration::from_secs(1));
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
        sleep(Duration::from_secs(1));
    }
    if rag_ok {
        logs.push(String::from("[✓] RAG Engine is ONLINE"));
    } else {
        logs.push(String::from("[-] RAG check timed out"));
    }

    // Wait for Worker sidecar (port 50053)
    let mut worker_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:50053".parse().unwrap(), poll_timeout).is_ok() {
            worker_ok = true;
            break;
        }
        sleep(Duration::from_secs(1));
    }
    if worker_ok {
        logs.push(String::from("[✓] Background Worker is ONLINE"));
    } else {
        logs.push(String::from("[-] Background Worker check timed out"));
    }

    // Wait for Gap Engine sidecar (port 50054)
    let mut gap_ok = false;
    for _ in 0..15 {
        if TcpStream::connect_timeout(&"127.0.0.1:50054".parse().unwrap(), poll_timeout).is_ok() {
            gap_ok = true;
            break;
        }
        sleep(Duration::from_secs(1));
    }
    if gap_ok {
        logs.push(String::from("[✓] Gap Engine is ONLINE"));
    } else {
        logs.push(String::from("[-] Gap Engine check timed out"));
    }

    Ok(logs.join("\n"))
}

fn validate_env() {
    if std::env::var("ENV").unwrap_or_default() == "production" {
        let api_key = std::env::var("API_KEY");
        let chroma_token = std::env::var("CHROMA_AUTH_TOKEN");
        let redis_url = std::env::var("REDIS_URL");
        
        let mut missing = Vec::new();
        if api_key.is_err() || api_key.unwrap().is_empty() {
            missing.push("API_KEY");
        }
        if chroma_token.is_err() || chroma_token.unwrap().is_empty() {
            missing.push("CHROMA_AUTH_TOKEN");
        }
        if redis_url.is_err() || redis_url.unwrap().is_empty() {
            missing.push("REDIS_URL");
        }
        
        if !missing.is_empty() {
            panic!(
                "CRITICAL ENVIRONMENT SCHEMA VALIDATION FAILURE: The following production variables are missing or empty: {:?}. Please configure them in your environment/.env file.",
                missing
            );
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    validate_env();

    // Securely initializes the async tracer inside a transient Tokio runtime context (Option 2)
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("Failed to build telemetry runtime");
    
    rt.block_on(async {
        telemetry::init_telemetry();
    });

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
            commands::db_commands::delete_opportunity,
            commands::db_commands::update_opportunity_status,
            commands::db_commands::get_opportunity_detail,
            commands::db_commands::get_attachments,
            commands::db_commands::save_attachment,
            commands::db_commands::delete_attachment,
            commands::db_commands::update_attachment_text,
            commands::db_commands::get_attachment_bytes,
            commands::db_commands::get_proposal_drafts,
            commands::db_commands::save_proposal_draft,
            commands::db_commands::update_proposal_draft,
            commands::db_commands::delete_proposal_draft,
            commands::db_commands::get_knowledge_base,
            commands::db_commands::save_knowledge_item,
            commands::db_commands::delete_knowledge_item,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
