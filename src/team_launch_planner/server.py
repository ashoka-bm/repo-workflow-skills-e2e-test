import json
import sqlite3
from contextlib import closing
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
