"""trajguard — trajectory privacy attack & protection benchmark."""

from trajguard.attacks import Attack
from trajguard.datasets import DatasetLoader
from trajguard.evaluation import Metric
from trajguard.maps import MapSource
from trajguard.matching import MapMatcher
from trajguard.privacy import PrivacyMechanism
from trajguard.synthesis import SyntheticGenerator

__version__ = "0.1.0"

__all__ = [
    "Attack",
    "DatasetLoader",
    "MapMatcher",
    "MapSource",
    "Metric",
    "PrivacyMechanism",
    "SyntheticGenerator",
    "__version__",
]
