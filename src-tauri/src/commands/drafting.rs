use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::sidecar::spawn_sidecar;

#[tauri::command]
pub async fn ingest_document(app: AppHandle, rfp_id: String, file_path: String) -> Result<(), SentinelError> {
    // 1. Verify file exists via Rust FS
    if !std::path::Path::new(&file_path).exists() {
        return Err(SentinelError::Io(format!("File not found: {}", file_path)));
    }

    // 2. Spawn RAG sidecar for ingestion
    spawn_sidecar(app, "rag", vec![
        "ingest".to_string(),
        "--rfp".to_string(), rfp_id,
        "--file".to_string(), file_path
    ]).await?;

    Ok(())
}

#[tauri::command]
pub async fn generate_draft(app: AppHandle, rfp_id: String, model: Option<String>) -> Result<(), SentinelError> {
    let target_model = model.unwrap_or_else(|| "llama3.1:8b".to_string());
    
    // Spawn RAG sidecar for drafting
    spawn_sidecar(app, "rag", vec![
        "draft".to_string(),
        "--rfp".to_string(), rfp_id,
        "--model".to_string(), target_model
    ]).await?;

    Ok(())
}
