from .config import Config
from .server import create_server


def main() -> None:
    server = create_server(
        Config(host="127.0.0.1", port=8000, database_path="team-launch.db")
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
