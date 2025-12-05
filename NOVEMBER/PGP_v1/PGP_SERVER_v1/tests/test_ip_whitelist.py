#!/usr/bin/env python
"""
Unit tests for IP whitelist validation and configuration.

Tests the IP whitelist middleware and allowed_ips configuration module
to ensure proper IP validation and access control.

Test Coverage:
- IP validation (IPv4, IPv6, CIDR ranges)
- Whitelist matching logic
- Environment-based configuration loading
- Flask decorator integration
- X-Forwarded-For header handling
"""
import pytest
import os
from unittest.mock import Mock, patch
from flask import Flask
from ipaddress import ip_network

from PGP_SERVER_v1.security.ip_whitelist import IPWhitelist, init_ip_whitelist
from PGP_SERVER_v1.security.allowed_ips import (
    get_allowed_ips,
    get_allowed_ips_from_env,
    validate_ip_list,
    NOWPAYMENTS_IPN_IPS,
    TELEGRAM_WEBHOOK_IPS,
    GCP_HEALTH_CHECK_RANGES
)


class TestIPWhitelistValidation:
    """Test suite for IP address validation and matching."""

    def setup_method(self):
        """Set up test fixtures."""
        self.allowed_ips = [
            '127.0.0.1',           # Single IP
            '10.0.0.0/8',          # CIDR range
            '192.168.1.0/24',      # Smaller CIDR range
        ]
        self.ip_whitelist = IPWhitelist(self.allowed_ips)

    def test_single_ip_allowed(self):
        """Test that single whitelisted IP is allowed."""
        assert self.ip_whitelist.is_allowed('127.0.0.1') is True

    def test_single_ip_blocked(self):
        """Test that non-whitelisted IP is blocked."""
        assert self.ip_whitelist.is_allowed('8.8.8.8') is False

    def test_cidr_range_allowed(self):
        """Test that IP within CIDR range is allowed."""
        assert self.ip_whitelist.is_allowed('10.5.10.20') is True
        assert self.ip_whitelist.is_allowed('10.255.255.255') is True

    def test_cidr_range_blocked(self):
        """Test that IP outside CIDR range is blocked."""
        assert self.ip_whitelist.is_allowed('11.0.0.1') is False

    def test_small_cidr_range(self):
        """Test /24 CIDR range validation."""
        # Inside range
        assert self.ip_whitelist.is_allowed('192.168.1.1') is True
        assert self.ip_whitelist.is_allowed('192.168.1.254') is True

        # Outside range
        assert self.ip_whitelist.is_allowed('192.168.2.1') is False
        assert self.ip_whitelist.is_allowed('192.168.0.1') is False

    def test_invalid_ip_format(self):
        """Test that invalid IP format is rejected."""
        assert self.ip_whitelist.is_allowed('not.an.ip') is False
        assert self.ip_whitelist.is_allowed('999.999.999.999') is False
        assert self.ip_whitelist.is_allowed('') is False

    def test_ipv6_support(self):
        """Test IPv6 address support."""
        ipv6_whitelist = IPWhitelist(['::1', '2001:db8::/32'])

        # IPv6 localhost
        assert ipv6_whitelist.is_allowed('::1') is True

        # IPv6 range
        assert ipv6_whitelist.is_allowed('2001:db8::1') is True
        assert ipv6_whitelist.is_allowed('2001:db8:ffff::1') is True

        # Outside range
        assert ipv6_whitelist.is_allowed('2001:db9::1') is False


class TestIPWhitelistDecorator:
    """Test suite for Flask decorator integration."""

    def setup_method(self):
        """Set up Flask app with IP whitelist."""
        self.app = Flask(__name__)
        self.ip_whitelist = IPWhitelist(['127.0.0.1', '10.0.0.0/8'])

        @self.app.route('/test', methods=['GET', 'POST'])
        @self.ip_whitelist.require_whitelisted_ip
        def test_endpoint():
            return {'status': 'ok'}, 200

        self.client = self.app.test_client()

    def test_allowed_ip_access(self):
        """Test that whitelisted IP can access endpoint."""
        response = self.client.get(
            '/test',
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        )
        assert response.status_code == 200

    def test_blocked_ip_access(self):
        """Test that non-whitelisted IP is blocked."""
        response = self.client.get(
            '/test',
            environ_base={'REMOTE_ADDR': '8.8.8.8'}
        )
        assert response.status_code == 403

    def test_x_forwarded_for_header(self):
        """Test that X-Forwarded-For header is used (behind proxy)."""
        # Whitelisted IP in X-Forwarded-For
        response = self.client.get(
            '/test',
            headers={'X-Forwarded-For': '127.0.0.1'},
            environ_base={'REMOTE_ADDR': '8.8.8.8'}  # Proxy IP
        )
        assert response.status_code == 200

    def test_x_forwarded_for_multiple_ips(self):
        """Test handling of multiple IPs in X-Forwarded-For (use first)."""
        # First IP is whitelisted
        response = self.client.get(
            '/test',
            headers={'X-Forwarded-For': '127.0.0.1, 8.8.8.8, 1.1.1.1'},
            environ_base={'REMOTE_ADDR': '8.8.8.8'}
        )
        assert response.status_code == 200

    def test_x_forwarded_for_blocked(self):
        """Test that blocked IP in X-Forwarded-For is rejected."""
        response = self.client.get(
            '/test',
            headers={'X-Forwarded-For': '8.8.8.8'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        )
        assert response.status_code == 403

    def test_cidr_range_access(self):
        """Test that IP in CIDR range can access endpoint."""
        response = self.client.get(
            '/test',
            environ_base={'REMOTE_ADDR': '10.50.100.200'}
        )
        assert response.status_code == 200


class TestAllowedIPsConfiguration:
    """Test suite for allowed_ips.py configuration module."""

    def test_development_environment(self):
        """Test development environment configuration."""
        ips = get_allowed_ips('development')

        # Should only have localhost
        assert '127.0.0.1/32' in ips or '127.0.0.1' in [ip.split('/')[0] for ip in ips]
        # Should be minimal
        assert len(ips) <= 2  # IPv4 and IPv6 localhost

    def test_staging_environment(self):
        """Test staging environment configuration."""
        ips = get_allowed_ips('staging')

        # Should include multiple ranges
        assert len(ips) > 5

        # Should include external webhooks
        assert any(ip in ips for ip in NOWPAYMENTS_IPN_IPS)
        assert any(ip in ips for ip in TELEGRAM_WEBHOOK_IPS)

        # Should include GCP ranges
        assert any(ip in ips for ip in GCP_HEALTH_CHECK_RANGES)

    def test_production_environment(self):
        """Test production environment configuration."""
        ips = get_allowed_ips('production')

        # Should include external webhooks
        assert any(ip in ips for ip in NOWPAYMENTS_IPN_IPS)
        assert any(ip in ips for ip in TELEGRAM_WEBHOOK_IPS)

        # Should include health check ranges (required for Cloud Run)
        assert any(ip in ips for ip in GCP_HEALTH_CHECK_RANGES)

        # Should NOT include broad GCP internal ranges (use HMAC for Cloud Run → Cloud Run)
        assert '10.0.0.0/8' not in ips

    def test_cloud_run_internal_environment(self):
        """Test cloud_run_internal environment configuration."""
        ips = get_allowed_ips('cloud_run_internal')

        # Should include GCP ranges
        assert '10.0.0.0/8' in ips  # Internal VPC
        assert any(ip in ips for ip in GCP_HEALTH_CHECK_RANGES)

        # May include us-central1 ranges
        assert len(ips) > 3

    def test_disabled_environment(self):
        """Test disabled environment (HMAC-only authentication)."""
        ips = get_allowed_ips('disabled')

        # Should be empty list
        assert ips == []

    def test_invalid_environment(self):
        """Test that invalid environment raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_allowed_ips('invalid_env')

        assert 'Unknown environment' in str(exc_info.value)

    def test_all_configurations_are_valid_ips(self):
        """Test that all preset configurations contain valid IP ranges."""
        for env in ['development', 'staging', 'production', 'cloud_run_internal']:
            ips = get_allowed_ips(env)
            validate_ip_list(ips)  # Should not raise


class TestEnvironmentVariableLoading:
    """Test suite for environment variable-based configuration."""

    def test_explicit_allowed_ips_override(self):
        """Test that ALLOWED_IPS environment variable overrides ENVIRONMENT."""
        with patch.dict(os.environ, {
            'ALLOWED_IPS': '192.168.1.1,10.0.0.0/24',
            'ENVIRONMENT': 'production'  # Should be ignored
        }):
            ips = get_allowed_ips_from_env()

            assert '192.168.1.1' in ips
            assert '10.0.0.0/24' in ips
            assert len(ips) == 2

    def test_environment_variable_fallback(self):
        """Test that ENVIRONMENT variable is used when ALLOWED_IPS not set."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            ips = get_allowed_ips_from_env()

            # Should get development config
            assert '127.0.0.1/32' in ips or any('127.0.0.1' in ip for ip in ips)

    def test_default_to_production(self):
        """Test that configuration defaults to production when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            ips = get_allowed_ips_from_env()

            # Should get production config
            assert any(ip in ips for ip in NOWPAYMENTS_IPN_IPS)

    def test_allowed_ips_whitespace_handling(self):
        """Test that whitespace in ALLOWED_IPS is handled correctly."""
        with patch.dict(os.environ, {
            'ALLOWED_IPS': ' 127.0.0.1 , 10.0.0.0/8 ,  192.168.1.1  '
        }):
            ips = get_allowed_ips_from_env()

            # Should trim whitespace
            assert '127.0.0.1' in ips
            assert '10.0.0.0/8' in ips
            assert '192.168.1.1' in ips
            assert len(ips) == 3

    def test_empty_allowed_ips(self):
        """Test handling of empty ALLOWED_IPS variable."""
        with patch.dict(os.environ, {'ALLOWED_IPS': ''}):
            ips = get_allowed_ips_from_env()

            # Should return empty list (IP whitelist disabled)
            assert ips == []


class TestIPValidation:
    """Test suite for IP validation utilities."""

    def test_validate_valid_ips(self):
        """Test validation of valid IP list."""
        valid_ips = [
            '127.0.0.1',
            '10.0.0.0/8',
            '192.168.1.0/24',
            '8.8.8.8',
            '::1',
            '2001:db8::/32'
        ]

        # Should not raise
        validate_ip_list(valid_ips)

    def test_validate_invalid_ips(self):
        """Test that invalid IPs raise ValueError."""
        invalid_ips = [
            '127.0.0.1',
            'not.an.ip',  # Invalid
            '10.0.0.0/8'
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_ip_list(invalid_ips)

        assert 'Invalid IP address or CIDR range' in str(exc_info.value)
        assert 'not.an.ip' in str(exc_info.value)

    def test_validate_invalid_cidr(self):
        """Test that invalid CIDR notation raises ValueError."""
        invalid_cidrs = [
            '10.0.0.0/8',
            '192.168.1.0/99',  # Invalid CIDR prefix length
        ]

        with pytest.raises(ValueError):
            validate_ip_list(invalid_cidrs)


class TestExternalWebhookIPRanges:
    """Test suite for external webhook IP configurations."""

    def test_nowpayments_ips_configured(self):
        """Test that NowPayments IPN IPs are configured."""
        assert len(NOWPAYMENTS_IPN_IPS) >= 3
        # Validate all IPs
        validate_ip_list(NOWPAYMENTS_IPN_IPS)

    def test_telegram_ips_configured(self):
        """Test that Telegram webhook IPs are configured."""
        assert len(TELEGRAM_WEBHOOK_IPS) >= 2
        # Validate all IPs
        validate_ip_list(TELEGRAM_WEBHOOK_IPS)

    def test_production_includes_all_external_webhooks(self):
        """Test that production config includes all external webhook IPs."""
        prod_ips = get_allowed_ips('production')

        # Should include all NowPayments IPs
        for ip in NOWPAYMENTS_IPN_IPS:
            assert ip in prod_ips

        # Should include all Telegram ranges
        for ip in TELEGRAM_WEBHOOK_IPS:
            assert ip in prod_ips


class TestIPWhitelistFactory:
    """Test suite for init_ip_whitelist factory function."""

    def test_factory_creates_instance(self):
        """Test that factory function creates IPWhitelist instance."""
        allowed_ips = ['127.0.0.1', '10.0.0.0/8']
        ip_whitelist = init_ip_whitelist(allowed_ips)

        assert isinstance(ip_whitelist, IPWhitelist)
        assert ip_whitelist.is_allowed('127.0.0.1') is True

    def test_factory_with_empty_list(self):
        """Test factory with empty list (IP whitelist disabled)."""
        ip_whitelist = init_ip_whitelist([])

        assert isinstance(ip_whitelist, IPWhitelist)
        # All IPs should be blocked
        assert ip_whitelist.is_allowed('127.0.0.1') is False
        assert ip_whitelist.is_allowed('10.0.0.1') is False


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_localhost_variants(self):
        """Test different localhost IP representations."""
        whitelist = IPWhitelist(['127.0.0.1/8'])  # Localhost CIDR

        assert whitelist.is_allowed('127.0.0.1') is True
        assert whitelist.is_allowed('127.0.0.2') is True
        assert whitelist.is_allowed('127.255.255.255') is True

    def test_network_address_boundary(self):
        """Test CIDR range boundaries."""
        whitelist = IPWhitelist(['192.168.1.0/24'])

        # Network address
        assert whitelist.is_allowed('192.168.1.0') is True

        # Broadcast address
        assert whitelist.is_allowed('192.168.1.255') is True

        # Just outside range
        assert whitelist.is_allowed('192.168.0.255') is False
        assert whitelist.is_allowed('192.168.2.0') is False

    def test_overlapping_ranges(self):
        """Test that overlapping CIDR ranges work correctly."""
        whitelist = IPWhitelist([
            '10.0.0.0/8',      # Broader range
            '10.50.0.0/16',    # Narrower range (overlap)
        ])

        # Should be allowed (matches both ranges)
        assert whitelist.is_allowed('10.50.100.200') is True

        # Should be allowed (matches broader range only)
        assert whitelist.is_allowed('10.100.50.1') is True

    def test_empty_x_forwarded_for(self):
        """Test handling of empty X-Forwarded-For header."""
        app = Flask(__name__)
        whitelist = IPWhitelist(['127.0.0.1'])

        @app.route('/test')
        @whitelist.require_whitelisted_ip
        def test_endpoint():
            return {'status': 'ok'}

        client = app.test_client()

        # Empty X-Forwarded-For should fall back to REMOTE_ADDR
        response = client.get(
            '/test',
            headers={'X-Forwarded-For': ''},
            environ_base={'REMOTE_ADDR': '127.0.0.1'}
        )
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
