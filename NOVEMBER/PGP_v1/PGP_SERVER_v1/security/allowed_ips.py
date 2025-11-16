#!/usr/bin/env python
"""
IP Whitelist Configuration for PGP_SERVER_v1.

This module defines allowed IP ranges for different environments and use cases.

IMPORTANT ARCHITECTURAL NOTE:
- Cloud Run services DO NOT have predefined egress IP ranges
- Inter-service communication (Cloud Run → Cloud Run) should rely on HMAC authentication, NOT IP whitelist
- IP whitelisting is primarily for external webhooks with known source IPs (NowPayments, Telegram)
- For Cloud Run → Cloud Run communication, disable IP whitelist and use HMAC-only authentication

References:
- https://cloud.google.com/run/docs/configuring/vpc-direct-vpc
- https://www.gstatic.com/ipranges/cloud.json (Google Cloud IP ranges)
"""

# =============================================================================
# INTERNAL GOOGLE CLOUD IP RANGES
# =============================================================================

# GCP Internal VPC ranges (RFC 1918 private addresses)
# Used when services communicate via VPC connector or internal load balancer
GCP_INTERNAL_VPC = [
    "10.0.0.0/8",       # Class A private network
    "172.16.0.0/12",    # Class B private network
    "192.168.0.0/16",   # Class C private network
]

# Google Cloud Load Balancer health check ranges
# Cloud Run services receive health checks from these IPs
GCP_HEALTH_CHECK_RANGES = [
    "35.191.0.0/16",    # Legacy health checks
    "130.211.0.0/22",   # Legacy health checks
]

# Google Cloud NAT IP ranges for us-central1
# ONLY applicable if using VPC Connector + Cloud NAT for static egress IPs
# NOTE: Cloud Run does NOT use these by default - dynamic IPs are used
GCP_US_CENTRAL1_RANGES = [
    "35.184.0.0/13",    # us-central1 range 1
    "35.192.0.0/14",    # us-central1 range 2
    "35.196.0.0/15",    # us-central1 range 3
    "34.72.0.0/13",     # us-central1 range 4
    "34.64.0.0/11",     # us-central1 range 5 (broader)
]

# =============================================================================
# EXTERNAL WEBHOOK IP RANGES
# =============================================================================

# NowPayments IPN webhook IPs
# Documentation: https://documenter.getpostman.com/view/7907941/S1a32n38#ipn
# Updated: 2025-01-16
NOWPAYMENTS_IPN_IPS = [
    "52.29.216.31",     # Primary IPN server (eu-central-1)
    "18.157.160.115",   # Secondary IPN server (eu-central-1)
    "3.126.138.126",    # Tertiary IPN server (eu-central-1)
]

# Telegram Bot API webhook IPs
# Documentation: https://core.telegram.org/bots/webhooks#the-short-version
# Updated: 2025-01-16
TELEGRAM_WEBHOOK_IPS = [
    "149.154.160.0/20",  # Telegram datacenter range 1
    "91.108.4.0/22",     # Telegram datacenter range 2
]

# =============================================================================
# DEVELOPMENT & TESTING IP RANGES
# =============================================================================

# Localhost / Development
LOCALHOST = [
    "127.0.0.1/32",      # IPv4 localhost
    "::1/128",           # IPv6 localhost
]

# Cloud Shell (for testing deployments)
CLOUD_SHELL_RANGES = [
    "35.235.240.0/20",   # Cloud Shell IP range
]

# =============================================================================
# PRESET CONFIGURATIONS
# =============================================================================

def get_allowed_ips(environment: str = 'production') -> list[str]:
    """
    Get allowed IP ranges for specified environment.

    Args:
        environment: One of 'development', 'staging', 'production', 'cloud_run_internal'

    Returns:
        List of IP addresses/CIDR ranges to whitelist

    Architectural Decisions:

    1. DEVELOPMENT:
       - Localhost only
       - For local testing with test API keys

    2. STAGING:
       - Internal GCP + Health checks + Cloud Shell
       - External webhooks (NowPayments, Telegram) for testing
       - Permissive for testing

    3. PRODUCTION:
       - ONLY external webhooks (NowPayments, Telegram)
       - DOES NOT include GCP ranges (Cloud Run → Cloud Run uses HMAC, not IP whitelist)
       - Minimal attack surface

    4. CLOUD_RUN_INTERNAL:
       - For services that ONLY receive internal Cloud Run traffic
       - Includes GCP internal ranges + health checks
       - Use when service has NO external webhooks

    5. DISABLED:
       - Empty list - IP whitelist disabled
       - Rely solely on HMAC authentication
       - Recommended for Cloud Run → Cloud Run communication
    """

    if environment == 'development':
        return LOCALHOST

    elif environment == 'staging':
        return (
            LOCALHOST +
            GCP_INTERNAL_VPC +
            GCP_HEALTH_CHECK_RANGES +
            CLOUD_SHELL_RANGES +
            NOWPAYMENTS_IPN_IPS +
            TELEGRAM_WEBHOOK_IPS
        )

    elif environment == 'production':
        # PRODUCTION: Only external webhooks
        # Cloud Run → Cloud Run communication uses HMAC authentication, NOT IP whitelist
        return (
            NOWPAYMENTS_IPN_IPS +
            TELEGRAM_WEBHOOK_IPS +
            GCP_HEALTH_CHECK_RANGES  # Required for Cloud Run health checks
        )

    elif environment == 'cloud_run_internal':
        # For services receiving ONLY internal Cloud Run traffic (no external webhooks)
        return (
            GCP_INTERNAL_VPC +
            GCP_HEALTH_CHECK_RANGES +
            GCP_US_CENTRAL1_RANGES  # Broad GCP range (only if using VPC connector)
        )

    elif environment == 'disabled':
        # IP whitelist disabled - use HMAC-only authentication
        # Recommended for Cloud Run → Cloud Run inter-service communication
        return []

    else:
        raise ValueError(f"Unknown environment: {environment}. "
                        "Use 'development', 'staging', 'production', 'cloud_run_internal', or 'disabled'")


# =============================================================================
# DEPLOYMENT-SPECIFIC CONFIGURATIONS
# =============================================================================

# PGP_SERVER_v1 endpoints and their recommended IP whitelist strategy:
#
# 1. /webhooks/notification (PGP_ORCHESTRATOR_v1 → PGP_SERVER_v1)
#    Recommendation: DISABLED - use HMAC authentication only
#    Reason: Cloud Run → Cloud Run, dynamic egress IPs
#
# 2. /webhooks/broadcast_trigger (Cloud Scheduler → PGP_SERVER_v1)
#    Recommendation: DISABLED - use HMAC authentication only
#    Reason: Cloud Scheduler IPs are dynamic, HMAC is sufficient
#
# 3. /webhooks/nowpayments (NowPayments → PGP_SERVER_v1)
#    Recommendation: ENABLED - use IP whitelist + HMAC
#    Reason: External webhook, known source IPs, defense in depth
#
# 4. /webhooks/telegram (Telegram → PGP_SERVER_v1)
#    Recommendation: ENABLED - use IP whitelist + secret token
#    Reason: External webhook, known source IPs, Telegram best practice

# Recommended configuration for PGP_SERVER_v1 in production:
# ALLOWED_IPS = get_allowed_ips('production')  # Only NowPayments + Telegram + health checks
# Apply IP whitelist ONLY to external webhook endpoints
# Use HMAC authentication for all internal Cloud Run → Cloud Run communication


# =============================================================================
# ENVIRONMENT VARIABLE HELPER
# =============================================================================

def get_allowed_ips_from_env() -> list[str]:
    """
    Get allowed IPs from environment variable with fallback to production config.

    Environment Variables:
        ENVIRONMENT: 'development', 'staging', 'production', 'cloud_run_internal', 'disabled'
        ALLOWED_IPS: Comma-separated IP ranges (overrides ENVIRONMENT if set)

    Returns:
        List of IP addresses/CIDR ranges

    Examples:
        ENVIRONMENT=production → NowPayments + Telegram + health checks
        ENVIRONMENT=disabled → Empty list (HMAC-only)
        ALLOWED_IPS=127.0.0.1,10.0.0.0/8 → Custom list (overrides ENVIRONMENT)
    """
    import os

    # Check for explicit ALLOWED_IPS environment variable (highest priority)
    allowed_ips_str = os.getenv('ALLOWED_IPS')
    if allowed_ips_str:
        return [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]

    # Fall back to ENVIRONMENT-based configuration
    environment = os.getenv('ENVIRONMENT', 'production')
    return get_allowed_ips(environment)


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_ip_list(ip_list: list[str]) -> None:
    """
    Validate that all entries in IP list are valid IP addresses or CIDR ranges.

    Args:
        ip_list: List of IP addresses/CIDR ranges to validate

    Raises:
        ValueError: If any entry is invalid

    Example:
        >>> validate_ip_list(['127.0.0.1', '10.0.0.0/8'])
        >>> validate_ip_list(['invalid.ip'])
        ValueError: Invalid IP address or CIDR range: invalid.ip
    """
    from ipaddress import ip_network

    for ip in ip_list:
        try:
            ip_network(ip, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid IP address or CIDR range: {ip} - {e}")


if __name__ == '__main__':
    """Test IP configuration loading."""
    print("IP Whitelist Configuration Test")
    print("=" * 80)

    for env in ['development', 'staging', 'production', 'cloud_run_internal', 'disabled']:
        ips = get_allowed_ips(env)
        print(f"\n{env.upper()}:")
        print(f"  Total ranges: {len(ips)}")
        if ips:
            print(f"  Ranges: {', '.join(ips[:5])}" + (" ..." if len(ips) > 5 else ""))
        else:
            print("  IP whitelist DISABLED (HMAC-only authentication)")

        # Validate
        try:
            validate_ip_list(ips)
            print(f"  ✅ All IP ranges valid")
        except ValueError as e:
            print(f"  ❌ Validation error: {e}")
