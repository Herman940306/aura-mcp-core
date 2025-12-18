from __future__ import annotations

import asyncio
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Tuple


class _SSEHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/_mcp/stream_test":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for i in range(1, 6):
                data = f'data: {{"progress": {i*20}}}\n\n'
                self.wfile.write(data.encode("utf-8"))
                self.wfile.flush()
                asyncio.run(asyncio.sleep(0.05))
        except BrokenPipeError:
            pass

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Silence default logging
        return


def start_server(
    host: str = "127.0.0.1", port: int = 8765
) -> Tuple[HTTPServer, Thread]:
    server = HTTPServer((host, port), _SSEHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server: HTTPServer) -> None:
    server.shutdown()
    server.server_close()
