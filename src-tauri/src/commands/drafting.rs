use tauri::AppHandle;
use crate::errors::SentinelError;
use crate::sidecar::execute_jsonrpc_method;

#[tauri::command]
pub async fn ingest_document(app: AppHandle, document_id: String, content: String) -> Result<(), SentinelError> {
    let req_id = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "document_id": document_id,
        "content": content
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
