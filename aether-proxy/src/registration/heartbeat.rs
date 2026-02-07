use std::sync::{Arc, RwLock};

use tokio::sync::watch;
use tracing::{debug, error, info, warn};

use crate::config::Config;
use crate::registration::client::{AetherClient, HeartbeatError};
use crate::runtime::{self, SharedDynamicConfig};

/// Run periodic heartbeat task until shutdown signal.
///
/// When Aether responds with 404 (node not found), this task automatically
/// re-registers the node and updates the shared `node_id` so the proxy
/// server and future heartbeats use the new identity.
///
/// When the heartbeat response includes a `remote_config`, it is applied
/// to the [`DynamicConfig`](crate::runtime::DynamicConfig) so the proxy
/// picks up changes without a restart.
pub async fn run(
    client: Arc<AetherClient>,
    node_id: Arc<RwLock<String>>,
    config: Arc<Config>,
    public_ip: String,
    tls_fingerprint: Option<String>,
    dynamic: SharedDynamicConfig,
    mut shutdown_rx: watch::Receiver<bool>,
) {
    let mut consecutive_failures: u32 = 0;

    // Skip the first tick (registration already acts as initial heartbeat)
    let initial_interval = dynamic.read().unwrap().heartbeat_interval;
    tokio::select! {
        _ = tokio::time::sleep(std::time::Duration::from_secs(initial_interval)) => {}
        _ = shutdown_rx.changed() => {
            debug!("heartbeat task stopping (during initial wait)");
            return;
        }
    }

    loop {
        let current_node_id = node_id.read().unwrap().clone();

        match client.heartbeat(&current_node_id, None, None, None).await {
            Ok(result) => {
                if consecutive_failures > 0 {
                    debug!(
                        previous_failures = consecutive_failures,
                        "heartbeat recovered"
                    );
                }
                consecutive_failures = 0;

                // Apply remote config if present and version changed
                if let Some(ref remote) = result.remote_config {
                    runtime::apply_remote_config(&dynamic, remote, result.config_version);
                }
            }
            Err(HeartbeatError::NodeNotFound(_)) => {
                warn!(
                    old_node_id = %current_node_id,
                    "node not found, re-registering"
                );
                match client.register(
                    &config,
                    &public_ip,
                    config.enable_tls,
                    tls_fingerprint.as_deref(),
                ).await {
                    Ok(new_id) => {
                        info!(
                            old_node_id = %current_node_id,
                            new_node_id = %new_id,
                            "re-registered successfully"
                        );
                        *node_id.write().unwrap() = new_id;
                        consecutive_failures = 0;
                    }
                    Err(e) => {
                        consecutive_failures += 1;
                        error!(
                            error = %e,
                            consecutive_failures,
                            "re-registration failed"
                        );
                    }
                }
            }
            Err(HeartbeatError::Other(e)) => {
                consecutive_failures += 1;
                warn!(
                    error = %e,
                    consecutive_failures,
                    "heartbeat failed"
                );
            }
        }

        // Read interval from dynamic config (may have been updated remotely)
        let interval_secs = dynamic.read().unwrap().heartbeat_interval;

        tokio::select! {
            _ = tokio::time::sleep(std::time::Duration::from_secs(interval_secs)) => {}
            _ = shutdown_rx.changed() => {
                debug!("heartbeat task stopping");
                break;
            }
        }
    }
}
