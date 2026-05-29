fn main() {
    tonic_build::configure()
        .build_server(false)
        .compile(
            &["../proto/hunter.proto", "../proto/rag.proto", "../proto/health.proto"],
            &["../proto"],
        )
        .unwrap();

    tauri_build::build()
}
