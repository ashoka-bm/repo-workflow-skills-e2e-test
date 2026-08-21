from .config import load_config
from .server import create_server


def main() -> None:
    server = create_server(load_config())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
