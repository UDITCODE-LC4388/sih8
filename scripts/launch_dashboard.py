#!/usr/bin/env python3
"""
Launcher Script for the ISRO Lunar Hazard-Map GCS Dashboard & Copilot Server

Starts the local HTTP server hosting the real-time terrain visualizer,
telemetry stream, and Groq-powered AI Mission Copilot.

Usage:
  python scripts/launch_dashboard.py --port 8080
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.navigation_interface.dashboard_server import start_dashboard_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Lunar GCS Dashboard & Copilot")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    print("=" * 72)
    print(" 🚀 ISRO LUNAR HAZARD-MAP SYSTEM: GROUND CONTROL STATION (GCS)")
    print("=" * 72)
    print(f" Web Visualizer & AI Copilot running at: http://localhost:{args.port}")
    print(" Press Ctrl+C to stop server.")
    print("=" * 72)

    server = start_dashboard_server(host=args.host, port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GCS server...")
        server.server_close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
