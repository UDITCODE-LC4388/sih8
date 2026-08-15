# ISRO Lunar Hazard-Map & Ground Control Station: Production Deployment & Security Guide

This document outlines the deployment architecture, hardening measures, security policies, and operational procedures for deploying the ISRO Lunar Hazard-Map Ground Control Station (GCS) in production.

---

## 1. Security Architecture & Threat Mitigation Matrix

| Vector | Threat | Mitigation Mechanism | Verification Test |
| :--- | :--- | :--- | :--- |
| **Path Traversal** | Accessing arbitrary host files via malicious `patch_id` or `layer` paths (e.g. `../../etc/passwd`) | Strict regex whitelist `^[a-zA-Z0-9_\-]+$` + directory escape rejection (`%00`, `..`, `/`) in `security_manager.validate_identifier()` | `test_path_traversal_sanitization` |
| **DoS & Flooding** | Resource exhaustion on 1D transect math & AI Copilot LLM generation | Thread-safe sliding-window rate limiting (180 req/min general, 40 req/min compute, burst limit 35/3s). Returns `HTTP 429` with `Retry-After` header | `test_rate_limiter_throttling` |
| **Clickjacking / MIME Sniffing / XSS** | UI embedding, content-type misinterpretation, script injection | Mandatory Aerospace Security Headers: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block` | `test_security_headers_structure` |
| **Unauthorized Access** | Unauthenticated callers accessing telemetry APIs | Optional configurable Bearer Token / Query parameter auth via `GCS_AUTH_TOKEN` environment variable. Returns `HTTP 401 Unauthorized` | `test_auth_token_verification` |
| **Buffer / Memory Overflow** | Giant POST payloads causing memory denial of service | Hard limit of 2 MB (`MAX_PAYLOAD_SIZE = 2097152 bytes`). Returns `HTTP 413 Payload Too Large` | `test_health_metrics_structure` |
| **Information Leakage** | Exposing stack traces or filesystem paths to clients | Generic, sanitized error JSON responses on 500 errors; full stack traces isolated to secure server log files | Server integration test |

---

## 2. Environment Configuration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Integer | `8080` | TCP port on which the GCS server listens |
| `GCS_AUTH_TOKEN` | String | *(Empty)* | Secret authorization token. If set, requires `Authorization: Bearer <token>` or `?auth=<token>` |
| `GROQ_API_KEY` | String | *(From .env)* | Groq API key for the LLaMA-3.3-70B AI Flight Copilot |
| `GCS_ENV` | String | `production` | Deployment environment identifier |

---

## 3. Production Health Probes & Monitoring

The server exposes a zero-overhead JSON health & telemetry endpoint at `/health` and `/api/health` compatible with Kubernetes Liveness/Readiness probes and Docker `HEALTHCHECK`.

### Health Check Response Example:
```json
{
  "status": "healthy",
  "deployment": "production_hardened",
  "uptime_seconds": 1284.5,
  "memory_resident_mb": 107.92,
  "security": {
    "rate_limiting": "enabled",
    "auth_protection": "open_demo",
    "path_traversal_guard": "enabled",
    "csp_policy": "enabled",
    "max_payload_bytes": 2097152
  },
  "service": "ISRO Lunar Hazard-Map Ground Control Station",
  "active_patches_available": 12,
  "ai_copilot_model": "llama-3.3-70b-versatile"
}
```

### Kubernetes Pod Spec Example:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 15
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## 4. Containerized Deployment (Docker / Compose)

### Single Command Launch:
```bash
# Build and run container with non-root security privileges and resource limits
docker-compose up -d --build
```

### Standalone Docker Run:
```bash
docker build -t isro-lunar-gcs:latest .
docker run -d \
  -p 8080:8080 \
  --name isro_gcs \
  --restart unless-stopped \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -e GROQ_API_KEY="your_groq_key" \
  -e GCS_AUTH_TOKEN="your_secure_auth_token" \
  isro-lunar-gcs:latest
```

---

## 5. Reverse Proxy & SSL Termination (Nginx Configuration)

When deploying behind an Nginx reverse proxy with SSL/TLS termination:

```nginx
server {
    listen 443 ssl http2;
    server_name gcs.isro.gov.in;

    ssl_certificate /etc/ssl/certs/gcs_bundle.crt;
    ssl_certificate_key /etc/ssl/private/gcs.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        access_log off;
    }
}
```
