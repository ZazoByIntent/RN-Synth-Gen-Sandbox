"""Registry mapping (kind, name) pairs to concrete implementation classes."""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T", bound=type)

_registry: dict[tuple[str, str], type] = {}


def register(kind: str, name: str) -> Callable[[T], T]:
    """Class decorator registering a concrete implementation under (kind, name)."""

    def decorator(cls: T) -> T:
        key = (kind, name)
        if key in _registry:
            raise ValueError(
                f"({kind!r}, {name!r}) is already registered "
                f"to {_registry[key].__qualname__}"
            )
        _registry[key] = cls
        return cls

    return decorator


def get(kind: str, name: str) -> type:
    """Return the class registered under (kind, name)."""
    try:
        return _registry[(kind, name)]
    except KeyError:
        known = ", ".join(available(kind)) or "none"
        raise KeyError(f"no {kind!r} named {name!r} is registered; available: {known}") from None


def available(kind: str) -> list[str]:
    """Return the sorted names of all implementations registered for a kind."""
    return sorted(name for k, name in _registry if k == kind)
