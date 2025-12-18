#!/usr/bin/env python3
"""
Simple HTTP server to serve the dashboard on port 9205.
"""
import http.server
import os
import socketserver

PORT = 9205
DASHBOARD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "dashboard"
)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)


def main():
    os.chdir(DASHBOARD_DIR)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving dashboard at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping dashboard server.")


if __name__ == "__main__":
    main()
