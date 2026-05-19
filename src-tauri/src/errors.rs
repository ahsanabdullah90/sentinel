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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_database_error_serialization() {
        let error = SentinelError::Database("connection failed".to_string());
        let serialized = serde_json::to_value(&error).unwrap();
        assert_eq!(serialized["code"], "DATABASE_ERROR");
        assert_eq!(serialized["message"], "connection failed");
    }

    #[test]
    fn test_sidecar_error_serialization() {
        let error = SentinelError::Sidecar("process crashed".to_string());
        let serialized = serde_json::to_value(&error).unwrap();
        assert_eq!(serialized["code"], "SIDECAR_ERROR");
        assert_eq!(serialized["message"], "process crashed");
    }

    #[test]
    fn test_validation_error_serialization() {
        let error = SentinelError::Validation("invalid input".to_string());
        let serialized = serde_json::to_value(&error).unwrap();
        assert_eq!(serialized["code"], "VALIDATION_ERROR");
        assert_eq!(serialized["message"], "invalid input");
    }

    #[test]
    fn test_io_error_from_std() {
        let std_error = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let sentinel_error = SentinelError::from(std_error);
        let serialized = serde_json::to_value(&sentinel_error).unwrap();
        assert_eq!(serialized["code"], "IO_ERROR");
    }

    #[test]
    fn test_ollama_unavailable_error() {
        let error = SentinelError::OllamaUnavailable("connection timeout".to_string());
        let serialized = serde_json::to_value(&error).unwrap();
        assert_eq!(serialized["code"], "OLLAMA_UNAVAILABLE");
    }

    #[test]
    fn test_chroma_unavailable_error() {
        let error = SentinelError::ChromaUnavailable("service unavailable".to_string());
        let serialized = serde_json::to_value(&error).unwrap();
        assert_eq!(serialized["code"], "CHROMA_UNAVAILABLE");
    }

    #[test]
    fn test_error_display() {
        let error = SentinelError::Database("test message".to_string());
        assert!(error.to_string().contains("Database error"));
    }
}
