use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum SentinelError {
    #[error("Database error: {0}")]
    Database(String),

    #[error("Sidecar error: {0}")]
    Sidecar(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("IO error: {0}")]
    Io(String),

    #[error("Ollama unavailable: {0}")]
    OllamaUnavailable(String),

    #[error("Chroma unavailable: {0}")]
    ChromaUnavailable(String),

    #[error("AI error: {0}")]
    Ai(String),

    #[error("Network error: {0}")]
    Network(String),
}

#[derive(Serialize)]
pub struct SentinelErrorJson {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context: Option<serde_json::Value>,
}

impl Serialize for SentinelError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        let (code, message) = match self {
            SentinelError::Database(m) => ("DATABASE_ERROR", m.clone()),
            SentinelError::Sidecar(m) => ("SIDECAR_ERROR", m.clone()),
            SentinelError::Validation(m) => ("VALIDATION_ERROR", m.clone()),
            SentinelError::Io(m) => ("IO_ERROR", m.clone()),
            SentinelError::OllamaUnavailable(m) => ("OLLAMA_UNAVAILABLE", m.clone()),
            SentinelError::ChromaUnavailable(m) => ("CHROMA_UNAVAILABLE", m.clone()),
            SentinelError::Ai(m) => ("AI_ERROR", m.clone()),
            SentinelError::Network(m) => ("NETWORK_ERROR", m.clone()),
        };

        let json = SentinelErrorJson {
            code: code.to_string(),
            message,
            context: None,
        };

        json.serialize(serializer)
    }
}

impl From<std::io::Error> for SentinelError {
    fn from(err: std::io::Error) -> Self {
        SentinelError::Io(err.to_string())
    }
}
