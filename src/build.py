"""One-shot build of the whole SYNTHETIC platform: generate -> pipeline -> model -> analysis.

``python -m src.build`` is also what the dashboard calls on first start when the DuckDB file is missing.
"""
from __future__ import annotations

import sys

from src.analysis import run_all
from src.generate.config import load_config
from src.generate.messify import write_raw
from src.model import propensity
from src.pipeline.run import run_pipeline


def build(images: bool = False) -> dict:
    cfg = load_config()
    print(f"[build] profile={cfg['profile']} seed={cfg['seed']}")
    print("[build] generating raw exports", write_raw(cfg=cfg))
    res = run_pipeline(cfg=cfg)
    print("[build] pipeline:", res["status"], res["counts"])
    if res["status"] == "failed":
        raise SystemExit("pipeline data-quality checks failed")
    propensity.main()
    sys.argv = ["run_all"] + ([] if images else ["--no-images"])
    run_all.main()
    return res


if __name__ == "__main__":
    build(images="--images" in sys.argv)
