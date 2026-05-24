use crate::errors::SentinelError;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize)]
pub struct PortalCredential {
    pub portal_id: String,
    pub username: Option<String>,
    pub password: String,
}

#[tauri::command]
pub async fn save_portal_credential(
    _app: tauri::AppHandle,
    credential: PortalCredential
) -> Result<String, SentinelError> {
    // In a production app, the password would be encrypted before storage.
    // For this implementation, we rely on the underlying SQLCipher encryption of the DB file.
    // The password here is passed as 'password', which we store in 'encrypted_password' column.

    // We'll use a placeholder for now as actual DB insertion is usually handled via the frontend SQL plugin,
    // but having a dedicated Rust command for 'heavy' encryption/decryption is a good pattern.

    println!("Saving credential for portal: {}", credential.portal_id);
    Ok(Uuid::new_v4().to_string())
}
