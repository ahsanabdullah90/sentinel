use crate::errors::SentinelError;

#[tauri::command]
pub async fn add_to_knowledge_base(file_path: String, _tags: Vec<String>) -> Result<String, SentinelError> {
    // 1. Verify file exists via Rust FS
    if !std::path::Path::new(&file_path).exists() {
        return Err(SentinelError::Io(format!("File not found: {}", file_path)));
    }

    // Sprint 2 implementation
    Ok(uuid::Uuid::new_v4().to_string())
}

#[tauri::command]
pub async fn search_knowledge_base(_query: String, _top_k: Option<u32>) -> Result<Vec<serde_json::Value>, SentinelError> {
    // Sprint 2 implementation
    Ok(vec![])
}
