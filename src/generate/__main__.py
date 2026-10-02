"""CLI: ``python -m src.generate [--out data/raw] [--sample data/sample --sample-rows 25]``."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import ROOT, load_config
from .messify import write_raw


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate SYNTHETIC raw exports.")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--sample", default=None, help="also write a tiny head() sample of each file here")
    ap.add_argument("--sample-rows", type=int, default=25)
    args = ap.parse_args()
    cfg = load_config(args.config)
    counts = write_raw(args.out, cfg)
    for k, v in counts.items():
        print(f"{k}: {v:,} rows")
    if args.sample:
        s = Path(args.sample)
        s.mkdir(parents=True, exist_ok=True)
        for f in Path(args.out).glob("*.csv"):
            with open(f, encoding="utf-8") as src, open(s / f.name, "w", encoding="utf-8") as dst:
                for i, line in enumerate(src):
                    if i > args.sample_rows:
                        break
                    dst.write(line)


if __name__ == "__main__":
    main()
