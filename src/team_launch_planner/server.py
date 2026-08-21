import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .config import Config


class LaunchServer(ThreadingHTTPServer):
    config: Config


def _database_available(path: str) -> bool:
    try:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return False
    return True


class RequestHandler(BaseHTTPRequestHandler):
    server: LaunchServer

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        payload = {
            "database": (
                "available"
                if _database_available(self.server.config.database_path)
                else "unavailable"
            ),
            "status": "ok",
            "version": __version__,
        }
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(config: Config) -> LaunchServer:
    server = LaunchServer((config.host, config.port), RequestHandler)
    server.config = config
    return server
