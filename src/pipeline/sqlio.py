"""Helpers to read the documented SQL files (one query per file, with a structured header)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from src.generate.config import ROOT

SQL_DIR = ROOT / "sql"
HEADER_KEYS = ("id", "name", "business_question", "tables", "grain", "output", "replaces", "kind")


def parse_header(text: str) -> dict:
    """Parse leading ``-- key: value`` comment lines (values may continue on ``--   `` lines)."""
    meta: dict[str, str] = {}
    key = None
    for line in text.splitlines():
        if not line.startswith("--"):
            break
        body = line[2:]
        m = re.match(r"^\s?(\w+):\s*(.*)$", body)
        if m and m.group(1) in HEADER_KEYS:
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif key and body.strip():
            meta[key] += " " + body.strip()
    return meta


@lru_cache(maxsize=None)
def catalog() -> list[dict]:
    """All SQL files with parsed headers, sorted by folder then id."""
    items = []
    for path in sorted(SQL_DIR.rglob("*.sql")):
        text = path.read_text(encoding="utf-8")
        meta = parse_header(text)
        meta.setdefault("id", path.stem)
        meta["folder"] = path.parent.name
        meta["path"] = str(path.relative_to(ROOT))
        meta["sql"] = text
        items.append(meta)
    return items


def get_sql(query_id: str) -> str:
    for q in catalog():
        if q["id"] == query_id:
            return q["sql"]
    raise KeyError(query_id)


def run_query(con, query_id: str):
    """Execute a catalogued SELECT and return a DataFrame."""
    return con.execute(get_sql(query_id)).df()


def run_script(con, path: Path) -> None:
    con.execute(path.read_text(encoding="utf-8"))
