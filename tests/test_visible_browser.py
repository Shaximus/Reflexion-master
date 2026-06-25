#!/usr/bin/env python3
"""
TWITTER SIGNUP FIELD DETECTION FIX
Properly detect and handle Twitter's dynamic signup form fields
"""

import asyncio
import logging
from datetime import datetime
from faker import Faker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_twitter_signup():
    """Fix Twitter signup with proper field detection"""
    
    from playwright_stealth_core import StealthBrowser
    
    faker = Faker()
    
    # Generate test account
    account = {
        'name': faker.name(),
        'email': f"test_{faker.user_name()}@reflexion.ai",
        'birth_year': faker.random_int(1985, 2003),
        'birth_month': faker.random_int(1, 12),
        'birth_day': faker.random_int(1, 28)
    }
    
    logger.info(f"Test account: {account['name']}")
    logger.info(f"Email: {account['email']}")
    
    # Launch visible browser
    browser = StealthBrowser()
    await browser.launch(headless=False)
    
    try:
        # Navigate to Twitter
        logger.info("Navigating to Twitter...")
        await browser.page.goto("https://twitter.com")
        await asyncio.sleep(5)
        
        # Click Create account
        create_btn = await browser.page.wait_for_selector(
            'a[href="/i/flow/signup"]:has-text("Create account")', 
            timeout=10000
        )
        await create_btn.click()
        await asyncio.sleep(3)
        
        # CRITICAL FIX: Detect what fields are actually present
        logger.info("\n=== DETECTING FORM FIELDS ===")
        
        # Check all input fields
        inputs = await browser.page.query_selector_all('input')
        logger.info(f"Found {len(inputs)} input fields")
        
        for i, input_elem in enumerate(inputs):
            name = await input_elem.get_attribute('name')
            placeholder = await input_elem.get_attribute('placeholder')
            input_type = await input_elem.get_attribute('type')
            autocomplete = await input_elem.get_attribute('autocomplete')
            
            logger.info(f"Input {i}: name='{name}', placeholder='{placeholder}', type='{input_type}', autocomplete='{autocomplete}'")
        
        # METHOD 1: Fill fields in the correct order
        logger.info("\n=== SMART FIELD FILLING ===")
        
        # Step 1: Fill name field first
        name_input = await browser.page.query_selector('input[name="name"]')
        if name_input:
            logger.info("Found name input, filling...")
            await name_input.fill(account['name'])
            await asyncio.sleep(1)
        
        # Step 2: Check if phone/email toggle is needed
        # Twitter often shows phone field by default
        phone_input = await browser.page.query_selector('input[name="phone_number"]')
        email_input = await browser.page.query_selector('input[name="email"]')
        
        if phone_input and not email_input:
            logger.info("Phone field detected, looking for email toggle...")
            
            # Find and click "Use email instead" link
            email_toggle = await browser.page.query_selector('span:has-text("Use email instead")')
            if not email_toggle:
                email_toggle = await browser.page.query_selector('text="Use email instead"')
            if not email_toggle:
                # Try alternative selectors
                email_toggle = await browser.page.query_selector('[role="button"]:has-text("email")')
            
            if email_toggle:
                logger.info("Clicking 'Use email instead'...")
                await email_toggle.click()
                await asyncio.sleep(2)  # Wait for form to update
                
                # Re-check for email field
                email_input = await browser.page.wait_for_selector('input[name="email"]', timeout=5000)
        
        # Step 3: Fill email field
        if not email_input:
            email_input = await browser.page.query_selector('input[name="email"]')
        
        if email_input:
            logger.info("Filling email field...")
            await email_input.fill(account['email'])
            await asyncio.sleep(1)
        else:
            logger.error("⚠️ Could not find email field!")
        
        # Step 4: Handle date selection
        logger.info("\n=== DATE SELECTION ===")
        
        # Method A: Try select elements first
        selects = await browser.page.query_selector_all('select')
        if len(selects) >= 3:
            logger.info(f"Found {len(selects)} select elements")
            
            # Month
            month_select = await browser.page.query_selector('select[aria-label*="Month" i]')
            if month_select:
                await month_select.select_option(str(account['birth_month']))
                logger.info(f"✅ Set month: {account['birth_month']}")
            
            # Day
            day_select = await browser.page.query_selector('select[aria-label*="Day" i]')
            if day_select:
                await day_select.select_option(str(account['birth_day']))
                logger.info(f"✅ Set day: {account['birth_day']}")
            
            # Year
            year_select = await browser.page.query_selector('select[aria-label*="Year" i]')
            if year_select:
                await year_select.select_option(str(account['birth_year']))
                logger.info(f"✅ Set year: {account['birth_year']}")
        
        else:
            # Method B: Custom dropdowns
            logger.info("Using custom dropdown method...")
            
            # Click dropdowns and select values
            dropdowns = await browser.page.query_selector_all('div[role="button"]')
            logger.info(f"Found {len(dropdowns)} dropdown buttons")
            
            # Handle month
            month_dropdown = None
            for dropdown in dropdowns:
                text = await dropdown.text_content()
                if 'Month' in text:
                    month_dropdown = dropdown
                    break
            
            if month_dropdown:
                await month_dropdown.click()
                await asyncio.sleep(0.5)
                
                month_names = ["", "January", "February", "March", "April", "May", "June",
                              "July", "August", "September", "October", "November", "December"]
                month_name = month_names[account['birth_month']]
                
                month_option = await browser.page.query_selector(f'div[role="option"]:has-text("{month_name}")')
                if month_option:
                    await month_option.click()
                    logger.info(f"✅ Selected month: {month_name}")
        
        await asyncio.sleep(2)
        
        # Step 5: Verify all fields are filled
        logger.info("\n=== VERIFICATION ===")
        
        # Check name
        name_value = await browser.page.evaluate('document.querySelector("input[name=\\"name\\"]")?.value')
        logger.info(f"Name field value: '{name_value}'")
        
        # Check email
        email_value = await browser.page.evaluate('document.querySelector("input[name=\\"email\\"]")?.value')
        logger.info(f"Email field value: '{email_value}'")
        
        # Check if Next button is enabled
        next_buttons = await browser.page.query_selector_all('div[role="button"]:has-text("Next")')
        for btn in next_buttons:
            is_disabled = await btn.evaluate('el => el.getAttribute("aria-disabled")')
            if is_disabled != "true":
                logger.info("✅ Next button is ENABLED")
                break
        else:
            logger.warning("⚠️ Next button still disabled")
        
        # Take screenshot
        await browser.page.screenshot(path="twitter_signup_fixed.png")
        
        logger.info("\n⏳ Keeping browser open for inspection...")
        await asyncio.sleep(30)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Take error screenshot
        await browser.page.screenshot(path="twitter_signup_error.png")
    
    finally:
        await browser.close()

async def alternative_approach():
    """Alternative approach using JavaScript injection"""
    
    from playwright_stealth_core import StealthBrowser
    
    faker = Faker()
    account = {
        'name': faker.name(),
        'email': f"test_{faker.user_name()}@reflexion.ai",
        'birth_year': faker.random_int(1985, 2003),
        'birth_month': faker.random_int(1, 12),
        'birth_day': faker.random_int(1, 28)
    }
    
    browser = StealthBrowser()
    await browser.launch(headless=False)
    
    try:
        await browser.page.goto("https://twitter.com/i/flow/signup")
        await asyncio.sleep(5)
        
        # JavaScript approach to force email mode
        await browser.page.evaluate("""
            // Find and click email toggle
            const toggles = Array.from(document.querySelectorAll('span'));
            const emailToggle = toggles.find(el => el.textContent.includes('Use email'));
            if (emailToggle) {
                emailToggle.click();
                console.log('Clicked email toggle');
            }
            
            // Wait a bit then fill fields
            setTimeout(() => {
                // Fill name
                const nameInput = document.querySelector('input[name="name"]');
                if (nameInput) {
                    nameInput.value = '%s';
                    nameInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
                
                // Fill email
                const emailInput = document.querySelector('input[name="email"]');
                if (emailInput) {
                    emailInput.value = '%s';
                    emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
                
                // Set dates if select elements exist
                const selects = document.querySelectorAll('select');
                if (selects.length >= 3) {
                    selects[0].value = '%d'; // month
                    selects[1].value = '%d'; // day
                    selects[2].value = '%d'; // year
                    
                    selects.forEach(s => {
                        s.dispatchEvent(new Event('change', { bubbles: true }));
                    });
                }
            }, 2000);
        """ % (account['name'], account['email'], 
               account['birth_month'], account['birth_day'], account['birth_year']))
        
        await asyncio.sleep(5)
        await browser.page.screenshot(path="twitter_js_approach.png")
        
        logger.info("JavaScript approach completed")
        await asyncio.sleep(20)
        
    finally:
        await browser.close()

async def main():
    """Run the fix"""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║           TWITTER SIGNUP FIELD DETECTION FIX                  ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print("\n1. Smart field detection approach")
    print("2. JavaScript injection approach")
    choice = input("\nSelect approach (1 or 2): ").strip()
    
    if choice == "2":
        await alternative_approach()
    else:
        await fix_twitter_signup()
    
    print("\n✅ Test complete!")
    print("Check screenshots to see the results")

if __name__ == "__main__":
    asyncio.run(main())
