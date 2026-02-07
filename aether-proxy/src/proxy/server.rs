use std::collections::HashSet;
use std::net::SocketAddr;
use std::sync::Arc;

use http_body_util::BodyExt;
use hyper::body::Incoming;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Method, Request};
use hyper_util::rt::TokioIo;
use tokio::net::TcpListener;
use tokio::sync::watch;
use tracing::{debug, info, warn};

use crate::config::Config;
use crate::proxy::{connect, plain};

/// Start the proxy server.
///
/// Listens for incoming TCP connections and dispatches:
/// - CONNECT requests -> tunnel handler
/// - Other HTTP requests -> plain forward proxy handler
pub async fn run(
    config: Arc<Config>,
    node_id: Arc<String>,
    mut shutdown_rx: watch::Receiver<bool>,
) -> anyhow::Result<()> {
    let addr = SocketAddr::from(([0, 0, 0, 0], config.listen_port));
    let listener = TcpListener::bind(addr).await?;
    info!(addr = %addr, "proxy server listening");

    let allowed_ports: Arc<HashSet<u16>> = Arc::new(config.allowed_ports.iter().copied().collect());

    loop {
        tokio::select! {
            result = listener.accept() => {
                let (stream, peer_addr) = match result {
                    Ok(v) => v,
                    Err(e) => {
                        warn!(error = %e, "failed to accept connection");
                        continue;
                    }
                };

                debug!(peer = %peer_addr, "new connection");

                let config = Arc::clone(&config);
                let node_id = Arc::clone(&node_id);
                let allowed_ports = Arc::clone(&allowed_ports);

                tokio::task::spawn(async move {
                    let io = TokioIo::new(stream);
                    let config = config;
                    let node_id = node_id;
                    let allowed_ports = allowed_ports;

                    let service = service_fn(move |req: Request<Incoming>| {
                        let config = Arc::clone(&config);
                        let node_id = Arc::clone(&node_id);
                        let allowed_ports = Arc::clone(&allowed_ports);

                        async move {
                            type BoxBody = http_body_util::combinators::BoxBody<bytes::Bytes, Box<dyn std::error::Error + Send + Sync>>;

                            if req.method() == Method::CONNECT {
                                let resp = connect::handle_connect(
                                    req,
                                    config,
                                    &node_id,
                                    &allowed_ports,
                                )
                                .await;
                                let resp = resp.map(|_| -> BoxBody {
                                    http_body_util::Empty::new()
                                        .map_err(|e| -> Box<dyn std::error::Error + Send + Sync> { match e {} })
                                        .boxed()
                                });
                                Ok::<_, hyper::Error>(resp)
                            } else {
                                let resp = plain::handle_plain(
                                    req,
                                    config,
                                    &node_id,
                                    &allowed_ports,
                                )
                                .await;
                                let resp = resp.map(|body| -> BoxBody {
                                    body.map_err(|e| -> Box<dyn std::error::Error + Send + Sync> { match e {} })
                                        .boxed()
                                });
                                Ok(resp)
                            }
                        }
                    });

                    if let Err(e) = http1::Builder::new()
                        .preserve_header_case(true)
                        .title_case_headers(false)
                        .serve_connection(io, service)
                        .with_upgrades()
                        .await
                    {
                        if !e.to_string().contains("connection closed") {
                            debug!(peer = %peer_addr, error = %e, "connection error");
                        }
                    }
                });
            }
            _ = shutdown_rx.changed() => {
                info!("proxy server shutting down");
                break;
            }
        }
    }

    Ok(())
}
