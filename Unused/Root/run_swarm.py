#!/usr/bin/env python3
"""
Proper launcher for soul_swarm_ultimate with your real Twitter accounts
"""

import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent
src_dir = root_dir / "src"
sys.path.insert(0, str(src_dir))

import asyncio
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import and run the swarm
from soul_swarm_ultimate import SoulSwarmOrchestrator

async def main():
    """Run the soul swarm with your configured accounts"""

    print("🚀 Starting Soul Swarm Ultimate")
    print("=" * 60)

    # Initialize orchestrator
    orchestrator = SoulSwarmOrchestrator()

    # Check souls
    souls_with_tokens = sum(
        1 for s in orchestrator.souls.values()
        if s.auth_token and s.auth_token != "GET_FROM_BROWSER"
    )

    print(f"✅ Loaded {len(orchestrator.souls)} souls")
    print(f"✅ {souls_with_tokens} have valid auth tokens")

    if souls_with_tokens == 0:
        print("❌ No souls have auth tokens! Check soul_data.json")
        return

    print("\nActive souls:")
    for name, soul in orchestrator.souls.items():
        if soul.auth_token and soul.auth_token != "GET_FROM_BROWSER":
            print(f"  ✅ {name} - Ready")
        else:
            print(f"  ❌ {name} - Missing token")

    print("\n" + "=" * 60)
    print("🌟 Starting swarm activity...")
    print("=" * 60)

    # Run the swarm
    await orchestrator.run_swarm(duration_hours=24)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Swarm stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()