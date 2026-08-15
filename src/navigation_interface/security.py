"""
Deployment Protection & Security Middleware (Module 6)

Provides production-grade deployment hardening for the Lunar GCS server:
1. Aerospace Security Headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
2. Thread-Safe Sliding Window IP Rate Limiting & DoS Throttling
3. Strict Path Traversal & Identifier Sanitization Guard
4. Configurable Authentication Token / API Key Guard (GCS_AUTH_TOKEN)
5. Request Payload Caps & Resource Protection
6. Production System Health & Telemetry Metrics
"""

from __future__ import annotations

import os
import re
import time
import threading
from collections import defaultdict, deque
from typing import Any, Dict, Optional, Tuple

# Strict whitelist: Only alphanumeric, underscore, and hyphen allowed for patch IDs & layers
SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
TRAVERSAL_REGEX = re.compile(r"(\.\./|\.\.\\|%2e%2e|%00|\0)", re.IGNORECASE)

# Maximum allowed POST payload size (2 Megabytes)
MAX_PAYLOAD_SIZE = 2 * 1024 * 1024


class RateLimiter:
    """Thread-safe sliding-window rate limiter with per-IP tracking."""

    def __init__(self, requests_per_minute: int = 120, burst_limit: int = 25):
        self.rpm = requests_per_minute
        self.burst_limit = burst_limit
        self.window_seconds = 60.0
        self._history: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str, cost: int = 1) -> Tuple[bool, int]:
        """
        Checks if the client IP is within rate limits.
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        window_start = now - self.window_seconds
        burst_window_start = now - 3.0  # 3 second burst window

        with self._lock:
            timestamps = self._history[client_ip]

            # Purge expired timestamps older than 60s
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            # Check burst limit in last 3 seconds
            burst_count = sum(1 for t in timestamps if t >= burst_window_start)
            if burst_count >= self.burst_limit:
                return False, 3

            # Check total requests in last 60 seconds
            if len(timestamps) + cost > self.rpm:
                oldest = timestamps[0] if timestamps else now
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return False, retry_after

            for _ in range(cost):
                timestamps.append(now)

            return True, 0

    def cleanup(self):
        """Cleans up stale IPs from memory."""
        now = time.time()
        window_start = now - self.window_seconds
        with self._lock:
            stale_ips = [ip for ip, dq in self._history.items() if not dq or dq[-1] < window_start]
            for ip in stale_ips:
                del self._history[ip]


class SecurityManager:
    """Master security manager for HTTP requests."""

    def __init__(self):
        self.general_limiter = RateLimiter(requests_per_minute=180, burst_limit=35)
        self.compute_limiter = RateLimiter(requests_per_minute=40, burst_limit=10)
        self.auth_token = os.environ.get("GCS_AUTH_TOKEN", "").strip()
        self.start_time = time.time()

    @property
    def auth_required(self) -> bool:
        return bool(self.auth_token)

    def validate_identifier(self, identifier: str) -> bool:
        """Validates that an identifier (patch_id, layer name) contains no traversal or invalid chars."""
        if not identifier or len(identifier) > 128:
            return False
        if TRAVERSAL_REGEX.search(identifier):
            return False
        return bool(SAFE_IDENTIFIER_REGEX.match(identifier))

    def verify_auth(self, headers: Any, query_params: Dict[str, list]) -> bool:
        """Verifies Bearer token or ?auth= query parameter if GCS_AUTH_TOKEN is active."""
        if not self.auth_required:
            return True

        # Check Authorization header: Bearer <token>
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token == self.auth_token:
                return True

        # Check query param ?auth=<token>
        auth_query = query_params.get("auth", [""])[0].strip()
        if auth_query == self.auth_token:
            return True

        return False

    def get_security_headers(self) -> Dict[str, str]:
        """Returns aerospace-grade security headers to attach to every HTTP response."""
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none';"
        )
        return {
            "Content-Security-Policy": csp,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Deployment-Protection": "Active (ISRO Ground Truth Guard)",
        }

    def get_health_metrics(self, extra_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns production readiness and system health metrics."""
        uptime = round(time.time() - self.start_time, 1)
        
        # Memory usage in MB if resource module available
        mem_mb = 0.0
        try:
            import resource
            # ru_maxrss is in KB on Linux, bytes on macOS
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            mem_mb = round(rss / (1024 * 1024) if sys_is_macos() else rss / 1024, 2)
        except Exception:
            pass

        metrics = {
            "status": "healthy",
            "deployment": "production_hardened",
            "uptime_seconds": uptime,
            "memory_resident_mb": mem_mb,
            "security": {
                "rate_limiting": "enabled",
                "auth_protection": "active" if self.auth_required else "open_demo",
                "path_traversal_guard": "enabled",
                "csp_policy": "enabled",
                "max_payload_bytes": MAX_PAYLOAD_SIZE,
            },
        }
        if extra_meta:
            metrics.update(extra_meta)
        return metrics


def sys_is_macos() -> bool:
    import platform
    return platform.system() == "Darwin"


# Global singleton instance
security_manager = SecurityManager()
