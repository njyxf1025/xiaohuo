"""End-to-end test: upload -> slice -> listen -> switch song -> check console for ERR_ABORTED."""
import sys
from playwright.sync_api import sync_playwright

FRONTEND = "http://localhost:5173"
TEST_FILES = [
    "/tmp/wf-test/test1.wav",
    "/tmp/wf-test/test2.wav",
]

console_logs = []
network_errors = []


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        page.on("console", lambda m: console_logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_logs.append(f"[pageerror] {e}"))
        page.on(
            "requestfailed",
            lambda r: network_errors.append(
                f"[failed] {r.method} {r.url} -> {r.failure}"
            ),
        )

        print(">>> goto /generate")
        page.goto(f"{FRONTEND}/generate", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(500)

        print(">>> upload test1.wav")
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(TEST_FILES[0])

        print(">>> wait for WaveformPlayer (试听整段 button)")
        listen_btn = page.get_by_role("button", name="试听整段")
        try:
            listen_btn.wait_for(state="visible", timeout=30_000)
        except Exception as e:
            print(f"!! WaveformPlayer never appeared: {e}")
            page.screenshot(path="/tmp/wf-test/no-waveform.png", full_page=True)
            browser.close()
            return 2

        print(">>> click 试听整段")
        listen_btn.click()
        page.wait_for_timeout(3_000)

        seg_btn = page.get_by_role("button", name="试听所选区间")
        if seg_btn.is_visible():
            seg_btn.click()
            page.wait_for_timeout(2_000)

        print(">>> upload test2.wav (切歌 -> triggers cleanup)")
        file_input2 = page.locator('input[type="file"]').first
        file_input2.set_input_files(TEST_FILES[1])
        page.wait_for_timeout(5_000)

        if listen_btn.is_visible():
            listen_btn.click()
            page.wait_for_timeout(3_000)

        page.wait_for_timeout(2_000)

        page.screenshot(path="/tmp/wf-test/final.png", full_page=True)
        browser.close()

    print("\n=== ALL CONSOLE MESSAGES ===")
    for log in console_logs:
        print(log)

    print("\n=== NETWORK FAILURES ===")
    for n in network_errors:
        print(n)

    err_aborted = [l for l in console_logs if "ERR_ABORTED" in l]
    print(f"\n=== ERR_ABORTED COUNT: {len(err_aborted)} ===")
    for l in err_aborted:
        print(l)

    return 0 if len(err_aborted) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
