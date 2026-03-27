#!/usr/bin/env python3
"""Headless smoke test for Rip City Pinball using Playwright."""

import json
import sys
import time
import subprocess
import os

PINBALL_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_ROUNDS = 50
MAX_WAIT_SECONDS = 600  # 10 minutes max
PORT = 8765


def start_server():
    """Start a simple HTTP server to serve the game."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=PINBALL_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return proc


def run_test():
    from playwright.sync_api import sync_playwright

    server = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1024, "height": 768})
            page = context.new_page()

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(msg.text))
            page.on("pageerror", lambda err: console_msgs.append(f"PAGE_ERROR: {err}"))

            url = f"http://localhost:{PORT}/index.html?test={TEST_ROUNDS}"
            print(f"Loading {url} ...")
            page.goto(url, wait_until="networkidle", timeout=30000)

            print(f"Waiting for {TEST_ROUNDS} rounds to complete (max {MAX_WAIT_SECONDS}s) ...")
            start_time = time.time()
            last_status = time.time()

            while True:
                elapsed = time.time() - start_time
                if elapsed > MAX_WAIT_SECONDS:
                    print(f"TIMEOUT after {MAX_WAIT_SECONDS}s")
                    break

                try:
                    complete = page.evaluate(
                        '() => document.getElementById("test-results")?.getAttribute("data-complete") === "true"'
                    )
                    if complete:
                        print(f"Test completed in {int(elapsed)}s")
                        break
                except Exception:
                    pass

                # Periodic status every 15 seconds
                if time.time() - last_status > 15:
                    try:
                        status = page.evaluate('''() => {
                            try {
                                return JSON.stringify({
                                    round: testRound,
                                    state: gameState,
                                    ball: ballNum,
                                    layer: ballLayer,
                                    y: pinball ? Math.round(pinball.position.y) : null,
                                    vy: pinball ? Math.round(pinball.velocity.y*10)/10 : null,
                                    isStatic: pinball ? pinball.isStatic : null,
                                    stuck: stuckFrames,
                                    lifetimes: testData.ballLifetimes.length,
                                });
                            } catch(e) { return JSON.stringify({error: e.message}); }
                        }''')
                        print(f"  [{int(elapsed)}s] {status}")
                    except Exception as e:
                        print(f"  [{int(elapsed)}s] Status error: {e}")
                    last_status = time.time()

                time.sleep(1)

            # Read results
            try:
                result_text = page.evaluate(
                    '() => document.getElementById("test-results")?.textContent || "{}"'
                )
                results = json.loads(result_text)
            except Exception as e:
                print(f"Error reading results: {e}")
                results = {}

            test_msgs = [m for m in console_msgs if "[TEST]" in m]
            if test_msgs:
                print(f"\n--- Test Console Output ({len(test_msgs)} messages) ---")
                for m in test_msgs[-20:]:
                    print(f"  {m}")

            browser.close()

        return results

    finally:
        server.terminate()
        server.wait()


def main():
    print("=" * 60)
    print("RIP CITY PINBALL — Automated Smoke Test")
    print(f"Rounds: {TEST_ROUNDS}")
    print("=" * 60)

    results = run_test()

    if not results:
        print("\nFAILED: No results received")
        return 1

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    print()

    total_rounds = results.get("totalRounds", 0)
    critical = results.get("criticalFailures", 0)
    tunneling = results.get("tunnelingIncidents", 0)
    stuck = results.get("stuckIncidents", 0)
    js_errors = results.get("jsErrors", 0)
    bumper_hits = results.get("totalBumperHits", 0)
    sling_hits = results.get("totalSlingshotHits", 0)
    max_speed = results.get("maxSpeedSeen", 0)
    avg_life = results.get("avgBallLifetime", 0)
    passed = results.get("passed", False)

    print(f"Rounds completed: {total_rounds}/{TEST_ROUNDS}")
    print(f"Critical failures: {critical}")
    print(f"  Tunneling: {tunneling}")
    print(f"  Stuck ball nudges: {stuck}")
    print(f"  JS errors: {js_errors}")
    print(f"Bumper hits: {bumper_hits}")
    print(f"Slingshot hits: {sling_hits}")
    print(f"Max speed: {max_speed}")
    print(f"Avg ball lifetime: {avg_life} frames")
    print(f"Total balls tracked: {results.get('totalBalls', 0)}")
    print()

    if passed and total_rounds >= TEST_ROUNDS:
        print("PASSED — Zero critical failures across all rounds.")
        return 0
    elif total_rounds < TEST_ROUNDS:
        print(f"INCOMPLETE — Only {total_rounds}/{TEST_ROUNDS} rounds completed.")
        return 1
    else:
        print(f"FAILED — {critical} critical failure(s) found.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
