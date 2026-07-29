fn main() {
    let binaries_dir = std::path::PathBuf::from(
        std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default(),
    )
    .join("binaries");
    std::fs::create_dir_all(&binaries_dir).unwrap_or_default();

    let target_triple = std::env::var("TARGET").unwrap_or_else(|_| "x86_64-pc-windows-msvc".to_string());
    for name in ["hunter", "rag", "gap_engine", "worker"] {
        let binary_name = if cfg!(target_os = "windows") {
            format!("{}-{}.exe", name, target_triple)
        } else {
            format!("{}-{}", name, target_triple)
        };
        let binary_path = binaries_dir.join(&binary_name);
        if !binary_path.exists() {
            println!("cargo:warning=Creating dummy sidecar binary for '{}' — run compile_sidecars.sh before production builds", name);
            std::fs::write(
                &binary_path,
                if cfg!(target_os = "windows") {
                    "Dummy Windows Sidecar Bin"
                } else {
                    "#!/bin/sh\necho \"Dummy sidecar\"\nexit 0\n"
                },
            )
            .unwrap_or_default();
        }
    }

    tauri_build::build()
}
