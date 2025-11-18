"""
Safe IP address extraction from HTTP requests.

This module provides secure IP extraction from X-Forwarded-For headers
to prevent IP spoofing attacks in Cloud Run environments.

Security Considerations:
- X-Forwarded-For can be spoofed by malicious clients
- Cloud Run adds its proxy IP as the rightmost value
- We must use the rightmost client IP (before Cloud Run's proxy)

Example X-Forwarded-For chain:
    "1.2.3.4, 5.6.7.8, 9.10.11.12"
     ^^^^^^^  ^^^^^^^  ^^^^^^^^^^^
     spoofed  spoofed  real client (from Cloud Run)

For Cloud Run with 1 trusted proxy (Cloud Run itself):
    trusted_proxy_count=1 → use IP at position -2 (before Cloud Run)

References:
- OWASP: A01:2021 - Broken Access Control
- CWE-290: Authentication Bypass by Spoofing
- PGP_SERVER_v1/security/IP_EXTRACTION_SECURITY.md
"""

from typing import Optional
from flask import Request


def get_real_client_ip(
    request: Request,
    trusted_proxy_count: int = 1
) -> str:
    """
    Safely extract the real client IP address from an HTTP request.

    This function prevents IP spoofing by using the rightmost IP address
    in the X-Forwarded-For header, accounting for trusted proxies.

    Args:
        request: Flask request object
        trusted_proxy_count: Number of trusted proxies between client and app.
                           For Cloud Run: 1 (Cloud Run's proxy)
                           For Cloud Run + Cloud Load Balancer: 2

    Returns:
        Real client IP address as string

    Raises:
        ValueError: If trusted_proxy_count is invalid

    Example:
        >>> # Cloud Run environment (1 trusted proxy)
        >>> request.headers['X-Forwarded-For'] = "1.2.3.4, 5.6.7.8, 9.10.11.12"
        >>> get_real_client_ip(request, trusted_proxy_count=1)
        '5.6.7.8'  # Second from right (before Cloud Run proxy)

        >>> # Direct connection (no X-Forwarded-For)
        >>> request.remote_addr = "10.20.30.40"
        >>> get_real_client_ip(request)
        '10.20.30.40'

    Security Notes:
        - NEVER use the leftmost IP (easily spoofed)
        - NEVER trust X-Forwarded-For without validation
        - ALWAYS account for your infrastructure's proxy count
        - Cloud Run adds exactly 1 proxy to X-Forwarded-For
    """
    if trusted_proxy_count < 0:
        raise ValueError("trusted_proxy_count must be >= 0")

    # Try to get X-Forwarded-For header
    x_forwarded_for = request.headers.get('X-Forwarded-For')

    if not x_forwarded_for:
        # No X-Forwarded-For header, use direct connection IP
        return request.remote_addr or "unknown"

    # Parse comma-separated IP list
    ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]

    # Remove empty strings
    ip_list = [ip for ip in ip_list if ip]

    if not ip_list:
        # Empty X-Forwarded-For, fallback to remote_addr
        return request.remote_addr or "unknown"

    # Calculate position of real client IP
    # Formula: use IP at position -(trusted_proxy_count + 1)
    #
    # Examples:
    #   trusted_proxy_count=1 → position -2 (skip rightmost)
    #   trusted_proxy_count=2 → position -3 (skip 2 rightmost)
    #
    # IP chain: [spoofed, spoofed, real_client, proxy1, proxy2...]
    #                               ^^^^^^^^^^ we want this

    client_ip_position = -(trusted_proxy_count + 1)

    try:
        client_ip = ip_list[client_ip_position]
    except IndexError:
        # Not enough IPs in chain, use the first one
        # This handles cases where there are fewer IPs than expected
        client_ip = ip_list[0]

    return client_ip


def get_all_forwarded_ips(request: Request) -> list[str]:
    """
    Get all IP addresses from X-Forwarded-For header (for logging/debugging).

    Args:
        request: Flask request object

    Returns:
        List of all IP addresses in X-Forwarded-For chain

    Example:
        >>> request.headers['X-Forwarded-For'] = "1.2.3.4, 5.6.7.8, 9.10.11.12"
        >>> get_all_forwarded_ips(request)
        ['1.2.3.4', '5.6.7.8', '9.10.11.12']
    """
    x_forwarded_for = request.headers.get('X-Forwarded-For', '')

    if not x_forwarded_for:
        return []

    ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]
    return [ip for ip in ip_list if ip]


def validate_ip_format(ip_address: str) -> bool:
    """
    Basic IP address format validation (IPv4 only for now).

    Args:
        ip_address: IP address string to validate

    Returns:
        True if valid IPv4 format, False otherwise

    Example:
        >>> validate_ip_format("192.168.1.1")
        True
        >>> validate_ip_format("999.999.999.999")
        False
        >>> validate_ip_format("not-an-ip")
        False

    Note:
        This is a basic validation. For production use with IPv6,
        consider using ipaddress.ip_address() from Python stdlib.
    """
    if not ip_address or ip_address == "unknown":
        return False

    parts = ip_address.split('.')

    if len(parts) != 4:
        return False

    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def is_private_ip(ip_address: str) -> bool:
    """
    Check if an IP address is in a private range (RFC 1918).

    Args:
        ip_address: IP address string to check

    Returns:
        True if IP is in private range, False otherwise

    Private IP ranges:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
        - 127.0.0.0/8 (loopback)

    Example:
        >>> is_private_ip("192.168.1.1")
        True
        >>> is_private_ip("8.8.8.8")
        False
        >>> is_private_ip("127.0.0.1")
        True
    """
    if not validate_ip_format(ip_address):
        return False

    parts = [int(p) for p in ip_address.split('.')]

    # 10.0.0.0/8
    if parts[0] == 10:
        return True

    # 172.16.0.0/12
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return True

    # 192.168.0.0/16
    if parts[0] == 192 and parts[1] == 168:
        return True

    # 127.0.0.0/8 (loopback)
    if parts[0] == 127:
        return True

    return False
