use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::sidecar::execute_jsonrpc_method;

#[tauri::command]
pub async fn ingest_document(app: AppHandle, rfp_id: String, file_path: String) -> Result<(), SentinelError> {
    // 1. Verify file exists via Rust FS
    if !std::path::Path::new(&file_path).exists() {
        return Err(SentinelError::Io(format!("File not found: {}", file_path)));
    }

    // 2. Spawn RAG sidecar for ingestion via JSON-RPC
    let req_id = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "rfp_id": rfp_id,
        "file_path": file_path
    });
    execute_jsonrpc_method(app, "rag", "ingest", params, &req_id).await?;

    Ok(())
}

#[tauri::command]
pub async fn generate_draft(app: AppHandle, rfp_id: String, model: Option<String>) -> Result<(), SentinelError> {
    let target_model = model.unwrap_or_else(|| "llama3.1:8b".to_string());
    
    // Spawn RAG sidecar for drafting via JSON-RPC
    let req_id = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "rfp_id": rfp_id,
        "model": target_model
    });
    execute_jsonrpc_method(app, "rag", "query", params, &req_id).await?;

    Ok(())
}
