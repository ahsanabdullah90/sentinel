use serde::{Deserialize, Serialize};
use crate::errors::SentinelError;

#[derive(Debug, Serialize, Deserialize)]
pub struct AppSettings {
    #[serde(rename = "ollamaModel")]
    pub ollama_model: String,
    #[serde(rename = "ollamaUrl")]
    pub ollama_url: String,
    #[serde(rename = "processingMode")]
    pub processing_mode: String,
    #[serde(rename = "cloudProvider")]
    pub cloud_provider: String,
    #[serde(rename = "apiKey")]
    pub api_key: String,
}

#[tauri::command]
pub async fn save_settings(settings: AppSettings) -> Result<(), SentinelError> {
    // In a real app, we'd save to a config file or DB.
    // For now, we'll just log it.
    println!("Saving settings: {:?}", settings);
    Ok(())
}

#[tauri::command]
pub async fn get_cloud_response(prompt: String, provider: String, api_key: String) -> Result<String, SentinelError> {
    let client = reqwest::Client::new();

    match provider.as_str() {
        "gemini" => {
            let url = format!("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={}", api_key);
            let res = client.post(&url)
                .json(&serde_json::json!({
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }]
                }))
                .send()
                .await
                .map_err(|e| SentinelError::Network(e.to_string()))?;

            let json: serde_json::Value = res.json().await.map_err(|e| SentinelError::Network(e.to_string()))?;

            if let Some(candidates) = json.get("candidates") {
                if let Some(content) = candidates[0].get("content") {
                    if let Some(parts) = content.get("parts") {
                        if let Some(text) = parts[0].get("text") {
                            return Ok(text.as_str().unwrap_or("").to_string());
                        }
                    }
                }
            }
            Err(SentinelError::Ai("Failed to parse Gemini response".to_string()))
        },
        "deepseek" => {
            let res = client.post("https://api.deepseek.com/v1/chat/completions")
                .header("Authorization", format!("Bearer {}", api_key))
                .json(&serde_json::json!({
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }))
                .send()
                .await
                .map_err(|e| SentinelError::Network(e.to_string()))?;

            let json: serde_json::Value = res.json().await.map_err(|e| SentinelError::Network(e.to_string()))?;
            if let Some(choices) = json.get("choices") {
                if let Some(message) = choices[0].get("message") {
                    if let Some(content) = message.get("content") {
                        return Ok(content.as_str().unwrap_or("").to_string());
                    }
                }
            }
            Err(SentinelError::Ai("Failed to parse DeepSeek response".to_string()))
        },
        "claude" => {
             let res = client.post("https://api.anthropic.com/v1/messages")
                .header("x-api-key", api_key)
                .header("anthropic-version", "2023-06-01")
                .json(&serde_json::json!({
                    "model": "claude-3-5-sonnet-20240620",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }))
                .send()
                .await
                .map_err(|e| SentinelError::Network(e.to_string()))?;

            let json: serde_json::Value = res.json().await.map_err(|e| SentinelError::Network(e.to_string()))?;
            if let Some(content) = json.get("content") {
                if let Some(text) = content[0].get("text") {
                    return Ok(text.as_str().unwrap_or("").to_string());
                }
            }
            Err(SentinelError::Ai("Failed to parse Claude response".to_string()))
        },
        _ => Err(SentinelError::Ai("Unknown cloud provider".to_string()))
    }
}
