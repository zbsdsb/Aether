use std::collections::HashSet;
use std::sync::Arc;

use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::{Request, Response};
use tracing::{debug, warn};

use crate::auth;
use crate::config::Config;
use crate::proxy::target_filter;

/// Handle plain HTTP forward proxy requests (non-CONNECT).
///
/// Flow: validate auth -> check target filter -> forward request -> return response
pub async fn handle_plain(
    req: Request<Incoming>,
    config: Arc<Config>,
    node_id: &str,
    allowed_ports: &HashSet<u16>,
) -> Response<Full<bytes::Bytes>> {
    // Extract Proxy-Authorization header
    let proxy_auth = req
        .headers()
        .get("proxy-authorization")
        .and_then(|v| v.to_str().ok());

    // HMAC authentication
    if let Err(e) = auth::validate_proxy_auth(proxy_auth, &config, node_id) {
        warn!(error = %e, "HTTP proxy auth failed");
        return proxy_auth_required(&e.to_string());
    }

    // Parse target from absolute URI
    let uri = req.uri().clone();
    let host = match uri.host() {
        Some(h) => h.to_string(),
        None => {
            warn!(uri = %uri, "HTTP proxy request missing host");
            return bad_request("missing host in URI");
        }
    };
    let port = uri.port_u16().unwrap_or(80);

    // Target filter
    let target_addr = match target_filter::validate_target(&host, port, allowed_ports) {
        Ok(addr) => addr,
        Err(e) => {
            warn!(host = %host, port, error = %e, "HTTP proxy target rejected");
            return forbidden(&e.to_string());
        }
    };

    debug!(target = %target_addr, method = %req.method(), "HTTP proxy forwarding");

    // Build outgoing request (strip proxy headers, use relative URI)
    let path_and_query = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or("/");

    let mut builder = Request::builder()
        .method(req.method())
        .uri(path_and_query)
        .version(req.version());

    // Copy headers, skipping proxy-specific ones
    for (name, value) in req.headers() {
        if name == "proxy-authorization" || name == "proxy-connection" {
            continue;
        }
        builder = builder.header(name, value);
    }

    // Collect the incoming body
    let body_bytes = match req.into_body().collect().await {
        Ok(collected) => collected.to_bytes(),
        Err(e) => {
            warn!(error = %e, "failed to read request body");
            return bad_gateway("failed to read request body");
        }
    };

    // Connect and send via raw TCP + hyper client
    let stream = match tokio::net::TcpStream::connect(target_addr).await {
        Ok(s) => s,
        Err(e) => {
            warn!(target = %target_addr, error = %e, "HTTP proxy connection failed");
            return bad_gateway(&format!("connection failed: {}", e));
        }
    };

    let io = hyper_util::rt::TokioIo::new(stream);
    let (mut sender, conn) = match hyper::client::conn::http1::handshake(io).await {
        Ok(pair) => pair,
        Err(e) => {
            warn!(error = %e, "HTTP handshake failed");
            return bad_gateway(&format!("handshake failed: {}", e));
        }
    };

    tokio::task::spawn(async move {
        if let Err(e) = conn.await {
            debug!(error = %e, "HTTP proxy client connection error");
        }
    });

    let outgoing = builder
        .body(Full::new(body_bytes))
        .expect("failed to build outgoing request");

    match sender.send_request(outgoing).await {
        Ok(resp) => {
            let (parts, body) = resp.into_parts();
            let body_bytes = match body.collect().await {
                Ok(collected) => collected.to_bytes(),
                Err(e) => {
                    warn!(error = %e, "failed to read response body");
                    return bad_gateway("failed to read response body");
                }
            };
            Response::from_parts(parts, Full::new(body_bytes))
        }
        Err(e) => {
            warn!(error = %e, "HTTP proxy request failed");
            bad_gateway(&format!("upstream request failed: {}", e))
        }
    }
}

fn proxy_auth_required(msg: &str) -> Response<Full<bytes::Bytes>> {
    Response::builder()
        .status(407)
        .header("Proxy-Authenticate", "HMAC-SHA256")
        .header("X-Error", msg)
        .body(Full::new(bytes::Bytes::new()))
        .unwrap()
}

fn forbidden(msg: &str) -> Response<Full<bytes::Bytes>> {
    Response::builder()
        .status(403)
        .header("X-Error", msg)
        .body(Full::new(bytes::Bytes::new()))
        .unwrap()
}

fn bad_request(msg: &str) -> Response<Full<bytes::Bytes>> {
    Response::builder()
        .status(400)
        .header("X-Error", msg)
        .body(Full::new(bytes::Bytes::new()))
        .unwrap()
}

fn bad_gateway(msg: &str) -> Response<Full<bytes::Bytes>> {
    Response::builder()
        .status(502)
        .header("X-Error", msg)
        .body(Full::new(bytes::Bytes::new()))
        .unwrap()
}
