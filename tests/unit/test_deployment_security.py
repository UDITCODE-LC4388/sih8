"""
Unit tests for Deployment Protection & Security Middleware (Module 6)
"""

import os
import pytest
from src.navigation_interface.security import RateLimiter, SecurityManager, MAX_PAYLOAD_SIZE


def test_path_traversal_sanitization():
    sec = SecurityManager()
    
    # Safe identifiers
    assert sec.validate_identifier("ch2_tmc_patch_001_r25000_c4000") is True
    assert sec.validate_identifier("lro_nac_patch_01_01_m1529414132re_r8000") is True
    assert sec.validate_identifier("dem") is True
    assert sec.validate_identifier("ortho") is True
    assert sec.validate_identifier("hazard") is True
    assert sec.validate_identifier("slope") is True

    # Malicious path traversal attempts
    assert sec.validate_identifier("../../etc/passwd") is False
    assert sec.validate_identifier("..\\..\\windows\\system32") is False
    assert sec.validate_identifier("patch_001; rm -rf /") is False
    assert sec.validate_identifier("patch_001%00") is False
    assert sec.validate_identifier("patch/with/subdirs") is False
    assert sec.validate_identifier("<script>alert(1)</script>") is False
    assert sec.validate_identifier("") is False


def test_rate_limiter_throttling():
    limiter = RateLimiter(requests_per_minute=5, burst_limit=3)
    ip = "192.168.1.100"

    # First 3 requests in burst window should be allowed
    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is True
    assert limiter.is_allowed(ip)[0] is True

    # 4th immediate burst request should be blocked
    allowed, retry_after = limiter.is_allowed(ip)
    assert allowed is False
    assert retry_after > 0


def test_security_headers_structure():
    sec = SecurityManager()
    headers = sec.get_security_headers()

    assert "Content-Security-Policy" in headers
    assert "X-Content-Type-Options" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert "Permissions-Policy" in headers


def test_auth_token_verification(monkeypatch):
    sec = SecurityManager()
    
    # Open mode when no token is set
    assert sec.verify_auth({}, {}) is True

    # Set auth token in environment
    monkeypatch.setenv("GCS_AUTH_TOKEN", "isro_secret_flight_token_123")
    sec_locked = SecurityManager()
    assert sec_locked.auth_required is True

    # Invalid requests
    assert sec_locked.verify_auth({}, {}) is False
    assert sec_locked.verify_auth({"Authorization": "Bearer wrong_token"}, {}) is False
    assert sec_locked.verify_auth({}, {"auth": ["wrong_token"]}) is False

    # Valid Bearer token
    assert sec_locked.verify_auth({"Authorization": "Bearer isro_secret_flight_token_123"}, {}) is True
    # Valid query param
    assert sec_locked.verify_auth({}, {"auth": ["isro_secret_flight_token_123"]}) is True


def test_health_metrics_structure():
    sec = SecurityManager()
    metrics = sec.get_health_metrics({"test_meta": 42})

    assert metrics["status"] == "healthy"
    assert metrics["deployment"] == "production_hardened"
    assert "uptime_seconds" in metrics
    assert metrics["security"]["rate_limiting"] == "enabled"
    assert metrics["security"]["path_traversal_guard"] == "enabled"
    assert metrics["security"]["max_payload_bytes"] == MAX_PAYLOAD_SIZE
    assert metrics["test_meta"] == 42
