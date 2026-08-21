import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """A startup setting is missing or invalid."""


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    database_path: str

    def validate(self, *, allow_ephemeral_port: bool = True) -> None:
        minimum_port = 0 if allow_ephemeral_port else 1
        if not self.host.strip():
            raise ConfigurationError("TLP_HOST must not be empty")
        if not minimum_port <= self.port <= 65535:
            raise ConfigurationError(
                f"TLP_PORT must be between {minimum_port} and 65535"
            )
        if not self.database_path.strip():
            raise ConfigurationError("TLP_DATABASE_PATH must not be empty")


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    values = os.environ if environ is None else environ
    host = values.get("TLP_HOST", "127.0.0.1").strip()
    database_path = values.get("TLP_DATABASE_PATH", "team-launch.db").strip()
    raw_port = values.get("TLP_PORT", "8000").strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise ConfigurationError("TLP_PORT must be an integer") from error

    config = Config(host=host, port=port, database_path=database_path)
    config.validate(allow_ephemeral_port=False)
    return config
