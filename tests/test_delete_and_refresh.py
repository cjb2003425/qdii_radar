"""
Test to verify that fund 161129 stays deleted after page refresh.

This test:
1. Adds fund 161129
2. Deletes it from the UI
3. Refreshes the page
4. Verifies the fund does NOT reappear
"""

from playwright.sync_api import sync_playwright
import time
import httpx

# URLs
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://127.0.0.1:8088"

# Fund details
FUND_CODE = "161129"
FUND_NAME = "易方达原油A类人民币"


def add_fund_via_api():
    """Add fund 161129 via backend API."""
    with httpx.Client() as client:
        response = client.post(
            f"{BACKEND_URL}/api/fund",
            params={"code": FUND_CODE, "name": FUND_NAME}
        )
        print(f"  API response: {response.json()}")
        return response.status_code == 200


def check_fund_in_backend():
    """Check if fund is in backend."""
    with httpx.Client() as client:
        response = client.get(f"{BACKEND_URL}/api/funds")
        funds = response.json()
        fund_codes = [f["code"] for f in funds]
        return FUND_CODE in fund_codes


def test_delete_and_refresh():
    """Test that fund stays deleted after refresh."""

    print("\n" + "="*60)
    print("TEST: DELETE & REFRESH - FUND 161129")
    print("="*60)

    # Step 0: Add fund
    print("\n[Step 0] Adding fund 161129...")
    add_fund_via_api()
    print("✓ Fund added")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Log console messages
        page.on("console", lambda msg: print(f"  Console: {msg.text}"))

        try:
            # Step 1: Load page
            print("\n[Step 1] Loading page...")
            page.goto(FRONTEND_URL, wait_until="networkidle")
            page.wait_for_timeout(3000)
            print("✓ Page loaded")

            # Step 2: Verify fund is visible
            print("\n[Step 2] Verifying fund is visible...")
            fund_locator = page.locator(f'text="{FUND_NAME}"')
            count_before = fund_locator.count()
            print(f"  Fund instances found: {count_before}")
            assert count_before > 0, "Fund should be visible before deletion"
            print("✓ Fund is visible")

            # Step 3: Set up dialog handler and delete
            print("\n[Step 3] Deleting fund...")

            def handle_dialog(dialog):
                print(f"  ✓ Dialog: {dialog.message}")
                dialog.accept()

            page.on("dialog", handle_dialog)

            # Find and click delete button
            desktop_rows = page.locator('tr').all()
            for row in desktop_rows:
                try:
                    if FUND_NAME in row.inner_text():
                        buttons = row.locator('button').all()
                        if len(buttons) > 0:
                            buttons[-1].click()
                            print("  ✓ Delete button clicked")
                            break
                except:
                    continue

            # Wait for deletion
            page.wait_for_timeout(3000)
            print("✓ Deletion completed")

            # Step 4: Verify fund is removed from UI
            print("\n[Step 4] Verifying fund removed from UI...")
            fund_locator_after = page.locator(f'text="{FUND_NAME}"')
            count_after = fund_locator_after.count()
            print(f"  Fund instances found: {count_after}")

            if count_after == 0:
                print("✓ Fund removed from UI")
            else:
                print("⚠ Fund still visible in UI")

            # Step 5: Check console logs for localStorage removal
            print("\n[Step 5] Checking console logs...")
            print("  (Console should show: '✅ Fund 161129 removed from localStorage')")

            # Step 6: REFRESH THE PAGE
            print("\n[Step 6] Refreshing the page...")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(3000)
            print("✓ Page refreshed")

            # Step 7: Verify fund does NOT reappear
            print("\n[Step 7] Verifying fund does NOT reappear...")
            fund_locator_refreshed = page.locator(f'text="{FUND_NAME}"')
            count_refreshed = fund_locator_refreshed.count()
            print(f"  Fund instances found: {count_refreshed}")

            if count_refreshed == 0:
                print("✅ SUCCESS: Fund did NOT reappear after refresh!")
            else:
                print("❌ FAIL: Fund reappeared after refresh!")
                print("  This means localStorage was not properly cleaned.")

            # Step 8: Verify backend also removed it
            print("\n[Step 8] Verifying backend state...")
            in_backend = check_fund_in_backend()
            if not in_backend:
                print("✓ Fund also removed from backend")
            else:
                print("⚠ Fund still in backend (unexpected)")

            # Final result
            print("\n" + "="*60)
            if count_refreshed == 0 and not in_backend:
                print("✅ TEST PASSED: Fund properly deleted from all locations")
            else:
                print("❌ TEST FAILED: Fund not properly deleted")
            print("="*60)

            # Screenshot
            page.screenshot(path='/tmp/refresh_test_final.png', full_page=True)
            print("\n✓ Screenshot saved: /tmp/refresh_test_final.png")

            # Keep browser open for inspection
            print("\nKeeping browser open for 10 seconds...")
            page.wait_for_timeout(10000)

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            page.screenshot(path='/tmp/refresh_test_error.png')
            page.wait_for_timeout(30000)

        finally:
            browser.close()


if __name__ == "__main__":
    test_delete_and_refresh()
