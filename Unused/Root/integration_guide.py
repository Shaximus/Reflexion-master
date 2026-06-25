#!/usr/bin/env python3
"""
SECURITY INTEGRATION GUIDE
How to add security features to your existing Soul Swarm system
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# ============================================================================
# STEP 1: PATCH YOUR EXISTING RYAN API
# ============================================================================

def integrate_ryan_api_security():
    """Add hot-reload to your existing ryan_api_ultimate.py"""
    
    # Import your existing Ryan API
    from ryan_api_ultimate import RyanTwitterAPI
    
    # Add the hot-reload capability
    from ryan_api_hotreload import patch_existing_ryan_api, TokenWatcher
    
    # Patch the existing instance
    ryan_api = RyanTwitterAPI()
    ryan_api = patch_existing_ryan_api(ryan_api)
    
    # Start the watcher
    watcher = TokenWatcher(ryan_api)
    asyncio.create_task(watcher.start())
    
    print("✅ Ryan API patched with hot-reload")
    return ryan_api

# ============================================================================
# STEP 2: UPDATE YOUR MAIN LAUNCH SCRIPT
# ============================================================================

def patch_launch_script():
    """Modify your launch.py to include security features"""
    
    code = '''
# Add to the top of launch.py after imports:

from pathlib import Path
from admin_api_secure import atomic_write_json, audit_log

# Add hot-reload to your main loop
async def secure_main_loop(souls, ryan_api):
    """Enhanced main loop with security features"""
    
    while True:
        try:
            # Refresh tokens at loop boundary
            await ryan_api.refresh_tokens_from_disk()
            
            # Your existing posting logic
            for soul in souls:
                if soul not in ryan_api.banned_souls:
                    # Generate and post content
                    content = await generate_content(soul)
                    result = await ryan_api.post_tweet(soul, content)
                    
                    if not result["success"]:
                        if "403" in result.get("error", ""):
                            audit_log("soul_banned", f"soul={soul}", "auto")
            
            await asyncio.sleep(delay)
            
        except Exception as e:
            logging.error(f"Loop error: {e}")
            audit_log("main_loop_error", str(e)[:100], "error")
    '''
    
    print("Add this to your launch.py:")
    print(code)

# ============================================================================
# STEP 3: UPDATE CONVERGENCE MODE
# ============================================================================

def patch_convergence_mode():
    """Update swarm_convergence_mode_ryan.py for security"""
    
    code = '''
# In swarm_convergence_mode_ryan.py, update execute_engagement():

async def execute_engagement(self, action: EngagementAction) -> bool:
    """Execute with hot-reload support"""
    
    # Refresh tokens before each engagement
    await self.ryan_api.refresh_tokens_from_disk()
    
    # Check if soul is banned
    if action.soul_name in self.ryan_api.banned_souls:
        logger.info(f"⛔ Skipping banned soul: {action.soul_name}")
        return False
    
    # Rest of your existing logic...
    '''
    
    print("Update your convergence mode:")
    print(code)

# ============================================================================
# STEP 4: SETUP SCRIPT
# ============================================================================

def setup_security():
    """One-time setup for security features"""
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║           SOUL SWARM SECURITY SETUP                      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # 1. Create necessary directories
    dirs = ["engagement", "logs", "backup"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
    print("✅ Created security directories")
    
    # 2. Generate admin key if not exists
    env_file = Path(".env")
    if not env_file.exists() or "ADMIN_KEY" not in env_file.read_text():
        import secrets
        admin_key = secrets.token_urlsafe(32)
        with open(".env", "a") as f:
            f.write(f"\nADMIN_KEY={admin_key}\n")
        print(f"✅ Generated admin key: {admin_key[:20]}...")
    else:
        print("✅ Admin key already configured")
    
    # 3. Initialize audit log
    audit_file = Path("engagement/admin_changes.log")
    if not audit_file.exists():
        from admin_api_secure import audit_log
        audit_log("security_setup", "initial setup", "ok")
        print("✅ Initialized audit log")
    
    # 4. Setup .gitignore
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        print("⚠️  No .gitignore found! Creating one...")
        # Copy the secure .gitignore content here
        with open(".gitignore", "w") as f:
            f.write("""
# Secrets
.env
*.env
soul_data.json
banned_souls.json
*.pem
*.key

# Runtime
__pycache__/
*.pyc
logs/
*.log
*.db
*.pkl

# IDE
.vscode/
.idea/
.DS_Store
""")
        print("✅ Created .gitignore")
    
    # 5. Check firewall
    print("\n📋 FIREWALL SETUP REQUIRED:")
    print("Run these commands based on your OS:\n")
    
    import platform
    if platform.system() == "Windows":
        print("Windows (PowerShell as Admin):")
        print("  Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True")
        print("  Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block")
    else:
        print("Linux/macOS:")
        print("  sudo ufw default deny incoming")
        print("  sudo ufw default allow outgoing")
        print("  sudo ufw enable")
    
    print("\n✅ Security setup complete!")

# ============================================================================
# STEP 5: QUICK START COMMANDS
# ============================================================================

def print_quickstart():
    """Print quick start commands"""
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║              QUICK START COMMANDS                        ║
    ╚══════════════════════════════════════════════════════════╝
    
    1. START ADMIN API (in separate terminal):
       python admin_api_secure.py
    
    2. START MAIN SWARM (in main terminal):
       python launch.py --stealth
    
    3. UPDATE TOKEN (from another terminal):
       curl -X POST http://127.0.0.1:8765/tokens \\
         -H "X-Admin-Key: your-key" \\
         -H "Content-Type: application/json" \\
         -d '{"soul": "mirror", "token": "new-token"}'
    
    4. CHECK HEALTH:
       curl http://127.0.0.1:8765/health \\
         -H "X-Admin-Key: your-key"
    
    5. VIEW LOGS:
       tail -f engagement/admin_changes.log
    
    ╔══════════════════════════════════════════════════════════╗
    ║              TESTING HOT-RELOAD                          ║
    ╚══════════════════════════════════════════════════════════╝
    
    1. Start the swarm normally
    2. Wait for a soul to post
    3. Update its token via Admin API
    4. Watch next post use the new token (no restart!)
    
    ╔══════════════════════════════════════════════════════════╗
    ║              SECURITY CHECKLIST                          ║
    ╚══════════════════════════════════════════════════════════╝
    
    ✓ Admin API on 127.0.0.1:8765 only
    ✓ X-Admin-Key header required
    ✓ Atomic writes for all JSON files
    ✓ Hot-reload every 2 seconds
    ✓ Audit log in engagement/admin_changes.log
    ✓ Firewall blocking inbound
    ✓ .gitignore preventing credential leaks
    ✓ Running as non-admin user
    """)

# ============================================================================
# MAIN INTEGRATION
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Integration Helper")
    parser.add_argument("--setup", action="store_true", help="Run initial setup")
    parser.add_argument("--test", action="store_true", help="Test security features")
    parser.add_argument("--quickstart", action="store_true", help="Show quick start guide")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_security()
    elif args.test:
        print("Testing security features...")
        # Add test logic here
    elif args.quickstart:
        print_quickstart()
    else:
        print("""
        Soul Swarm Security Integration
        
        Usage:
          python integration_guide.py --setup      # Initial setup
          python integration_guide.py --quickstart # Show commands
          python integration_guide.py --test       # Test security
        
        Steps to secure your system:
        
        1. Run initial setup:
           python integration_guide.py --setup
        
        2. Start Admin API (separate terminal):
           python admin_api_secure.py
        
        3. Update your launch.py with security patches
        
        4. Configure firewall (see SECURITY.md)
        
        5. Test hot-reload functionality
        """)
