use std::collections::HashSet;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr, ToSocketAddrs};

/// Check if an IP address belongs to a private/reserved network.
fn is_private_ip(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => is_private_ipv4(v4),
        IpAddr::V6(v6) => is_private_ipv6(v6),
    }
}

fn is_private_ipv4(ip: &Ipv4Addr) -> bool {
    let octets = ip.octets();
    // 10.0.0.0/8
    if octets[0] == 10 {
        return true;
    }
    // 172.16.0.0/12
    if octets[0] == 172 && (16..=31).contains(&octets[1]) {
        return true;
    }
    // 192.168.0.0/16
    if octets[0] == 192 && octets[1] == 168 {
        return true;
    }
    // 127.0.0.0/8
    if octets[0] == 127 {
        return true;
    }
    // 169.254.0.0/16 (link-local)
    if octets[0] == 169 && octets[1] == 254 {
        return true;
    }
    // 0.0.0.0/8
    if octets[0] == 0 {
        return true;
    }
    false
}

fn is_private_ipv6(ip: &Ipv6Addr) -> bool {
    // ::1 loopback
    if ip.is_loopback() {
        return true;
    }
    // :: unspecified
    if ip.is_unspecified() {
        return true;
    }
    let segments = ip.segments();
    // fc00::/7 (ULA) - first byte is 0xfc or 0xfd
    if segments[0] & 0xfe00 == 0xfc00 {
        return true;
    }
    // fe80::/10 (link-local)
    if segments[0] & 0xffc0 == 0xfe80 {
        return true;
    }
    // IPv4-mapped IPv6 (::ffff:x.x.x.x) - check the embedded IPv4
    if let Some(v4) = ip.to_ipv4_mapped() {
        return is_private_ipv4(&v4);
    }
    false
}

#[derive(Debug)]
pub enum FilterError {
    PrivateIp(IpAddr),
    PortNotAllowed(u16),
    DnsResolutionFailed(String),
    AllAddressesPrivate(String),
}

impl std::fmt::Display for FilterError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::PrivateIp(ip) => write!(f, "target IP {} is in private/reserved range", ip),
            Self::PortNotAllowed(port) => write!(f, "port {} not in allowed list", port),
            Self::DnsResolutionFailed(host) => write!(f, "DNS resolution failed for {}", host),
            Self::AllAddressesPrivate(host) => {
                write!(f, "all resolved addresses for {} are private", host)
            }
        }
    }
}

/// Validate that the target host:port is allowed.
///
/// Returns the resolved socket address to connect to.
pub fn validate_target(
    host: &str,
    port: u16,
    allowed_ports: &HashSet<u16>,
) -> Result<SocketAddr, FilterError> {
    // Port whitelist check
    if !allowed_ports.contains(&port) {
        return Err(FilterError::PortNotAllowed(port));
    }

    // Try parsing as IP directly
    if let Ok(ip) = host.parse::<IpAddr>() {
        if is_private_ip(&ip) {
            return Err(FilterError::PrivateIp(ip));
        }
        return Ok(SocketAddr::new(ip, port));
    }

    // DNS resolution with private IP check (DNS rebinding protection)
    let addr_str = format!("{}:{}", host, port);
    let addrs: Vec<SocketAddr> = addr_str
        .to_socket_addrs()
        .map_err(|_| FilterError::DnsResolutionFailed(host.to_string()))?
        .collect();

    if addrs.is_empty() {
        return Err(FilterError::DnsResolutionFailed(host.to_string()));
    }

    // All resolved addresses must be non-private
    for addr in &addrs {
        if is_private_ip(&addr.ip()) {
            return Err(FilterError::PrivateIp(addr.ip()));
        }
    }

    // Return the first valid address
    Ok(addrs[0])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ports() -> HashSet<u16> {
        [80, 443, 8080, 8443].into_iter().collect()
    }

    #[test]
    fn test_private_ipv4() {
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(172, 16, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(192, 168, 1, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(169, 254, 1, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0))));
        assert!(!is_private_ip(&IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8))));
        assert!(!is_private_ip(&IpAddr::V4(Ipv4Addr::new(203, 0, 113, 1))));
    }

    #[test]
    fn test_private_ipv6() {
        assert!(is_private_ip(&IpAddr::V6(Ipv6Addr::LOCALHOST)));
        assert!(is_private_ip(&IpAddr::V6(Ipv6Addr::UNSPECIFIED)));
        // fc00::1 (ULA)
        assert!(is_private_ip(&IpAddr::V6(Ipv6Addr::new(
            0xfc00, 0, 0, 0, 0, 0, 0, 1
        ))));
        // fe80::1 (link-local)
        assert!(is_private_ip(&IpAddr::V6(Ipv6Addr::new(
            0xfe80, 0, 0, 0, 0, 0, 0, 1
        ))));
    }

    #[test]
    fn test_port_not_allowed() {
        let result = validate_target("8.8.8.8", 22, &ports());
        assert!(matches!(result, Err(FilterError::PortNotAllowed(22))));
    }

    #[test]
    fn test_private_ip_blocked() {
        let result = validate_target("127.0.0.1", 80, &ports());
        assert!(matches!(result, Err(FilterError::PrivateIp(_))));
    }

    #[test]
    fn test_public_ip_allowed() {
        let result = validate_target("8.8.8.8", 443, &ports());
        assert!(result.is_ok());
    }
}
