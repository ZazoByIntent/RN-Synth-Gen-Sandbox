"""Tests for the (kind, name) implementation registry."""

from collections.abc import Iterator

import pytest

from trajguard.experiments import registry


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Isolate registry state per test."""
    saved = dict(registry._registry)
    registry._registry.clear()
    yield
    registry._registry.clear()
    registry._registry.update(saved)


def test_register_and_get_roundtrip() -> None:
    @registry.register("attack", "dummy")
    class DummyAttack:
        pass

    assert registry.get("attack", "dummy") is DummyAttack


def test_decorator_returns_class_unchanged() -> None:
    class Plain:
        pass

    decorated = registry.register("metric", "plain")(Plain)
    assert decorated is Plain


def test_duplicate_registration_raises() -> None:
    @registry.register("privacy", "noop")
    class First:
        pass

    with pytest.raises(ValueError, match="already registered"):

        @registry.register("privacy", "noop")
        class Second:
            pass


def test_unknown_lookup_raises_with_available_names() -> None:
    @registry.register("attack", "known")
    class Known:
        pass

    with pytest.raises(KeyError, match="known"):
        registry.get("attack", "missing")


def test_same_name_different_kind_is_allowed() -> None:
    @registry.register("attack", "markov")
    class MarkovAttack:
        pass

    @registry.register("generator", "markov")
    class MarkovGenerator:
        pass

    assert registry.get("attack", "markov") is MarkovAttack
    assert registry.get("generator", "markov") is MarkovGenerator


def test_available_lists_sorted_names_per_kind() -> None:
    @registry.register("metric", "zeta")
    class Zeta:
        pass

    @registry.register("metric", "alpha")
    class Alpha:
        pass

    @registry.register("attack", "other")
    class Other:
        pass

    assert registry.available("metric") == ["alpha", "zeta"]
    assert registry.available("nonexistent") == []
