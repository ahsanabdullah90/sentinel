fn main() {
    tonic_build::configure()
        .build_server(false)
        .compile(
            &["../proto/hunter.proto", "../proto/rag.proto"],
            &["../proto"],
        )
        .unwrap();

    tauri_build::build()
}
