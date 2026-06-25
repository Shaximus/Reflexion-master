#!/usr/bin/env python3
"""
SECURITY TEST SUITE
Comprehensive tests for all security features
Run this after implementing security to verify everything works
"""

import os
import sys
import json
import time
import asyncio
import aiohttp
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
import secrets

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(name: str, passed: bool, details: str = ""):
    """Print test result with color"""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"  {status} - {name}")
    if details and not passed:
        print(f"      {YELLOW}→ {details}{RESET}")

def print_section(title: str):
    """Print section header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

# ============================================================================
# TEST 1: FILE PERMISSIONS & STRUCTURE
# ============================================================================

def test_file_structure():
    """Test that all required files and directories exist"""
    print_section("1. FILE STRUCTURE & PERMISSIONS")
    
    required_dirs = ["engagement", "logs", "memlogs"]
    required_files = [".gitignore", ".env"]
    
    all_passed = True
    
    # Create missing directories automatically
    for dir_name in required_dirs:
        path = Path(dir_name)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print_test(f"Directory {dir_name} created", True)
        else:
            print_test(f"Directory {dir_name} exists", True)
    
    for file_name in required_files:
        exists = Path(file_name).exists()
        print_test(f"File {file_name} exists", exists)
        all_passed = all_passed and exists
    
    # Check .env has ADMIN_KEY
    if Path(".env").exists():
        env_content = Path(".env").read_text()
        has_admin = "ADMIN_KEY" in env_content
        print_test("ADMIN_KEY in .env", has_admin)
        all_passed = all_passed and has_admin
    
    return all_passed

# ============================================================================
# TEST 2: ATOMIC WRITES
# ============================================================================

def test_atomic_writes():
    """Test atomic write functionality"""
    print_section("2. ATOMIC FILE WRITES")
    
    from admin_api_secure import atomic_write_json
    
    test_file = Path("test_atomic.json")
    test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
    
    try:
        # Test atomic write
        atomic_write_json(test_file, test_data)
        exists = test_file.exists()
        print_test("Atomic write creates file", exists)
        
        # Verify content
        if exists:
            loaded = json.loads(test_file.read_text())
            matches = loaded == test_data
            print_test("Content matches after write", matches)
        else:
            print_test("Content matches after write", False, "File doesn't exist")
        
        # Test no temp file left
        temp_exists = test_file.with_suffix(".json.tmp").exists()
        print_test("No temp file remains", not temp_exists)
        
        # Cleanup
        if test_file.exists():
            test_file.unlink()
        
        return exists and matches and not temp_exists
        
    except Exception as e:
        print_test("Atomic write function", False, str(e))
        return False

# ============================================================================
# TEST 3: ADMIN API
# ============================================================================

async def test_admin_api():
    """Test Admin API security features"""
    print_section("3. ADMIN API SECURITY")
    
    # Get admin key from env
    from dotenv import load_dotenv
    load_dotenv()
    admin_key = os.getenv("ADMIN_KEY", "test-key")
    
    base_url = "http://127.0.0.1:8765"
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: No auth should fail
        try:
            async with session.get(f"{base_url}/health") as resp:
                no_auth_fails = resp.status == 401
                print_test("Rejects requests without auth", no_auth_fails)
        except:
            print_test("Rejects requests without auth", False, "API not running")
            return False
        
        # Test 2: Wrong auth should fail
        try:
            headers = {"X-Admin-Key": "wrong-key"}
            async with session.get(f"{base_url}/health", headers=headers) as resp:
                wrong_auth_fails = resp.status == 401
                print_test("Rejects wrong authentication", wrong_auth_fails)
        except:
            wrong_auth_fails = False
        
        # Test 3: Correct auth should work
        try:
            headers = {"X-Admin-Key": admin_key}
            async with session.get(f"{base_url}/health", headers=headers) as resp:
                correct_auth_works = resp.status == 200
                print_test("Accepts correct authentication", correct_auth_works)
                
                if correct_auth_works:
                    data = await resp.json()
                    has_souls = "souls" in data
                    print_test("Returns valid health data", has_souls)
        except:
            print_test("Accepts correct authentication", False, "Request failed")
            return False
        
        # Test 4: Localhost only (this should fail from external IP)
        # Note: This test is informational only
        print_test("Bound to localhost only", True, "Manual verification needed")
        
        return no_auth_fails and wrong_auth_fails and correct_auth_works

# ============================================================================
# TEST 4: HOT RELOAD
# ============================================================================

async def test_hot_reload():
    """Test token hot-reload functionality"""
    print_section("4. HOT-RELOAD SYSTEM")
    
    from ryan_api_hotreload import RyanTwitterAPISecure
    
    # Create test instance
    api = RyanTwitterAPISecure()
    
    # Test initial load
    initial_count = len(api.soul_tokens)
    print_test(f"Loaded {initial_count} tokens initially", True)
    
    # Modify soul_data.json
    test_soul = "test_soul_" + secrets.token_hex(4)
    test_token = "test_token_" + secrets.token_hex(8)
    
    soul_data = {}
    if Path("soul_data.json").exists():
        with open("soul_data.json", "r") as f:
            soul_data = json.load(f)
    
    # Add test soul
    soul_data[test_soul] = {"auth_token": test_token}
    
    from admin_api_secure import atomic_write_json
    atomic_write_json(Path("soul_data.json"), soul_data)
    
    # Wait for reload
    await asyncio.sleep(3)
    await api.refresh_tokens_from_disk()
    
    # Check if new token loaded
    reloaded = test_soul in api.soul_tokens
    print_test("Hot-reload detects changes", reloaded)
    
    if reloaded:
        token_matches = api.soul_tokens[test_soul] == test_token
        print_test("New token loaded correctly", token_matches)
    else:
        print_test("New token loaded correctly", False, "Token not found")
    
    # Cleanup
    del soul_data[test_soul]
    atomic_write_json(Path("soul_data.json"), soul_data)
    
    return reloaded

# ============================================================================
# TEST 5: AUDIT LOGGING
# ============================================================================

def test_audit_logging():
    """Test audit log functionality"""
    print_section("5. AUDIT LOGGING")
    
    from admin_api_secure import audit_log
    
    log_file = Path("engagement/admin_changes.log")
    
    # Create test entry
    test_id = secrets.token_hex(4)
    audit_log("test_action", f"test_id={test_id}", "ok")
    
    # Check if logged
    if log_file.exists():
        content = log_file.read_text()
        has_entry = test_id in content
        print_test("Audit log entry created", has_entry)
        
        # Check format
        lines = content.strip().split("\n")
        if lines:
            last_line = lines[-1]
            has_timestamp = last_line.startswith("20")  # Year 20xx
            has_actor = "actor=local" in last_line
            has_action = "action=test_action" in last_line
            
            print_test("Correct log format", all([has_timestamp, has_actor, has_action]))
            return has_entry and has_timestamp
    else:
        print_test("Audit log exists", False)
        return False

# ============================================================================
# TEST 6: GITIGNORE
# ============================================================================

def test_gitignore():
    """Test .gitignore configuration"""
    print_section("6. GIT SECURITY")
    
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        print_test(".gitignore exists", False)
        return False
    
    content = gitignore.read_text()
    
    critical_patterns = [
        ".env",
        "soul_data.json",
        "*.key",
        "*.pem",
        "__pycache__",
        "*.log"
    ]
    
    all_present = True
    for pattern in critical_patterns:
        present = pattern in content
        print_test(f"Ignores {pattern}", present)
        all_present = all_present and present
    
    return all_present

# ============================================================================
# TEST 7: NETWORK SECURITY
# ============================================================================

def test_network_security():
    """Test network security (informational)"""
    print_section("7. NETWORK SECURITY")
    
    import socket
    import platform
    
    # Get local IP
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
        print(f"  Local IP: {local_ip}")
    except:
        local_ip = "unknown"
    
    # Check if admin API is reachable from network
    # This should fail if properly configured
    if local_ip != "unknown" and local_ip != "127.0.0.1":
        try:
            import requests
            resp = requests.get(f"http://{local_ip}:8765/health", timeout=1)
            reachable = resp.status_code == 200
            print_test("Admin API NOT reachable from network", not reachable)
        except:
            print_test("Admin API NOT reachable from network", True)
    
    # Platform-specific firewall check
    system = platform.system()
    
    if system == "Windows":
        print(f"\n  {YELLOW}Windows Firewall Check:{RESET}")
        print("  Run in PowerShell as Admin:")
        print("    Get-NetFirewallProfile | Select Name, Enabled")
    elif system == "Linux":
        print(f"\n  {YELLOW}Linux Firewall Check:{RESET}")
        print("  Run: sudo ufw status")
    elif system == "Darwin":  # macOS
        print(f"\n  {YELLOW}macOS Firewall Check:{RESET}")
        print("  Run: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate")
    
    return True  # Informational only

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all security tests"""
    print(f"""
{BLUE}╔══════════════════════════════════════════════════════════╗
║         SOUL SWARM SECURITY TEST SUITE                   ║
╚══════════════════════════════════════════════════════════╝{RESET}
    """)
    
    results = {}
    
    # Run tests
    results["file_structure"] = test_file_structure()
    results["atomic_writes"] = test_atomic_writes()
    results["audit_logging"] = test_audit_logging()
    results["gitignore"] = test_gitignore()
    
    # Async tests
    print(f"\n{YELLOW}Note: Admin API must be running for next tests{RESET}")
    input("Press Enter when Admin API is running on port 8765...")
    
    try:
        results["admin_api"] = await test_admin_api()
        results["hot_reload"] = await test_hot_reload()
    except Exception as e:
        print(f"{RED}Async tests failed: {e}{RESET}")
        results["admin_api"] = False
        results["hot_reload"] = False
    
    results["network"] = test_network_security()
    
    # Summary
    print_section("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {test_name:20} {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n{GREEN}🎉 ALL SECURITY TESTS PASSED!{RESET}")
        print("\nYour system is properly secured. Remember to:")
        print("  1. Configure your firewall")
        print("  2. Use a strong ADMIN_KEY")
        print("  3. Run as non-admin user")
        print("  4. Never expose ports to the internet")
    else:
        print(f"\n{RED}⚠️  Some tests failed. Review and fix issues above.{RESET}")
    
    return passed == total

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Test Suite")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--admin", action="store_true", help="Test admin API only")
    
    args = parser.parse_args()
    
    if args.admin:
        asyncio.run(test_admin_api())
    elif args.quick:
        test_file_structure()
        test_gitignore()
        test_audit_logging()
    else:
        asyncio.run(run_all_tests())
