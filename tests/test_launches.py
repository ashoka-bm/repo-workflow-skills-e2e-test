import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
