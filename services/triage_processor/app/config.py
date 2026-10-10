import os
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config"


def config_dir() -> Path:
    return Path(os.environ.get("CONFIG_DIR", _DEFAULT_DIR))


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(config_dir() / name) as f:
        return yaml.safe_load(f)
