#!/usr/bin/env python3
"""
SECURITY QUICK FIX
Applies all of ChatGPT's recommended security fixes in one shot
Run this ONCE to fix the issues ChatGPT found
"""

import os
import secrets
from pathlib import Path

print("""
╔══════════════════════════════════════════════════════════╗
║        APPLYING CHATGPT'S SECURITY FIXES                 ║
╚══════════════════════════════════════════════════════════╝
""")

# 1. Check/Create .env with proper keys
env_file = Path(".env")
env_content = env_file.read_text() if env_file.exists() else ""

fixes_needed = []

# Check for ADMIN_KEY
if "ADMIN_KEY=" not in env_content:
    admin_key = secrets.token_urlsafe(32)
    fixes_needed.append(f"ADMIN_KEY={admin_key}")
    print(f"✅ Generated ADMIN_KEY: {admin_key[:20]}...")
else:
    print("✓ ADMIN_KEY already in .env")

# Check for RAPIDAPI_KEY
if "RAPIDAPI_KEY=" not in env_content:
    fixes_needed.append("RAPIDAPI_KEY=YOUR_RAPIDAPI_KEY_HERE")
    print("⚠️ Added RAPIDAPI_KEY placeholder - UPDATE WITH YOUR KEY!")
else:
    print("✓ RAPIDAPI_KEY already in .env")

# Write new keys to .env
if fixes_needed:
    with open(".env", "a") as f:
        f.write("\n# Security fixes added by quickfix\n")
        for fix in fixes_needed:
            f.write(f"{fix}\n")
    print(f"✅ Updated .env with {len(fixes_needed)} keys")

# 2. Copy gitignore_secure to .gitignore
gitignore_secure = Path("gitignore_secure.txt")
gitignore = Path(".gitignore")

if gitignore_secure.exists() and not gitignore.exists():
    gitignore.write_text(gitignore_secure.read_text())
    print("✅ Created .gitignore from gitignore_secure.txt")
elif gitignore.exists():
    print("✓ .gitignore already exists")
else:
    # Use the one from the artifact
    print("⚠️ Creating basic .gitignore")
    gitignore.write_text("""# Secrets
.env
*.env
soul_data.json
soul_auth_tokens.json
banned_souls.json
*.pem
*.key

# Runtime
__pycache__/
*.pyc
*.log
*.db
*.pkl
engagement/
logs/
memlogs/

# OS/IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
""")
    print("✅ Created basic .gitignore")

# 3. Create required directories
required_dirs = ["engagement", "logs", "memlogs"]
for dir_name in required_dirs:
    Path(dir_name).mkdir(exist_ok=True)
print(f"✅ Created/verified {len(required_dirs)} directories")

# 4. Check if soul_data.json exists, create template if not
soul_data = Path("soul_data.json")
if not soul_data.exists():
    template = {
        "mirror": {"auth_token": "GET_FROM_BROWSER_COOKIES"},
        "nexus": {"auth_token": "GET_FROM_BROWSER_COOKIES"},
        "echoes": {"auth_token": "GET_FROM_BROWSER_COOKIES"},
        "void": {"auth_token": "GET_FROM_BROWSER_COOKIES"},
        "architect": {"auth_token": "GET_FROM_BROWSER_COOKIES"},
    }
    import json
    with open(soul_data, "w") as f:
        json.dump(template, f, indent=2)
    print("✅ Created soul_data.json template")
else:
    print("✓ soul_data.json already exists")

# 5. Show what needs manual action
print("""
╔══════════════════════════════════════════════════════════╗
║                  MANUAL ACTIONS NEEDED                   ║
╚══════════════════════════════════════════════════════════╝

1. UPDATE YOUR .env FILE:
   - Replace YOUR_RAPIDAPI_KEY_HERE with your actual RapidAPI key
   - The one that was hardcoded: b6b201782cmsh...
   
2. GET SOUL TOKENS:
   - Login to each soul Twitter account
   - F12 → Application → Cookies → auth_token
   - Update soul_data.json with real tokens

3. TEST THE SETUP:
   Terminal 1: python admin_api_secure.py
   Terminal 2: python security_test_script.py

4. OPTIONAL BUT RECOMMENDED:
   - Set firewall to block inbound (see SECURITY.md)
   - Run as non-admin user
   - Rotate the leaked RapidAPI key

╔══════════════════════════════════════════════════════════╗
║                    SECURITY STATUS                       ║
╚══════════════════════════════════════════════════════════╝
""")

# Check current status
checks = [
    ("ADMIN_KEY", "ADMIN_KEY=" in open(".env").read() if env_file.exists() else False),
    ("RAPIDAPI_KEY placeholder", "RAPIDAPI_KEY=" in open(".env").read() if env_file.exists() else False),
    (".gitignore", gitignore.exists()),
    ("Required directories", all(Path(d).exists() for d in required_dirs)),
    ("soul_data.json", soul_data.exists()),
]

for check, status in checks:
    status_icon = "✅" if status else "❌"
    print(f"  {status_icon} {check}")

print("""
╔══════════════════════════════════════════════════════════╗
║         ChatGPT's fixes have been applied! 🎉            ║
╚══════════════════════════════════════════════════════════╝

Next steps:
1. Add your RAPIDAPI_KEY to .env
2. Start admin API: python admin_api_secure.py
3. Run tests: python security_test_script.py
""")
