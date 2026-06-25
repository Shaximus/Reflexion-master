#!/usr/bin/env python3
"""
TEST THE REAL STEALTH API
Found the methods: apply_stealth_async, use_async, etc.
"""

import asyncio
from pathlib import Path

async def test_real_stealth_api():
    """Test the real Stealth API methods"""
    print("="*60)
    print("TESTING REAL STEALTH API")
    print("="*60)
    
    from playwright.async_api import async_playwright
    from playwright_stealth.stealth import Stealth
    
    # Method 1: apply_stealth_async
    print("\n🔧 Method 1: apply_stealth_async")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Create Stealth instance with all features enabled
            stealth = Stealth(
                chrome_app=True,
                chrome_csi=True,
                chrome_load_times=True,
                chrome_runtime=True,  # Enable this too
                hairline=True,
                iframe_content_window=True,
                media_codecs=True,
                navigator_hardware_concurrency=True,
                navigator_languages=True,
                navigator_permissions=True,
                navigator_platform=True,
                navigator_plugins=True,
                navigator_user_agent=True,
                navigator_vendor=True,
                navigator_webdriver=True,
                sec_ch_ua=True,
                webgl_vendor=True,
                navigator_languages_override=('en-US', 'en'),
                navigator_platform_override='Win32',
                navigator_vendor_override='Google Inc.',
                webgl_vendor_override='Intel Inc.',
                webgl_renderer_override='Intel Iris OpenGL Engine'
            )
            
            # Apply stealth
            await stealth.apply_stealth_async(context)
            print("   ✅ Applied stealth.apply_stealth_async(context)")
            
            # Test it
            page = await context.new_page()
            await page.goto('https://bot.sannysoft.com')
            
            # Check results
            checks = {
                'webdriver': await page.evaluate('navigator.webdriver'),
                'chrome': await page.evaluate('typeof window.chrome'),
                'chrome.runtime': await page.evaluate('typeof window.chrome?.runtime'),
                'plugins': await page.evaluate('navigator.plugins.length'),
                'languages': await page.evaluate('navigator.languages'),
                'platform': await page.evaluate('navigator.platform'),
                'vendor': await page.evaluate('navigator.vendor'),
            }
            
            print("\n   📊 Results:")
            for key, val in checks.items():
                status = "✅" if (key == 'webdriver' and val is None) or (key != 'webdriver' and val) else "⚠️"
                print(f"     {status} {key}: {val}")
            
            await page.screenshot(path='stealth_method1.png')
            await browser.close()
            
    except Exception as e:
        print(f"   ❌ Method 1 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 2: use_async
    print("\n🔧 Method 2: use_async")
    try:
        async with async_playwright() as p:
            # Create Stealth instance
            stealth = Stealth(
                chrome_runtime=True,
                navigator_webdriver=True,
                navigator_plugins=True,
                navigator_languages_override=('en-US', 'en'),
            )
            
            # Use the use_async method to get a wrapped playwright
            p_stealth = await stealth.use_async(p)
            print("   ✅ Got stealth-wrapped playwright")
            
            # Launch browser with stealth playwright
            browser = await p_stealth.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto('https://bot.sannysoft.com')
            
            # Check results
            checks = {
                'webdriver': await page.evaluate('navigator.webdriver'),
                'chrome': await page.evaluate('typeof window.chrome'),
                'plugins': await page.evaluate('navigator.plugins.length'),
            }
            
            print("\n   📊 Results:")
            for key, val in checks.items():
                status = "✅" if (key == 'webdriver' and val is None) or (key != 'webdriver' and val) else "⚠️"
                print(f"     {status} {key}: {val}")
            
            await page.screenshot(path='stealth_method2.png')
            await browser.close()
            
    except Exception as e:
        print(f"   ❌ Method 2 failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 3: hook_playwright_context
    print("\n🔧 Method 3: hook_playwright_context")
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth.stealth import Stealth
        
        async with async_playwright() as p:
            # Create stealth instance
            stealth = Stealth(
                chrome_runtime=True,
                navigator_webdriver=True,
                navigator_plugins=True,
            )
            
            # Hook the playwright instance
            stealth.hook_playwright_context(p)
            print("   ✅ Hooked playwright context")
            
            # Now use playwright normally
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto('https://bot.sannysoft.com')
            
            # Check results
            checks = {
                'webdriver': await page.evaluate('navigator.webdriver'),
                'chrome': await page.evaluate('typeof window.chrome'),
                'plugins': await page.evaluate('navigator.plugins.length'),
            }
            
            print("\n   📊 Results:")
            for key, val in checks.items():
                status = "✅" if (key == 'webdriver' and val is None) or (key != 'webdriver' and val) else "⚠️"
                print(f"     {status} {key}: {val}")
            
            await page.screenshot(path='stealth_method3.png')
            await browser.close()
            
    except Exception as e:
        print(f"   ❌ Method 3 failed: {e}")
        import traceback
        traceback.print_exc()

async def create_working_implementation():
    """Create the final working implementation"""
    print("\n" + "="*60)
    print("CREATING WORKING IMPLEMENTATION")
    print("="*60)
    
    code = '''#!/usr/bin/env python3
"""
WORKING PLAYWRIGHT STEALTH IMPLEMENTATION
Based on the real API discovered
"""

from playwright.async_api import async_playwright, BrowserContext
from playwright_stealth.stealth import Stealth

async def apply_stealth_to_context(context: BrowserContext):
    """Apply stealth to an existing context"""
    stealth = Stealth(
        chrome_app=True,
        chrome_csi=True,
        chrome_load_times=True,
        chrome_runtime=True,
        hairline=True,
        iframe_content_window=True,
        media_codecs=True,
        navigator_hardware_concurrency=True,
        navigator_languages=True,
        navigator_permissions=True,
        navigator_platform=True,
        navigator_plugins=True,
        navigator_user_agent=True,
        navigator_vendor=True,
        navigator_webdriver=True,
        sec_ch_ua=True,
        webgl_vendor=True,
        navigator_languages_override=('en-US', 'en'),
        navigator_platform_override='Win32',
        navigator_vendor_override='Google Inc.',
        webgl_vendor_override='Intel Inc.',
        webgl_renderer_override='Intel Iris OpenGL Engine'
    )
    
    await stealth.apply_stealth_async(context)
    return context

async def create_stealth_browser():
    """Create a browser with stealth applied"""
    playwright = await async_playwright().start()
    
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
        ]
    )
    
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    
    # Apply stealth
    await apply_stealth_to_context(context)
    
    return playwright, browser, context

# Example usage:
async def main():
    playwright, browser, context = await create_stealth_browser()
    
    page = await context.new_page()
    await page.goto('https://bot.sannysoft.com')
    
    # Check stealth
    webdriver = await page.evaluate('navigator.webdriver')
    print(f"navigator.webdriver: {webdriver}")  # Should be None
    
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
    
    # Save the working implementation
    with open('working_stealth_implementation.py', 'w') as f:
        f.write(code)
    
    print("✅ Created working_stealth_implementation.py")
    print("\nThe correct usage is:")
    print("1. Create a Stealth instance with desired options")
    print("2. Call await stealth.apply_stealth_async(context)")
    print("3. Or use stealth.hook_playwright_context(playwright)")

def main():
    """Main test runner"""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║           TESTING REAL PLAYWRIGHT-STEALTH API                ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Test the real API
    asyncio.run(test_real_stealth_api())
    
    # Create working implementation
    asyncio.run(create_working_implementation())
    
    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    print("✅ The correct API is:")
    print("   stealth = Stealth(**options)")
    print("   await stealth.apply_stealth_async(context)")
    print("\nNow we can update playwright_stealth_core.py to use this!")

if __name__ == "__main__":
    main()
