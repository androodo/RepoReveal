"""ID helpers."""


def normalize_id(value: int | str) -> int:
    if isinstance(value, int):
        return value
    return int(str(value).strip())
