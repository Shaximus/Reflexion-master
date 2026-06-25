#!/usr/bin/env python3
"""
TEST THE STEALTH CLASS - THE REAL DEAL
Found it! There's a Stealth class in playwright_stealth.stealth
"""

import asyncio
import inspect
from pathlib import Path

async def test_stealth_class():
    """Test the Stealth class we found"""
    print("="*60)
    print("TESTING STEALTH CLASS")
    print("="*60)
    
    from playwright.async_api import async_playwright
    from playwright_stealth.stealth import Stealth
    
    print(f"✅ Imported Stealth class")
    print(f"   Type: {type(Stealth)}")
    
    # Inspect the Stealth class
    print("\n📦 Stealth class methods:")
    for name in dir(Stealth):
        if not name.startswith('_'):
            attr = getattr(Stealth, name)
            print(f"  - {name}: {type(attr).__name__}")
    
    # Check if it has __init__
    if hasattr(Stealth, '__init__'):
        try:
            sig = inspect.signature(Stealth.__init__)
            print(f"\n✨ Stealth.__init__ signature: {sig}")
        except:
            pass
    
    # Try to instantiate and use it
    print("\n🧪 Testing Stealth class usage...")
    
    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # Create context
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Try to use Stealth class
            print("\n🔧 Attempting to apply Stealth...")
            
            # Method 1: Instantiate and apply
            try:
                stealth = Stealth()
                print("   Created Stealth instance")
                
                # Check for apply method
                if hasattr(stealth, 'apply'):
                    stealth.apply(context)
                    print("   ✅ Called stealth.apply(context)")
                elif hasattr(stealth, '__call__'):
                    stealth(context)
                    print("   ✅ Called stealth(context)")
                else:
                    # Try as context manager
                    print("   Trying other methods...")
                    
            except Exception as e:
                print(f"   Method 1 failed: {e}")
                
                # Method 2: Direct class usage
                try:
                    Stealth(context)
                    print("   ✅ Called Stealth(context) directly")
                except Exception as e2:
                    print(f"   Method 2 failed: {e2}")
            
            # Create page and test
            page = await context.new_page()
            await page.goto('https://bot.sannysoft.com')
            
            # Check stealth effectiveness
            checks = {
                'webdriver': await page.evaluate('navigator.webdriver'),
                'chrome': await page.evaluate('typeof window.chrome'),
                'plugins': await page.evaluate('navigator.plugins.length'),
                'languages': await page.evaluate('navigator.languages'),
                'permissions': await page.evaluate('typeof navigator.permissions'),
            }
            
            print("\n📊 Stealth check results:")
            for key, val in checks.items():
                status = "✅" if (key == 'webdriver' and val is None) or (key != 'webdriver' and val) else "⚠️"
                print(f"  {status} {key}: {val}")
            
            await page.screenshot(path='stealth_class_test.png')
            print("\n📸 Screenshot saved: stealth_class_test.png")
            
            await browser.close()
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def find_correct_usage():
    """Find the correct way to use playwright-stealth"""
    print("\n" + "="*60)
    print("FINDING CORRECT USAGE")
    print("="*60)
    
    # Read the actual source to understand it
    try:
        from playwright_stealth import stealth
        stealth_file = Path(stealth.__file__)
        
        if stealth_file.exists():
            content = stealth_file.read_text()
            
            # Look for usage patterns
            print("📖 Analyzing source code...")
            
            # Check if Stealth class has specific methods
            if 'class Stealth' in content:
                print("✅ Found Stealth class definition")
                
                # Extract class methods
                import re
                methods = re.findall(r'def\s+(\w+)\s*\(self[^)]*\)', content)
                if methods:
                    print(f"   Class methods: {', '.join(methods)}")
                
                # Look for __init__ parameters
                init_match = re.search(r'def __init__\(self([^)]*)\)', content)
                if init_match:
                    params = init_match.group(1)
                    print(f"   __init__ parameters: __init__(self{params})")
                
                # Look for usage examples in comments
                example_match = re.search(r'#.*?usage.*?:.*?\n(.*?)(?:\n\n|$)', content, re.IGNORECASE | re.DOTALL)
                if example_match:
                    print(f"\n📝 Found usage example in source:")
                    print(example_match.group(1))
            
            # Check for a standalone stealth function
            if 'def stealth(' in content:
                print("\n✅ Found standalone stealth function")
                func_match = re.search(r'def stealth\((.*?)\):', content)
                if func_match:
                    print(f"   Parameters: stealth({func_match.group(1)})")
                    
    except Exception as e:
        print(f"Error reading source: {e}")

async def test_all_approaches():
    """Test all possible approaches comprehensively"""
    print("\n" + "="*60)
    print("COMPREHENSIVE TESTING")
    print("="*60)
    
    from playwright.async_api import async_playwright
    
    approaches = []
    
    # Approach 1: Import and instantiate Stealth class
    try:
        from playwright_stealth.stealth import Stealth
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            stealth_instance = Stealth()
            # Try different method names
            for method in ['apply', 'apply_stealth', 'use', '__call__']:
                if hasattr(stealth_instance, method):
                    getattr(stealth_instance, method)(context)
                    print(f"✅ Approach 1: Stealth().{method}(context)")
                    approaches.append(f"Stealth().{method}(context)")
                    break
            
            await browser.close()
    except Exception as e:
        print(f"❌ Approach 1 failed: {e}")
    
    # Approach 2: Use Stealth as a function/decorator
    try:
        from playwright_stealth.stealth import Stealth
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Try using Stealth directly on context
            result = Stealth(context)
            print(f"✅ Approach 2: Stealth(context)")
            approaches.append("Stealth(context)")
            
            await browser.close()
    except Exception as e:
        print(f"❌ Approach 2 failed: {e}")
    
    # Approach 3: Look for module-level function
    try:
        import playwright_stealth.stealth as stealth_module
        
        # Check for a module-level stealth function
        if hasattr(stealth_module, 'stealth') and callable(stealth_module.stealth):
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                stealth_module.stealth(context)
                print(f"✅ Approach 3: stealth_module.stealth(context)")
                approaches.append("stealth_module.stealth(context)")
                
                await browser.close()
    except Exception as e:
        print(f"❌ Approach 3 failed: {e}")
    
    if approaches:
        print(f"\n✅ Working approaches found: {approaches}")
        return approaches[0]
    else:
        print("\n⚠️ No working approach found with the package")
        return None

def main():
    """Main test runner"""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║              STEALTH CLASS INVESTIGATION                      ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Test the Stealth class
    asyncio.run(test_stealth_class())
    
    # Find correct usage
    asyncio.run(find_correct_usage())
    
    # Test all approaches
    working_approach = asyncio.run(test_all_approaches())
    
    print("\n" + "="*60)
    print("FINAL RECOMMENDATION")
    print("="*60)
    
    if working_approach:
        print(f"✅ Use this approach: {working_approach}")
        print("\nCode snippet:")
        print(f"""
from playwright_stealth.stealth import Stealth
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context()
    
    # Apply stealth
    {working_approach}
    
    page = await context.new_page()
    # Your automation code here
""")
    else:
        print("✅ Use manual stealth implementation")
        print("\nSince the package isn't working properly, we'll implement")
        print("the FULL stealth manually with all advanced features!")

if __name__ == "__main__":
    main()
