#!/usr/bin/env python3
"""
Trading System Health Server

Simple HTTP server exposing /health endpoint for external monitoring.
Reads health status from the file written by LiveTradingEngine.

Usage:
    python health_server.py [--port 8080] [--health-file /path/to/health.json]

Endpoints:
    GET /health     - Returns health status (200 OK or 503 Unhealthy)
    GET /metrics    - Returns detailed metrics
    GET /           - Simple status page

For external monitoring (UptimeRobot, Pingdom, etc.), point to:
    http://your-server:8080/health
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Configuration
DEFAULT_PORT = 8080
DEFAULT_HEALTH_FILE = "/opt/trading-system/data/health.json"
MAX_HEALTH_AGE_SECONDS = 120  # Health file must be updated within 2 minutes


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health endpoints."""

    health_file: str = DEFAULT_HEALTH_FILE

    def log_message(self, format, *args):
        """Custom log format."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {args[0]}")

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status: int = 200):
        """Send plain text response."""
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_health_file(self) -> tuple[dict | None, str | None]:
        """
        Read and validate health file.

        Returns:
            (health_data, error_message)
        """
        health_path = Path(self.health_file)

        if not health_path.exists():
            return None, "Health file not found"

        try:
            file_age = time.time() - health_path.stat().st_mtime
            if file_age > MAX_HEALTH_AGE_SECONDS:
                return None, f"Health file stale ({int(file_age)}s old)"

            with open(health_path) as f:
                data = json.load(f)

            # Validate required fields
            if "status" not in data:
                return None, "Health file missing 'status' field"

            data["_file_age_seconds"] = int(file_age)
            return data, None

        except json.JSONDecodeError as e:
            return None, f"Invalid JSON in health file: {e}"
        except Exception as e:
            return None, f"Error reading health file: {e}"

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.handle_health()
        elif self.path == "/metrics":
            self.handle_metrics()
        elif self.path == "/":
            self.handle_index()
        else:
            self.send_error(404, "Not Found")

    def handle_health(self):
        """
        Health check endpoint.

        Returns 200 if healthy, 503 if unhealthy.
        """
        health_data, error = self.read_health_file()

        if error:
            self.send_json(
                {
                    "status": "unhealthy",
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
                status=503,
            )
            return

        status = health_data.get("status", "unknown")
        is_healthy = status in ("running", "healthy")

        response = {
            "status": "healthy" if is_healthy else "unhealthy",
            "engine_status": status,
            "uptime_seconds": health_data.get("uptime_seconds", 0),
            "last_update_age_seconds": health_data.get("_file_age_seconds", 0),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        self.send_json(response, status=200 if is_healthy else 503)

    def handle_metrics(self):
        """
        Detailed metrics endpoint.

        Returns full health data for monitoring systems.
        """
        health_data, error = self.read_health_file()

        if error:
            self.send_json({"error": error}, status=503)
            return

        self.send_json(health_data, status=200)

    def handle_index(self):
        """Simple status page."""
        health_data, error = self.read_health_file()

        if error:
            self.send_text(f"UNHEALTHY: {error}", status=503)
            return

        status = health_data.get("status", "unknown")
        uptime = health_data.get("uptime_seconds", 0)
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)

        text = f"""Trading System Status
=====================
Status: {status.upper()}
Uptime: {hours}h {minutes}m {seconds}s
Last Update: {health_data.get('_file_age_seconds', '?')}s ago

Endpoints:
  /health  - Health check (for monitoring)
  /metrics - Full metrics (JSON)
"""
        self.send_text(text, status=200)


def run_server(port: int, health_file: str):
    """Run the health check HTTP server."""
    HealthCheckHandler.health_file = health_file

    server_address = ("", port)
    httpd = HTTPServer(server_address, HealthCheckHandler)

    print(f"Health server starting on port {port}")
    print(f"Health file: {health_file}")
    print(f"Endpoints: /health, /metrics, /")
    print("")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="Trading System Health Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python health_server.py
  python health_server.py --port 9090
  python health_server.py --health-file /custom/path/health.json

For systemd, see deploy/systemd/trading-system-health.service
        """,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("HEALTH_PORT", DEFAULT_PORT)),
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--health-file",
        default=os.environ.get("HEALTH_FILE", DEFAULT_HEALTH_FILE),
        help=f"Path to health.json file (default: {DEFAULT_HEALTH_FILE})",
    )

    args = parser.parse_args()
    run_server(args.port, args.health_file)


if __name__ == "__main__":
    main()
