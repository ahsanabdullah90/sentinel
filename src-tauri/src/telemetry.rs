use tracing_subscriber::prelude::*;
use tracing_subscriber::EnvFilter;

pub fn init_telemetry() {
    let fmt_layer = tracing_subscriber::fmt::layer()
        .json() // Use structured JSON format
        .with_file(true)
        .with_line_number(true)
        .with_target(false)
        .with_thread_ids(true)
        .with_thread_names(true);
        
    let filter_layer = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,sentinel_rfp_lib=debug"));

    tracing_subscriber::registry()
        .with(filter_layer)
        .with(fmt_layer)
        .init();
        
    tracing::info!("Structured JSON logging initialized in Rust");
}
