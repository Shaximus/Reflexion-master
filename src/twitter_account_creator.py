#!/usr/bin/env python3
"""
Twitter Account Creator - Automated via Claude's Telephone
Uses browser automation, SMS verification, captcha solving
Integrates with Vultr VPS for IP rotation
"""

import json
import random
import string
import time
import requests
from datetime import datetime
from typing import Optional, Dict

# Configuration
TELEPHONE_BASE = "https://claudes-telephone.kingsley-w-m-curtis.workers.dev"
VULTR_API_KEY = "YOUR_VULTR_API_KEY"  # Set via env
SMS_SERVICE = "5sim"  # or other service integrated with /sms endpoint

class TwitterAccountCreator:
    """Automated Twitter account creation via Claude's Telephone"""
    
    def __init__(self, telephone_jwt: str):
        self.jwt = telephone_jwt
        self.headers = {"Authorization": f"Bearer {telephone_jwt}"}
        self.browser_session = None
    
    def generate_identity(self) -> Dict:
        """Generate random but realistic identity"""
        # Name generation
        first_names = ["Alex", "Jordan", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Skyler", "Dakota", "Reese"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        
        # Username with random suffix
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        username = f"{first.lower()}{last.lower()}{suffix}"
        
        # Email (use your catch-all domain)
        email = f"{username}@reflexionsoftware.com"
        
        # Password
        password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%", k=16))
        
        # Birthdate (18-45 years old)
        year = random.randint(1979, 2006)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        return {
            "name": f"{first} {last}",
            "username": username,
            "email": email,
            "password": password,
            "birthdate": {"year": year, "month": month, "day": day}
        }
    
    def rotate_vultr_ip(self) -> str:
        """Rotate IP via Vultr VPS"""
        # Create/destroy instances to get new IPs
        # Or use Vultr's floating IPs
        # Implementation depends on your Vultr setup
        pass
    
    def get_phone_number(self) -> str:
        """Get phone number via /sms endpoint"""
        response = requests.post(
            f"{TELEPHONE_BASE}/sms",
            headers=self.headers,
            json={"action": "get_number", "country": "us", "service": "twitter"}
        )
        data = response.json()
        return data["phone_number"], data["id"]  # number and order ID
    
    def get_sms_code(self, order_id: str, timeout: int = 120) -> Optional[str]:
        """Poll for SMS verification code"""
        start = time.time()
        while time.time() - start < timeout:
            response = requests.post(
                f"{TELEPHONE_BASE}/sms",
                headers=self.headers,
                json={"action": "get_sms", "id": order_id}
            )
            data = response.json()
            if data.get("code"):
                return data["code"]
            time.sleep(5)
        return None
    
    def start_browser(self) -> str:
        """Start browser session via Telephone"""
        response = requests.get(
            f"{TELEPHONE_BASE}/browser?action=start&url=https://twitter.com/i/flow/signup",
            headers=self.headers
        )
        data = response.json()
        self.browser_session = data["sessionId"]
        return self.browser_session
    
    def browser_action(self, action: str, **params) -> Dict:
        """Execute browser action"""
        url = f"{TELEPHONE_BASE}/browser?session={self.browser_session}&action={action}"
        for key, value in params.items():
            url += f"&{key}={value}"
        
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def solve_captcha(self, site_key: str, page_url: str) -> str:
        """Solve captcha via /captcha endpoint"""
        response = requests.post(
            f"{TELEPHONE_BASE}/captcha",
            headers=self.headers,
            json={"type": "recaptcha", "site_key": site_key, "page_url": page_url}
        )
        data = response.json()
        return data["token"]
    
    def create_account(self) -> Dict:
        """Full account creation workflow"""
        identity = self.generate_identity()
        print(f"[{datetime.now()}] Creating: {identity['username']}")
        
        # Start browser
        session = self.start_browser()
        print(f"  Browser session: {session}")
        
        try:
            # Step 1: Fill name
            self.browser_action("type", selector='input[name="name"]', text=identity["name"])
            time.sleep(random.uniform(0.5, 1.5))
            
            # Step 2: Fill phone (use email instead if possible)
            # Twitter sometimes allows email-only signup
            phone, order_id = self.get_phone_number()
            print(f"  Phone: {phone}")
            
            self.browser_action("type", selector='input[name="phone_number"]', text=phone)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Step 3: Birthdate
            self.browser_action("select", selector='select[aria-label="Month"]', text=str(identity["birthdate"]["month"]))
            self.browser_action("select", selector='select[aria-label="Day"]', text=str(identity["birthdate"]["day"]))
            self.browser_action("select", selector='select[aria-label="Year"]', text=str(identity["birthdate"]["year"]))
            time.sleep(random.uniform(0.5, 1.5))
            
            # Step 4: Click Next
            self.browser_action("click", selector='[role="button"]:has-text("Next")')
            time.sleep(random.uniform(2, 4))
            
            # Step 5: Handle verification (if prompted)
            # Check if captcha appears
            html = self.browser_action("html")
            if "captcha" in html.lower():
                print("  Captcha detected - solving...")
                # Extract site_key and solve
                # token = self.solve_captcha(site_key, "https://twitter.com")
                # Inject token
            
            # Step 6: Get SMS code
            print("  Waiting for SMS...")
            code = self.get_sms_code(order_id)
            if not code:
                raise Exception("SMS timeout")
            print(f"  Code: {code}")
            
            # Step 7: Enter verification code
            self.browser_action("type", selector='input[autocomplete="one-time-code"]', text=code)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Step 8: Click verify
            self.browser_action("click", selector='[role="button"]:has-text("Verify")')
            time.sleep(random.uniform(2, 4))
            
            # Step 9: Set password
            self.browser_action("type", selector='input[name="password"]', text=identity["password"])
            time.sleep(random.uniform(0.5, 1.5))
            
            # Step 10: Click Next to create account
            self.browser_action("click", selector='[role="button"]:has-text("Sign up")')
            time.sleep(random.uniform(3, 6))
            
            # Check if account created successfully
            html = self.browser_action("html")
            if "home" in html.lower() or "welcome" in html.lower():
                print(f"  ✓ Account created: @{identity['username']}")
                
                # Save credentials
                self.save_credentials(identity)
                
                # Close browser
                self.browser_action("action", action="close")
                
                return identity
            else:
                raise Exception("Account creation failed - unknown state")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            # Screenshot for debugging
            self.browser_action("screenshot")
            self.browser_action("action", action="close")
            raise
    
    def save_credentials(self, identity: Dict):
        """Save credentials to secure storage"""
        # Store in Telephone KV or local encrypted file
        timestamp = datetime.now().isoformat()
        entry = {
            **identity,
            "created_at": timestamp,
            "phone": identity.get("phone"),
            "status": "active"
        }
        
        # Save to KV
        requests.post(
            f"{TELEPHONE_BASE}/kv?k=twitter_account_{identity['username']}",
            headers=self.headers,
            json={"value": entry}
        )
        
        # Also save locally
        with open("/home/shax/Desktop/Shax_inbox/twitter_accounts.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

def main():
    """Create accounts in batch"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python twitter_account_creator.py <TELEPHONE_JWT> [count]")
        sys.exit(1)
    
    jwt = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    creator = TwitterAccountCreator(jwt)
    
    for i in range(count):
        print(f"\n[{i+1}/{count}]")
        try:
            account = creator.create_account()
            print(f"  Saved: {account['username']}")
            
            # Delay between accounts
            if i < count - 1:
                delay = random.randint(300, 900)  # 5-15 minutes
                print(f"  Waiting {delay}s before next...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"  Failed: {e}")
            continue

if __name__ == "__main__":
    main()
