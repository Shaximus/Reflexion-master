#!/usr/bin/env python3
"""
QUICK DEBUG TEST - VISIBLE BROWSER
Test Twitter account creation with visible browser
"""

import asyncio
import logging
from datetime import datetime
from faker import Faker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_twitter_signup():
    """Test Twitter signup page with visible browser"""
    
    from playwright_stealth_core import StealthBrowser
    
    faker = Faker()
    
    # Generate test account
    account = {
        'name': faker.name(),
        'email': f"test_{faker.user_name()}@reflexion.ai",
        'password': faker.password(length=16, special_chars=True),
        'birth_year': faker.random_int(1985, 2003),
        'birth_month': faker.random_int(1, 12),
        'birth_day': faker.random_int(1, 28)
    }
    
    logger.info(f"Test account: {account['name']} ({account['email']})")
    
    # Launch visible browser
    browser = StealthBrowser()
    await browser.launch(headless=False)  # VISIBLE
    
    logger.info("Browser launched - you should see it!")
    
    try:
        # Navigate to Twitter signup
        logger.info("Navigating to Twitter signup...")
        await browser.page.goto("https://twitter.com/i/flow/signup")
        
        # Wait a bit for page to load
        await asyncio.sleep(5)
        
        # Take screenshot
        await browser.page.screenshot(path=f"twitter_signup_{datetime.now().strftime('%H%M%S')}.png")
        
        # Check for elements
        logger.info("Checking for signup elements...")
        
        elements = {
            'Create account button': 'span:has-text("Create account")',
            'Sign up button': 'div[role="button"]:has-text("Sign up")',
            'Name input': 'input[name="name"]',
            'Email input': 'input[name="email"]',
            'Phone input': 'input[name="phone_number"]',
        }
        
        found = {}
        for name, selector in elements.items():
            try:
                element = await browser.page.query_selector(selector)
                found[name] = element is not None
                logger.info(f"  {'✅' if element else '❌'} {name}")
            except Exception as e:
                found[name] = False
                logger.error(f"  ❌ {name}: {e}")
        
        # Try clicking Create Account if it exists
        create_btn = await browser.page.query_selector('span:has-text("Create account")')
        if create_btn:
            logger.info("Clicking 'Create account' button...")
            await create_btn.click()
            await asyncio.sleep(3)
            
            # Check for name input after clicking
            name_input = await browser.page.query_selector('input[name="name"]')
            if name_input:
                logger.info("✅ Name input appeared after clicking Create Account")
                
                # Try typing
                logger.info(f"Typing name: {account['name']}")
                await browser.human_type('input[name="name"]', account['name'])
                await asyncio.sleep(2)
            else:
                logger.warning("❌ Name input not found after clicking")
        else:
            logger.warning("Create account button not found")
        
        # Keep browser open for 10 seconds so you can see
        logger.info("Keeping browser open for 10 seconds...")
        await asyncio.sleep(10)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await browser.close()
        logger.info("Browser closed")

async def test_bot_detection():
    """Test on bot detection site with visible browser"""
    
    from playwright_stealth_core import StealthBrowser
    
    browser = StealthBrowser()
    await browser.launch(headless=False)  # VISIBLE
    
    logger.info("Testing bot detection...")
    await browser.page.goto("https://bot.sannysoft.com")
    
    await asyncio.sleep(3)
    
    # Check stealth
    checks = {
        'webdriver': await browser.page.evaluate('navigator.webdriver'),
        'chrome': await browser.page.evaluate('typeof window.chrome'),
        'plugins': await browser.page.evaluate('navigator.plugins.length'),
    }
    
    for key, val in checks.items():
        logger.info(f"  {key}: {val}")
    
    logger.info("Check the browser window to see the bot detection results!")
    await asyncio.sleep(10)
    
    await browser.close()

async def main():
    """Run tests"""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║           VISIBLE BROWSER DEBUG TEST                          ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print("\n1. Testing bot detection...")
    await test_bot_detection()
    
    print("\n2. Testing Twitter signup...")
    await test_twitter_signup()
    
    print("\n✅ Tests complete!")

if __name__ == "__main__":
    asyncio.run(main())
