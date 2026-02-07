mod auth;
mod config;
mod proxy;
mod registration;
mod runtime;
mod setup;

use std::path::PathBuf;
use std::sync::{Arc, RwLock};

use clap::Parser;
use tokio::signal;
use tokio::sync::watch;
use tracing::{error, info};

use config::Config;
use registration::client::{detect_public_ip, AetherClient};
use runtime::DynamicConfig;

/// Default config file name.
const DEFAULT_CONFIG: &str = "aether-proxy.toml";

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().collect();

    // ── Handle `setup` subcommand before clap parsing ────────────────────
    if args.len() > 1 && args[1] == "setup" {
        let path = args
            .get(2)
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(DEFAULT_CONFIG));
        return setup::run(path);
    }

    // ── Load config file as env-var defaults (before clap) ───────────────
    let config_file_path = std::env::var("AETHER_PROXY_CONFIG")
        .unwrap_or_else(|_| DEFAULT_CONFIG.to_string());
    if std::path::Path::new(&config_file_path).exists() {
        if let Ok(file_cfg) = config::ConfigFile::load(std::path::Path::new(&config_file_path)) {
            file_cfg.inject_env();
        }
    }

    // ── Parse config; fall back to setup TUI if required args are missing ─
    let config = match Config::try_parse() {
        Ok(c) => c,
        Err(e) => {
            if e.kind() == clap::error::ErrorKind::MissingRequiredArgument {
                eprintln!("缺少必要配置，启动交互式配置向导...\n");
                return setup::run(PathBuf::from(&config_file_path));
            }
            e.exit();
        }
    };

    // Initialize tracing (with hot-reload support)
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

    // Initialize TLS if enabled
    let (tls_acceptor, tls_fingerprint) = if config.enable_tls {
        let cert_path = std::path::PathBuf::from(&config.tls_cert);
        let key_path = std::path::PathBuf::from(&config.tls_key);

        proxy::tls::ensure_self_signed_cert(&cert_path, &key_path)?;
        let acceptor = proxy::tls::build_tls_acceptor(&cert_path, &key_path)?;
        let fingerprint = proxy::tls::cert_sha256_fingerprint(&cert_path)?;

        info!(fingerprint = %fingerprint, "TLS enabled");
        (Some(acceptor), Some(fingerprint))
    } else {
        info!("TLS disabled");
        (None, None)
    };

    let node_id = aether_client
        .register(&config, &public_ip, config.enable_tls, tls_fingerprint.as_deref())
        .await?;

    info!(node_id = %node_id, "node registered");

    let node_id = Arc::new(RwLock::new(node_id));

    // Dynamic config (hot-reloadable via heartbeat)
    let dynamic = Arc::new(RwLock::new(DynamicConfig::from_config(&config)));

    // Shutdown signal channel
    let (shutdown_tx, shutdown_rx) = watch::channel(false);

    let config = Arc::new(config);

    // Start heartbeat task
    let heartbeat_handle = {
        let client = Arc::clone(&aether_client);
        let node_id = Arc::clone(&node_id);
        let config = Arc::clone(&config);
        let dynamic = Arc::clone(&dynamic);
        let public_ip = public_ip.clone();
        let fingerprint = tls_fingerprint.clone();
        let rx = shutdown_rx.clone();
        tokio::spawn(async move {
            registration::heartbeat::run(client, node_id, config, public_ip, fingerprint, dynamic, rx).await;
        })
    };

    // Start proxy server
    let server_handle = {
        let config = Arc::clone(&config);
        let node_id = Arc::clone(&node_id);
        let dynamic = Arc::clone(&dynamic);
        let rx = shutdown_rx.clone();
        let tls = tls_acceptor.clone();
        tokio::spawn(async move {
            if let Err(e) = proxy::server::run(config, node_id, dynamic, tls, rx).await {
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
    let current_node_id = node_id.read().unwrap().clone();
    if let Err(e) = aether_client.unregister(&current_node_id).await {
        error!(error = %e, "unregister failed during shutdown");
    }

    // Wait for tasks to finish
    let _ = tokio::join!(heartbeat_handle, server_handle);

    info!("aether-proxy stopped");
    Ok(())
}

fn init_tracing(config: &Config) {
    use tracing_subscriber::prelude::*;
    use tracing_subscriber::{reload, EnvFilter};

    let filter =
        EnvFilter::try_new(&config.log_level).unwrap_or_else(|_| EnvFilter::new("info"));

    let (filter_layer, reload_handle) = reload::Layer::new(filter);

    // Register log-level hot-reloader
    runtime::set_log_reloader(Box::new(move |level: &str| {
        if let Ok(new_filter) = EnvFilter::try_new(level) {
            let _ = reload_handle.modify(|f| *f = new_filter);
        }
    }));

    if config.log_json {
        tracing_subscriber::registry()
            .with(filter_layer)
            .with(tracing_subscriber::fmt::layer().json())
            .init();
    } else {
        tracing_subscriber::registry()
            .with(filter_layer)
            .with(tracing_subscriber::fmt::layer())
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
