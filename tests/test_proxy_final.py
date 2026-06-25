import asyncio
from playwright.async_api import async_playwright

async def test_with_proper_auth():
    # Split the credentials properly
    username = "jK60icuSGqVJuQVL"
    password = "7EBenwdHrLmMZu2C_streaming-1_skipispstatic-1"
    server = "geo.iproyal.com:12321"
    
    print(f"🔍 Testing IPRoyal proxy with proper authentication...")
    
    async with async_playwright() as p:
        # Launch with proxy using dict format
        browser = await p.chromium.launch(
            headless=False,
            proxy={
                "server": f"http://{server}",
                "username": username,
                "password": password
            }
        )
        
        page = await browser.new_page()
        
        try:
            # Test 1: Check IP
            print("⏳ Checking IP...")
            await page.goto("http://httpbin.org/ip", timeout=30000)
            content = await page.text_content("body")
            print(f"✅ Your IP: {content}")
            
            # Test 2: Google
            print("⏳ Testing Google...")
            await page.goto("https://www.google.com", timeout=30000)
            print("✅ Google loads!")
            
            # Test 3: Google Accounts
            print("⏳ Testing Google Accounts...")
            await page.goto("https://accounts.google.com", timeout=60000)
            print("✅ Google Accounts loads!")
            
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

asyncio.run(test_with_proper_auth())
