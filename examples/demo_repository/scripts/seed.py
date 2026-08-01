"""Utility script outside the package."""

from demo_service.utils.ids import normalize_id


def main() -> None:
    print(normalize_id("42"))


if __name__ == "__main__":
    main()
