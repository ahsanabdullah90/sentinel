pub mod hunter {
    tonic::include_proto!("hunter");
}

pub mod rag {
    tonic::include_proto!("rag");
}

pub mod gap_engine {
    tonic::include_proto!("gap_engine");
}

pub use hunter::hunter_service_client::HunterServiceClient;
pub use rag::rag_service_client::RagServiceClient;
pub use gap_engine::gap_engine_service_client::GapEngineServiceClient;

use std::sync::atomic::{AtomicU16, Ordering};
use std::str::FromStr;

pub static HUNTER_PORT: AtomicU16 = AtomicU16::new(50051);
pub static RAG_PORT: AtomicU16 = AtomicU16::new(50052);
pub static GAP_ENGINE_PORT: AtomicU16 = AtomicU16::new(50054);

/// Securely wraps any gRPC payload into a tonic::Request, injecting the `x-sentinel-token`
/// header key with the environment-configured API key (C-8, C-1).
pub fn get_api_request<T>(payload: T) -> tonic::Request<T> {
    let mut req = tonic::Request::new(payload);
    let api_key = std::env::var("API_KEY").unwrap_or_else(|_| "sentinel-secret-api-key".to_string());
    if let Ok(meta_val) = tonic::metadata::MetadataValue::from_str(&api_key) {
        req.metadata_mut().insert("x-sentinel-token", meta_val);
    }
    req
}

pub async fn get_hunter_client() -> Result<HunterServiceClient<tonic::transport::Channel>, tonic::transport::Error> {
    let port = HUNTER_PORT.load(Ordering::SeqCst);
    HunterServiceClient::connect(format!("http://127.0.0.1:{}", port)).await
}

pub async fn get_rag_client() -> Result<RagServiceClient<tonic::transport::Channel>, tonic::transport::Error> {
    let port = RAG_PORT.load(Ordering::SeqCst);
    RagServiceClient::connect(format!("http://127.0.0.1:{}", port)).await
}

pub async fn get_gap_engine_client() -> Result<GapEngineServiceClient<tonic::transport::Channel>, tonic::transport::Error> {
    let port = GAP_ENGINE_PORT.load(Ordering::SeqCst);
    GapEngineServiceClient::connect(format!("http://127.0.0.1:{}", port)).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_api_request_header_injection() {
        // Test fallback token when API_KEY is unset
        std::env::remove_var("API_KEY");
        let req = get_api_request(());
        let token_header = req.metadata().get("x-sentinel-token");
        assert!(token_header.is_some(), "Expected x-sentinel-token header to be present");
        assert_eq!(token_header.unwrap().to_str().unwrap(), "sentinel-secret-api-key");

        // Test custom token injection
        std::env::set_var("API_KEY", "my-secure-custom-token");
        let req2 = get_api_request(());
        let token_header2 = req2.metadata().get("x-sentinel-token");
        assert!(token_header2.is_some());
        assert_eq!(token_header2.unwrap().to_str().unwrap(), "my-secure-custom-token");
        std::env::remove_var("API_KEY");
    }

    #[test]
    fn test_atomic_ports_defaults() {
        assert_eq!(HUNTER_PORT.load(Ordering::SeqCst), 50051);
        assert_eq!(RAG_PORT.load(Ordering::SeqCst), 50052);
        assert_eq!(GAP_ENGINE_PORT.load(Ordering::SeqCst), 50054);
    }

    #[test]
    fn test_port_reconfiguration() {
        HUNTER_PORT.store(60051, Ordering::SeqCst);
        RAG_PORT.store(60052, Ordering::SeqCst);
        GAP_ENGINE_PORT.store(60054, Ordering::SeqCst);

        assert_eq!(HUNTER_PORT.load(Ordering::SeqCst), 60051);
        assert_eq!(RAG_PORT.load(Ordering::SeqCst), 60052);
        assert_eq!(GAP_ENGINE_PORT.load(Ordering::SeqCst), 60054);

        // Reset to original defaults
        HUNTER_PORT.store(50051, Ordering::SeqCst);
        RAG_PORT.store(50052, Ordering::SeqCst);
        GAP_ENGINE_PORT.store(50054, Ordering::SeqCst);
    }
}
