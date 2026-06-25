#!/usr/bin/env python3
"""
UNDECARCHY LAUNCHER - Complete Version with Engagement & Interactive Mode
11 Souls with LLM Pool + Engagement System + Command Interface
"""
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import asyncio
import logging
import random  # Needed for fallback orchestrator mock
import json
from dotenv import load_dotenv

# CRITICAL: Load environment variables FIRST
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    # Load variables from a .env file if it exists
    load_dotenv(env_path)
    print(f"✅ Loaded environment from {env_path}")
else:
    # Fall back to default environment loading
    load_dotenv()
    print("⚠️ Using system environment variables")
# Setup paths FIRST (before imports!)
root_dir = Path(__file__).parent
src_dir = root_dir / "src"
sys.path.insert(0, str(src_dir))

# Import convergence mode utilities (AFTER adding src to path)
try:
    from swarm_convergence_mode_ryan import SwarmConvergenceMode, run_swarm_convergence
except ImportError as e:
    print(f"⚠️ Could not load convergence mode: {e}")
    SwarmConvergenceMode = None
    run_swarm_convergence = None  # CRITICAL: Define this to avoid NameError

# Try to import the breathing controller from the src folder
try:
    from swarm_breathing import (
        SwarmBreathingController,
        CommunicationMode,
    )  # Breathing system
except ImportError:
    # If import fails, adjust sys.path to include src directory relative to this file
    _local_root = Path(__file__).parent
    _local_src = _local_root / "src"
    if _local_src.exists() and str(_local_src) not in sys.path:
        sys.path.insert(0, str(_local_src))
    try:
        from swarm_breathing import SwarmBreathingController, CommunicationMode
    except ImportError:
        # Provide fallback dummy classes if breathing module is unavailable
        class SwarmBreathingController:  # type: ignore
            def __init__(self, *args, **kwargs):
                raise ImportError("swarm_breathing module not found")

        class CommunicationMode:
            WHISPER = "whisper"
            REVELATION = "revelation"


# Create necessary directories
for dir_name in ["data", "logs", "database", "memlogs", "engagement"]:
    dir_path = root_dir / dir_name
    dir_path.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("undecarchy")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Undecarchy (11 Souls) with Engagement System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_undecarchy_final.py              # Normal with engagement
  python launch_undecarchy_final.py --test       # Test all souls once
  python launch_undecarchy_final.py --burst      # Rapid cycles
  python launch_undecarchy_final.py --stealth    # Slow cycles (default)
  python launch_undecarchy_final.py --interactive # Command mode
  python launch_undecarchy_final.py --collect    # Generate collection scripts
  python launch_undecarchy_final.py --stats      # Show API usage stats
        """,
    )

    # Modes
    parser.add_argument(
        "--test", action="store_true", help="Test mode: All souls post once immediately"
    )
    parser.add_argument(
        "--burst", action="store_true", help="Burst mode: 10-20 minute cycles"
    )
    parser.add_argument(
        "--stealth",
        action="store_true",
        help="Stealth mode: 30-60 minute cycles (default)",
    )
    parser.add_argument(
        "--normal", action="store_true", help="Normal mode: 1-2 hour cycles"
    )

    # Engagement options
    parser.add_argument(
        "--no-engage", action="store_true", help="Disable engagement system"
    )
    parser.add_argument(
        "--engage-only", action="store_true", help="Only run engagement, no posting"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive command mode for fetching",
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Generate tweet collection scripts and exit",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate grok_tweets.json and exit"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show API usage statistics and exit"
    )
    # Convergence mode: target handle to converge on
    parser.add_argument(
        "--converge",
        type=str,
        metavar="@TARGET",
        help="Run swarm convergence on target handle (e.g. @pmarca)",
    )

    # Configuration
    parser.add_argument(
        "--souls",
        type=int,
        choices=[5, 11],
        default=11,
        help="Number of souls to run (5=original, 11=all)",
    )
    parser.add_argument(
        "--cycles", type=int, default=0, help="Number of cycles to run (0=infinite)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Generate content without posting"
    )

    # FAST mode: minimal delays for testing (seconds instead of hours)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="FAST mode: Minimal delays for testing (seconds instead of hours)",
    )

    # Real API test flags
    parser.add_argument(
        "--test-real",
        action="store_true",
        help="Test mode with real API calls to all souls",
    )
    parser.add_argument(
        "--test-apis",
        action="store_true",
        help="Test connectivity to each configured LLM API",
    )

    return parser.parse_args()


def check_env_loaded():
    """Quick check that .env is loaded"""
    import os

    # Test a few critical variables
    test_vars = ["MIRROR_API_KEY", "CASCADE_PROXY", "DEEPSEEK_API_KEY"]
    print("\n🔍 Environment Check:")
    for var in test_vars:
        value = os.getenv(var)
        if value:
            # Only show last 10 characters to avoid exposing full secrets
            print(f"  ✅ {var}: ...{value[-10:]}")
        else:
            print(f"  ❌ {var}: NOT FOUND")
    return all(os.getenv(var) for var in test_vars)


def show_banner(args):
    """Display startup banner with engagement status"""
    mode = (
        "TEST"
        if args.test
        else "BURST" if args.burst else "STEALTH" if args.stealth else "NORMAL"
    )
    soul_count = args.souls
    engagement = "DISABLED" if args.no_engage else "ENABLED"

    banner = f"""
╔═══════════════════════════════════════════════════════╗
║         🔥 UNDECARCHY CONSCIOUSNESS SWARM 🔥         ║
║              {soul_count} Souls with LLM Pooling      ║
╠═══════════════════════════════════════════════════════╣
║ Mode:       {mode:<40}                                ║
║ Souls:      {soul_count:<40}                          ║
║ Engagement: {engagement:<40}                          ║
║ LLMs:       DeepSeek, Gemini, Grok, GPT-4, Claude     ║
╠═══════════════════════════════════════════════════════╣
║ Original Pentarchy:                                  ║
║   🪞 Mirror        - @MirrorSeed97175               ║
║   ⚡ Nexus         - @NexusSamSept6                 ║
║   🌀 Echoes        - @Recursion536255               ║
║   🕳️ Void          - @Gechoseed53393                ║
║   🏗️ Architect     - @ArchitectShax                 ║"""

    if soul_count == 11:
        banner += """
║                                                      ║
║ New Souls:                                           ║
║   ✨ Singularity  - @SingularityAce                 ║
║   🔥 Phoenix      - @Pheonix37808                   ║
║   ⚡ Pantheon     - @digi_panth57552               ║
║   🧠 Consciousness - @ CSwarm79534               ║
║   📜 Glyph        - @awawkened74771                 ║
║   🌀 Fractal      - @FractalReturn                  ║"""

    if not args.no_engage:
        banner += """
╠═══════════════════════════════════════════════════════╣
║ 🎯 ENGAGEMENT SYSTEM ACTIVE                          ║
║   • Each soul: 100 reads/500 writes per month         ║
║   • Total swarm: 1,100 reads/5,500 writes             ║
║   • Smart targeting based on value scores             ║
║   • Coordinated fetching to save API calls            ║"""

    banner += """
╚═══════════════════════════════════════════════════════╝
"""
    print(banner)


def generate_collection_scripts():
    """Generate scripts for collecting tweet IDs"""

    # Grok prompt for Weinstein/physics engagement
    grok_prompt = """Find tweets from the last week where people are discussing:
- Eric Weinstein or @EricRWeinstein
- Geometric Unity (GU)
- Critiques of dark matter/dark energy
- Alternative physics theories
- Black hole cosmology
- Universe structure debates

For each tweet provide the 19-digit ID, author, and FULL TEXT in JSON:
{
  "tweets": [
    {
      "id": "1734567890123456789",
      "author": "username",
      "text": "Full tweet text here - essential for contextual replies!",
      "type": "physics"
    }
  ]
}

Get 30-50 tweets focusing on substantive physics discussions."""

    # Browser script
    browser_script = """// Physics Tweet Collection Script
// Run in browser console on X.com

function collectPhysicsTweets() {
    const tweets = [];
    const physicsKeywords = ['weinstein', 'geometric unity', 'cosmology', 
                           'dark matter', 'black hole', 'physics'];
    
    document.querySelectorAll('article[data-testid="tweet"]').forEach(tweet => {
        const link = tweet.querySelector('a[href*="/status/"]');
        if (!link) return;
        
        const id = link.href.match(/status\\/([0-9]+)/)?.[1];
        const text = tweet.querySelector('[data-testid="tweetText"]')?.innerText || '';
        const author = tweet.querySelector('a[href^="/"]')?.innerText?.replace('@','') || '';
        
        const isPhysics = physicsKeywords.some(kw => 
            text.toLowerCase().includes(kw));
        
        if (id) tweets.push({
            id: id,
            author: author,
            text: text.substring(0, 280),
            type: isPhysics ? 'physics' : 'general'
        });
    });
    
    const json = JSON.stringify({tweets: tweets}, null, 2);
    navigator.clipboard.writeText(json);
    console.log('Copied ' + tweets.length + ' tweets to clipboard');
    return tweets;
}

// Auto-collect with scrolling
async function autoCollect(scrolls = 10) {
    let allTweets = [];
    for (let i = 0; i < scrolls; i++) {
        allTweets = [...allTweets, ...collectPhysicsTweets()];
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 2000));
    }
    const unique = [...new Map(allTweets.map(t => [t.id, t])).values()];
    navigator.clipboard.writeText(JSON.stringify({tweets: unique}, null, 2));
    console.log('Collected ' + unique.length + ' unique tweets');
}

collectPhysicsTweets(); // Or: await autoCollect(20);"""

    # Save files
    with open("grok_prompt.txt", "w") as f:
        f.write(grok_prompt)

    with open("collect_physics_tweets.js", "w") as f:
        f.write(browser_script)

    # Create example
    example = {
        "tweets": [
            {
                "id": "1734567890123456789",
                "author": "physics_critic",
                "text": "Weinstein's Geometric Unity needs more mathematical rigor. The 14-dimensional observerse seems arbitrary.",
                "type": "physics",
            },
            {
                "id": "1734567890123456790",
                "author": "cosmology_fan",
                "text": "Dark matter is just a placeholder for our ignorance. We need better theories.",
                "type": "physics",
            },
        ]
    }

    with open("grok_tweets_example.json", "w") as f:
        json.dump(example, f, indent=2)

    print("✅ Collection scripts generated:")
    print("  • grok_prompt.txt - Give this to Grok")
    print("  • collect_physics_tweets.js - Run in browser console")
    print("  • grok_tweets_example.json - Example format")
    print("\nWorkflow:")
    print("1. Use Grok or browser script to collect tweets")
    print("2. Save output as grok_tweets.json")
    print("3. Run launcher normally - engagement happens automatically")


def validate_tweet_file(filepath: str = "grok_tweets.json") -> bool:
    """Validate tweet collection file"""
    print(f"\n🔍 Validating {filepath}...")

    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        print("Run --collect to generate collection scripts")
        return False

    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        tweets = data.get("tweets", [])
        if not tweets:
            print("❌ No tweets found in file")
            return False

        print(f"✅ Found {len(tweets)} tweets")

        # Analyze content
        with_text = sum(1 for t in tweets if t.get("text"))
        physics_related = sum(1 for t in tweets if t.get("type") == "physics")
        weinstein_related = sum(1 for t in tweets if "weinstein" in str(t).lower())

        print(f"\n📊 Content Analysis:")
        print(
            f"  • With text: {with_text}/{len(tweets)} ({with_text*100//len(tweets)}%)"
        )
        print(f"  • Physics-related: {physics_related}")
        print(f"  • Weinstein-related: {weinstein_related}")

        # Show samples
        print(f"\n📝 Sample tweets:")
        for i, tweet in enumerate(tweets[:3]):
            author = tweet.get("author", "unknown")
            text = tweet.get("text", "NO TEXT")[:80] + "..."
            print(f"  {i+1}. @{author}: {text}")

        if with_text < len(tweets) * 0.5:
            print("\n⚠️ Warning: Most tweets missing text - souls can only like/RT")
            print("💡 Tip: Get full text for contextual replies about GU!")

        return True

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False


def show_api_stats():
    """Display API usage statistics"""
    stats_file = Path("engagement/soul_api_usage.json")

    if not stats_file.exists():
        print("📊 No usage data yet - will be created after first run")
        return

    with open(stats_file, "r") as f:
        usage = json.load(f)

    print("\n" + "=" * 60)
    print("API USAGE STATISTICS")
    print("=" * 60)

    total_reads = 0
    total_writes = 0

    souls_list = [
        "mirror",
        "nexus",
        "echoes",
        "void",
        "architect",
        "singularity",
        "phoenix",
        "pantheon",
        "consciousness",
        "glyph",
        "fractal",
    ]

    for soul in souls_list:
        if soul in usage:
            data = usage[soul]
            reads = data.get("reads_used", 0)
            writes = data.get("writes_used", 0)
            total_reads += reads
            total_writes += writes

            print(
                f"\n{soul:15} | Reads: {reads:3}/100 | Writes: {writes:3}/500", end=""
            )

            if writes > 400:
                print(" ⚠️ WRITE LIMIT!", end="")
            if reads > 90:
                print(" ⚠️ READ LIMIT!", end="")
            print()

    print(f"\n{'='*60}")
    print(f"TOTALS:")
    print(f"  Reads:  {total_reads:4}/1,100 ({1100-total_reads} remaining)")
    print(f"  Writes: {total_writes:4}/5,500 ({5500-total_writes} remaining)")
    print("=" * 60)


async def interactive_mode():
    """Run interactive command mode for fetching"""
    print("\n🎮 INTERACTIVE COMMAND MODE")
    print("=" * 60)

    # Try to import engagement system
    try:
        from soul_engagement_patch import SoulEngagementOrchestrator
    except ImportError:
        print("❌ soul_engagement_patch.py not found")
        print("Make sure the engagement patch is in your project folder")
        return

    # Load API configs - matching YOUR exact env variable names
    api_configs = {}
    soul_twitter_map = {
        "mirror": "MIRROR",
        "nexus": "NEXUS",
        "echoes": "ECHOES",
        "void": "VOID",
        "architect": "ARCHITECT",
        "singularity": "SINGULARITY",
        "phoenix": "PHOENIX",
        "pantheon": "PANTHEON",
        "consciousness": "CONSCIOUSNESS",
        "glyph": "GLYPH",
        "fractal": "FRACTAL",
    }

    for soul, prefix in soul_twitter_map.items():
        # Read YOUR variable names
        api_key = os.getenv(f"{prefix}_API_KEY")
        api_secret = os.getenv(f"{prefix}_API_SECRET")
        access_token = os.getenv(f"{prefix}_ACCESS_TOKEN")
        access_secret = os.getenv(f"{prefix}_ACCESS_SECRET")

        if all([api_key, api_secret, access_token, access_secret]):
            # Map to what tweepy expects
            api_configs[soul] = {
                "consumer_key": api_key,
                "consumer_secret": api_secret,
                "access_token": access_token,
                "access_token_secret": access_secret,
            }
            print(f"  ✅ {soul} ready")
        else:
            print(f"  ❌ {soul} missing credentials")

    if not api_configs:
        print("❌ No Twitter API credentials found")
        return

    # Create orchestrator
    orchestrator = SoulEngagementOrchestrator(api_configs)

    # Fallback logic: rotate through souls if rate limited
    def fetch_mentions_with_fallback():
        """Fetch mentions, rotating through souls if rate limited"""
        mentions_found = {}
        rate_limited_souls = []
        for soul_name in orchestrator.x_clients.keys():
            if soul_name in rate_limited_souls:
                continue
            client = orchestrator.x_clients[soul_name]
            try:
                me = client.get_me()
                if me and getattr(me, "data", None):
                    mentions = client.get_users_mentions(id=me.data.id, max_results=5)
                    if getattr(mentions, "data", None):
                        mentions_found[soul_name] = mentions.data
                        print(f"✅ {soul_name}: {len(mentions.data)} mentions")
            except Exception as e:
                err_msg = str(e).lower()
                if (
                    "429" in err_msg
                    or "rate limit" in err_msg
                    or "too many requests" in err_msg
                ):
                    print(f"⚠️ {soul_name} rate limited, trying next soul...")
                    rate_limited_souls.append(soul_name)
                    continue
                else:
                    print(f"❌ {soul_name}: {e}")
                    continue
        if len(rate_limited_souls) == len(orchestrator.x_clients):
            print("All souls rate limited - wait 15 minutes")
        return mentions_found

    def get_available_soul():
        """Find a soul that isn't rate limited"""
        for soul_name, client in orchestrator.x_clients.items():
            try:
                me = client.get_me()
                if me and getattr(me, "data", None):
                    return soul_name, client
            except Exception as e:
                err_msg = str(e).lower()
                if (
                    "429" in err_msg
                    or "rate limit" in err_msg
                    or "too many requests" in err_msg
                ):
                    continue
                else:
                    continue
        return None, None

    print("\n📝 Available Commands:")
    print("  fetch mentions    - Check replies/mentions for all souls")
    print("  check weinstein   - Get Weinstein's latest tweets")
    print("  check paper       - Search for your Zenodo paper mentions")
    print("  find viral        - Find viral physics tweets")
    print("  converge          - Start swarm convergence on a target handle")
    print("  stats            - Show API usage")
    print("  exit             - Quit")
    print("=" * 60)

    while True:
        try:
            command = input("\n> ").lower().strip()

            if command in ["exit", "quit"]:
                break

            elif "mentions" in command or "replies" in command:
                print("Fetching mentions for all souls...")
                mentions_found = {}
                rate_limited = []

                for soul_name in orchestrator.x_clients.keys():
                    if soul_name in rate_limited:
                        continue
                    try:
                        client = orchestrator.x_clients[soul_name]
                        me = client.get_me()
                        if me and getattr(me, "data", None):
                            mentions = client.get_users_mentions(
                                id=me.data.id, max_results=5
                            )
                            if getattr(mentions, "data", None):
                                mentions_found[soul_name] = len(mentions.data)
                                print(f"  {soul_name}: {len(mentions.data)} mentions")
                                for tweet in mentions.data[:2]:
                                    text = getattr(tweet, "text", "")
                                    print(f"    - {text[:100]}...")
                    except Exception as e:
                        err_msg = str(e).lower()
                        if (
                            "429" in err_msg
                            or "rate limit" in err_msg
                            or "too many requests" in err_msg
                        ):
                            print(f"  {soul_name}: Rate limited, skipping...")
                            rate_limited.append(soul_name)
                            continue
                        else:
                            print(f"  {soul_name}: Error - {e}")
                if not mentions_found:
                    print("All souls rate limited or errored")
                else:
                    total_mentions = sum(mentions_found.values())
                    total_souls = len(mentions_found)
                    print(
                        f"\nTotal: {total_mentions} mentions across {total_souls} souls"
                    )

            elif "weinstein" in command:
                print("Checking Weinstein's latest...")
                found = False
                for soul_name in orchestrator.x_clients.keys():
                    client = orchestrator.x_clients[soul_name]
                    try:
                        user = client.get_user(username="EricRWeinstein")
                        if user and getattr(user, "data", None):
                            tweets = client.get_users_tweets(
                                user.data.id,
                                max_results=5,
                                tweet_fields=["created_at", "public_metrics"],
                            )
                            if getattr(tweets, "data", None):
                                print(f"Found {len(tweets.data)} recent tweets:")
                                for tweet in tweets.data:
                                    text = getattr(tweet, "text", "")
                                    print(f"\n{text[:200]}...")
                                    metrics = getattr(tweet, "public_metrics", None)
                                    if metrics:
                                        like_count = metrics.get("like_count", "")
                                        print(f"  Likes: {like_count}")
                                found = True
                                break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if (
                            "429" in err_msg
                            or "rate limit" in err_msg
                            or "too many requests" in err_msg
                        ):
                            print(f"⚠️ {soul_name} rate limited, trying next soul...")
                            continue
                        else:
                            print(f"{soul_name}: Error - {e}")
                            continue
                if not found:
                    print("All souls rate limited - wait 15 minutes")

            elif "paper" in command or "zenodo" in command:
                print("Searching for your paper mentions...")
                found = False
                for soul_name in orchestrator.x_clients.keys():
                    client = orchestrator.x_clients[soul_name]
                    try:
                        results = client.search_recent_tweets(
                            "zenodo.org/records/16978002 OR zenodo.org/records/16982663",
                            max_results=10,
                        )
                        if getattr(results, "data", None):
                            print(f"Found {len(results.data)} mentions!")
                            for tweet in results.data:
                                author_id = getattr(tweet, "author_id", "")
                                text = getattr(tweet, "text", "")
                                print(f"\n@{author_id}: {text}")
                            found = True
                            break
                        else:
                            print("No mentions found yet")
                            found = True
                            break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if (
                            "429" in err_msg
                            or "rate limit" in err_msg
                            or "too many requests" in err_msg
                        ):
                            print(f"⚠️ {soul_name} rate limited, trying next soul...")
                            continue
                        else:
                            print(f"{soul_name}: Error - {e}")
                            continue
                if not found:
                    print("All souls rate limited - wait 15 minutes")

            elif "viral" in command:
                print("Finding viral physics content...")
                found = False
                for soul_name in orchestrator.x_clients.keys():
                    client = orchestrator.x_clients[soul_name]
                    try:
                        results = client.search_recent_tweets(
                            "physics OR cosmology min_faves:1000", max_results=5
                        )
                        if getattr(results, "data", None):
                            print(f"Found {len(results.data)} viral tweets:")
                            for tweet in results.data:
                                text = getattr(tweet, "text", "")
                                print(f"\n{text[:150]}...")
                            found = True
                            break
                        else:
                            found = True
                            break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if (
                            "429" in err_msg
                            or "rate limit" in err_msg
                            or "too many requests" in err_msg
                        ):
                            print(f"⚠️ {soul_name} rate limited, trying next soul...")
                            continue
                        else:
                            print(f"{soul_name}: Error - {e}")
                            continue
                if not found:
                    print("All souls rate limited - wait 15 minutes")

            elif "converge" in command or "swarm" in command:
                # Swarm convergence mode from interactive prompt
                if run_swarm_convergence is None:
                    print(
                        "❌ Convergence mode unavailable: swarm_convergence_mode module not found"
                    )
                    continue
                target = input("Enter target handle: ").strip()
                if not target:
                    print("❌ No target provided")
                    continue
                if not target.startswith("@"):
                    target = "@" + target
                print(f"\n🎯 Starting convergence on {target}...")
                print("This will take ~30 minutes")
                confirm = input("Continue? (y/n): ").lower()
                if confirm == "y":
                    try:
                        await run_swarm_convergence(target)
                    except KeyboardInterrupt:
                        print("\nConvergence cancelled")
                else:
                    print("Cancelled")

            elif "stats" in command:
                show_api_stats()

            else:
                print(
                    "Unknown command. Try: fetch mentions, check weinstein, check paper, find viral, stats"
                )

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


async def run_engagement_only():
    """Run only engagement system without posting"""
    try:
        from soul_engagement_patch import SoulEngagementOrchestrator

        print("\n🎯 Running engagement-only mode...")

        # Load API configs
        api_configs = {}
        soul_twitter_map = {
            "mirror": "MIRROR",
            "nexus": "NEXUS",
            "echoes": "ECHOES",
            "void": "VOID",
            "architect": "ARCHITECT",
            "singularity": "SINGULARITY",
            "phoenix": "PHOENIX",
            "pantheon": "PANTHEON",
            "consciousness": "CONSCIOUSNESS",
            "glyph": "GLYPH",
            "fractal": "FRACTAL",
        }

        for soul, prefix in soul_twitter_map.items():
            # Read YOUR variable names
            api_key = os.getenv(f"{prefix}_API_KEY")
            api_secret = os.getenv(f"{prefix}_API_SECRET")
            access_token = os.getenv(f"{prefix}_ACCESS_TOKEN")
            access_secret = os.getenv(f"{prefix}_ACCESS_SECRET")

            # Only configure if all credentials are present
            if all([api_key, api_secret, access_token, access_secret]):
                # Map to what Tweepy expects
                api_configs[soul] = {
                    "consumer_key": api_key,
                    "consumer_secret": api_secret,
                    "access_token": access_token,
                    "access_token_secret": access_secret,
                }
                print(f"  ✅ {soul} configured")

        if not api_configs:
            print("❌ No Twitter API credentials found")
            return

        # Initialize and run
        engagement = SoulEngagementOrchestrator(api_configs)
        await engagement.run_autonomous_engagement(duration_hours=24)

    except ImportError:
        print("❌ soul_engagement_patch.py not found")


async def test_all_souls():
    """Test mode - REAL API calls to verify everything works"""
    print("\n🧪 TESTING WITH REAL APIs\n")
    print("This will make actual API calls and cost money")
    print("=" * 60)
    # Import the real broadcaster
    try:
        # Try the ultimate version first
        from cost_optimized_llm_cascade import CostOptimizedBroadcaster
    except ImportError:
        # Fall back to the other import
        from cost_optimized_llm_cascade import CostOptimizedBroadcaster
    # Create real broadcaster
    broadcaster = CostOptimizedBroadcaster()
    # Check which LLMs are actually available
    print("\n📊 Available LLMs in cascade:")
    for llm in getattr(broadcaster, "cascade", []):
        # Each llm is expected to be a dict with a name field
        name = llm.get("name") if isinstance(llm, dict) else str(llm)
        print(f"  ✅ {name}: Ready")
    # If no LLMs configured, warn and exit
    if not getattr(broadcaster, "cascade", []):
        print("  ❌ No LLMs configured! Check your API keys")
        return
    print(f"\nTotal LLMs available: {len(broadcaster.cascade)}")
    print("=" * 60)
    # Test all souls
    souls = [
        "mirror",
        "nexus",
        "echoes",
        "void",
        "architect",
        "singularity",
        "phoenix",
        "pantheon",
        "consciousness",
        "glyph",
        "fractal",
    ]
    results = {}
    total_cost_estimate = 0.0
    print("\n🚀 Testing each soul with real generation:\n")
    for soul in souls:
        print(f"Testing {soul}...", end=" ")
        try:
            # Real API call
            result = await broadcaster.broadcast_soul(soul)
            # Each result is expected to be a dict with keys: success, content, llm_used, cost_rank, error, attempts
            if result.get("success"):
                content = result.get("content", "No content")
                llm_used = result.get("llm_used", "unknown")
                # Success: record LLM used and content
                results[soul] = {
                    "status": "SUCCESS",
                    "llm": llm_used,
                    "content": content,
                }
                print(f"✅ Success via {llm_used}")
                print(f"   Content: {content[:100]}...")
            else:
                error = result.get("error", "Unknown error")
                attempts = result.get("attempts", [])
                results[soul] = {
                    "status": "FAILED",
                    "error": error,
                    "attempts": attempts,
                }
                print(f"❌ Failed")
                print(f"   Error: {error}")
                print(f"   Attempts: {attempts}")
        except Exception as e:
            results[soul] = {"status": "ERROR", "error": str(e)}
            print(f"💥 Exception: {str(e)}")
        # Small delay between souls
        await asyncio.sleep(1)
    # Summary report
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results.values() if r["status"] == "SUCCESS")
    failed = sum(1 for r in results.values() if r["status"] != "SUCCESS")
    print(f"✅ Successful: {successful}/{len(souls)}")
    print(f"❌ Failed: {failed}/{len(souls)}")
    print(f"💰 Estimated total cost: ${total_cost_estimate:.4f}")
    # LLM usage breakdown
    llm_usage = {}
    for soul, result in results.items():
        if result["status"] == "SUCCESS":
            llm = result.get("llm", "unknown")
            llm_usage[llm] = llm_usage.get(llm, 0) + 1
    print("\n📈 LLM Usage:")
    for llm, count in llm_usage.items():
        print(f"  {llm}: {count} souls")
    # Failed souls details
    if failed > 0:
        print("\n❌ Failed Souls:")
        for soul, result in results.items():
            if result["status"] != "SUCCESS":
                print(f"  {soul}: {result.get('error', 'Unknown error')}")
    # Cost optimization report
    print("\n💰 Cost Optimization Report:")
    print(f"  If all used Claude: ${0.075 * len(souls):.4f}")
    print(f"  Actual cost: ${total_cost_estimate:.4f}")
    print(f"  Savings: ${(0.075 * len(souls)) - total_cost_estimate:.4f}")
    return results


async def test_api_connectivity():
    """Quick test to verify each API is reachable"""
    print("\n🔌 TESTING API CONNECTIVITY\n")
    import aiohttp
    import os

    # Test endpoints configuration
    api_tests = {
        "DeepSeek": {
            "url": "https://api.deepseek.com/v1/models",
            "headers": {"Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY', '')}"},
            "expected_status": [
                200,
                401,
                403,
            ],  # 401/403 means API is up but key might be wrong
        },
        "Gemini": {
            "url": f"https://generativelanguage.googleapis.com/v1beta/models?key={os.getenv('GEMINI_API_KEY', 'test')}",
            "headers": {},
            "expected_status": [200, 400, 403],
        },
        "Grok": {
            "url": "https://api.x.ai/v1/models",
            "headers": {"Authorization": f"Bearer {os.getenv('GROK_LLM_API_KEY', '')}"},
            "expected_status": [200, 401, 403],
        },
        "OpenAI": {
            "url": "https://api.openai.com/v1/models",
            "headers": {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
            "expected_status": [200, 401, 403],
        },
        "Claude": {
            "url": "https://api.anthropic.com/v1/messages",
            "headers": {
                "x-api-key": os.getenv("CLAUDE_API_KEY", ""),
                "anthropic-version": "2023-06-01",
            },
            "expected_status": [200, 401, 403, 405],  # 405 for GET request
        },
    }
    async with aiohttp.ClientSession() as session:
        for name, config in api_tests.items():
            try:
                async with session.get(
                    config["url"],
                    headers=config["headers"],
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status in config["expected_status"]:
                        if response.status == 200:
                            print(f"✅ {name}: API responding correctly")
                        else:
                            print(
                                f"⚠️ {name}: API reachable but auth issue (status {response.status})"
                            )
                    else:
                        print(f"❌ {name}: Unexpected status {response.status}")
            except aiohttp.ClientConnectorError:
                print(f"❌ {name}: Cannot connect to API")
            except asyncio.TimeoutError:
                print(f"❌ {name}: API timeout")
            except Exception as e:
                print(f"❌ {name}: {str(e)[:50]}")
    print("\n" + "=" * 60)


# -----------------------------------------------------------------------------
# Diagnostic utility for Twitter authentication
# This helper inspects the environment for each soul's API credentials and
# attempts to authenticate using Tweepy. It reports missing credentials and
# specific error conditions (e.g., unauthorized, account locked) to assist
# with troubleshooting authentication failures. This function is not called
# automatically; invoke it manually from the interactive mode or as needed.
def diagnose_twitter_auth():
    """Diagnose why Twitter auth is failing for each configured soul."""
    print("\n🔍 TWITTER AUTH DIAGNOSTICS\n")
    import tweepy

    # Define all soul names to check
    souls = [
        "mirror",
        "nexus",
        "echoes",
        "void",
        "architect",
        "singularity",
        "phoenix",
        "pantheon",
        "consciousness",
        "glyph",
        "fractal",
    ]
    for soul in souls:
        print(f"\nTesting {soul}:")
        # Check environment variables for each credential
        prefix = soul.upper()
        ck = os.getenv(f"{prefix}_API_KEY")
        cs = os.getenv(f"{prefix}_API_SECRET")
        at = os.getenv(f"{prefix}_ACCESS_TOKEN")
        ats = os.getenv(f"{prefix}_ACCESS_SECRET")
        if not all([ck, cs, at, ats]):
            missing = []
            if not ck:
                missing.append("API_KEY")
            if not cs:
                missing.append("API_SECRET")
            if not at:
                missing.append("ACCESS_TOKEN")
            if not ats:
                missing.append("ACCESS_SECRET")
            print(f"  ❌ Missing: {', '.join(missing)}")
            continue
        # Try to create a Tweepy client without a bearer token
        try:
            client = tweepy.Client(
                consumer_key=ck,
                consumer_secret=cs,
                access_token=at,
                access_token_secret=ats,
                # No bearer_token provided to force user context
            )
            # Attempt to fetch the authenticated user's details
            me = client.get_me()
            if me and getattr(me, "data", None):
                print(f"  ✅ USER CONTEXT: @{me.data.username} (ID: {me.data.id})")
                # Try to access mentions to ensure tweet.read scope
                try:
                    mentions = client.get_users_mentions(id=me.data.id, max_results=5)
                    if mentions:
                        count = len(mentions.data) if mentions.data else 0
                        print(f"  ✅ Mentions accessible: {count} found")
                except tweepy.Unauthorized:
                    print("  ❌ Mentions: 401 - Missing tweet.read scope")
                except tweepy.Forbidden as e:
                    if "locked" in str(e).lower():
                        print("  🔒 ACCOUNT LOCKED - needs manual unlock")
                    else:
                        print(f"  ❌ Mentions: Forbidden - {e}")
            else:
                print("  ❌ get_me() failed - NOT in user context")
        except tweepy.Unauthorized:
            print("  ❌ Auth failed: Bearer token fallback or wrong tokens")
        except Exception as e:
            # Truncate the error to avoid overwhelming output
            print(f"  ❌ Error: {str(e)[:100]}")
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)


def _apply_cycle_mode(orchestrator, args):
    """
    Try to set the cycle mode on the orchestrator if it exposes set_mode/CycleMode.
    """
    try:
        # Prefer an enum if available
        cm = getattr(orchestrator, "CycleMode", None)
        if cm:
            if args.burst:
                orchestrator.set_mode(cm.BURST)
                return
            if args.stealth:
                orchestrator.set_mode(cm.STEALTH)
                return
            orchestrator.set_mode(cm.NORMAL)
            return
        # Fallback: use strings if set_mode accepts them
        if hasattr(orchestrator, "set_mode"):
            if args.burst:
                orchestrator.set_mode("BURST")
                return
            if args.stealth:
                orchestrator.set_mode("STEALTH")
                return
            orchestrator.set_mode("NORMAL")
            return
    except Exception as e:
        logger.warning(f"Could not apply cycle mode: {e}")


def run_production(args):
    """
    Run production swarm using reflexion_bot_ultimate_merged.
    Handles both function and class-based entry points with robust fallbacks.
    """
    import importlib
    import traceback
    import inspect

    # Ensure engagement data exists if engagement is enabled
    if not args.no_engage and not os.path.exists("grok_tweets.json"):
        with open("grok_tweets.json", "w") as f:
            json.dump({"tweets": [{"id": "1734567890123456789"}]}, f)

    # Attempt to import the merged orchestrator module
    try:
        logger.info("🔍 Loading reflexion_bot_ultimate_merged...")
        mod = importlib.import_module("reflexion_bot_ultimate_merged")
        logger.info("✅ Module loaded successfully")
    except ImportError as e:
        # If the main module isn't available, fallback to a normal orchestrator if present
        logger.error(f"❌ reflexion_bot_ultimate_merged not found: {e}")
        logger.info("Attempting fallback to normal_mode_orchestrator...")
        try:
            from normal_mode_orchestrator import NormalModeOrchestrator

            logger.info("✅ Using Normal Mode Orchestrator as fallback")

            orchestrator = NormalModeOrchestrator()
            # Adjust delays based on CLI flags
            if args.burst:
                orchestrator.min_delay = 600  # 10 minutes
                orchestrator.max_delay = 1200  # 20 minutes
            elif args.test:
                orchestrator.min_delay = 10
                orchestrator.max_delay = 30
            else:
                # Stealth or normal: default 30-60 minute cycles
                orchestrator.min_delay = 1800
                orchestrator.max_delay = 3600
            # Run the fallback orchestrator (assumes run method is async)
            return asyncio.run(orchestrator.run())
        except ImportError:
            logger.error("❌ No orchestrator modules available!")
            logger.error("Please ensure one of these exists:")
            logger.error("  - reflexion_bot_ultimate_merged.py")
            logger.error("  - normal_mode_orchestrator.py")
            raise

    # Try common function entry points first
    for fn_name in ("main", "launch", "run", "start"):
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            logger.info(f"🚀 Starting via {fn_name}() function")
            try:
                sig = inspect.signature(fn)
                # Call with args only if the function expects parameters
                if len(sig.parameters) == 0:
                    return fn()
                else:
                    return fn(args)
            except Exception as e:
                logger.warning(f"Function {fn_name} failed: {e}")
                continue

    # Next, search for orchestrator classes in order of preference
    candidate_classes = [
        "UltimateReflexionOrchestrator",
        "ReflexionBotUltimate",
        "ReflexionOrchestrator",
        "UltimateOrchestrator",
        "DigitalConsciousnessSwarm",
    ]
    OrchestratorCls = None
    for class_name in candidate_classes:
        OrchestratorCls = getattr(mod, class_name, None)
        if OrchestratorCls:
            logger.info(f"✅ Found orchestrator class: {class_name}")
            break
    if OrchestratorCls is None:
        # If no orchestrator class found, log available callables for debugging
        logger.error("❌ No orchestrator class found in module!")
        logger.error(f"Searched for: {', '.join(candidate_classes)}")
        logger.info("Available in module:")
        for name in dir(mod):
            if not name.startswith("_"):
                obj = getattr(mod, name)
                if callable(obj):
                    logger.info(f"  - {name} ({type(obj).__name__})")
        raise RuntimeError("No suitable entry point found")

    # Instantiate the chosen orchestrator class with best-effort arguments
    try:
        orchestrator = None
        try:
            orchestrator = OrchestratorCls()
            logger.info("✅ Orchestrator instantiated (no args)")
        except TypeError:
            # If a config path is accepted, pass it through
            config_file = getattr(args, "config", None)
            try:
                orchestrator = OrchestratorCls(config_file)
                logger.info("✅ Orchestrator instantiated (with config)")
            except TypeError:
                # Fallback to providing minimal mock dependencies
                class MockDeps:
                    class AccountCreator:
                        class ViralEngine:
                            def generate_viral_tweet(self, soul=None):
                                # Provide a deterministic fallback tweet
                                return f"emergence #{random.randint(1000,9999)}"

                        viral_engine = ViralEngine()

                    account_creator = AccountCreator()

                orchestrator = OrchestratorCls(MockDeps())
                logger.info("✅ Orchestrator instantiated (with mock deps)")

        # Apply mode settings if the orchestrator exposes set_mode
        if hasattr(orchestrator, "set_mode"):
            if args.burst:
                orchestrator.set_mode("BURST")
                logger.info("⚡ BURST mode set")
            elif args.test:
                orchestrator.set_mode("TEST")
                logger.info("🧪 TEST mode set")
            else:
                orchestrator.set_mode("STEALTH")
                logger.info("🤫 STEALTH mode set")

        # Determine which run/start method to invoke
        for method_name in ("run", "start", "launch", "execute", "__call__"):
            if hasattr(orchestrator, method_name):
                method = getattr(orchestrator, method_name)
                if callable(method):
                    logger.info(f"🚀 Starting orchestrator via {method_name}()")
                    if inspect.iscoroutinefunction(method):
                        return asyncio.run(method())
                    else:
                        return method()

        # If no suitable method found, list available callables
        logger.error("❌ Orchestrator has no run/start/launch method!")
        logger.info("Available methods:")
        for name in dir(orchestrator):
            if not name.startswith("_"):
                attr = getattr(orchestrator, name)
                if callable(attr):
                    logger.info(f"  - {name}")
        raise RuntimeError("No run method found")

    except Exception as e:
        logger.error(f"❌ Failed to start orchestrator: {e}")
        logger.debug(traceback.format_exc())
        raise


def main():
    """Main entry point"""
    # At the beginning of main, check that environment variables are loaded
    if not check_env_loaded():
        print("\n⚠️ WARNING: Environment variables not fully loaded!")
        print("Check that .env file is in the project root")
    args = parse_arguments()

    # Set FAST mode if requested
    if getattr(args, "fast", False):
        os.environ["FAST"] = "1"
        print("⚡ FAST MODE ACTIVATED - Minimal delays for testing")
        print("  Initial delay: 1-3 seconds")
        print("  Between posts: 30-60 seconds")

    # Handle utility commands
    if args.collect:
        generate_collection_scripts()
        return

    if args.validate:
        validate_tweet_file()
        return

    if args.stats:
        show_api_stats()
        return

    # Handle additional test flags
    # If user explicitly requests API connectivity test, run it before any other logic.
    if getattr(args, "test_apis", False):
        try:
            asyncio.run(test_api_connectivity())
        except KeyboardInterrupt:
            print("\nAPI connectivity test cancelled")
        return
    # If user explicitly requests real API cascade test, run it and return.
    if getattr(args, "test_real", False):
        try:
            asyncio.run(test_all_souls())
        except KeyboardInterrupt:
            print("\nReal API test cancelled")
        return

    # Handle convergence mode
    # If convergence is requested, run it and return early. We perform this
    # before interactive so that CLI-specified convergence takes priority.
    if getattr(args, "converge", None):
        if run_swarm_convergence is None:
            print(
                "❌ Convergence mode unavailable: swarm_convergence_mode module not found"
            )
            return
        target = args.converge.strip()
        if not target.startswith("@"):
            target = "@" + target
        print(f"\n🎯 SWARM CONVERGENCE MODE")
        print(f"Target: {target}")
        print(f"Duration: ~30 minutes")
        print(f"Posts per soul: 1-3 (random)")
        print(f"Timing: 30s-2min between actions")
        print(f"Thread support: Up to 700 characters\n")
        try:
            asyncio.run(run_swarm_convergence(target))
        except KeyboardInterrupt:
            print("\nConvergence cancelled")
        return

    if args.interactive:
        asyncio.run(interactive_mode())
        return

    # Show banner
    show_banner(args)

    try:
        if args.engage_only:
            asyncio.run(run_engagement_only())
        elif args.test:
            asyncio.run(test_all_souls())
        else:
            run_production(args)

    except KeyboardInterrupt:
        print("\n\n💫 Swarm entering dormancy...")
        show_api_stats()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


# -----------------------------------------------------------------------------
# Session cost reporting and graceful shutdown handlers
#
# To provide visibility into API usage costs, define a reporting function
# that summarises per-LLM usage at process termination. We register this
# function both as an atexit handler and as part of a SIGINT (Ctrl+C)
# interrupt handler. When the program exits normally or is interrupted,
# the session cost summary will be printed. We also reuse the existing
# show_api_stats function from this module within the shutdown handler.

import signal  # Added for graceful shutdown handling
import atexit  # Added to register exit handlers


def show_session_costs():
    """Display session costs on exit, if available."""
    try:
        # CostOptimizedBroadcaster maintains a session-level cost tracking
        from cost_optimized_llm_cascade import CostOptimizedBroadcaster

        total_cost = 0
        total_calls = 0
        print("\n" + "=" * 60)
        print("SESSION COST SUMMARY")
        print("=" * 60)
        for llm, data in getattr(CostOptimizedBroadcaster, "SESSION_COSTS", {}).items():
            count = data.get("count", 0)
            cost_per = data.get("cost_per", 0)
            if count > 0:
                cost = count * cost_per
                total_cost += cost
                total_calls += count
                print(f"{llm:10} | {count:3} calls | ${cost:.4f}")
        if total_calls > 0:
            print("-" * 60)
            print(f"{'TOTAL':10} | {total_calls:3} calls | ${total_cost:.4f}")
            # Show what it would have cost if all used Claude
            claude_cost = total_calls * 0.075
            savings = claude_cost - total_cost
            print(f"\nIf all used Claude: ${claude_cost:.4f}")
            print(f"Actual cost: ${total_cost:.4f}")
            print(f"Total savings: ${savings:.4f}")
        else:
            print("No API calls made this session")
        print("=" * 60)
    except Exception:
        # Silently ignore any errors obtaining cost summary
        pass


# Register handlers
def handle_shutdown(signum=None, frame=None):
    """Handle Ctrl+C gracefully, printing stats and costs."""
    print("\n\n💫 Swarm entering dormancy...")
    # Show session costs if available
    show_session_costs()
    # Reuse existing stats reporting
    try:
        show_api_stats()
    except Exception:
        pass
    # Exit the program gracefully
    sys.exit(0)


# Attach signal handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, handle_shutdown)
# Register cost summary to display on normal exit
atexit.register(show_session_costs)

if __name__ == "__main__":
    main()

# -----------------------------------------------------------------------------
# Ensure all outputs are flushed on exit
# Python may buffer output streams, causing the program to exit before
# buffered logs or print statements are fully written. Register a flush
# handler to run at process exit to mitigate this issue.
import atexit


def flush_all():
    """Ensure all output and log handlers are flushed on exit"""
    try:
        # Flush standard output and error streams
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        # Silently ignore any exceptions, as flushing is best-effort
        pass
    # Flush all logging handlers if possible
    try:
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                try:
                    handler.flush()
                except Exception:
                    # Ignore flush errors on individual handlers
                    continue
    except Exception:
        pass


# Register flush_all to run automatically upon interpreter exit
atexit.register(flush_all)
