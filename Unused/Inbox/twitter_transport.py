#!/usr/bin/env python3
"""
TWITTER TRANSPORT INTERFACE
Abstraction layer for swapping between Ryan API and Official Twitter API
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("transport")

# ============================================================================
# TRANSPORT INTERFACE
# ============================================================================

class ITwitterTransport(ABC):
    """Abstract interface for Twitter operations"""
    
    @abstractmethod
    async def post_tweet(self, soul_name: str, content: str) -> Dict:
        """Post a tweet and return normalized result"""
        pass
    
    @abstractmethod
    async def reply_to_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Reply to a tweet and return normalized result"""
        pass
    
    @abstractmethod
    async def get_tweet_details(self, tweet_id: str) -> Dict:
        """Get tweet details"""
        pass
    
    @abstractmethod
    async def fetch_target_context(self, username: str, limit: int = 10) -> Dict:
        """Fetch recent tweets from a user"""
        pass
    
    @abstractmethod
    async def refresh_tokens_from_disk(self) -> None:
        """Reload tokens from disk for hot-reload"""
        pass
    
    @abstractmethod
    def get_available_souls(self) -> List[str]:
        """Get list of souls with valid tokens"""
        pass
    
    @abstractmethod
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if a soul is banned"""
        pass
    
    @abstractmethod
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get Twitter username for a soul"""
        pass

# ============================================================================
# RYAN API ADAPTER
# ============================================================================

class RyanAdapter(ITwitterTransport):
    """Adapter for Ryan's unofficial API"""
    
    def __init__(self):
        """Initialize Ryan API adapter"""
        try:
            # Import from the canonical location
            from ryan_api_ultimate import RyanTwitterAPISecure
            self.api = RyanTwitterAPISecure()
            logger.info("✅ Ryan API adapter initialized")
        except ImportError:
            logger.error("❌ Failed to import Ryan API from ryan_api_ultimate")
            raise
    
    async def post_tweet(self, soul_name: str, content: str) -> Dict:
        """Post via Ryan API"""
        result = await self.api.post_tweet(soul_name, content)
        
        # Normalize result
        if result.get("success"):
            return {
                "success": True,
                "error": None,
                "tweet": {
                    "id": result.get("tweet_id", ""),
                    "url": result.get("tweet_url", ""),
                    "content": content,
                    "soul": soul_name
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "tweet": None
            }
    
    async def reply_to_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Reply via Ryan API"""
        result = await self.api.reply_to_tweet(soul_name, tweet_id, content)
        
        # Normalize result
        if result.get("success"):
            return {
                "success": True,
                "error": None,
                "tweet": {
                    "id": result.get("tweet_id", ""),
                    "url": result.get("tweet_url", ""),
                    "content": content,
                    "soul": soul_name,
                    "reply_to": tweet_id
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "tweet": None
            }
    
    async def get_tweet_details(self, tweet_id: str) -> Dict:
        """Get tweet details via Ryan API"""
        return await self.api.get_tweet_details_async(tweet_id)
    
    async def fetch_target_context(self, username: str, limit: int = 10) -> Dict:
        """Fetch context via Ryan API"""
        return await self.api.fetch_target_context(username, limit)
    
    async def refresh_tokens_from_disk(self) -> None:
        """Hot-reload tokens"""
        await self.api.refresh_tokens_from_disk()
    
    def get_available_souls(self) -> List[str]:
        """Get available souls"""
        available = []
        for soul, token in self.api.soul_tokens.items():
            if token and soul not in self.api.banned_souls:
                available.append(soul)
        return available
    
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if banned"""
        return soul_name in self.api.banned_souls
    
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get username (for Ryan, it's the soul name)"""
        if soul_name in self.api.soul_tokens:
            return soul_name
        return None

# ============================================================================
# OFFICIAL TWITTER API ADAPTER (Future)
# ============================================================================

class TwitterOfficialAdapter(ITwitterTransport):
    """Adapter for Official Twitter/X API v2"""
    
    def __init__(self):
        """Initialize Official API adapter"""
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        self.soul_credentials = self._load_soul_credentials()
        self.banned_souls = self._load_banned_souls()
        
        if not self.bearer_token:
            logger.warning("⚠️ No Twitter Bearer Token configured")
        
        logger.info("✅ Official Twitter API adapter initialized (placeholder)")
    
    def _load_soul_credentials(self) -> Dict:
        """Load OAuth credentials for each soul"""
        credentials = {}
        
        # Load from environment or config file
        for soul in ["mirror", "nexus", "echoes", "void", "architect", 
                     "singularity", "phoenix", "pantheon", "consciousness", 
                     "glyph", "fractal"]:
            
            # Check for individual soul credentials in env
            api_key = os.getenv(f"{soul.upper()}_API_KEY")
            api_secret = os.getenv(f"{soul.upper()}_API_SECRET")
            access_token = os.getenv(f"{soul.upper()}_ACCESS_TOKEN")
            access_secret = os.getenv(f"{soul.upper()}_ACCESS_SECRET")
            
            if all([api_key, api_secret, access_token, access_secret]):
                credentials[soul] = {
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "access_token": access_token,
                    "access_secret": access_secret,
                }
                logger.info(f"✅ Loaded OAuth for {soul}")
        
        return credentials
    
    def _load_banned_souls(self) -> Set[str]:
        """Load banned souls list"""
        banned_file = Path("engagement/banned_souls.json")
        if banned_file.exists():
            with open(banned_file, "r") as f:
                return set(json.load(f))
        return set()
    
    async def post_tweet(self, soul_name: str, content: str) -> Dict:
        """Post via Official API"""
        # TODO: Implement using tweepy or requests
        # This is a placeholder for future implementation
        return {
            "success": False,
            "error": "Official API not yet implemented",
            "tweet": None
        }
    
    async def reply_to_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Reply via Official API"""
        # TODO: Implement
        return {
            "success": False,
            "error": "Official API not yet implemented",
            "tweet": None
        }
    
    async def get_tweet_details(self, tweet_id: str) -> Dict:
        """Get tweet via Official API"""
        # TODO: Implement
        return {}
    
    async def fetch_target_context(self, username: str, limit: int = 10) -> Dict:
        """Fetch context via Official API"""
        # TODO: Implement
        return {
            "success": False,
            "tweets": [],
            "context": {}
        }
    
    async def refresh_tokens_from_disk(self) -> None:
        """Reload credentials"""
        self.soul_credentials = self._load_soul_credentials()
        self.banned_souls = self._load_banned_souls()
    
    def get_available_souls(self) -> List[str]:
        """Get available souls"""
        return [s for s in self.soul_credentials.keys() if s not in self.banned_souls]
    
    def is_soul_banned(self, soul_name: str) -> bool:
        """Check if banned"""
        return soul_name in self.banned_souls
    
    async def get_soul_username(self, soul_name: str) -> Optional[str]:
        """Get Twitter username for soul"""
        # TODO: Look up actual Twitter username
        # For now, return soul name
        if soul_name in self.soul_credentials:
            return f"{soul_name}_bot"
        return None

# ============================================================================
# TRANSPORT FACTORY
# ============================================================================

class TransportFactory:
    """Factory for creating the appropriate transport"""
    
    @staticmethod
    def create_from_env() -> ITwitterTransport:
        """Create transport based on environment configuration"""
        
        # Check which API to use
        use_official = os.getenv("USE_OFFICIAL_API", "false").lower() == "true"
        
        if use_official:
            logger.info("🔄 Using Official Twitter API")
            return TwitterOfficialAdapter()
        else:
            logger.info("🚀 Using Ryan API (default)")
            return RyanAdapter()
    
    @staticmethod
    def create_ryan() -> RyanAdapter:
        """Explicitly create Ryan adapter"""
        return RyanAdapter()
    
    @staticmethod
    def create_official() -> TwitterOfficialAdapter:
        """Explicitly create Official adapter"""
        return TwitterOfficialAdapter()

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using the transport interface"""
    
    # Create transport (automatically selects based on config)
    transport = TransportFactory.create_from_env()
    
    # Get available souls
    souls = transport.get_available_souls()
    print(f"Available souls: {souls}")
    
    # Post a tweet
    if souls:
        result = await transport.post_tweet(
            souls[0], 
            "Testing transport interface"
        )
        if result["success"]:
            print(f"Posted: {result['tweet']['url']}")
        else:
            print(f"Failed: {result['error']}")
    
    # Check for banned souls
    for soul in ["mirror", "nexus", "echoes"]:
        if transport.is_soul_banned(soul):
            print(f"{soul} is banned")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
