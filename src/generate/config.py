"""Config loading for the SYNTHETIC data generator.

All parameters live in ``config/synthetic.yaml``; nothing here is derived from real data.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "synthetic.yaml"


def load_config(path: str | Path | None = None, profile: str | None = None) -> dict:
    """Load the YAML config and resolve the active profile (``GAW_PROFILE`` env var by default)."""
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    name = profile or os.environ.get("GAW_PROFILE", "default")
    if name not in cfg["profiles"]:
        raise KeyError(f"unknown profile {name!r}; available: {sorted(cfg['profiles'])}")
    cfg["profile"] = name
    cfg["scale"] = cfg["profiles"][name]
    return cfg
