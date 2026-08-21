import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ServiceHealthTests(unittest.TestCase):
    def test_running_service_reports_version_and_database_availability(self) -> None:
        from team_launch_planner.config import Config
        from team_launch_planner.server import create_server

        with tempfile.TemporaryDirectory() as directory:
            config = Config(
                host="127.0.0.1",
                port=0,
                database_path=str(Path(directory) / "launches.db"),
            )
            server = create_server(config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def stop_server() -> None:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

            self.addCleanup(stop_server)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/health", timeout=2
            ) as response:
                payload = json.load(response)

            self.assertEqual(response.status, 200)
            self.assertEqual(
                payload,
                {"database": "available", "status": "ok", "version": "1"},
            )


class ConfigurationTests(unittest.TestCase):
    def test_documented_defaults_are_loaded_when_settings_are_missing(self) -> None:
        from team_launch_planner.config import load_config

        self.assertEqual(
            load_config({}),
            load_config(
                {
                    "TLP_HOST": "127.0.0.1",
                    "TLP_PORT": "8000",
                    "TLP_DATABASE_PATH": "team-launch.db",
                }
            ),
        )

    def test_explicit_settings_are_loaded(self) -> None:
        from team_launch_planner.config import Config, load_config

        self.assertEqual(
            load_config(
                {
                    "TLP_HOST": "localhost",
                    "TLP_PORT": "9000",
                    "TLP_DATABASE_PATH": ":memory:",
                }
            ),
            Config(host="localhost", port=9000, database_path=":memory:"),
        )

    def test_invalid_settings_fail_before_database_or_listener_creation(self) -> None:
        from team_launch_planner.config import Config, ConfigurationError, load_config
        from team_launch_planner.server import create_server

        cases = (
            {"TLP_HOST": ""},
            {"TLP_PORT": "not-a-port"},
            {"TLP_PORT": "0"},
            {"TLP_PORT": "65536"},
            {"TLP_DATABASE_PATH": ""},
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "must-not-exist.db"
            for overrides in cases:
                with self.subTest(overrides=overrides):
                    settings = {"TLP_DATABASE_PATH": str(database), **overrides}
                    with self.assertRaises(ConfigurationError):
                        load_config(settings)
                    self.assertFalse(database.exists())

            with self.assertRaises(ConfigurationError):
                create_server(
                    Config(host="", port=8000, database_path=str(database))
                )
            self.assertFalse(database.exists())

    def test_unusable_database_path_fails_before_the_port_is_bound(self) -> None:
        from team_launch_planner.config import Config, ConfigurationError
        from team_launch_planner.server import create_server

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing" / "launches.db"
            with self.assertRaises(ConfigurationError):
                create_server(
                    Config(
                        host="127.0.0.1",
                        port=port,
                        database_path=str(database),
                    )
                )
            self.assertFalse(database.exists())

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))

    def test_port_bind_failure_leaves_a_new_database_path_untouched(self) -> None:
        from team_launch_planner.config import Config
        from team_launch_planner.server import create_server

        with tempfile.TemporaryDirectory() as directory, socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            database = Path(directory) / "must-not-exist.db"

            with self.assertRaises(OSError):
                create_server(
                    Config(
                        host="127.0.0.1",
                        port=occupied.getsockname()[1],
                        database_path=str(database),
                    )
                )

            self.assertFalse(database.exists())


class ResponseMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        from team_launch_planner.config import Config
        from team_launch_planner.server import create_server

        self.server = create_server(
            Config(host="127.0.0.1", port=0, database_path=":memory:")
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def request(self, correlation_id: str | None = None):
        headers = {}
        if correlation_id is not None:
            headers["X-Correlation-ID"] = correlation_id
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.server_port}/health",
            headers=headers,
        )
        return urllib.request.urlopen(request, timeout=2)

    def raw_request(self, request: bytes) -> bytes:
        with socket.create_connection(
            ("127.0.0.1", self.server.server_port), timeout=2
        ) as connection:
            connection.sendall(request)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := connection.recv(4096):
                chunks.append(chunk)
        return b"".join(chunks)

    def test_supplied_correlation_identifier_is_preserved(self) -> None:
        with self.request("client-request-123") as response:
            self.assertEqual(response.headers["X-API-Version"], "1")
            self.assertEqual(
                response.headers["X-Correlation-ID"], "client-request-123"
            )

    def test_missing_correlation_identifier_is_generated(self) -> None:
        with self.request() as first, self.request() as second:
            first_id = first.headers["X-Correlation-ID"]
            second_id = second.headers["X-Correlation-ID"]

        self.assertEqual(str(uuid.UUID(first_id)), first_id)
        self.assertEqual(str(uuid.UUID(second_id)), second_id)
        self.assertNotEqual(first_id, second_id)

    def test_inherited_error_response_includes_mandatory_metadata(self) -> None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.server_port}/health",
            data=b"{}",
            headers={"X-Correlation-ID": "unsupported-method-1"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=2)
        response = caught.exception
        payload = json.load(response)
        response.close()

        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.headers["X-API-Version"], "1")
        self.assertEqual(
            response.headers["X-Correlation-ID"], "unsupported-method-1"
        )
        self.assertEqual(payload["error"]["type"], "validation")

    def test_head_response_has_metadata_without_body(self) -> None:
        response = self.raw_request(
            b"HEAD /health HTTP/1.1\r\nHost: localhost\r\n"
            b"X-Correlation-ID: head-method-1\r\nConnection: close\r\n\r\n"
        )
        headers, body = response.split(b"\r\n\r\n", 1)

        self.assertIn(b"Content-Type: application/json", headers)
        self.assertIn(b"X-API-Version: 1", headers)
        self.assertIn(b"X-Correlation-ID: head-method-1", headers)
        self.assertEqual(body, b"")

    def test_parser_error_generates_metadata_without_parsed_headers(self) -> None:
        response = self.raw_request(b"GET / HTTP/9.9\r\n\r\n")
        headers, body = response.split(b"\r\n\r\n", 1)

        self.assertIn(b"Content-Type: application/json", headers)
        self.assertIn(b"X-API-Version: 1", headers)
        self.assertIn(b"X-Correlation-ID:", headers)
        self.assertEqual(json.loads(body)["error"]["type"], "validation")

    def test_legacy_http_request_is_upgraded_to_a_metadata_response(self) -> None:
        response = self.raw_request(b"GET /health\r\n")
        headers, body = response.split(b"\r\n\r\n", 1)

        self.assertTrue(headers.startswith(b"HTTP/1.0 200"))
        self.assertIn(b"Content-Type: application/json", headers)
        self.assertIn(b"X-API-Version: 1", headers)
        self.assertIn(b"X-Correlation-ID:", headers)
        self.assertEqual(json.loads(body)["status"], "ok")


class ErrorEnvelopeTests(unittest.TestCase):
    def test_known_failures_share_one_correlated_envelope(self) -> None:
        from team_launch_planner.errors import ApiError, error_response

        cases = {
            "validation": 400,
            "missing": 404,
            "conflict": 409,
            "authorization": 403,
            "internal": 500,
        }
        for category, expected_status in cases.items():
            with self.subTest(category=category):
                status, payload = error_response(
                    ApiError(category, f"{category} detail"), "request-7"
                )
                self.assertEqual(status, expected_status)
                self.assertEqual(
                    payload,
                    {
                        "error": {
                            "correlation_id": "request-7",
                            "message": f"{category} detail",
                            "type": category,
                        }
                    },
                )

    def test_unexpected_failure_does_not_expose_diagnostics(self) -> None:
        from team_launch_planner.errors import error_response

        with self.assertLogs("team_launch_planner.errors", level="ERROR") as logs:
            status, payload = error_response(
                RuntimeError("secret stack detail"), "request-8"
            )

        self.assertEqual(status, 500)
        self.assertNotIn("secret", json.dumps(payload))
        self.assertEqual(payload["error"]["type"], "internal")
        self.assertIn("request-8", "\n".join(logs.output))
        self.assertIn("secret stack detail", "\n".join(logs.output))

    def test_missing_route_returns_json_with_response_metadata(self) -> None:
        from team_launch_planner.config import Config
        from team_launch_planner.server import create_server

        server = create_server(
            Config(host="127.0.0.1", port=0, database_path=":memory:")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/missing",
                headers={"X-Correlation-ID": "missing-route-1"},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=2)
            response = caught.exception
            payload = json.load(response)
            response.close()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(response.code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.headers["X-API-Version"], "1")
        self.assertEqual(response.headers["X-Correlation-ID"], "missing-route-1")
        self.assertEqual(payload["error"]["type"], "missing")

    def test_internal_request_failure_is_logged_but_not_returned(self) -> None:
        from team_launch_planner.config import Config
        from team_launch_planner.server import create_server

        server = create_server(
            Config(host="127.0.0.1", port=0, database_path=":memory:")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/health",
                headers={"X-Correlation-ID": "failed-request-1"},
            )
            with (
                patch(
                    "team_launch_planner.server._database_available",
                    side_effect=RuntimeError("private database diagnostic"),
                ),
                self.assertLogs(
                    "team_launch_planner.errors", level="ERROR"
                ) as logs,
                self.assertRaises(urllib.error.HTTPError) as caught,
            ):
                urllib.request.urlopen(request, timeout=2)
            response = caught.exception
            payload = json.load(response)
            response.close()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(response.code, 500)
        self.assertNotIn("private database diagnostic", json.dumps(payload))
        self.assertIn("failed-request-1", "\n".join(logs.output))
        self.assertIn("private database diagnostic", "\n".join(logs.output))


class AdministrativeShellTests(unittest.TestCase):
    def run_admin(self, *arguments: str, cwd: str | None = None):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "team_launch_planner.admin", *arguments],
            cwd=cwd or ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_help_lists_reserved_administrative_boundaries(self) -> None:
        result = self.run_admin("--help")

        self.assertEqual(result.returncode, 0)
        for command in ("migrate", "tokens", "export", "backup"):
            self.assertIn(command, result.stdout)

    def test_subcommand_help_parses_without_running_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_admin("migrate", "--help", cwd=directory)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_unknown_command_fails_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_admin("destroy-everything", cwd=directory)

            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid choice", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
