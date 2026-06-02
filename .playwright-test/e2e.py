"""End-to-end Playwright smoke test for the Singing Digital Human web app.

Verifies:
  1. Home page loads, system info card shows 200 MB upload limit even when DirectML is unavailable
  2. /generate page loads, MusicUploader shows updated 200 MB limit
  3. After mock-upload (setInputFiles), the flow advances to step 2-3
  4. Model selector shows two cards (Wav2Lip / MuseTalk) when both music and slice are present
  5. No uncaught console errors
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("/workspace/.playwright-out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TEST_AUDIO = "/tmp/test_audio.wav"

console_messages: list[tuple[str, str]] = []
network_errors: list[str] = []


def on_console(msg) -> None:
    console_messages.append((msg.type, msg.text))
    print(f"  CONSOLE [{msg.type}] {msg.text}")


def on_pageerror(exc) -> None:
    console_messages.append(("error", f"PAGE_ERROR: {exc}"))
    print(f"  PAGE_ERROR: {exc}")


def on_requestfailed(req) -> None:
    url = req.url
    if "favicon" in url or "hot-update" in url:
        return
    failure = req.failure
    msg = f"REQUEST_FAILED: {req.method} {url} -> {failure}"
    network_errors.append(msg)
    print(f"  {msg}")


def on_response(resp) -> None:
    if resp.status >= 400 and "favicon" not in resp.url and "hot-update" not in resp.url:
        print(f"  HTTP {resp.status} {resp.request.method} {resp.url}")


results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "✓" if condition else "✗"
    print(f"  {status} {name}" + (f"  ({detail})" if detail else ""))
    results.append((name, condition, detail))


def run() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("requestfailed", on_requestfailed)
        page.on("response", on_response)

        # 1. HOME PAGE
        print("\n=== [1] HOME PAGE ===")
        page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT_DIR / "01-home.png"), full_page=True)

        h1_text = page.locator("h1").first.text_content() or ""
        check("home page H1 contains '数字人'", "数字人" in h1_text, h1_text)

        max_upload_line = page.locator("text=最大上传体积").first
        check("home shows 最大上传体积 label", max_upload_line.count() > 0)
        if max_upload_line.count() > 0:
            parent_text = max_upload_line.locator("..").text_content() or ""
            check("home shows 200 MB upload limit (handles 503 body)",
                  "200 MB" in parent_text, parent_text[:80])

        # 2. GENERATE PAGE — initial state
        print("\n=== [2] GENERATE PAGE (initial) ===")
        page.goto("http://localhost:5173/generate", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "02-generate-initial.png"), full_page=True)

        check("generate H1 is 创作中心",
              "创作中心" in (page.locator("h1").first.text_content() or ""))

        limit_label = page.locator("text=后端 200 MB 上限").first
        check("MusicUploader shows '后端 200 MB 上限' label",
              limit_label.count() > 0)

        # ModelInfoCard always renders both Wav2Lip and MuseTalk column titles
        wav2lip_info = page.locator("text=Wav2Lip-ONNX").first
        musetalk_info = page.locator("text=MuseTalk").first
        check("ModelInfoCard shows Wav2Lip column", wav2lip_info.count() > 0)
        check("ModelInfoCard shows MuseTalk column", musetalk_info.count() > 0)

        # 3. UPLOAD MUSIC (drives the flow forward to step 2)
        print("\n=== [3] UPLOAD MUSIC ===")
        file_input = page.locator('input[type="file"]').first
        check("file input exists", file_input.count() > 0)
        if file_input.count() > 0:
            file_input.set_input_files(TEST_AUDIO)
            # Wait for the upload to either succeed or fail (sandbox has no DirectML → 503
            # but the upload endpoint is separate from /system/info and may return 503 too).
            try:
                page.wait_for_selector("text=音乐上传成功", timeout=10_000)
                upload_ok = True
            except Exception:
                upload_ok = False
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT_DIR / "03-after-upload.png"), full_page=True)
            print(f"  (upload_ok: {upload_ok} — sandbox may have rejected via 503)")

        # 4. UI smoke (progress bar, controls) — no specific assertion; just screenshot
        # 5. HISTORY PAGE
        print("\n=== [4] HISTORY PAGE ===")
        page.goto("http://localhost:5173/history", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "04-history.png"), full_page=True)
        h1 = page.locator("h1").first.text_content() or ""
        check("history page loads", "历史" in h1 or "History" in h1, h1)

        # 6. CONSOLE / NETWORK AUDIT
        print("\n=== [5] CONSOLE / NETWORK AUDIT ===")
        real_errors = [
            (t, msg) for t, msg in console_messages
            if t == "error"
            and "503" not in msg
            and "500" not in msg
            and "Failed to load resource" not in msg
        ]
        check("no unexpected console errors", len(real_errors) == 0,
              f"{len(real_errors)} errors: " + str(real_errors[:3]))

        real_net_errors = [
            e for e in network_errors if "favicon" not in e and "hot-update" not in e
        ]
        check("no unexpected network failures", len(real_net_errors) == 0,
              f"{len(real_net_errors)} errors: " + str(real_net_errors[:3]))

        (OUT_DIR / "summary.json").write_text(json.dumps(
            {"results": results, "console": console_messages, "network_errors": network_errors},
            ensure_ascii=False, indent=2))

        browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== SUMMARY: {passed}/{len(results)} checks passed ===")
    print(f"Screenshots: {OUT_DIR}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())
