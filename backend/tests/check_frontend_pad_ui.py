"""Small browser regression check for pad colour control and cap-note layout stability.

Run directly; the page is static and needs no backend:
  python backend/tests/check_frontend_pad_ui.py
"""
from __future__ import annotations

from pathlib import Path
import sys

from playwright.sync_api import sync_playwright


def main(url: str | None = None) -> None:
    source = Path(__file__).parents[2] / "frontend" / "index.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(url or source.as_uri(), wait_until="domcontentloaded")
        page.wait_for_selector("#padColour", timeout=2_000, state="attached")
        assert page.locator("#padColour").input_value() == "#ffffff"
        page.locator("#padColour").evaluate("el => { el.value = '#123456'; el.dispatchEvent(new Event('input', { bubbles: true })); }")
        assert page.locator("#padColourHex").inner_text() == "#123456"
        text = source.read_text(encoding="utf-8")
        assert 'id="ftStatus" class="hint text-[11px] mt-2 min-h-[3.9em]"' in text
        assert "const cap = FT_KEYS.find((it) => FT.rows[it.k]?.capped);" in text
        browser.close()
    print("frontend pad UI checks passed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
