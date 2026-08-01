"""Application settings."""

from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
