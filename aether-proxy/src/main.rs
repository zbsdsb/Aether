mod auth;
mod config;
mod proxy;
mod registration;

use std::sync::Arc;

use clap::Parser;
use tokio::signal;
use tokio::sync::watch;
use tracing::{error, info};

use config::Config;
use registration::client::{detect_public_ip, AetherClient};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = Config::parse();

    // Initialize tracing
    init_tracing(&config);

    info!(
        version = env!("CARGO_PKG_VERSION"),
        port = config.listen_port,
        node_name = %config.node_name,
        "aether-proxy starting"
    );

    // Resolve public IP
    let public_ip = match &config.public_ip {
        Some(ip) => ip.clone(),
        None => detect_public_ip().await?,
    };
    info!(public_ip = %public_ip, "using public IP");

    // Register with Aether
    let aether_client = Arc::new(AetherClient::new(&config));
    let node_id = aether_client.register(&config, &public_ip).await?;
    let node_id = Arc::new(node_id);

    info!(node_id = %node_id, "node registered");

    // Shutdown signal channel
    let (shutdown_tx, shutdown_rx) = watch::channel(false);

    let config = Arc::new(config);

    // Start heartbeat task
    let heartbeat_handle = {
        let client = Arc::clone(&aether_client);
        let node_id = Arc::clone(&node_id);
        let interval = config.heartbeat_interval;
        let rx = shutdown_rx.clone();
        tokio::spawn(async move {
            registration::heartbeat::run(client, node_id, interval, rx).await;
        })
    };

    // Start proxy server
    let server_handle = {
        let config = Arc::clone(&config);
        let node_id = Arc::clone(&node_id);
        let rx = shutdown_rx.clone();
        tokio::spawn(async move {
            if let Err(e) = proxy::server::run(config, node_id, rx).await {
                error!(error = %e, "proxy server error");
            }
        })
    };

    // Wait for shutdown signal (SIGTERM or SIGINT)
    wait_for_shutdown().await;

    info!("shutdown signal received, cleaning up...");

    // Signal all tasks to stop
    let _ = shutdown_tx.send(true);

    // Graceful unregister (best-effort)
    if let Err(e) = aether_client.unregister(&node_id).await {
        error!(error = %e, "unregister failed during shutdown");
    }

    // Wait for tasks to finish
    let _ = tokio::join!(heartbeat_handle, server_handle);

    info!("aether-proxy stopped");
    Ok(())
}

fn init_tracing(config: &Config) {
    use tracing_subscriber::EnvFilter;

    let filter = EnvFilter::try_new(&config.log_level)
        .unwrap_or_else(|_| EnvFilter::new("info"));

    if config.log_json {
        tracing_subscriber::fmt()
            .with_env_filter(filter)
            .json()
            .init();
    } else {
        tracing_subscriber::fmt()
            .with_env_filter(filter)
            .init();
    }
}

async fn wait_for_shutdown() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}
