#!/usr/bin/env python3
"""Playwright E2E for the GridIQ demo path using the SYSTEM Chromium.

No Playwright browser downloads are used: we launch /usr/bin/chromium directly.

Usage:
    python scripts/e2e_demo.py
Writes screenshots to reports/screenshots/ and reports/browser_e2e.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("E2E_PORT", "8899"))
BASE = f"http://127.0.0.1:{PORT}"
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
SHOTS = ROOT / "reports" / "screenshots"
REPORT = ROOT / "reports" / "browser_e2e.json"


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


def run() -> int:
    if not Path(CHROMIUM).exists():
        print(f"SKIP: chromium not found at {CHROMIUM}")
        return 0
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"SKIP: playwright unavailable ({exc})")
        return 0

    SHOTS.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pages_done: list[str] = []
    try:
        wait_health()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROMIUM,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(90_000)
            page.goto(f"{BASE}/?demo=1", wait_until="domcontentloaded")
            page.wait_for_selector("#nav .navbtn", timeout=30_000)
            assert page.locator("#demoStrip").count() == 1, "demo strip missing at ?demo=1"

            def go(name: str) -> None:
                page.click(f'.navbtn[data-page="{name}"]')
                page.wait_for_timeout(500)
                pages_done.append(name)
                page.screenshot(path=str(SHOTS / f"{len(pages_done):02d}-{name}.png"), full_page=True)

            # 1. Overview
            go("overview")
            page.wait_for_selector("#supplyChart, #lossChart")

            # 2. Network & E2 -> system study -> model loss -> BPC comparison
            go("network")
            page.click("#runE2System")
            page.get_by_text("E2 result", exact=False).first.wait_for()
            page.click("#useModelLoss")
            page.get_by_text("Difference", exact=False).first.wait_for()
            page.screenshot(path=str(SHOTS / "02b-e2-loss.png"), full_page=True)

            # 3. Optimizer A/B
            go("optimizer")
            def set_e1(solar: str, bess: str, imp: str) -> None:
                page.fill("#e1solar", solar)
                page.fill("#e1bess", bess)
                page.fill("#e1impCap", imp)
            set_e1("2500", "400", "400")
            page.click("#runE1")
            page.get_by_text("E1 result", exact=False).first.wait_for()
            page.click("#saveE1A")
            set_e1("1200", "1000", "190")
            page.click("#runE1")
            page.wait_for_timeout(600)
            page.click("#saveE1B")
            page.get_by_text("A/B system-cost comparison", exact=False).first.wait_for()
            page.screenshot(path=str(SHOTS / "03b-e1-ab.png"), full_page=True)

            # 4. Criticality
            go("criticality")
            page.click("#runE3")
            page.get_by_text("Ranked bridge watch-list", exact=False).first.wait_for()
            page.screenshot(path=str(SHOTS / "04b-e3.png"), full_page=True)

            # 5. VillageFit (offline: NASA cache on, GEP off to avoid the blocked upstream)
            go("villagefit")
            page.uncheck("#e4gep")
            page.fill("#e4annual", "800")
            page.fill("#e4peak", "0.25")
            page.fill("#e4evening", "65")
            page.click("#runE4")
            page.get_by_text("Right-sizing", exact=False).first.wait_for()
            page.click("#scoreAllPilots")
            page.get_by_text("Six-pilot comparison", exact=False).first.wait_for()
            page.screenshot(path=str(SHOTS / "05b-villagefit.png"), full_page=True)

            # 6. Data + Audit
            go("data")
            go("audit")
            page.get_by_text("BPC", exact=False).first.wait_for()

            browser.close()
        REPORT.write_text(json.dumps({
            "pass": True,
            "version": "1.7.0",
            "at": datetime.now(timezone.utc).isoformat(),
            "pages": pages_done,
            "screenshots": [p.name for p in sorted(SHOTS.glob("*.png"))],
        }, indent=2), encoding="utf-8")
        print(f"PASS: walked {len(pages_done)} pages; screenshots in {SHOTS.relative_to(ROOT)}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(run())
