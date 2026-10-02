"""CLI: ``python -m src.pipeline`` runs raw -> staging -> core -> marts and the quality checks."""
from __future__ import annotations

import sys

from .run import run_pipeline


def main() -> int:
    res = run_pipeline()
    print(f"run {res['run_id']}: {res['status']}  rows by layer: {res['counts']}")
    for name, layer, _, details in res["warned"]:
        print(f"  WARN {layer}/{name}: {details}")
    for name, layer, _, details in res["failed"]:
        print(f"  FAIL {layer}/{name}: {details}")
    return 1 if res["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
