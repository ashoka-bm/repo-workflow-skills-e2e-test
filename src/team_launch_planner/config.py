from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    database_path: str
