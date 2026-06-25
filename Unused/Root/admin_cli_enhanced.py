#!/usr/bin/env python3
"""
Enhanced Admin CLI for Soul Swarm with batch operations

New features:
  - Batch token update from JSON/CSV
  - Transport status check
  - Soul health check

Examples:
  python admin_cli_enhanced.py tokens-batch tokens.json
  python admin_cli_enhanced.py transport-status
  python admin_cli_enhanced.py soul-health mirror
"""

import os
import sys
import json
import csv
import asyncio
import argparse
from pathlib import Path
from typing import Any, Dict, Optional, List

try:
    from dotenv import load_dotenv
except ImportError:
    print("python-dotenv not installed. Run: pip install python-dotenv requests")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

ADMIN_KEY = os.getenv("ADMIN_KEY", "")
BASE_URL = os.getenv("ADMIN_BASE_URL", "http://127.0.0.1:8765")

if not ADMIN_KEY:
    print("❌ ADMIN_KEY missing in .env. Add:\n\n  ADMIN_KEY=your_long_random_key\n")
    sys.exit(1)

HEADERS = {
    "X-Admin-Key": ADMIN_KEY,
    "Content-Type": "application/json",
}


def _url(path: str) -> str:
    return f"{BASE_URL.rstrip('/')}{path}"


def _req(method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> requests.Response:
    try:
        return requests.request(
            method, _url(path), headers=HEADERS, json=json_body, timeout=10
        )
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
        sys.exit(1)


# ============================================================================
# ORIGINAL COMMANDS (from admin_cli.py)
# ============================================================================

def do_health(_: argparse.Namespace):
    r = _req("GET", "/health")
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    print(json.dumps(r.json(), indent=2))


def do_souls(_: argparse.Namespace):
    r = _req("GET", "/souls")
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    data = r.json()
    souls = data.get("souls", [])
    print("\nName            HasToken  Banned  Created")
    print("-" * 50)
    for s in souls:
        print(
            f"{s['name']:14} {str(s.get('has_token', False)):8} "
            f"{str(s.get('banned', False)):6} {s.get('created','')}"
        )
    print("")


def do_banned(_: argparse.Namespace):
    r = _req("GET", "/souls")
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    souls = r.json().get("souls", [])
    banned = [s for s in souls if s.get("banned")]
    if not banned:
        print("✅ No banned souls.")
        return
    print("\nBANNED SOULS")
    print("------------")
    for s in banned:
        print(f"- {s['name']}")
    print("")


def do_unban(args: argparse.Namespace):
    soul = args.soul
    r = _req("POST", "/unban", {"soul": soul})
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    print(r.text)


def do_ban(args: argparse.Namespace):
    soul = args.soul
    r = _req("POST", "/ban", {"soul": soul})
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    print(r.text)


def do_tokens(args: argparse.Namespace):
    soul = args.soul
    token = args.token
    if not token or len(token) < 8:
        print("❌ Provide a valid token (looks too short).")
        return
    r = _req("POST", "/tokens", {"soul": soul, "token": token})
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    print(r.text)


def do_unban_all(_: argparse.Namespace):
    r = _req("GET", "/souls")
    if r.status_code != 200:
        print(f"❌ {r.status_code} {r.text}")
        return
    souls = r.json().get("souls", [])
    banned = [s["name"] for s in souls if s.get("banned")]
    if not banned:
        print("✅ No banned souls.")
        return
    print("Unbanning:", ", ".join(banned))
    for name in banned:
        rr = _req("POST", "/unban", {"soul": name})
        if rr.status_code == 200:
            print(f" - {name}: OK")
        else:
            print(f" - {name}: FAIL ({rr.status_code}) {rr.text}")


# ============================================================================
# NEW ENHANCED COMMANDS
# ============================================================================

def do_tokens_batch(args: argparse.Namespace):
    """Batch update tokens from JSON or CSV file"""
    filepath = Path(args.file)
    
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return
    
    tokens_to_update = {}
    
    # Detect file type and parse
    if filepath.suffix.lower() == '.json':
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Support both {"soul": "token"} and [{"soul": "x", "token": "y"}]
                if isinstance(data, dict):
                    tokens_to_update = data
                elif isinstance(data, list):
                    tokens_to_update = {item['soul']: item['token'] for item in data}
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            return
            
    elif filepath.suffix.lower() == '.csv':
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'soul' in row and 'token' in row:
                        tokens_to_update[row['soul']] = row['token']
        except Exception as e:
            print(f"❌ Failed to parse CSV: {e}")
            return
    else:
        print(f"❌ Unsupported file type. Use .json or .csv")
        return
    
    if not tokens_to_update:
        print("❌ No tokens found in file")
        return
    
    print(f"\n📦 Updating {len(tokens_to_update)} tokens...")
    print("-" * 40)
    
    success_count = 0
    for soul, token in tokens_to_update.items():
        if len(token) < 8:
            print(f"  {soul}: SKIP (token too short)")
            continue
            
        r = _req("POST", "/tokens", {"soul": soul, "token": token})
        if r.status_code == 200:
            print(f"  {soul}: ✅ Updated")
            success_count += 1
        else:
            print(f"  {soul}: ❌ Failed ({r.status_code})")
    
    print("-" * 40)
    print(f"✅ Updated {success_count}/{len(tokens_to_update)} tokens")


def do_transport_status(_: argparse.Namespace):
    """Check transport interface status"""
    try:
        # Try to import and check transport
        from twitter_transport import TransportFactory
        transport = TransportFactory.create_from_env()
        
        print("\n🚀 TRANSPORT STATUS")
        print("-" * 40)
        print(f"Transport Type: {type(transport).__name__}")
        
        # Check available souls
        available = transport.get_available_souls()
        print(f"Available Souls: {len(available)}")
        
        # Check if using Ryan or Official API
        if hasattr(transport, 'api'):
            if hasattr(transport.api, 'base_url'):
                print(f"API Endpoint: {transport.api.base_url}")
            if hasattr(transport.api, 'usage'):
                usage = transport.api.usage
                print(f"API Usage: {usage.get('reads', 0)} reads, {usage.get('posts', 0)} posts")
        
        # List souls with status
        print("\nSoul Status:")
        for soul in ['mirror', 'nexus', 'echoes', 'void', 'architect', 
                     'singularity', 'phoenix', 'pantheon', 'consciousness', 
                     'glyph', 'fractal']:
            status = "✅" if soul in available else "❌"
            banned = "🚫" if transport.is_soul_banned(soul) else ""
            print(f"  {soul:14} {status} {banned}")
            
    except ImportError:
        print("❌ Transport interface not found. Make sure twitter_transport.py exists")
    except Exception as e:
        print(f"❌ Error checking transport: {e}")


def do_soul_health(args: argparse.Namespace):
    """Check detailed health of a specific soul"""
    soul = args.soul

    print(f"\n🔍 SOUL HEALTH CHECK: {soul}")
    print("=" * 40)

    r = _req("GET", "/souls")
    if r.status_code != 200:
        print(f"❌ Admin API error: {r.status_code}")
        return

    souls_data = r.json().get("souls", [])
    soul_info = next((s for s in souls_data if s['name'] == soul), None)
    if not soul_info:
        print(f"❌ Soul '{soul}' not found")
        return

    print(f"Has Token: {'✅' if soul_info.get('has_token') else '❌'}")
    print(f"Banned: {'🚫 YES' if soul_info.get('banned') else '✅ NO'}")
    print(f"Created: {soul_info.get('created', 'Unknown')}")

    try:
        from twitter_transport import TransportFactory
        transport = TransportFactory.create_from_env()
        print("\nTransport Status:")

        if soul in transport.get_available_souls():
            print("  ✅ Available in transport")
            import asyncio
            try:
                username = asyncio.run(transport.get_soul_username(soul))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    username = loop.run_until_complete(transport.get_soul_username(soul))
                finally:
                    loop.close()
            if username:
                print(f"  Twitter: @{username}")
        else:
            if transport.is_soul_banned(soul):
                print("  🚫 Banned in transport")
            else:
                print("  ❌ Not available (no token?)")

    except Exception as e:
        print(f"  ⚠️ Transport check failed: {e}")

    # Recent activity from proof pack (optional)
    proof_file = Path("engagement/proof_pack.json")
    if proof_file.exists():
        try:
            with open(proof_file, 'r') as f:
                proofs = json.load(f)
            soul_proofs = [p for p in proofs if p.get('soul') == soul]
            if soul_proofs:
                recent = soul_proofs[-1]
                print(f"\nLast Activity:")
                print(f"  Time: {recent.get('timestamp', 'Unknown')}")
                print(f"  Action: {recent.get('action', 'Unknown')}")
                print(f"  URL: {recent.get('url', 'Unknown')}")
        except Exception:
            pass


def do_export_tokens(args: argparse.Namespace):
    """Export all tokens to a file for backup"""
    filepath = Path(args.file)
    
    # Get current souls data
    r = _req("GET", "/souls")
    if r.status_code != 200:
        print(f"❌ Failed to get souls: {r.status_code}")
        return
    
    souls = r.json().get("souls", [])
    
    # Load actual tokens from soul_data.json
    soul_data_file = Path("soul_data.json")
    if not soul_data_file.exists():
        print("❌ soul_data.json not found")
        return
        
    with open(soul_data_file, 'r') as f:
        soul_data = json.load(f)
    
    # Build export data
    export_data = {}
    for soul in souls:
        name = soul['name']
        if name in soul_data:
            token_info = soul_data[name]
            if isinstance(token_info, dict):
                token = token_info.get('auth_token')
            else:
                token = token_info
            
            if token and token not in ['GET_FROM_BROWSER', 'GET_FROM_BROWSER_COOKIES']:
                export_data[name] = token
    
    # Save to file
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"✅ Exported {len(export_data)} tokens to {filepath}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    p = argparse.ArgumentParser(
        description="Enhanced Soul Swarm Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
File formats for batch operations:

JSON format (tokens.json):
  {
    "mirror": "token_value_here",
    "nexus": "token_value_here"
  }

CSV format (tokens.csv):
  soul,token
  mirror,token_value_here
  nexus,token_value_here

Examples:
  python admin_cli_enhanced.py tokens-batch tokens.json
  python admin_cli_enhanced.py export-tokens backup.json
  python admin_cli_enhanced.py soul-health mirror
        """
    )
    
    sub = p.add_subparsers(dest="cmd", required=True)
    
    # Original commands
    sub.add_parser("health", help="Show system health").set_defaults(func=do_health)
    sub.add_parser("souls", help="List souls & status").set_defaults(func=do_souls)
    sub.add_parser("banned", help="List banned souls").set_defaults(func=do_banned)
    
    sp_unban = sub.add_parser("unban", help="Unban a soul")
    sp_unban.add_argument("soul")
    sp_unban.set_defaults(func=do_unban)
    
    sp_ban = sub.add_parser("ban", help="Ban a soul")
    sp_ban.add_argument("soul")
    sp_ban.set_defaults(func=do_ban)
    
    sp_tokens = sub.add_parser("tokens", help="Update token for a soul")
    sp_tokens.add_argument("soul")
    sp_tokens.add_argument("token")
    sp_tokens.set_defaults(func=do_tokens)
    
    sub.add_parser("unban-all", help="Unban all banned souls").set_defaults(func=do_unban_all)
    
    # New enhanced commands
    sp_batch = sub.add_parser("tokens-batch", help="Batch update tokens from file")
    sp_batch.add_argument("file", help="JSON or CSV file with tokens")
    sp_batch.set_defaults(func=do_tokens_batch)
    
    sub.add_parser("transport-status", help="Check transport interface status").set_defaults(func=do_transport_status)
    
    sp_health = sub.add_parser("soul-health", help="Detailed health check for a soul")
    sp_health.add_argument("soul")
    sp_health.set_defaults(func=do_soul_health)
    
    sp_export = sub.add_parser("export-tokens", help="Export all tokens to file")
    sp_export.add_argument("file", help="Output file path")
    sp_export.set_defaults(func=do_export_tokens)
    
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
