"""Render the Mermaid ER diagram in docs/SCHEMA.md to docs/img/schema.png (needs playwright + internet for mermaid CDN)."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "docs" / "SCHEMA.md").read_text(encoding="utf-8")
code = re.search(r"```mermaid\n(.*?)```", src, re.S).group(1)
html = f"""<!doctype html><html><body style="background:#F6F5F0;margin:0;padding:24px;font-family:Lato,sans-serif">
<pre class="mermaid">{code}</pre>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({{startOnLoad: false, theme: 'base', themeVariables: {{
  background: '#F6F5F0', primaryColor: '#FFFFFF', primaryBorderColor: '#050505', primaryTextColor: '#050505',
  lineColor: '#7E8791', secondaryColor: '#F6F5F0', tertiaryColor: '#F6F5F0', fontFamily: 'Lato, sans-serif', fontSize: '14px'}},
  er: {{useMaxWidth: false}}}});
await mermaid.run();
document.body.setAttribute('data-done', '1');
</script></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=1.5)
    pg.set_content(html)
    pg.wait_for_selector("body[data-done='1']", timeout=60000)
    el = pg.query_selector("svg")
    el.screenshot(path=str(ROOT / "docs" / "img" / "schema.png"))
    b.close()
print("wrote docs/img/schema.png")
