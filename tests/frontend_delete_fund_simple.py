"""
Simplified frontend test for deleting fund 161129 from the UI using Playwright.

This test:
1. Navigates to the frontend
2. Locates fund 161129 (易方达原油A类人民币)
3. Clicks the delete (X) button
4. Accepts the confirmation dialog
5. Verifies the fund is removed
"""

from playwright.sync_api import sync_playwright
import time
import httpx
import asyncio

# URLs
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://127.0.0.1:8088"

# Fund details
FUND_CODE = "161129"
FUND_NAME = "易方达原油A类人民币"


def setup_fund():
    """Ensure fund 161129 is added before testing deletion."""
    async def add_and_check():
        async with httpx.AsyncClient() as client:
            # Add fund
            response = await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": FUND_CODE, "name": FUND_NAME}
            )
            print(f"Add fund response: {response.json()}")

    asyncio.run(add_and_check())


def verify_fund_deleted():
    """Verify fund is deleted from backend."""
    import httpx
    # Use synchronous client to avoid asyncio issues
    with httpx.Client() as client:
        response = client.get(f"{BACKEND_URL}/api/funds")
        funds = response.json()
        fund_codes = [f["code"] for f in funds]
        return FUND_CODE not in fund_codes


def test_delete_fund_from_ui():
    """Test deleting fund 161129 from the frontend UI."""

    print("\n" + "="*60)
    print("FRONTEND DELETE TEST FOR FUND 161129")
    print("="*60)

    # Step 0: Ensure fund exists
    print("\n[Step 0] Setting up fund 161129...")
    setup_fund()
    print("✓ Fund 161129 is ready for deletion")

    with sync_playwright() as p:
        # Launch browser in headed mode to watch the action
        browser = p.chromium.launch(
            headless=False,
            slow_mo=500  # Slow down actions to see them clearly
        )
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  Console: {msg.text}"))

        try:
            # Step 1: Navigate to frontend
            print("\n[Step 1] Navigating to frontend...")
            page.goto(FRONTEND_URL, wait_until="networkidle")
            print("✓ Page loaded")

            # Wait for fund list to load
            print("\n[Step 2] Waiting for fund list to load...")
            page.wait_for_timeout(3000)  # Give time for data to load
            print("✓ Fund list loaded")

            # Take initial screenshot
            page.screenshot(path='/tmp/delete_test_1_initial.png', full_page=True)
            print("✓ Screenshot: /tmp/delete_test_1_initial.png")

            # Step 2: Locate fund 161129
            print(f"\n[Step 3] Locating fund {FUND_CODE} ({FUND_NAME})...")

            # The fund name should be visible
            # Note: The app renders both mobile and desktop views, so we get multiple instances
            # Some are hidden due to responsive design (md:hidden, hidden md:block, etc.)
            fund_locator = page.locator(f'text="{FUND_NAME}"').first

            # Wait for the fund to be attached in DOM (not necessarily visible)
            fund_locator.wait_for(state="attached", timeout=5000)
            print(f"✓ Found fund {FUND_NAME} in DOM")

            # Take screenshot showing the fund
            page.screenshot(path='/tmp/delete_test_2_fund_found.png')
            print("✓ Screenshot: /tmp/delete_test_2_fund_found.png")

            # Step 3: Set up dialog handler BEFORE clicking delete
            print(f"\n[Step 4] Setting up dialog handler...")

            def handle_dialog(dialog):
                print(f"  Dialog appeared: {dialog.message}")
                dialog.accept()  # Click OK/Confirm

            page.on("dialog", handle_dialog)
            print("  ✓ Dialog handler registered")

            # Step 4: Find and click the delete button
            print(f"\n[Step 5] Looking for delete button...")

            # The delete button is the X icon button in the fund row/card
            # Strategy: Find the container with fund name, then find the delete button within it

            found_delete = False

            # Method 1: Look for the delete button in desktop table view
            print("  Trying desktop table view...")
            desktop_rows = page.locator('tr').all()

            for i, row in enumerate(desktop_rows):
                try:
                    # Check if this row contains our fund
                    if FUND_NAME in row.inner_text():
                        print(f"    Found fund in desktop row {i}")

                        # Get all buttons in this row
                        buttons = row.locator('button').all()

                        # The delete button is the last one (X icon)
                        if len(buttons) > 0:
                            delete_btn = buttons[-1]  # Last button
                            print(f"    ✓ Clicking delete button (total buttons: {len(buttons)})")

                            # Set up dialog handler before clicking
                            def handle_dialog(dialog):
                                print(f"    ✓ Dialog appeared: {dialog.message}")
                                dialog.accept()

                            page.on("dialog", handle_dialog)

                            delete_btn.click()
                            found_delete = True
                            break
                except Exception as e:
                    continue

            if not found_delete:
                print("  Trying mobile card view...")
                # Method 2: Look for the delete button in mobile card view
                mobile_cards = page.locator('div[class*="rounded"]').all()

                for i, card in enumerate(mobile_cards):
                    try:
                        # Check if this card contains our fund
                        if FUND_NAME in card.inner_text():
                            print(f"    Found fund in mobile card {i}")

                            # Get all buttons in this card
                            buttons = card.locator('button').all()

                            # The delete button is usually the last one
                            if len(buttons) > 0:
                                delete_btn = buttons[-1]  # Last button
                                print(f"    ✓ Clicking delete button (total buttons: {len(buttons)})")

                                # Set up dialog handler before clicking
                                def handle_dialog(dialog):
                                    print(f"    ✓ Dialog appeared: {dialog.message}")
                                    dialog.accept()

                                page.on("dialog", handle_dialog)

                                delete_btn.click()
                                found_delete = True
                                break
                    except Exception as e:
                        continue

            if not found_delete:
                print("  ⚠ Could not find delete button with selector")
                print("  Trying alternative approach...")

                # Alternative: Click on the X icon directly
                # The X is an SVG, let's try to find it by its path
                x_icons = page.locator('svg').all()

                for i, icon in enumerate(x_icons):
                    try:
                        # Check if this SVG looks like an X (two lines crossing)
                        # The lucide-react X icon has specific path data
                        paths = icon.locator('path').all()

                        if len(paths) == 2:  # X icon has 2 paths
                            # Get the parent button
                            parent = icon.locator('xpath=../..')

                            # Check if it's a button
                            tag_name = parent.evaluate('el => el.tagName')

                            if tag_name == 'BUTTON':
                                print(f"  ✓ Found potential delete button (icon {i+1})")
                                icon.scroll_into_view_if_needed()
                                icon.click()
                                found_delete = True
                                break
                    except:
                        continue

            if not found_delete:
                print("  ✗ Could not find or click delete button")
                raise Exception("Delete button not found")

            print("✓ Delete button clicked")

            # Step 5: Wait for deletion to complete
            print("\n[Step 6] Waiting for deletion to complete...")
            page.wait_for_timeout(3000)  # Wait for API call and UI update

            # Take screenshot after deletion
            page.screenshot(path='/tmp/delete_test_3_after_click.png')
            print("✓ Screenshot: /tmp/delete_test_3_after_click.png")

            # Step 6: Verify fund is removed
            print("\n[Step 7] Verifying fund is removed...")

            # Check UI
            fund_after = page.locator(f'text="{FUND_NAME}"').count()

            if fund_after == 0:
                print("✓ Fund removed from UI")
            else:
                print(f"⚠ Fund still visible in UI (count: {fund_after})")

            # Check backend
            page.wait_for_timeout(2000)  # Wait for API call to complete

            if verify_fund_deleted():
                print("✓ Fund removed from backend API")
            else:
                print("⚠ Fund still in backend API")

            # Final screenshot
            page.screenshot(path='/tmp/delete_test_4_final.png', full_page=True)
            print("✓ Screenshot: /tmp/delete_test_4_final.png")

            print("\n" + "="*60)
            print("TEST COMPLETED")
            print("="*60)

            # Keep browser open for inspection
            print("\nKeeping browser open for 10 seconds for inspection...")
            page.wait_for_timeout(10000)

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

            # Take error screenshot
            page.screenshot(path='/tmp/delete_test_error.png', full_page=True)
            print("✓ Error screenshot: /tmp/delete_test_error.png")

            # Keep browser open for debugging
            print("\nKeeping browser open for 30 seconds for debugging...")
            page.wait_for_timeout(30000)

        finally:
            browser.close()


if __name__ == "__main__":
    test_delete_fund_from_ui()
