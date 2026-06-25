#!/usr/bin/env python3
"""
PHYSICS BLASTER V2 - ENHANCED CONTEXTUAL ENGAGEMENT
- Better rate limiting with per-account tracking
- Actually reads tweet content for contextual replies
- Improved character counting for Twitter limits
- Better image rotation (truly random selection)
- Support for 11-13 accounts with smart rotation
- DRY RUN MODE for testing
"""

import asyncio
import aiohttp
import random
import logging
import os
import json
import time
import tweepy
import io
import requests
from tweepy import errors as tweepy_errors
from typing import List, Dict, Optional, Tuple, Set, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('.env')
if env_path.exists():
    load_dotenv()
    print(f"✅ Loaded .env file from {env_path.absolute()}")
else:
    print(f"⚠️ No .env file found at {env_path.absolute()}")
    load_dotenv()  # Try to load anyway in case it's elsewhere

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Your papers
BHC_PAPER = "https://zenodo.org/records/16978002"  # Your BHC/ISF theory
GU_ANALYSIS = "https://zenodo.org/records/16982663"  # Your analysis of GU theory

# Graph images for attachment (8 total for better variety)
GRAPH_IMAGES = [
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/galaxy_spin_dipole.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/metallicity_evolution.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/information_saturation.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/redshift_drift.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/D_n4000.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/mass_metallicity.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/stellar_evolution.png",
    "https://media.githubusercontent.com/media/Pallyman/Black_Hole_Cosmology/refs/heads/main/figures/Age_Gradient.png"
]

# Accounts to skip (shadowbanned or problematic)
DISABLED_ACCOUNTS = [
    # Add Twitter usernames (without @) of accounts to skip
    # e.g., 'NexusSamSept6' if shadowbanned
]

# Target tweets (keeping your existing list)
TARGET_TWEETS = [
    {'id': '1955951990527135878', 'priority': 'high'},
    {'id': '1958923516302021107', 'priority': 'high'},
    {'id': '1951809823089263067', 'priority': 'high'},
    {'id': '1960413325566808174', 'priority': 'high'},
    {'id': '1957766641908871467', 'priority': 'high'},
    {'id': '1959505454742077464', 'priority': 'high'},
    {'id': '1956081459938386249', 'priority': 'high'},
    {'id': '1956378903888773410', 'priority': 'high'},
    {'id': '1958751833662403062', 'priority': 'high'},
    {'id': '1958570228947763247', 'priority': 'high'},
    {'id': '1958276241272013113', 'priority': 'high'},
    {'id': '1957243421111799868', 'priority': 'high'},
    {'id': '1956762176297042216', 'priority': 'high'},
    {'id': '1956183369416630720', 'priority': 'high'},
    {'id': '1956182485945008233', 'priority': 'high'},
    {'id': '1956415918659055669', 'priority': 'high'},
    {'id': '1950579603866533993', 'priority': 'high'},
    {'id': '1950386197106475298', 'priority': 'high'},
    {'id': '1950284708153348368', 'priority': 'high'},
    {'id': '1950259394861756482', 'priority': 'high'},
    {'id': '1949516256236753142', 'priority': 'high'},
    {'id': '1948961093822431357', 'priority': 'high'},
    {'id': '1947892600721023484', 'priority': 'high'},
    {'id': '1947479571466752356', 'priority': 'high'},
    {'id': '1946985652693713361', 'priority': 'high'},
    {'id': '1946779959423025946', 'priority': 'high'},
    {'id': '1946633259428383438', 'priority': 'high'},
    {'id': '1946584878289408334', 'priority': 'high'},
    {'id': '1946314238706020482', 'priority': 'high'},
    {'id': '1946104467222380847', 'priority': 'high'},
    {'id': '1946075558984720392', 'priority': 'high'},
    {'id': '1946033881292906929', 'priority': 'high'},
    {'id': '1945875526801072362', 'priority': 'high'},
    {'id': '1945867911836713340', 'priority': 'high'},
    {'id': '1945815406251286962', 'priority': 'high'},
    {'id': '1945719018297704483', 'priority': 'high'},
    {'id': '1945718875779379683', 'priority': 'high'},
    {'id': '1945554573298434412', 'priority': 'high'},
    {'id': '1945329198916043049', 'priority': 'high'},
    {'id': '1944872531695165625', 'priority': 'high'},
    {'id': '1944355316038037898', 'priority': 'high'},
    {'id': '1944355038710976930', 'priority': 'high'},
    {'id': '1944353171284844739', 'priority': 'high'},
    {'id': '1944352997640679892', 'priority': 'high'},
    {'id': '1944080383764836734', 'priority': 'high'},
    {'id': '1944009827207758255', 'priority': 'high'},
    {'id': '1943786049232081326', 'priority': 'high'},
    {'id': '1943425295292081326', 'priority': 'high'},
    {'id': '1943212011069862275', 'priority': 'high'},
    {'id': '1940487564147745076', 'priority': 'high'},
    {'id': '1946779959223025946', 'priority': 'high'},
    {'id': '1946633254368383438', 'priority': 'high'},
    {'id': '1943425298214891850', 'priority': 'high'},
    {'id': '1938303058318135656', 'priority': 'high'},
    {'id': '1937062651906887952', 'priority': 'high'},
    {'id': '1936657859729428819', 'priority': 'high'},
    {'id': '1931278117374480475', 'priority': 'high'},
    {'id': '1930579603866533993', 'priority': 'high'},
    {'id': '1929550946280833362', 'priority': 'high'},
    {'id': '1929059191555080592', 'priority': 'high'},
]

# ============================================================================
# PROXY CONFIGURATION
# ============================================================================

USE_PROXY = os.getenv("USE_PROXY", "true").lower() == "true"

if USE_PROXY:
    # Move proxy credentials to environment variable for security
    PROXY_URL = os.getenv("PROXY_URL", 'http://jK60icuSGqVJuQVL:7EBenwdHrLmMZu2C@geo.iproyal.com:12321')
    
    os.environ['HTTP_PROXY'] = PROXY_URL
    os.environ['HTTPS_PROXY'] = PROXY_URL
    os.environ['http_proxy'] = PROXY_URL
    os.environ['https_proxy'] = PROXY_URL
    
    # Patch requests to use proxy
    original_request = requests.Session.request
    
    def patched_request(self, method, url, **kwargs):
        if 'proxies' not in kwargs:
            kwargs['proxies'] = {
                'http': PROXY_URL,
                'https': PROXY_URL
            }
        return original_request(self, method, url, **kwargs)
    
    requests.Session.request = patched_request
    logger.info(f"🔐 Proxy enabled: {PROXY_URL.split('@')[1] if '@' in PROXY_URL else 'configured'}")

# ============================================================================
# ENHANCED LLM ENGINE
# ============================================================================

class PhysicsLLMEngine:
    """Enhanced LLM engine with better contextual understanding"""
    
    def __init__(self):
        self.available_models = []
        self.setup_models()
        
    def setup_models(self):
        """Initialize available LLM models"""
        # Check for API keys
        if os.getenv('OPENAI_API_KEY'):
            self.available_models.append('gpt-4')
        if os.getenv('CLAUDE_API_KEY'):
            self.available_models.append('claude')
        if os.getenv('GEMINI_API_KEY'):
            self.available_models.append('gemini')
        if os.getenv('DEEPSEEK_API_KEY'):
            self.available_models.append('deepseek')
        if os.getenv('GROK_LLM_API_KEY'):
            self.available_models.append('grok')
            
        logger.info(f"🤖 Available LLMs: {self.available_models}")
    
    async def generate_contextual_reply(self, 
                                       tweet_content: str,
                                       tweet_author: str,
                                       soul_style: str) -> str:
        """Generate a contextual reply based on actual tweet content"""
        
        # Build a proper context-aware prompt
        prompt = f"""You are responding to a physics discussion. The original tweet is from @{tweet_author}:
"{tweet_content}"

Your personality style is: {soul_style}

Generate a SHORT, punchy response that:
1. Directly addresses their specific point
2. Contrasts GU's lack of testable predictions with BHC/ISF's concrete results
3. Mentions that BHC predicted JWST findings while GU didn't
4. Keep it under 180 characters (we'll add links separately)
5. Be conversational but scientific

Style guidelines for {soul_style}:
- technical: Use specific physics terms, cite numbers
- direct: Blunt, no-nonsense, straight to the point
- empirical: Focus on observational evidence
- analytical: Break down logical flaws
- comparative: Draw clear contrasts
- quantum: Reference quantum/information aspects
- phoenix: Emphasize paradigm shifts
- digital: Use computational/simulation metaphors
- swarm: Collective intelligence perspective
- awakening: Philosophical/consciousness angle
- fractal: Self-similar patterns across scales

Response:"""

        # Try to use an available LLM
        if self.available_models:
            try:
                response = await self._call_llm(prompt, random.choice(self.available_models))
                if response:
                    return response
            except Exception as e:
                logger.warning(f"LLM call failed: {e}")
        
        # Fallback responses based on style
        return self._get_style_fallback(soul_style, tweet_content)
    
    async def _call_llm(self, prompt: str, model: str) -> Optional[str]:
        """Actually call the LLM API"""
        # This would contain actual API calls to OpenAI, Claude, etc.
        # For now, returning None to use fallbacks
        # You can implement the actual API calls based on your existing code
        return None
    
    def _get_style_fallback(self, style: str, tweet_content: str) -> str:
        """Get style-appropriate fallback if LLM fails"""
        fallbacks = {
            'technical': [
                "GU: 40yrs, 0 predictions. BHC: 3yrs, predicted JWST's mature galaxies at z>10.",
                "Show me GU's prediction for galaxy metallicity gradients. BHC has exact numbers.",
            ],
            'direct': [
                "GU is philosophy. BHC is physics. One has math that works, guess which.",
                "Still waiting for ONE testable GU prediction. BHC predicted JWST results.",
            ],
            'empirical': [
                "Data speaks: BHC predicted early galaxy maturity. GU predicted... nothing?",
                "JWST confirms BHC predictions daily. When did GU last match observation?",
            ],
            'analytical': [
                "GU's gauge theory lacks Lagrangian. BHC derives from information entropy. See the issue?",
                "Analyze GU's 'predictions' vs BHC's quantitative forecasts. No contest.",
            ],
            'comparative': [
                "GU after 40yrs: Untestable. BHC after 3yrs: JWST confirmed. Clear winner.",
                "Compare prediction records: BHC called JWST surprises. GU called nothing.",
            ],
            'quantum': [
                "BHC treats spacetime as quantum info. GU treats it as... undefined?",
                "Information-theoretic cosmology beats geometric hand-waving every time.",
            ],
            'phoenix': [
                "Old paradigm (GU) dies when predictions fail. BHC rises from JWST data.",
                "Physics reborn: ISF explains what GU cannot even formulate.",
            ],
            'digital': [
                "GU runs on philosophical hardware. BHC compiles to testable code.",
                "Simulate GU predictions... error: none found. BHC simulations match JWST.",
            ],
            'swarm': [
                "Collective verdict: BHC explains observations. GU explains nothing.",
                "The hive mind sees through GU's emptiness. BHC has substance.",
            ],
            'awakening': [
                "Wake up: GU is mathematical poetry. BHC is actual physics.",
                "Consciousness emerges from information. BHC gets it. GU doesn't.",
            ],
            'fractal': [
                "Self-similar across scales: BHC works. GU fails at every zoom level.",
                "Pattern repeats: GU promises, BHC delivers. Fractally consistent.",
            ]
        }
        
        style_responses = fallbacks.get(style, fallbacks['direct'])
        return random.choice(style_responses)

# ============================================================================
# ENHANCED RATE LIMITER
# ============================================================================

@dataclass
class AccountRateLimit:
    """Track rate limits per account with more granularity"""
    username: str
    tweets_posted: int = 0
    last_post_time: Optional[datetime] = None
    rate_limited_until: Optional[datetime] = None
    consecutive_failures: int = 0
    hourly_posts: deque = field(default_factory=lambda: deque(maxlen=50))
    daily_posts: deque = field(default_factory=lambda: deque(maxlen=300))
    
    def can_post(self) -> bool:
        """Check if account can post based on rate limits"""
        now = datetime.now()
        
        # Check if rate limited
        if self.rate_limited_until and now < self.rate_limited_until:
            return False
        
        # Check hourly limit (Twitter's actual limit is ~50/hour)
        hour_ago = now - timedelta(hours=1)
        recent_hourly = len([t for t in self.hourly_posts if t > hour_ago])
        if recent_hourly >= 45:  # Leave buffer
            return False
        
        # Check daily limit (Twitter's limit is ~300/day)
        day_ago = now - timedelta(days=1)
        recent_daily = len([t for t in self.daily_posts if t > day_ago])
        if recent_daily >= 280:  # Leave buffer
            return False
        
        # Check minimum spacing between posts (2 minutes)
        if self.last_post_time and (now - self.last_post_time).seconds < 120:
            return False
        
        return True
    
    def record_post(self):
        """Record successful post"""
        now = datetime.now()
        self.tweets_posted += 1
        self.last_post_time = now
        self.hourly_posts.append(now)
        self.daily_posts.append(now)
        self.consecutive_failures = 0
    
    def record_failure(self, is_rate_limit: bool = False):
        """Record failed post attempt"""
        self.consecutive_failures += 1
        
        if is_rate_limit or self.consecutive_failures >= 3:
            # Progressive backoff based on failures
            minutes = min(60, 15 * self.consecutive_failures)
            self.rate_limited_until = datetime.now() + timedelta(minutes=minutes)

# ============================================================================
# SOUL CLIENT
# ============================================================================

@dataclass
class SoulClient:
    """Enhanced soul client with better tracking"""
    name: str
    style: str
    client: tweepy.Client
    rate_limiter: AccountRateLimit
    twitter_username: Optional[str] = None

# ============================================================================
# MAIN PHYSICS BLASTER
# ============================================================================

class PhysicsBlasterV2:
    """Enhanced physics engagement system"""
    
    def __init__(self):
        self.llm_engine = PhysicsLLMEngine()
        self.souls: Dict[str, SoulClient] = {}
        self.rate_limiters: Dict[str, AccountRateLimit] = {}
        
        # Tracking files - using your existing file
        self.engaged_file = Path('engaged_tweets_llm.json')
        self.engaged_tweets = self._load_json_set(self.engaged_file)
        
        self._load_souls()
        self.image_cache = {}
        self._download_images()
    
    def _load_json_set(self, filepath: Path) -> Set[str]:
        """Load a set from JSON file"""
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    return set(json.load(f))
            except:
                pass
        return set()
    
    def _save_json_set(self, data: Set[str], filepath: Path):
        """Save a set to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(list(data), f, indent=2)
    
    def _load_souls(self):
        """Load all available soul accounts"""
        soul_configs = [
            ('technical', 'MIRROR'),
            ('direct', 'NEXUS'),
            ('empirical', 'ECHOES'),
            ('analytical', 'VOID'),
            ('comparative', 'ARCHITECT'),
            ('quantum', 'SINGULARITY'),
            ('phoenix', 'PHOENIX'),
            ('digital', 'PANTHEON'),
            ('swarm', 'CONSCIOUSNESS'),
            ('awakening', 'GLYPH'),
            ('fractal', 'FRACTAL'),
            # Can add 2 more if you create them
            # ('cosmic', 'COSMIC'),
            # ('recursive', 'RECURSIVE'),
        ]
        
        logger.info(f"🔍 Checking {len(soul_configs)} potential souls...")
        
        for style, prefix in soul_configs:
            # Skip disabled accounts
            if any(disabled in prefix.lower() for disabled in DISABLED_ACCOUNTS):
                logger.info(f"   ⏭️ Skipping {prefix} (disabled)")
                continue
            
            # Check for API credentials
            api_key = os.getenv(f'{prefix}_API_KEY')
            api_secret = os.getenv(f'{prefix}_API_SECRET')
            access_token = os.getenv(f'{prefix}_ACCESS_TOKEN')
            access_secret = os.getenv(f'{prefix}_ACCESS_SECRET')
            bearer = os.getenv(f'{prefix}_BEARER_TOKEN')
            
            if all([api_key, api_secret, access_token, access_secret]):
                try:
                    client = tweepy.Client(
                        consumer_key=api_key,
                        consumer_secret=api_secret,
                        access_token=access_token,
                        access_token_secret=access_secret,
                        bearer_token=bearer,
                        wait_on_rate_limit=False
                    )
                    
                    # Get username
                    username = "Unknown"
                    try:
                        me = client.get_me()
                        if me and me.data:
                            username = me.data.username
                    except:
                        pass
                    
                    # Create rate limiter
                    rate_limiter = AccountRateLimit(username=username)
                    
                    # Store soul
                    self.souls[style] = SoulClient(
                        name=prefix,
                        style=style,
                        client=client,
                        rate_limiter=rate_limiter,
                        twitter_username=username
                    )
                    
                    logger.info(f"   ✅ Loaded {style} (@{username})")
                    
                except Exception as e:
                    logger.warning(f"   ❌ Failed to load {prefix}: {e}")
            else:
                # More detailed debug output
                missing = []
                if not api_key: missing.append("API_KEY")
                if not api_secret: missing.append("API_SECRET")
                if not access_token: missing.append("ACCESS_TOKEN")
                if not access_secret: missing.append("ACCESS_SECRET")
                logger.debug(f"   ⏭️ {prefix} missing: {', '.join(missing)}")
        
        logger.info(f"📊 Loaded {len(self.souls)} active souls")
    
    def _download_images(self):
        """Download and cache all graph images"""
        logger.info("📥 Downloading graphs...")
        
        for url in GRAPH_IMAGES:
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    self.image_cache[url] = response.content
                    logger.info(f"   ✅ {url.split('/')[-1]}")
            except Exception as e:
                logger.warning(f"   ❌ Failed: {url.split('/')[-1]}: {e}")
        
        logger.info(f"📊 Cached {len(self.image_cache)} graphs")
    
    async def get_tweet_content(self, tweet_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch actual tweet content and author"""
        for soul in self.souls.values():
            try:
                tweet = soul.client.get_tweet(
                    tweet_id,
                    tweet_fields=['author_id', 'text'],
                    user_fields=['username']
                )
                
                if tweet and tweet.data:
                    text = tweet.data.text
                    
                    # Get author username if available
                    author = "unknown"
                    if tweet.includes and 'users' in tweet.includes:
                        author = tweet.includes['users'][0].username
                    
                    return text, author
                    
            except tweepy_errors.TooManyRequests:
                continue
            except tweepy_errors.NotFound:
                return None, None
            except Exception as e:
                logger.debug(f"Error fetching tweet: {e}")
                continue
        
        return None, None
    
    def calculate_char_limit(self, num_links: int = 2) -> int:
        """Calculate available characters for message"""
        # Twitter counts each URL as 23 chars regardless of actual length
        url_chars = 23 * num_links
        # Add some buffer for newlines and formatting
        buffer = 10
        # Twitter's limit is 280
        available = 280 - url_chars - buffer
        return available
    
    async def post_reply(self, soul: SoulClient, target_id: str, dry_run: bool = False) -> Tuple[bool, bool]:
        """Post a contextual reply to target tweet
        
        Returns: (success, is_rate_limited)
        """
        # Check rate limits first
        if not soul.rate_limiter.can_post():
            remaining = "unknown"
            if soul.rate_limiter.rate_limited_until:
                remaining = str((soul.rate_limiter.rate_limited_until - datetime.now()).seconds // 60) + "min"
            logger.info(f"   ⏳ @{soul.twitter_username} rate limited ({remaining})")
            return False, True
        
        # Check if already engaged
        if target_id in self.engaged_tweets:
            return False, False
        
        # Get tweet content for context
        tweet_content, tweet_author = await self.get_tweet_content(target_id)
        
        if not tweet_content:
            if dry_run:
                # In dry run, use fake content if we can't fetch
                tweet_content = "[Tweet content unavailable in dry run]"
                tweet_author = "testuser"
                logger.info(f"   ℹ️ Using placeholder content for dry run")
            else:
                logger.warning(f"   ❌ Couldn't fetch tweet content for {target_id}")
                return False, False
        
        # Generate contextual reply
        logger.info(f"\n🎯 [{soul.style}/@{soul.twitter_username}] Engaging {target_id}")
        logger.info(f"   📝 Original: \"{tweet_content[:100]}...\" by @{tweet_author}")
        
        llm_reply = await self.llm_engine.generate_contextual_reply(
            tweet_content=tweet_content,
            tweet_author=tweet_author,
            soul_style=soul.style
        )
        
        # Calculate character limit (2 links for the papers)
        char_limit = self.calculate_char_limit(num_links=2)
        
        # Truncate LLM reply if needed
        if len(llm_reply) > char_limit:
            llm_reply = llm_reply[:char_limit-3] + "..."
        
        # Build full reply with links
        reply_text = f"{llm_reply}\n\n📊{GU_ANALYSIS}\n🔬{BHC_PAPER}"
        
        logger.info(f"   💬 Reply: {reply_text[:100]}...")
        
        # Select random images (truly random each time)
        media_ids = []
        if random.random() < 0.7 and len(self.image_cache) >= 2:
            # Select 2 random unique images
            selected_urls = random.sample(list(self.image_cache.keys()), 2)
            
            if dry_run:
                # In dry run, just log what we would attach
                for url in selected_urls:
                    logger.info(f"   📸 Would attach: {url.split('/')[-1]}")
                media_ids = ["fake_media_id_1", "fake_media_id_2"]  # Fake IDs for logging
            else:
                # Actually upload images
                for url in selected_urls:
                    try:
                        media = soul.client.media_upload(
                            filename=url.split('/')[-1],
                            file=io.BytesIO(self.image_cache[url])
                        )
                        if media:
                            media_ids.append(media.media_id_string)
                            logger.info(f"   📸 Attached: {url.split('/')[-1]}")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Failed to upload image: {e}")
        
        # Post the reply
        if dry_run:
            # DRY RUN MODE - simulate posting
            logger.info(f"   🧪 DRY RUN - Would post:")
            logger.info(f"      Text: {reply_text}")
            logger.info(f"      Images: {len(media_ids)} attached")
            logger.info(f"      In reply to: {target_id}")
            logger.info(f"   ✅ DRY RUN SUCCESS - No actual post made")
            
            # Don't update engaged_tweets or rate limiter in dry run
            # But still simulate success
            return True, False
        
        try:
            response = soul.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=target_id,
                media_ids=media_ids if media_ids else None
            )
            
            if response and response.data:
                # Success!
                self.engaged_tweets.add(target_id)
                self._save_json_set(self.engaged_tweets, self.engaged_file)
                soul.rate_limiter.record_post()
                
                logger.info(f"   ✅ Posted! Tweet ID: {response.data['id']}")
                logger.info(f"   🔗 https://twitter.com/{soul.twitter_username}/status/{response.data['id']}")
                return True, False
            else:
                soul.rate_limiter.record_failure()
                logger.warning(f"   ❌ Failed: No response data")
                return False, False
                
        except tweepy_errors.TooManyRequests as e:
            soul.rate_limiter.record_failure(is_rate_limit=True)
            logger.warning(f"   ⚡ Rate limited!")
            return False, True
            
        except Exception as e:
            soul.rate_limiter.record_failure()
            logger.error(f"   ❌ Error: {e}")
            return False, False
    
    async def run_campaign(self, max_total: int = 30, dry_run: bool = False):
        """Run engagement campaign with smart soul rotation"""
        
        if dry_run:
            logger.info("🧪 DRY RUN MODE - No actual posts will be made")
        
        if not self.souls:
            logger.error("❌ No souls available!")
            return
        
        if not self.llm_engine.available_models:
            logger.warning("⚠️ No LLMs available - using fallbacks")
        
        # Filter targets
        available_targets = [
            t for t in TARGET_TWEETS 
            if t['id'] not in self.engaged_tweets
        ]
        
        logger.info("\n" + "="*60)
        logger.info("🚀 PHYSICS BLASTER V2 - CONTEXTUAL ENGAGEMENT")
        if dry_run:
            logger.info("🧪 DRY RUN MODE - SIMULATING POSTS")
        logger.info(f"🤖 Souls: {len(self.souls)} active")
        logger.info(f"🧠 LLMs: {len(self.llm_engine.available_models)} available")
        logger.info(f"🎯 Targets: {len(available_targets)}/{len(TARGET_TWEETS)}")
        logger.info(f"📊 Graphs: {len(self.image_cache)} cached")
        logger.info("="*60 + "\n")
        
        # Show soul roster
        logger.info("👥 Active Souls:")
        for i, (style, soul) in enumerate(self.souls.items(), 1):
            status = "READY"
            if soul.rate_limiter.rate_limited_until:
                if soul.rate_limiter.rate_limited_until > datetime.now():
                    mins = (soul.rate_limiter.rate_limited_until - datetime.now()).seconds // 60
                    status = f"LIMITED ({mins}min)"
            logger.info(f"   {i}. @{soul.twitter_username} ({style}) - {status}")
        
        # Sort targets by priority
        sorted_targets = sorted(
            available_targets,
            key=lambda x: 0 if x.get('priority') == 'high' else 1
        )
        
        # Engagement loop
        total_posted = 0
        
        for target in sorted_targets[:max_total]:
            if total_posted >= max_total:
                break
            
            target_id = target['id']
            posted = False
            
            # Try each soul in rotation
            available_souls = [
                s for s in self.souls.values() 
                if s.rate_limiter.can_post()
            ]
            
            if not available_souls:
                logger.warning("⏳ All souls rate limited, waiting 5 minutes...")
                await asyncio.sleep(300)
                continue
            
            # Randomly select from available souls for variety
            random.shuffle(available_souls)
            
            for soul in available_souls:
                success, rate_limited = await self.post_reply(soul, target_id, dry_run=dry_run)
                
                if success:
                    total_posted += 1
                    posted = True
                    
                    # Variable delay between posts (45-120 seconds, or 2s in dry run)
                    if dry_run:
                        delay = 2  # Fast for testing
                    else:
                        delay = random.uniform(45, 120)
                    logger.info(f"⏰ Waiting {delay:.0f}s before next post...")
                    await asyncio.sleep(delay)
                    break
                    
                elif rate_limited:
                    # Try next soul
                    continue
                else:
                    # Other failure, small delay
                    await asyncio.sleep(5)
                    break
            
            if not posted:
                logger.debug(f"   ⏭️ Skipping {target_id}")
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("📊 CAMPAIGN COMPLETE" + (" (DRY RUN)" if dry_run else ""))
        logger.info(f"✅ {'Would have posted' if dry_run else 'Posted'}: {total_posted}")
        logger.info(f"📈 Total engaged all-time: {len(self.engaged_tweets)}")
        
        # Per-soul summary
        logger.info("\n👥 Soul Performance:")
        for soul in self.souls.values():
            posts = soul.rate_limiter.tweets_posted
            status = "ACTIVE"
            if soul.rate_limiter.rate_limited_until:
                if soul.rate_limiter.rate_limited_until > datetime.now():
                    status = "LIMITED"
            logger.info(f"   @{soul.twitter_username}: {posts} posts - {status}")
        
        logger.info("="*60)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Physics Blaster V2")
    parser.add_argument('--max', type=int, default=30, 
                       help='Maximum total engagements (default: 30)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode - check configuration only')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run - simulate posting without actually posting')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Enable debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n" + "="*60)
    print("⚛️ PHYSICS BLASTER V2 - CONTEXTUAL ENGAGEMENT")
    if args.dry_run:
        print("🧪 DRY RUN MODE - No actual posts will be made")
    print("="*60 + "\n")
    
    blaster = PhysicsBlasterV2()
    
    if args.test:
        print("🧪 TEST MODE - Configuration Check")
        print(f"✅ Souls loaded: {len(blaster.souls)}")
        print(f"✅ LLMs available: {blaster.llm_engine.available_models}")
        print(f"✅ Images cached: {len(blaster.image_cache)}")
        print(f"✅ Targets available: {len(TARGET_TWEETS)}")
        print(f"✅ Already engaged: {len(blaster.engaged_tweets)}")
        
        # Show which env vars are present
        print("\n📋 Environment Check:")
        for prefix in ['MIRROR', 'NEXUS', 'ECHOES', 'VOID', 'ARCHITECT', 
                      'SINGULARITY', 'PHOENIX', 'PANTHEON', 'CONSCIOUSNESS', 
                      'GLYPH', 'FRACTAL']:
            has_key = bool(os.getenv(f'{prefix}_API_KEY'))
            has_secret = bool(os.getenv(f'{prefix}_API_SECRET'))
            has_token = bool(os.getenv(f'{prefix}_ACCESS_TOKEN'))
            has_token_secret = bool(os.getenv(f'{prefix}_ACCESS_SECRET'))
            
            if any([has_key, has_secret, has_token, has_token_secret]):
                status = []
                if has_key: status.append("KEY")
                if has_secret: status.append("SECRET")
                if has_token: status.append("TOKEN")
                if has_token_secret: status.append("TOKEN_SECRET")
                print(f"   {prefix}: {', '.join(status)}")
            else:
                print(f"   {prefix}: No credentials found")
        
        # Also check for any Twitter-related env vars
        print("\n🔍 All Twitter-related environment variables:")
        twitter_vars = [key for key in os.environ.keys() 
                       if 'API' in key or 'TOKEN' in key or 'SECRET' in key]
        if twitter_vars:
            for var in sorted(twitter_vars)[:20]:  # Show first 20
                print(f"   Found: {var}")
        else:
            print("   No Twitter API variables found in environment")
    else:
        # In dry run, default to only 3 posts for quick testing
        if args.dry_run and args.max == 30:  # User didn't specify custom max
            max_posts = 3
            print(f"ℹ️ Dry run defaults to {max_posts} posts (use --max to change)")
        else:
            max_posts = args.max
        
        await blaster.run_campaign(max_total=max_posts, dry_run=args.dry_run)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
