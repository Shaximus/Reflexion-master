#!/usr/bin/env python3
"""
Admin CLI for Soul Swarm (no curl needed)

Examples:
  python admin_cli.py health
  python admin_cli.py souls
  python admin_cli.py banned
  python admin_cli.py unban glyph
  python admin_cli.py tokens mirror NEW_TOKEN_VALUE
  python admin_cli.py ban void
  python admin_cli.py unban-all
"""

import os
import sys
import json
import argparse
from typing import Any, Dict, Optional

try:
    # Load .env so you don't have to paste keys
    from dotenv import load_dotenv
except ImportError:
    print(
        "python-dotenv not installed. Run:\n  "
        ".\\venv\\Scripts\\python.exe -m pip install python-dotenv requests"
    )
    sys.exit(1)

try:
    import requests
except ImportError:
    print(
        "requests not installed. Run:\n  "
        ".\\venv\\Scripts\\python.exe -m pip install requests python-dotenv"
    )
    sys.exit(1)

load_dotenv()

ADMIN_KEY = os.getenv("ADMIN_KEY", "")
BASE_URL = os.getenv(
    "ADMIN_BASE_URL", "http://127.0.0.1:8765"
)  # you can override in .env if needed

if not ADMIN_KEY:
    print("❌ ADMIN_KEY missing in .env. Add:\n\n  ADMIN_KEY=your_long_random_key\n")
    sys.exit(1)

HEADERS = {
    "X-Admin-Key": ADMIN_KEY,
    "Content-Type": "application/json",
}


def _url(path: str) -> str:
    return f"{BASE_URL.rstrip('/')}{path}"


def _req(
    method: str, path: str, json_body: Optional[Dict[str, Any]] = None
) -> requests.Response:
    try:
        return requests.request(
            method, _url(path), headers=HEADERS, json=json_body, timeout=10
        )
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
        sys.exit(1)


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
    # Pretty print in columns
    print("\nName            HasToken  Banned  Created")
    print("-" * 50)
    for s in souls:
        print(
            f"{s['name']:14} {str(s.get('has_token', False)):8} {str(s.get('banned', False)):6} {s.get('created','')}"
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
    # Fetch banned souls and unban them one-by-one
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


def main():
    p = argparse.ArgumentParser(description="Soul Swarm Admin CLI (no curl)")
    sub = p.add_subparsers(dest="cmd", required=True)

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
    sub.add_parser("unban-all", help="Unban all banned souls").set_defaults(
        func=do_unban_all
    )

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
