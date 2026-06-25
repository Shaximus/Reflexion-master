#!/usr/bin/env python3
"""
SIMPLE PLAYWRIGHT TEST
Quick test to verify Playwright is working correctly
"""

import asyncio
import sys
from pathlib import Path

async def test_playwright():
    """Test basic Playwright functionality"""
    print("Testing Playwright installation...")
    
    try:
        from playwright.async_api import async_playwright
        print("✅ Playwright imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Playwright: {e}")
        return False
    
    try:
        async with async_playwright() as p:
            print("🌐 Launching browser...")
            browser = await p.chromium.launch(headless=True)
            print("✅ Browser launched")
            
            page = await browser.new_page()
            print("📄 Created new page")
            
            print("🔗 Navigating to example.com...")
            await page.goto('https://example.com')
            
            title = await page.title()
            print(f"📝 Page title: {title}")
            
            # Take a screenshot
            screenshot_path = Path("test_screenshot.png")
            await page.screenshot(path=str(screenshot_path))
            print(f"📸 Screenshot saved to: {screenshot_path}")
            
            await browser.close()
            print("✅ Browser closed")
            
            return title == "Example Domain"
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_stealth():
    """Test playwright-stealth"""
    print("\nTesting playwright-stealth...")
    
    try:
        from playwright_stealth import stealth_async
        print("✅ playwright-stealth imported")
        
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Apply stealth
            await stealth_async(context)
            print("✅ Stealth applied to context")
            
            page = await context.new_page()
            
            # Test on a bot detection site
            print("🔍 Testing on bot detection site...")
            await page.goto('https://bot.sannysoft.com')
            await page.screenshot(path="bot_test.png")
            print("📸 Bot test screenshot saved")
            
            await browser.close()
            print("✅ Stealth test complete")
            return True
            
    except Exception as e:
        print(f"❌ Stealth test failed: {e}")
        return False

def main():
    """Main test runner"""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║              PLAYWRIGHT INSTALLATION TEST                     ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Test basic Playwright
    result1 = asyncio.run(test_playwright())
    
    # Test stealth
    result2 = asyncio.run(test_stealth())
    
    print("\n" + "="*60)
    print("TEST RESULTS:")
    print("="*60)
    print(f"Basic Playwright: {'✅ PASSED' if result1 else '❌ FAILED'}")
    print(f"Playwright Stealth: {'✅ PASSED' if result2 else '❌ FAILED'}")
    
    if result1 and result2:
        print("\n✨ All tests passed! You can now run the debug script:")
        print("python debug_account_creator.py --test-all --use-mocks --headless")
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
