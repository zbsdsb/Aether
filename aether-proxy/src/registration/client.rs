use reqwest::Client;
use serde::{Deserialize, Serialize};
use tracing::{debug, error, info, warn};

use crate::config::Config;

#[derive(Debug, Serialize)]
struct RegisterRequest {
    name: String,
    ip: String,
    port: u16,
    #[serde(skip_serializing_if = "Option::is_none")]
    region: Option<String>,
    heartbeat_interval: u64,
}

#[derive(Debug, Deserialize)]
pub struct RegisterResponse {
    pub node_id: String,
}

#[derive(Debug, Serialize)]
struct HeartbeatRequest {
    node_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    active_connections: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    total_requests: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    avg_latency_ms: Option<f64>,
}

#[derive(Debug, Serialize)]
struct UnregisterRequest {
    node_id: String,
}

/// Aether API client for proxy node lifecycle management.
pub struct AetherClient {
    http: Client,
    base_url: String,
    token: String,
}

impl AetherClient {
    pub fn new(config: &Config) -> Self {
        let http = Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .expect("failed to create HTTP client");

        Self {
            http,
            base_url: config.aether_url.trim_end_matches('/').to_string(),
            token: config.management_token.clone(),
        }
    }

    /// Register this node with Aether (idempotent upsert by ip:port).
    ///
    /// Returns the stable node_id assigned by Aether.
    pub async fn register(
        &self,
        config: &Config,
        public_ip: &str,
    ) -> anyhow::Result<String> {
        let url = format!("{}/api/admin/proxy-nodes/register", self.base_url);
        let body = RegisterRequest {
            name: config.node_name.clone(),
            ip: public_ip.to_string(),
            port: config.listen_port,
            region: config.node_region.clone(),
            heartbeat_interval: config.heartbeat_interval,
        };

        info!(
            url = %url,
            name = %body.name,
            ip = %body.ip,
            port = body.port,
            "registering with Aether"
        );

        let resp = self
            .http
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.token))
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        if !status.is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("register failed (HTTP {}): {}", status, text);
        }

        let data: RegisterResponse = resp.json().await?;
        info!(node_id = %data.node_id, "registered successfully");
        Ok(data.node_id)
    }

    /// Send heartbeat to Aether.
    pub async fn heartbeat(
        &self,
        node_id: &str,
        active_connections: Option<i64>,
        total_requests: Option<i64>,
        avg_latency_ms: Option<f64>,
    ) -> anyhow::Result<()> {
        let url = format!("{}/api/admin/proxy-nodes/heartbeat", self.base_url);
        let body = HeartbeatRequest {
            node_id: node_id.to_string(),
            active_connections,
            total_requests,
            avg_latency_ms,
        };

        debug!(node_id = %node_id, "sending heartbeat");

        let resp = self
            .http
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.token))
            .json(&body)
            .send()
            .await?;

        let status = resp.status();
        if !status.is_success() {
            let text = resp.text().await.unwrap_or_default();
            warn!(status = %status, body = %text, "heartbeat failed");
            anyhow::bail!("heartbeat failed (HTTP {}): {}", status, text);
        }

        debug!(node_id = %node_id, "heartbeat ok");
        Ok(())
    }

    /// Unregister this node from Aether (graceful shutdown).
    pub async fn unregister(&self, node_id: &str) -> anyhow::Result<()> {
        let url = format!("{}/api/admin/proxy-nodes/unregister", self.base_url);
        let body = UnregisterRequest {
            node_id: node_id.to_string(),
        };

        info!(node_id = %node_id, "unregistering from Aether");

        let resp = self
            .http
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.token))
            .json(&body)
            .send()
            .await;

        match resp {
            Ok(r) if r.status().is_success() => {
                info!(node_id = %node_id, "unregistered successfully");
                Ok(())
            }
            Ok(r) => {
                let text = r.text().await.unwrap_or_default();
                error!(body = %text, "unregister failed");
                anyhow::bail!("unregister failed: {}", text);
            }
            Err(e) => {
                // Best-effort during shutdown
                error!(error = %e, "unregister request failed");
                anyhow::bail!("unregister request failed: {}", e);
            }
        }
    }
}

/// Auto-detect public IP by querying external services.
pub async fn detect_public_ip() -> anyhow::Result<String> {
    let endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ];

    let client = Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()?;

    for endpoint in &endpoints {
        match client.get(*endpoint).send().await {
            Ok(resp) if resp.status().is_success() => {
                let ip = resp.text().await?.trim().to_string();
                if !ip.is_empty() {
                    info!(ip = %ip, source = %endpoint, "detected public IP");
                    return Ok(ip);
                }
            }
            Ok(resp) => {
                debug!(endpoint = %endpoint, status = %resp.status(), "IP detection failed");
            }
            Err(e) => {
                debug!(endpoint = %endpoint, error = %e, "IP detection failed");
            }
        }
    }

    anyhow::bail!("failed to detect public IP from any source; use --public-ip")
}
