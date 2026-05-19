use opentelemetry::global;
use opentelemetry::trace::TracerProvider as _;
use tracing_subscriber::prelude::*;

pub fn init_telemetry() {
    global::set_text_map_propagator(opentelemetry_sdk::propagation::TraceContextPropagator::new());
    
    let provider = opentelemetry_sdk::trace::TracerProvider::builder().build();
    global::set_tracer_provider(provider.clone());
    
    let tracer = provider.tracer("sentinel");

    let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);
    
    tracing_subscriber::registry()
        .with(telemetry)
        .with(tracing_subscriber::fmt::layer())
        .init();
        
    println!("OpenTelemetry initialized in Rust");
}
