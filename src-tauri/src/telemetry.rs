use opentelemetry::global;
use opentelemetry::trace::TracerProvider as _;
use tracing_subscriber::prelude::*;
use opentelemetry_otlp::WithExportConfig;

pub fn init_telemetry() {
    global::set_text_map_propagator(opentelemetry_sdk::propagation::TraceContextPropagator::new());
    
    let exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint("http://localhost:4317")
        .build()
        .expect("Failed to build OTLP span exporter");

    let tracer_provider = opentelemetry_sdk::trace::TracerProvider::builder()
        .with_batch_exporter(exporter, opentelemetry_sdk::runtime::Tokio)
        .build();

    global::set_tracer_provider(tracer_provider.clone());
    let tracer = tracer_provider.tracer("sentinel");

    let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);
    
    tracing_subscriber::registry()
        .with(telemetry)
        .with(tracing_subscriber::fmt::layer())
        .init();
        
    println!("OpenTelemetry OTLP initialized in Rust");
}
