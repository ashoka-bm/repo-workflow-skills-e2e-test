import json
import sqlite3
from contextlib import closing
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .config import Config, ConfigurationError


class LaunchServer(ThreadingHTTPServer):
    config: Config


def _database_available(path: str) -> bool:
    try:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return False
    return True


def _database_path_is_usable(path: str) -> bool:
    database = None if path == ":memory:" else Path(path)
    existed = database is not None and database.exists()
    available = _database_available(path)
    if database is not None and not existed and database.exists():
        try:
            database.unlink()
        except OSError:
            return False
    return available


class RequestHandler(BaseHTTPRequestHandler):
    server: LaunchServer

    @property
    def correlation_id(self) -> str:
        value = getattr(self, "_correlation_id", None)
        if value is None:
            headers = getattr(self, "headers", None)
            supplied = headers.get("X-Correlation-ID") if headers else None
            value = supplied or str(uuid.uuid4())
            self._correlation_id = value
        return value

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        request_version = getattr(self, "request_version", "")
        if not request_version.startswith("HTTP/1."):
            self.request_version = "HTTP/1.0"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-API-Version", __version__)
        self.send_header("X-Correlation-ID", self.correlation_id)
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(body)

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        category = "missing" if code == 404 else "validation"
        public_message = message or self.responses.get(
            code, ("Request failed", "")
        )[0]
        self.send_json(
            code if code < 500 else 400,
            {
                "error": {
                    "correlation_id": self.correlation_id,
                    "message": public_message,
                    "type": category,
                }
            },
        )

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
        self.send_json(200, payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(config: Config) -> LaunchServer:
    config.validate()
    if not _database_path_is_usable(config.database_path):
        raise ConfigurationError("TLP_DATABASE_PATH is not usable by SQLite")
    server = LaunchServer((config.host, config.port), RequestHandler)
    database = (
        None if config.database_path == ":memory:" else Path(config.database_path)
    )
    database_existed = database is not None and database.exists()
    if not _database_available(config.database_path):
        server.server_close()
        if database is not None and not database_existed and database.exists():
            database.unlink()
        raise ConfigurationError("TLP_DATABASE_PATH is not usable by SQLite")
    server.config = config
    return server
