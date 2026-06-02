"""Diagnose: are the 3 WaveformPlayer buttons actually wired up?
Also check the 3 preset <img> thumbnails and the 504 from AvatarSelector upload."""
from playwright.sync_api import sync_playwright
import time, os, base64, tempfile

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
    failed = []
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    page.on("response", lambda r: (r.status >= 400) and logs.append(f"[HTTP {r.status}] {r.url}"))

    page.goto("http://localhost:5173/generate")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    for txt in ["试听整段", "试听所选区间", "重置为自动检测"]:
        loc = page.locator(f"button:has-text('{txt}')")
        n = loc.count()
        print(f"BUTTON '{txt}': count={n}")

    print("\n--- preset thumbnails ---")
    thumbs = page.locator("img[src*='/api/v1/avatars/presets/']")
    print("preset img count:", thumbs.count())
    for i in range(min(thumbs.count(), 3)):
        src = thumbs.nth(i).get_attribute("src")
        print(f"  [{i}] src={src}")
        r = page.evaluate("(url) => fetch(url).then(r => ({status: r.status, ct: r.headers.get('content-type')})).catch(e => ({error: e.message}))", src)
        print(f"        response={r}")

    print("\n--- try upload ---")
    page.locator("button:has-text('自定义')").first.click()
    time.sleep(0.5)
    fi = page.locator("input[type='file']").first
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tf.write(png); tf.close()
    fi.set_input_files(tf.name)
    time.sleep(8)
    os.unlink(tf.name)

    print("\n--- console + http errors ---")
    for l in logs[-40:]: print(l)
    print("\n--- requestfailed ---")
    for u, f in failed: print(u, f)

    page.screenshot(path="/tmp/diag.png", full_page=True)
    browser.close()
