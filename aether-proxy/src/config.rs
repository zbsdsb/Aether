use clap::Parser;

/// Aether forward proxy with HMAC authentication.
///
/// Deployed on overseas VPS to relay API traffic for Aether instances
/// behind the GFW. Registers with Aether, sends heartbeats, and validates
/// incoming proxy requests via HMAC-SHA256 signatures in Basic Auth.
#[derive(Parser, Debug, Clone)]
#[command(version, about)]
pub struct Config {
    /// Aether server URL (e.g. https://aether.example.com)
    #[arg(long, env = "AETHER_PROXY_AETHER_URL")]
    pub aether_url: String,

    /// Management Token for Aether admin API (ae_xxx)
    #[arg(long, env = "AETHER_PROXY_MANAGEMENT_TOKEN")]
    pub management_token: String,

    /// HMAC-SHA256 key for proxy authentication
    #[arg(long, env = "AETHER_PROXY_HMAC_KEY")]
    pub hmac_key: String,

    /// Port to listen on for proxy connections
    #[arg(long, env = "AETHER_PROXY_LISTEN_PORT", default_value_t = 18080)]
    pub listen_port: u16,

    /// Public IP address of this node (auto-detected if omitted)
    #[arg(long, env = "AETHER_PROXY_PUBLIC_IP")]
    pub public_ip: Option<String>,

    /// Human-readable node name
    #[arg(long, env = "AETHER_PROXY_NODE_NAME", default_value = "proxy-01")]
    pub node_name: String,

    /// Region label (e.g. ap-northeast-1)
    #[arg(long, env = "AETHER_PROXY_NODE_REGION")]
    pub node_region: Option<String>,

    /// Heartbeat interval in seconds
    #[arg(long, env = "AETHER_PROXY_HEARTBEAT_INTERVAL", default_value_t = 30)]
    pub heartbeat_interval: u64,

    /// Allowed destination ports (default: 80,443,8080,8443)
    #[arg(long, env = "AETHER_PROXY_ALLOWED_PORTS", value_delimiter = ',', default_values_t = vec![80, 443, 8080, 8443])]
    pub allowed_ports: Vec<u16>,

    /// Timestamp tolerance window in seconds for HMAC validation
    #[arg(long, env = "AETHER_PROXY_TIMESTAMP_TOLERANCE", default_value_t = 300)]
    pub timestamp_tolerance: u64,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, env = "AETHER_PROXY_LOG_LEVEL", default_value = "info")]
    pub log_level: String,

    /// Output logs as JSON
    #[arg(long, env = "AETHER_PROXY_LOG_JSON", default_value_t = false)]
    pub log_json: bool,
}
