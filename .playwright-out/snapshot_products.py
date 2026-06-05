#!/usr/bin/env python3
"""Capture product screenshots: frontend home + generation page + history page."""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/workspace/.playwright-out/products")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:5173"

PRODUCTS = [
    ("01-home", f"{BASE}/", "Home page (system status, quick start)"),
    ("02-generate", f"{BASE}/generate", "Generation page (3 steps: avatar + music + generate)"),
    ("03-history", f"{BASE}/history", "History page (task list)"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    console_msgs: list[dict] = []
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text[:200]}))

    summary = []
    for name, url, desc in PRODUCTS:
        print(f"==> {name}: {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"   navigation issue: {e}; retrying with domcontentloaded")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Give time for axios / layout / canvas wavesurfer to settle
        page.wait_for_timeout(2500)
        out = OUT / f"{name}.png"
        page.screenshot(path=str(out), full_page=True)
        title = page.title()
        body_text = (page.locator("body").inner_text() or "")[:400]
        summary.append({"name": name, "url": url, "desc": desc, "title": title, "preview": body_text.replace("\n", " | "), "file": str(out)})
        print(f"   captured -> {out}  title={title!r}")

    errs = [m for m in console_msgs if m["type"] in ("error",)]
    (OUT / "console.json").write_text(json.dumps(console_msgs, indent=2, ensure_ascii=False))
    (OUT / "summary.json").write_text(json.dumps({"pages": summary, "errors": errs}, indent=2, ensure_ascii=False))

    print(f"\nDone. {len(summary)} pages captured, {len(errs)} console errors")
    for e in errs[:10]:
        print("  ERR:", e["text"][:160])

    browser.close()
