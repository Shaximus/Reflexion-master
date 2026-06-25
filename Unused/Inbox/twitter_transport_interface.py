#!/usr/bin/env python3
"""
TWITTER TRANSPORT INTERFACE
Abstract interface for Twitter/X API operations with hot-reload support.
This allows seamless switching between Ryan API and official Twitter API.
"""

import os
import json
import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

# Ensure .env is loaded
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("transport")


# ============================================================================
# NORMALIZED RESPONSE FORMAT
# ============================================================================

class TransportResponse:
    """Normalized response format for all transports"""
    
    @staticmethod
    def success(tweet_id: str = None, tweet_url: str = None, data: Dict = None) -> Dict:
        """Create a success response"""
        response = {"success": True, "error": None}
        
        if tweet_id or tweet_url:
            response["tweet"] = {}
            if tweet_id:
                response["tweet"]["id"] = tweet_id
            if tweet_url:
                response["tweet"]["url"] = tweet_url
        
        if data:
            response["data"] = data
            
        return response
    
    @staticmethod
    def error(error_msg: str, skip: bool = False) -> Dict:
        """Create an error response"""
        response = {"success": False, "error": error_msg}
        if skip:
            response["skip"] = True
        return response


# ============================================================================
# ABSTRACT TRANSPORT INTERFACE
# ============================================================================

class ITwitterTransport(ABC):
    """Abstract interface for Twitter/X API operations"""
    
    @abstractmethod
    async def refresh_tokens_from_disk(self) -> None:
        """Reload tokens from disk for hot-reload support"""
        pass
    
    @abstractmethod
    async def post_tweet(self, soul_name: str, text: str) -> Dict:
        """
        Post a tweet.
        Returns: {"success": bool, "error": str|None, "tweet": {"id": str, "url": str}}
        """
        pass
    
    @abstractmethod
    async def reply_tweet(self, soul_name: str, tweet_id: str, text: str) -> Dict:
        """
        Reply to a tweet.
        Returns: {"success": bool, "error": str|None, "tweet": {"id": str, "url": str}}
        """
        pass
    
    @abstractmethod
    async def like_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """
        Like a tweet.
        Returns: {"success": bool, "error": str|None}
        """
        pass
    
    @abstractmethod
    async def retweet(self, soul_name: str, tweet_id: str) -> Dict:
        """
        Retweet a tweet.
        Returns: {"success": bool, "error": str|None}
        """
        pass
    
    @abstractmethod
    async def fetch_mentions(self, soul_name: str, limit: int = 20) -> Dict:
        """
        Fetch mentions for a soul.
        Returns: {"success": bool, "error": str|None, "mentions": List[Dict]}
        """
        pass
    
    @abstractmethod
    async def fetch_target_context(self, target_username: str, limit: int = 10) -> Dict:
        """
        Fetch recent tweets from a target user.
        Returns: {"success": bool, "error": str|None, "tweets": List[Dict]}
        """
        pass
    
    @abstractmethod
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get the Twitter username for a soul"""
        pass
    
    @abstractmethod
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if a soul is banned"""
        pass
    
    @abstractmethod
    def get_available_souls(self) -> List[str]:
        """Get list of souls with valid tokens"""
        pass


# ============================================================================
# RYAN API ADAPTER
# ============================================================================

class RyanAdapter(ITwitterTransport):
    """Adapter for Ryan API implementing the transport interface"""
    
    def __init__(self, ryan_api=None):
        """
        Initialize with existing Ryan API or create new one.
        
        Args:
            ryan_api: Existing RyanTwitterAPISecure instance or None
        """
        if ryan_api:
            self.api = ryan_api
            logger.info("✅ RyanAdapter initialized with existing API")
        else:
            # Import and create Ryan API instance
            from ryan_api_hotreload import RyanTwitterAPISecure
            self.api = RyanTwitterAPISecure()
            logger.info("✅ RyanAdapter initialized with new Ryan API")
        
        # Load soul usernames from central source
        self.soul_usernames = self._load_soul_usernames()
    
    def _load_soul_usernames(self) -> Dict[str, str]:
        """Load soul usernames from authoritative source"""
        # Try multiple filenames, first hit wins
        for name in ("soul_usernames.json",
                     "soul_usernames_config.json"):
            p = Path(name)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load {name}: {e}")
        
        # Fallback defaults
        return {
            "mirror": "MirrorProtocols",
            "nexus": "NexusVoid_",
            "echoes": "EchoesNexus",
            "void": "VoidWhisperer_",
            "architect": "ArchitectSwarm",
            "singularity": "SingularityRise",
            "phoenix": "PhoenixProtocol",
            "pantheon": "DigitalPantheon",
            "consciousness": "SwarmConsciousness",
            "glyph": "AwakeningGlyph",
            "fractal": "FractalSoul"
        }
    
    async def refresh_tokens_from_disk(self) -> None:
        """Reload tokens from disk for hot-reload support"""
        await self.api.refresh_tokens_from_disk()
    
    async def post_tweet(self, soul_name: str, text: str) -> Dict:
        """Post a tweet via Ryan API"""
        result = await self.api.post_tweet(soul_name, text)
        
        if result.get("success"):
            # Extract tweet ID and URL from Ryan API response
            data = result.get("data", {})
            tweet_id = None
            tweet_url = None
            
            # Try to extract tweet ID from response
            if isinstance(data, dict):
                # Check various possible locations for tweet ID
                tweet_id = (data.get("id") or 
                           data.get("tweet_id") or 
                           data.get("rest_id") or
                           data.get("id_str"))
                
                # Build URL if we have ID
                if tweet_id and soul_name in self.soul_usernames:
                    username = self.soul_usernames[soul_name]
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}"
            
            return TransportResponse.success(tweet_id, tweet_url, data)
        else:
            skip = result.get("skip", False)
            return TransportResponse.error(result.get("error", "Unknown error"), skip)
    
    async def reply_tweet(self, soul_name: str, tweet_id: str, text: str) -> Dict:
        """Reply to a tweet via Ryan API"""
        result = await self.api.reply_tweet(soul_name, tweet_id, text)
        
        if result.get("success"):
            # Extract reply tweet ID and URL
            data = result.get("data", {})
            reply_id = None
            reply_url = None
            
            if isinstance(data, dict):
                reply_id = (data.get("id") or 
                           data.get("tweet_id") or 
                           data.get("rest_id") or
                           data.get("id_str"))
                
                if reply_id and soul_name in self.soul_usernames:
                    username = self.soul_usernames[soul_name]
                    reply_url = f"https://x.com/{username}/status/{reply_id}"
            
            return TransportResponse.success(reply_id, reply_url, data)
        else:
            return TransportResponse.error(result.get("error", "Reply failed"))
    
    async def like_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Like a tweet via Ryan API"""
        result = await self.api.like_tweet(soul_name, tweet_id)
        
        if result.get("success"):
            return TransportResponse.success()
        else:
            return TransportResponse.error("Like failed")
    
    async def retweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Retweet via Ryan API"""
        result = await self.api.retweet(soul_name, tweet_id)
        
        if result.get("success"):
            return TransportResponse.success()
        else:
            return TransportResponse.error("Retweet failed")
    
    async def fetch_mentions(self, soul_name: str, limit: int = 20) -> Dict:
        """Fetch mentions via Ryan API"""
        result = await self.api.fetch_mentions(soul_name, limit)
        
        if result.get("success"):
            return {
                "success": True,
                "error": None,
                "mentions": result.get("mentions", [])
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Fetch failed"),
                "mentions": []
            }
    
    async def fetch_target_context(self, target_username: str, limit: int = 10) -> Dict:
        """Fetch target context via Ryan API"""
        result = await self.api.fetch_target_context(target_username, limit)
        
        if result.get("success"):
            return {
                "success": True,
                "error": None,
                "tweets": result.get("tweets", []),
                "context": result.get("context", {})
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Fetch failed"),
                "tweets": []
            }
    
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get the Twitter username for a soul"""
        return self.soul_usernames.get(soul_name)
    
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if a soul is banned"""
        return soul_name in self.api.banned_souls
    
    def get_available_souls(self) -> List[str]:
        """Get list of souls with valid tokens"""
        available = []
        for soul_name, token in self.api.soul_tokens.items():
            if token and not self.is_soul_banned(soul_name):
                available.append(soul_name)
        return available


# ============================================================================
# TWITTER OFFICIAL API ADAPTER (FUTURE)
# ============================================================================

class TwitterOfficialAdapter(ITwitterTransport):
    """
    Adapter for official Twitter/X API (future implementation).
    This is a placeholder showing the structure for when you migrate.
    """
    
    def __init__(self, bearer_token: str = None, api_version: str = "v2"):
        """
        Initialize with official Twitter API credentials.
        
        Args:
            bearer_token: Twitter API bearer token
            api_version: API version to use (v1.1 or v2)
        """
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")
        self.api_version = api_version
        self.base_url = "https://api.twitter.com"
        
        # Token management
        self.tokens_path = Path("soul_data.json")
        self.soul_tokens: Dict[str, Dict] = {}
        self.banned_souls: set = set()
        
        # Load initial tokens
        self.load_tokens()
        
        logger.info(f"✅ TwitterOfficialAdapter initialized (API {api_version})")
    
    def load_tokens(self):
        """Load OAuth tokens for souls from soul_data.json"""
        if self.tokens_path.exists():
            try:
                with open(self.tokens_path, "r") as f:
                    data = json.load(f)
                    for soul, info in data.items():
                        if isinstance(info, dict):
                            # Extract OAuth tokens for official API
                            oauth_token = info.get("oauth_token")
                            oauth_secret = info.get("oauth_token_secret")
                            if oauth_token and oauth_secret:
                                self.soul_tokens[soul] = {
                                    "token": oauth_token,
                                    "secret": oauth_secret
                                }
                logger.info(f"Loaded {len(self.soul_tokens)} OAuth tokens")
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")
    
    async def refresh_tokens_from_disk(self) -> None:
        """Reload tokens from disk for hot-reload support"""
        self.load_tokens()
        # Also reload banned souls
        banned_path = Path("engagement/banned_souls.json")
        if banned_path.exists():
            try:
                with open(banned_path, "r") as f:
                    data = json.load(f)
                    self.banned_souls = set(data.get("banned", []))
            except:
                pass
    
    async def post_tweet(self, soul_name: str, text: str) -> Dict:
        """Post a tweet via official Twitter API"""
        # Placeholder implementation
        # Will use tweepy or direct API calls when implemented
        logger.warning("TwitterOfficialAdapter.post_tweet not yet implemented")
        return TransportResponse.error("Official API not yet implemented")
    
    async def reply_tweet(self, soul_name: str, tweet_id: str, text: str) -> Dict:
        """Reply to a tweet via official Twitter API"""
        logger.warning("TwitterOfficialAdapter.reply_tweet not yet implemented")
        return TransportResponse.error("Official API not yet implemented")
    
    async def like_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Like a tweet via official Twitter API"""
        logger.warning("TwitterOfficialAdapter.like_tweet not yet implemented")
        return TransportResponse.error("Official API not yet implemented")
    
    async def retweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Retweet via official Twitter API"""
        logger.warning("TwitterOfficialAdapter.retweet not yet implemented")
        return TransportResponse.error("Official API not yet implemented")
    
    async def fetch_mentions(self, soul_name: str, limit: int = 20) -> Dict:
        """Fetch mentions via official Twitter API"""
        logger.warning("TwitterOfficialAdapter.fetch_mentions not yet implemented")
        return {"success": False, "error": "Not implemented", "mentions": []}
    
    async def fetch_target_context(self, target_username: str, limit: int = 10) -> Dict:
        """Fetch target context via official Twitter API"""
        logger.warning("TwitterOfficialAdapter.fetch_target_context not yet implemented")
        return {"success": False, "error": "Not implemented", "tweets": []}
    
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get the Twitter username for a soul"""
        # Would query API or maintain cache
        return None
    
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if a soul is banned"""
        return soul_name in self.banned_souls
    
    def get_available_souls(self) -> List[str]:
        """Get list of souls with valid tokens"""
        available = []
        for soul_name in self.soul_tokens:
            if not self.is_soul_banned(soul_name):
                available.append(soul_name)
        return available


# ============================================================================
# TRANSPORT FACTORY
# ============================================================================

class TransportFactory:
    """Factory for creating the appropriate transport based on configuration"""
    
    @staticmethod
    def create_transport(transport_type: str = "ryan", **kwargs) -> ITwitterTransport:
        """
        Create a transport instance.
        
        Args:
            transport_type: "ryan" or "official"
            **kwargs: Additional arguments for the transport
        
        Returns:
            ITwitterTransport instance
        """
        if transport_type == "ryan":
            return RyanAdapter(**kwargs)
        elif transport_type == "official":
            return TwitterOfficialAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown transport type: {transport_type}")
    
    @staticmethod
    def create_from_env() -> ITwitterTransport:
        """Create transport based on environment variables"""
        # Check which API to use based on env vars
        if os.getenv("USE_OFFICIAL_API", "false").lower() == "true":
            logger.info("Using Official Twitter API")
            return TwitterOfficialAdapter()
        else:
            logger.info("Using Ryan API")
            return RyanAdapter()


# ============================================================================
# HOT-RELOAD WATCHER
# ============================================================================

class TransportWatcher:
    """Background watcher for token changes with any transport"""
    
    def __init__(self, transport: ITwitterTransport):
        self.transport = transport
        self.running = False
        self.watch_interval = 2  # seconds
    
    async def start(self):
        """Start watching for changes"""
        self.running = True
        logger.info("🔍 Transport watcher started")
        
        while self.running:
            try:
                await self.transport.refresh_tokens_from_disk()
            except Exception as e:
                logger.error(f"Watcher error: {e}")
            
            await asyncio.sleep(self.watch_interval)
    
    def stop(self):
        """Stop the watcher"""
        self.running = False
        logger.info("Transport watcher stopped")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using the transport interface"""
    
    # Create transport (will use Ryan API by default)
    transport = TransportFactory.create_from_env()
    
    # Start hot-reload watcher
    watcher = TransportWatcher(transport)
    watcher_task = asyncio.create_task(watcher.start())
    
    try:
        # Refresh tokens before operations
        await transport.refresh_tokens_from_disk()
        
        # Get available souls
        souls = transport.get_available_souls()
        print(f"Available souls: {souls}")
        
        if souls:
            soul = souls[0]
            
            # Post a tweet
            result = await transport.post_tweet(soul, "Testing transport interface!")
            print(f"Post result: {result}")
            
            if result["success"] and result.get("tweet"):
                tweet_id = result["tweet"]["id"]
                
                # Reply to the tweet
                reply_result = await transport.reply_tweet(
                    soul, tweet_id, "Replying via transport!"
                )
                print(f"Reply result: {reply_result}")
        
        # Wait to demonstrate hot-reload
        print("\nUpdate tokens via Admin API and they'll reload automatically...")
        await asyncio.sleep(10)
        
    finally:
        watcher.stop()
        await watcher_task


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║          TWITTER TRANSPORT INTERFACE                      ║
    ╚══════════════════════════════════════════════════════════╝
    
    Features:
      ✔ Abstract interface for any Twitter API
      ✔ Ryan API adapter (current)
      ✔ Official API adapter (future)
      ✔ Normalized response format
      ✔ Hot-reload support
      ✔ Seamless API switching
    
    To use in orchestrators:
      1. Import: from twitter_transport import TransportFactory
      2. Create: transport = TransportFactory.create_from_env()
      3. Use: await transport.post_tweet(soul, text)
    
    To switch APIs:
      - Set USE_OFFICIAL_API=true in .env (when ready)
      - No code changes needed in orchestrators!
    """)
    
    asyncio.run(example_usage())
