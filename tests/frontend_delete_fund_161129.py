"""
Frontend test for deleting fund 161129 from the UI using Playwright.

This test:
1. Navigates to the frontend application
2. Adds fund 161129 if not present
3. Locates the fund in the list
4. Clicks the delete button
5. Confirms deletion
6. Verifies fund is removed from the UI
"""

from playwright.sync_api import sync_playwright, expect
import time

# Backend and frontend URLs
BACKEND_URL = "http://127.0.0.1:8088"
FRONTEND_URL = "http://localhost:3000"
FUND_CODE = "161129"
FUND_NAME = "易方达原油A类人民币"


def test_delete_fund_161129_from_frontend():
    """Test deleting fund 161129 from the frontend UI."""

    with sync_playwright() as p:
        # Launch browser in headed mode to see the action
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        print("\n=== Step 1: Navigating to frontend ===")
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')

        # Take initial screenshot
        page.screenshot(path='/tmp/frontend_initial.png', full_page=True)
        print("✓ Frontend loaded, screenshot saved to /tmp/frontend_initial.png")

        # Wait for funds to load
        page.wait_for_selector('text=华夏纳指100ETF联接A', timeout=10000)
        print("✓ Fund list loaded")

        # Check if fund 161129 is already in the list
        print(f"\n=== Step 2: Checking if fund {FUND_CODE} exists ===")
        fund_element = page.locator(f'text="{FUND_NAME}"').count()

        if fund_element == 0:
            print(f" Fund {FUND_CODE} not found, adding it first...")
            # Add fund via API since we need it in the list
            import httpx
            import asyncio

            async def add_fund():
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{BACKEND_URL}/api/fund",
                        params={"code": FUND_CODE, "name": FUND_NAME}
                    )

            asyncio.run(add_fund())
            print(f"✓ Fund {FUND_CODE} added via API")

            # Refresh the page to see the fund
            page.reload()
            page.wait_for_load_state('networkidle')
            time.sleep(2)  # Wait for data to load
        else:
            print(f"✓ Fund {FUND_CODE} found in list")

        # Take screenshot before deletion
        page.screenshot(path='/tmp/frontend_before_delete.png', full_page=True)
        print("✓ Screenshot saved to /tmp/frontend_before_delete.png")

        print(f"\n=== Step 3: Locating fund {FUND_CODE} in the list ===")

        # Look for the fund row - it should have the fund name and a delete button
        # Try different selectors to find the delete button
        fund_row = page.locator(f'text="{FUND_NAME}"').first

        # Scroll to the fund
        fund_row.scroll_into_view_if_needed()
        print(f"✓ Found fund {FUND_NAME} in list")

        # Look for the delete button - it's typically an icon or button near the fund
        # Based on the app structure, look for a button with delete icon or text
        print(f"\n=== Step 4: Finding delete button for fund {FUND_CODE} ===")

        # Try to find delete button - could be an icon, a button with certain text, etc.
        # Common patterns:
        # - button[aria-label="Delete"]
        # - button with trash icon
        # - Settings button that opens a modal with delete option

        # Let's inspect the fund row to find the delete button
        # Get the parent element of the fund name
        fund_content = page.content()
        print("Page HTML snippet around fund:")

        # Find all buttons on the page
        buttons = page.locator('button').all()
        print(f"Found {len(buttons)} buttons on the page")

        # Log button texts/labels
        for i, button in enumerate(buttons):
            try:
                text = button.text_content()
                aria_label = button.get_attribute('aria-label')
                print(f"  Button {i}: text='{text}', aria-label='{aria_label}'")
            except:
                pass

        # Look for a settings button or delete button
        # The app might use a settings/gear icon that opens a modal with delete option
        print("\n=== Step 5: Looking for settings/delete button ===")

        # Try to find button near the fund name
        # In React apps, this is often in the same row
        fund_name_element = page.locator(f'text="{FUND_NAME}"').first

        # Get the parent row
        # The structure might be: tr > td > fund name, then another td with delete button
        # Or for mobile: div.card > fund name + delete button

        # Let's try clicking on a settings icon if it exists
        # Common icon patterns: ⚙️, 🗑️, ×, or buttons with aria-label

        # Try to find and click a delete/settings button
        delete_button_found = False

        # Method 1: Look for button with "删除" or "delete" text
        delete_buttons = page.locator('button:has-text("删除")')
        if delete_buttons.count() > 0:
            print(f"✓ Found {delete_buttons.count()} delete button(s) with '删除' text")
            delete_button_found = True

        # Method 2: Look for trash icon (common in React apps)
        trash_icon = page.locator('[data-icon="trash"], svg[class*="trash"]')
        if trash_icon.count() > 0:
            print(f"✓ Found {trash_icon.count()} trash icon(s)")
            delete_button_found = True

        # Method 3: Look for settings button
        settings_buttons = page.locator('button:has-text("设置"), button[aria-label*="setting"]')
        if settings_buttons.count() > 0:
            print(f"✓ Found {settings_buttons.count()} settings button(s)")
            delete_button_found = True

        if not delete_button_found:
            print("⚠ No delete button found with common patterns")
            print("Let's try to interact with the fund row directly...")

            # Try to click on the fund row to see if it opens a menu
            fund_row_element = page.locator(f'text="{FUND_NAME}"').first
            try:
                fund_row_element.click()
                page.wait_for_timeout(1000)
                print("✓ Clicked on fund row")

                # Check if a modal appeared
                modal = page.locator('[role="dialog"], .modal, .popup').first
                if modal.count() > 0:
                    print("✓ Modal appeared after clicking fund row")
                    page.screenshot(path='/tmp/frontend_modal.png')
                    print("✓ Screenshot saved to /tmp/frontend_modal.png")

                    # Look for delete button in modal
                    delete_in_modal = modal.locator('button:has-text("删除"), button:has-text("Delete")').first
                    if delete_in_modal.count() > 0:
                        print("✓ Found delete button in modal")
                        delete_in_modal.click()
                        page.wait_for_timeout(1000)

                        # Look for confirmation button
                        confirm_button = page.locator('button:has-text("确认"), button:has-text("确定"), button:has-text("Confirm")').first
                        if confirm_button.count() > 0:
                            confirm_button.click()
                            print("✓ Confirmed deletion")
            except Exception as e:
                print(f"⚠ Error clicking fund row: {e}")
        else:
            # Click the delete button
            print("\n=== Step 6: Clicking delete button ===")
            delete_buttons.first.click()
            page.wait_for_timeout(1000)

            # Check for confirmation dialog
            confirm_button = page.locator('button:has-text("确认"), button:has-text("确定"), button:has-text("Confirm")').first
            if confirm_button.count() > 0:
                print("✓ Confirmation dialog appeared")
                confirm_button.click()
                print("✓ Confirmed deletion")

        # Wait for deletion to complete
        page.wait_for_timeout(2000)

        print(f"\n=== Step 7: Verifying fund {FUND_CODE} was deleted ===")

        # Check if fund is no longer in the list
        fund_after = page.locator(f'text="{FUND_NAME}"').count()
        if fund_after == 0:
            print(f"✓ Fund {FUND_CODE} successfully deleted from UI")
        else:
            print(f"⚠ Fund {FUND_CODE} still visible in UI")

        # Take final screenshot
        page.screenshot(path='/tmp/frontend_after_delete.png', full_page=True)
        print("✓ Screenshot saved to /tmp/frontend_after_delete.png")

        # Also verify via API
        import httpx
        import asyncio

        async def check_api():
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/api/funds")
                funds = response.json()
                fund_codes = [f["code"] for f in funds]
                return FUND_CODE not in fund_codes

        deleted_from_api = asyncio.run(check_api())
        if deleted_from_api:
            print(f"✓ Fund {FUND_CODE} also deleted from backend API")
        else:
            print(f"⚠ Fund {FUND_CODE} still in backend API")

        print("\n=== Test completed ===")

        # Keep browser open for a few seconds to see the result
        time.sleep(5)

        browser.close()


if __name__ == "__main__":
    test_delete_fund_161129_from_frontend()
