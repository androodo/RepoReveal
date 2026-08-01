"""User model."""

from dataclasses import dataclass


@dataclass(slots=True)
class User:
    id: int
    email: str
    active: bool
