"""Capture dashboard screenshots for the README (needs the app running on :8050 and playwright)."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8050"
PAGES = {"acquisition": "/", "usage": "/usage", "limits": "/limits", "retention": "/retention", "model": "/model",
         "kpis": "/kpis", "pipeline": "/pipeline", "queries": "/queries"}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("console", lambda m: errors.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    for name, path in PAGES.items():
        pg.goto(BASE + path, wait_until="networkidle")
        pg.wait_for_timeout(2500)
        pg.screenshot(path=str(ROOT / "docs" / "img" / f"dash_{name}.png"), full_page=(name in {"pipeline"}))
        print("shot", name)
    b.close()
print("console errors:", errors[:10] if errors else "none")
