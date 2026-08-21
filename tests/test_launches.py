import json
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


if __name__ == "__main__":
    unittest.main()
