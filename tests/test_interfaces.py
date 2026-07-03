"""Smoke tests: the package imports and the seven ABCs are genuinely abstract."""

import pytest

import trajguard
from trajguard import (
    Attack,
    DatasetLoader,
    MapMatcher,
    MapSource,
    Metric,
    PrivacyMechanism,
    SyntheticGenerator,
)

ABCS = [Attack, DatasetLoader, MapMatcher, MapSource, Metric, PrivacyMechanism, SyntheticGenerator]


def test_package_imports_with_version() -> None:
    assert trajguard.__version__


@pytest.mark.parametrize("abc", ABCS, ids=lambda c: c.__name__)
def test_abc_rejects_direct_instantiation(abc: type) -> None:
    with pytest.raises(TypeError):
        abc()
