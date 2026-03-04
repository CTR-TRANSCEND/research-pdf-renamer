#!/usr/bin/env python3
"""
Test script to verify the LLM Service Status error message in the admin panel.

This test:
1. Navigates to the admin panel
2. Logs in with admin credentials
3. Clicks on the System Status tab
4. Verifies the LLM Service Status shows the improved error message
"""

import asyncio
from playwright.async_api import async_playwright
import pytest
import sys


@pytest.mark.e2e
async def test_admin_system_status():
    """Test the admin panel System Status tab and verify LLM error message."""

    # Configuration
    base_url = "http://localhost/pdf-renamer"
    admin_email = "admin@example.com"
    admin_password = "admin123"

    print("=" * 80)
    print("Admin Panel System Status Test")
    print("=" * 80)
    print(f"Base URL: {base_url}")
    print(f"Admin Email: {admin_email}")
    print()

    async with async_playwright() as p:
        # Launch browser (headless=False to see the test running)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Step 1: Navigate to admin panel
            print("[Step 1] Navigating to admin panel...")
            await page.goto(f"{base_url}/admin")
            await page.wait_for_load_state("networkidle")
            print("✓ Page loaded successfully")
            print()

            # Check if we need to login
            current_url = page.url
            print(f"Current URL: {current_url}")

            if "login" in current_url:
                # Step 2: Login via API to get token
                print("[Step 2] Logging in via API...")
                print(f"  Email: {admin_email}")

                # Use API to login and get token
                login_response = await page.request.post(
                    f"{base_url}/api/auth/login",
                    data={"email": admin_email, "password": admin_password},
                )

                if login_response.ok:
                    login_data = await login_response.json()
                    token = login_data.get(
                        "token"
                    )  # Changed from 'access_token' to 'token'

                    if token:
                        # Set the token in localStorage
                        await page.evaluate(
                            f'localStorage.setItem("auth_token", "{token}")'
                        )
                        print("✓ Login successful, token stored")

                        # Navigate to admin panel again
                        await page.goto(f"{base_url}/admin")
                        await page.wait_for_load_state("networkidle")
                        print("✓ Navigated to admin panel")
                    else:
                        print("✗ No token in response")
                        print(f"Response data: {login_data}")
                        return False
                else:
                    error_text = await login_response.text()
                    print(f"✗ Login failed: {error_text}")
                    return False
            else:
                print("✓ Already authenticated or redirected")
            print()

            # Step 3: Click on System Status tab
            print("[Step 3] Clicking on System Status tab...")

            # Set up network listener to capture API response
            api_responses = []

            async def capture_response(response):
                if "/api/admin/system-status" in response.url:
                    try:
                        data = await response.json()
                        api_responses.append(data)
                        print(f"  API Response captured: {data}")
                    except:
                        text = await response.text()
                        api_responses.append({"text": text})
                        print(f"  API Response (text): {text}")

            page.on("response", capture_response)

            await page.wait_for_selector("button#system-tab", timeout=5000)
            await page.click("button#system-tab")
            print("✓ System Status tab clicked")

            # Wait a bit for the API call to complete
            await page.wait_for_timeout(2000)
            print()

            # Step 4: Wait for system status to load
            print("[Step 4] Waiting for system status to load...")
            await page.wait_for_selector("#llm-service-status", timeout=5000)
            print("✓ System status loaded")
            print()

            # Display captured API responses
            if api_responses:
                print("Captured API Responses:")
                print("-" * 80)
                for i, resp in enumerate(api_responses):
                    print(f"Response {i + 1}:")
                    if isinstance(resp, dict):
                        import json

                        print(json.dumps(resp, indent=2))
                    print()
                print("-" * 80)
                print()
            else:
                print("Warning: No API responses captured")
                print()

            # Step 5: Check LLM Service Status
            print("[Step 5] Checking LLM Service Status...")
            print()

            # Get the LLM service status element
            llm_status_element = await page.query_selector("#llm-service-status")
            llm_status_html = await llm_status_element.inner_html()

            print("LLM Service Status HTML:")
            print("-" * 80)
            print(llm_status_html)
            print("-" * 80)
            print()

            # Check for status indicator
            status_indicator = await page.query_selector(
                "#llm-service-status .w-3.h-3.rounded-full"
            )
            if status_indicator:
                status_class = await status_indicator.get_attribute("class")

                if "bg-red-500" in status_class:
                    print("✓ Status indicator: RED (Error state)")
                elif "bg-green-500" in status_class:
                    print("✓ Status indicator: GREEN (Healthy state)")
                else:
                    print(f"? Status indicator: Unknown color ({status_class})")
            else:
                print("✗ No status indicator found")
            print()

            # Get ALL text content from the LLM service status
            all_text = await llm_status_element.inner_text()
            print("All Text Content:")
            print("-" * 80)
            print(all_text)
            print("-" * 80)
            print()

            # Check for error message in the text content
            expected_message = "API key exists but cannot be decrypted"

            if expected_message in all_text:
                print("✓ SUCCESS: Error message contains the expected text!")
                print(f"  Expected substring: '{expected_message}'")
                print()

                # Extract and display the full error message
                lines = all_text.strip().split("\n")
                for line in lines:
                    if line.strip():
                        print(f"  {line.strip()}")
                print()

                return True
            elif "Error" in all_text or "error" in all_text.lower():
                print("✗ Error state detected but message doesn't match expected text")
                print(f"  Expected to contain: '{expected_message}'")
                print(f"  Actual content: {all_text}")
                print()
                return False
            else:
                print("✗ No error message found (LLM service might be healthy)")
                print()

                # Check if it shows healthy status
                if "Healthy" in all_text:
                    print("Note: LLM service is healthy (not an error state)")
                    print("This is expected if the API key is properly configured")
                print()

                return False

        except Exception as e:
            print(f"✗ Error during test: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            # Take screenshot for debugging
            screenshot_path = "/tmp/admin_system_status_screenshot.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")
            print()

            # Close browser
            await browser.close()
            print("Browser closed")


async def main():
    """Main entry point."""
    success = await test_admin_system_status()

    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    if success:
        print("✓ Test PASSED: Improved error message is displayed correctly")
        print()
        print("The error message now reads:")
        print('  "API key exists but cannot be decrypted. This may be due to')
        print('   SECRET_KEY change. Please re-enter the API key in LLM Settings."')
        sys.exit(0)
    else:
        print("✗ Test FAILED: Expected error message not found")
        print()
        print("Possible reasons:")
        print("  1. LLM service is healthy (API key properly configured)")
        print("  2. Error message format is different")
        print("  3. System status failed to load")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
