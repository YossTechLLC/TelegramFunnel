#!/usr/bin/env python
"""
IP whitelist middleware for Flask endpoints.
Restricts access to known Cloud Run egress IPs.
"""
import logging
from functools import wraps
from flask import request, abort
from ipaddress import ip_address, ip_network
from typing import List
from PGP_COMMON.utils import get_real_client_ip

logger = logging.getLogger(__name__)


class IPWhitelist:
    """
    IP-based access control for webhook endpoints.

    Security:
    - Checks X-Forwarded-For header (behind proxy)
    - Supports CIDR notation for IP ranges
    - Logs all access attempts
    """

    def __init__(self, allowed_ips: List[str]):
        """
        Initialize IP whitelist.

        Args:
            allowed_ips: List of allowed IPs/CIDR ranges
                Example: ['10.0.0.0/8', '35.123.45.67']
        """
        self.allowed_networks = [ip_network(ip) for ip in allowed_ips]
        logger.info("🔒 [IP_WHITELIST] Initialized with {} networks".format(
            len(self.allowed_networks)
        ))

    def is_allowed(self, client_ip: str) -> bool:
        """
        Check if client IP is in whitelist.

        Args:
            client_ip: Client IP address string

        Returns:
            True if allowed, False otherwise
        """
        try:
            ip = ip_address(client_ip)

            for network in self.allowed_networks:
                if ip in network:
                    return True

            return False

        except ValueError as e:
            logger.error("❌ [IP_WHITELIST] Invalid IP format: {} - {}".format(
                client_ip, e
            ))
            return False

    def require_whitelisted_ip(self, f):
        """
        Decorator to restrict Flask route to whitelisted IPs.

        Usage:
            @app.route('/webhook', methods=['POST'])
            @ip_whitelist.require_whitelisted_ip
            def webhook():
                return jsonify({'status': 'ok'})

        Security Note:
            Uses get_real_client_ip() to prevent IP spoofing via X-Forwarded-For.
            Cloud Run adds 1 trusted proxy, so we use trusted_proxy_count=1.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get real client IP (secure against spoofing)
            # Cloud Run environment has 1 trusted proxy
            client_ip = get_real_client_ip(request, trusted_proxy_count=1)

            if not self.is_allowed(client_ip):
                logger.warning("⚠️ [IP_WHITELIST] Blocked request from {}".format(
                    client_ip
                ))
                abort(403, "Unauthorized IP address")

            logger.info("✅ [IP_WHITELIST] Allowed request from {}".format(
                client_ip
            ))
            return f(*args, **kwargs)

        return decorated_function


def init_ip_whitelist(allowed_ips: List[str]) -> IPWhitelist:
    """
    Factory function to initialize IP whitelist.

    Args:
        allowed_ips: List of allowed IPs/CIDR ranges

    Returns:
        IPWhitelist instance
    """
    return IPWhitelist(allowed_ips)
