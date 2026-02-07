use std::sync::Arc;

use tokio::sync::watch;
use tracing::{debug, warn};

use crate::registration::client::AetherClient;

/// Run periodic heartbeat task until shutdown signal.
pub async fn run(
    client: Arc<AetherClient>,
    node_id: Arc<String>,
    interval_secs: u64,
    mut shutdown_rx: watch::Receiver<bool>,
) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(interval_secs));
    // Skip the first immediate tick (registration already acts as initial heartbeat)
    interval.tick().await;

    let mut consecutive_failures: u32 = 0;

    loop {
        tokio::select! {
            _ = interval.tick() => {
                match client.heartbeat(&node_id, None, None, None).await {
                    Ok(()) => {
                        if consecutive_failures > 0 {
                            debug!(
                                previous_failures = consecutive_failures,
                                "heartbeat recovered"
                            );
                        }
                        consecutive_failures = 0;
                    }
                    Err(e) => {
                        consecutive_failures += 1;
                        warn!(
                            error = %e,
                            consecutive_failures,
                            "heartbeat failed"
                        );
                    }
                }
            }
            _ = shutdown_rx.changed() => {
                debug!("heartbeat task stopping");
                break;
            }
        }
    }
}
