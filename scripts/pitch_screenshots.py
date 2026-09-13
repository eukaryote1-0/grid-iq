#!/usr/bin/env python3
"""Capture the two pitch-deck screenshots (Village Engine first, then National).

Matches the deck's two-engine framing: exactly two images.

Usage:
    python scripts/pitch_screenshots.py
Outputs docs/pitch_assets/village-engine.png and docs/pitch_assets/national-engine.png.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "pitch_assets"
PORT = int(os.environ.get("E2E_PORT", "8893"))
BASE = f"http://127.0.0.1:{PORT}"
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")


def wait_health(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    with httpx.Client(base_url=BASE, timeout=3) as c:
        while time.time() < deadline:
            try:
                if c.get("/api/health").status_code == 200:
                    return
            except Exception:
                time.sleep(0.4)
    raise SystemExit("server did not become healthy")


def main() -> int:
    if not Path(CHROMIUM).exists():
        print(f"SKIP: chromium not found at {CHROMIUM}")
        return 1
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_health()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM, headless=True,
                                        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            page.set_default_timeout(90_000)
            page.goto(f"{BASE}/?demo=1", wait_until="domcontentloaded")
            page.wait_for_selector("#nav .navbtn", timeout=30_000)
            # Keep the header in place so it never overlays element captures.
            page.add_style_tag(content="header.topbar{position:static!important}")

            # ---- Village Engine FIRST (urgent) --------------------------------
            page.click('.navbtn[data-page="villagefit"]')
            page.wait_for_timeout(500)
            page.uncheck("#e4gep")
            page.fill("#e4annual", "800"); page.fill("#e4peak", "0.25"); page.fill("#e4evening", "65")
            page.click("#runE4")
            page.get_by_text("Right-sizing", exact=False).first.wait_for()
            page.click("#scoreAllPilots")
            page.get_by_text("Six-pilot comparison", exact=False).first.wait_for()
            page.wait_for_timeout(600)
            page.locator(".split > div").nth(1).screenshot(path=str(OUT / "village-engine-panel.png"))
            page.get_by_text("Six-pilot comparison", exact=False).first.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "village-engine.png"))
            print(f"wrote {(OUT / 'village-engine.png').relative_to(ROOT)} (+ panel)")

            # ---- National Engine: E1 A/B -------------------------------------
            page.click('.navbtn[data-page="optimizer"]')
            page.wait_for_timeout(400)
            page.fill("#e1solar", "2500"); page.fill("#e1bess", "400"); page.fill("#e1impCap", "400")
            page.click("#runE1")
            page.get_by_text("E1 result", exact=False).first.wait_for()
            page.click("#saveE1A")
            page.fill("#e1solar", "1200"); page.fill("#e1bess", "1000"); page.fill("#e1impCap", "190")
            page.click("#runE1")
            page.wait_for_timeout(700)
            page.click("#saveE1B")
            target = page.get_by_text("A/B system-cost comparison", exact=False).first
            target.wait_for()
            target.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "national-engine.png"))
            print(f"wrote {(OUT / 'national-engine.png').relative_to(ROOT)}")

            browser.close()
        for name in ("village-engine.png", "national-engine.png"):
            path = OUT / name
            print(f"{name}: {path.stat().st_size//1024} KB")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
