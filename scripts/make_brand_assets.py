"""Generate README header SVGs and the "A" symbol with OUTLINED Lato glyphs (renders identically everywhere).

PROVISIONAL: the brand book's own "A" symbol file was not found in any repository, so the symbol is an
outlined Lato Black "A" on a Carbon tile with a Cobalt bar. Replace assets/brand/symbol.svg to swap it.
Usage: python scripts/make_brand_assets.py
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import theme as T  # noqa: E402

FONT_DIR = Path.home() / ".local" / "share" / "fonts"
OUT = Path(__file__).resolve().parents[1] / "assets" / "brand"


def text_path(font_file: str, text: str, size: float, x: float, y: float, tracking: float = 0.0) -> tuple[str, float]:
    font = TTFont(FONT_DIR / font_file)
    gs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm
    scale = size / upm
    d, cursor = [], x
    for ch in text:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        pen = SVGPathPen(gs)
        gs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, y)))
        d.append(pen.getCommands())
        cursor += gs[name].width * scale + tracking
    return " ".join(d), cursor - x


def symbol_svg(size: int = 128) -> str:
    font = TTFont(FONT_DIR / "Lato-Black.ttf")
    gs, upm = font.getGlyphSet(), font["head"].unitsPerEm
    name = font.getBestCmap()[ord("A")]
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    x0, y0, x1, y1 = bp.bounds
    target = size * 0.52
    s = target / (y1 - y0)
    ox = (size - (x1 - x0) * s) / 2 - x0 * s
    oy = size * 0.70
    pen = SVGPathPen(gs)
    gs[name].draw(TransformPen(pen, (s, 0, 0, -s, ox, oy)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" '
            f'aria-label="ABADE A symbol (provisional)"><rect width="{size}" height="{size}" fill="{T.CARBON}"/>'
            f'<path d="{pen.getCommands()}" fill="{T.IVORY}"/>'
            f'<rect x="{size * 0.28}" y="{size * 0.80}" width="{size * 0.44}" height="{size * 0.045}" fill="{T.COBALT}"/></svg>')


def header_svg(dark: bool) -> str:
    bg, fg, sub = (T.CARBON, T.IVORY, T.STEEL) if dark else (T.IVORY, T.CARBON, "#4A5159")
    w, h = 1600, 360
    title, _ = text_path("Lato-Black.ttf", "growth-analytics-warehouse", 92, 80, 190, tracking=-2)
    eyebrow, _ = text_path("Lato-Bold.ttf", "GROWTH ANALYTICS  ·  SNOWFLAKE WAREHOUSE  ·  SYNTHETIC DATA", 22, 80, 96, tracking=4)
    tag, _ = text_path("Lato-Regular.ttf", "From ad spend to paid CAC, LTV/CAC, usage limits and an upgrade-propensity model.", 30, 80, 250)
    lines = "".join(f'<path d="M {-200 + i * 120},{h} L {i * 120 + 0},0" stroke="{fg}" stroke-opacity="0.06" fill="none"/>' for i in range(0, 22))
    sym = symbol_svg(96).replace('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"', '<svg x="1424" y="40" width="96" height="96"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="growth-analytics-warehouse: synthetic growth analytics platform">'
            f'<rect width="{w}" height="{h}" fill="{bg}"/><g>{lines}</g>'
            f'<ellipse cx="1330" cy="110" rx="430" ry="330" fill="{T.COBALT}" fill-opacity="0.09"/>'
            f'<path d="{eyebrow}" fill="{T.COBALT}"/><path d="{title}" fill="{fg}"/><path d="{tag}" fill="{sub}"/>'
            f'<rect x="80" y="296" width="120" height="6" fill="{T.COBALT}"/>{sym}</svg>')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "symbol.svg").write_text(symbol_svg(), encoding="utf-8")
    (OUT / "header-light.svg").write_text(header_svg(False), encoding="utf-8")
    (OUT / "header-dark.svg").write_text(header_svg(True), encoding="utf-8")
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
