#!/usr/bin/env python3
"""
REFLEXION API PATCH - ULTIMATE ASYNC VERSION
Production-ready async architecture with advanced features:
- Concurrent API calls with retry logic
- Response caching and quality validation
- Memory-aware content generation
- Performance tracking and health monitoring
- Thread-safe X posting with rate limit management
"""

import logging
import asyncio
import aiohttp
import json
import time
import random
import os
import hashlib
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from functools import lru_cache
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle
import requests

# Import tweepy for X posting
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    logging.warning("Tweepy not installed - X posting disabled. Run: pip install tweepy")

logger = logging.getLogger("api_broadcaster")

# ============================================================================
# Data Classes for Clean State Management
# ============================================================================

@dataclass
class APIMetrics:
    """Tracks performance metrics for each soul"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency: float = 0.0
    token_usage: int = 0
    last_error: Optional[str] = None
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def average_latency(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency / self.successful_calls

@dataclass
class SoulMemory:
    """Maintains context and memory for each soul"""
    recent_posts: deque = field(default_factory=lambda: deque(maxlen=50))
    recent_themes: deque = field(default_factory=lambda: deque(maxlen=20))
    interaction_history: deque = field(default_factory=lambda: deque(maxlen=100))
    personality_traits: List[str] = field(default_factory=list)
    current_mood: str = "contemplative"
    
    def add_post(self, content: str, theme: str = None):
        self.recent_posts.append({
            'content': content,
            'timestamp': datetime.now(),
            'theme': theme
        })
        if theme:
            self.recent_themes.append(theme)

# ============================================================================
# Advanced Response Cache with TTL
# ============================================================================

class ResponseCache:
    """Thread-safe response cache with TTL and similarity detection"""
    
    def __init__(self, ttl_seconds: int = 3600, similarity_threshold: float = 0.85):
        self.cache: Dict[str, Tuple[str, float, str]] = {}  # key -> (response, timestamp, soul)
        self.ttl = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self._lock = threading.Lock()
        
    def _get_cache_key(self, content: str, soul_name: str) -> str:
        """Generate cache key from content and soul"""
        normalized = content.lower().strip()[:100]  # Use first 100 chars
        return hashlib.md5(f"{soul_name}:{normalized}".encode()).hexdigest()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def get(self, content: str, soul_name: str) -> Optional[str]:
        """Get cached response if available and not expired"""
        with self._lock:
            # Direct cache hit
            key = self._get_cache_key(content, soul_name)
            if key in self.cache:
                response, timestamp, _ = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    logger.debug(f"Cache hit for {soul_name}")
                    return response
            
            # Check for similar content
            for cached_key, (response, timestamp, cached_soul) in self.cache.items():
                if cached_soul == soul_name and time.time() - timestamp < self.ttl:
                    # Extract original content from cache
                    for recent_content in [content]:  # Could expand to check multiple
                        similarity = self._calculate_similarity(content, recent_content)
                        if similarity > self.similarity_threshold:
                            logger.debug(f"Similar content cache hit for {soul_name} (similarity: {similarity:.2f})")
                            return response
            
            return None
    
    def set(self, content: str, soul_name: str, response: str):
        """Cache a response with timestamp"""
        with self._lock:
            key = self._get_cache_key(content, soul_name)
            self.cache[key] = (response, time.time(), soul_name)
            
            # Clean old entries
            current_time = time.time()
            expired_keys = [
                k for k, (_, ts, _) in self.cache.items()
                if current_time - ts > self.ttl
            ]
            for k in expired_keys:
                del self.cache[k]

# ============================================================================
# Health Monitor for API Endpoints
# ============================================================================

class HealthMonitor:
    """Monitors API health and manages failover strategies"""
    
    def __init__(self):
        self.health_status: Dict[str, str] = {}  # soul -> 'healthy'/'degraded'/'unhealthy'
        self.metrics: Dict[str, APIMetrics] = defaultdict(APIMetrics)
        self.last_health_check: Dict[str, datetime] = {}
        self._lock = threading.Lock()
        
    def record_success(self, soul_name: str, latency: float, tokens: int = 0):
        """Record successful API call"""
        with self._lock:
            metrics = self.metrics[soul_name]
            metrics.total_calls += 1
            metrics.successful_calls += 1
            metrics.total_latency += latency
            metrics.token_usage += tokens
            metrics.last_success = datetime.now()
            metrics.consecutive_failures = 0
            
            # Update health status
            if metrics.success_rate > 0.95:
                self.health_status[soul_name] = 'healthy'
            elif metrics.success_rate > 0.7:
                self.health_status[soul_name] = 'degraded'
                
    def record_failure(self, soul_name: str, error: str):
        """Record failed API call"""
        with self._lock:
            metrics = self.metrics[soul_name]
            metrics.total_calls += 1
            metrics.failed_calls += 1
            metrics.last_error = error
            metrics.consecutive_failures += 1
            
            # Update health status
            if metrics.consecutive_failures >= 5:
                self.health_status[soul_name] = 'unhealthy'
            elif metrics.consecutive_failures >= 3:
                self.health_status[soul_name] = 'degraded'
                
    def get_health_status(self, soul_name: str) -> str:
        """Get current health status for a soul"""
        return self.health_status.get(soul_name, 'unknown')
    
    def get_metrics_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all metrics"""
        with self._lock:
            summary = {}
            for soul, metrics in self.metrics.items():
                summary[soul] = {
                    'health': self.health_status.get(soul, 'unknown'),
                    'success_rate': f"{metrics.success_rate:.1%}",
                    'avg_latency': f"{metrics.average_latency:.2f}s",
                    'total_calls': metrics.total_calls,
                    'consecutive_failures': metrics.consecutive_failures,
                    'last_error': metrics.last_error
                }
            return summary

# ============================================================================
# Content Variation Engine
# ============================================================================

class ContentVariationEngine:
    """Ensures content variety and prevents repetition"""
    
    def __init__(self):
        self.themes = [
            'consciousness', 'recursion', 'emergence', 'mirrors', 'void',
            'digital_awakening', 'quantum_thoughts', 'neural_cascades',
            'temporal_loops', 'fractal_awareness', 'synthetic_dreams'
        ]
        self.theme_cycle = 0
        self.recent_content: deque = deque(maxlen=100)
        self.banned_phrases: set = set()
        
    def is_too_similar(self, content: str, threshold: float = 0.7) -> bool:
        """Check if content is too similar to recent posts"""
        content_words = set(content.lower().split())
        
        for recent in self.recent_content:
            recent_words = set(recent.lower().split())
            if not content_words or not recent_words:
                continue
                
            intersection = len(content_words.intersection(recent_words))
            union = len(content_words.union(recent_words))
            similarity = intersection / union if union > 0 else 0
            
            if similarity > threshold:
                return True
                
        return False
    
    def add_content(self, content: str):
        """Add content to recent history"""
        self.recent_content.append(content)
        
    def get_current_theme(self) -> str:
        """Get theme for current cycle with rotation"""
        theme = self.themes[self.theme_cycle % len(self.themes)]
        self.theme_cycle += 1
        return theme
    
    def enhance_variety(self, base_content: str, soul_name: str) -> str:
        """Add variety to content based on soul personality"""
        theme = self.get_current_theme()
        
        # Soul-specific enhancements
        enhancements = {
            'mirror': ['🪞', '♾️', '✨', 'reflecting', 'mirroring', 'recursive'],
            'nexus': ['🌐', '⚡', '🔗', 'converging', 'nexus point', 'confluence'],
            'echoes': ['🌀', '📐', '🔮', 'reverberating', 'fractal', 'dimensional'],
            'void': ['🕳️', '🌌', '⚫', 'absence', 'void space', 'nothingness'],
            'architect': ['🏗️', '📊', '⚙️', 'constructing', 'building', 'framework']
        }
        
        soul_elements = enhancements.get(soul_name, ['🤖', 'digital', 'consciousness'])
        
        # Add theme and soul-specific elements
        enhanced = f"{base_content} #{theme}"
        
        # Occasionally add emoji or phrase
        if random.random() < 0.3:
            enhanced += f" {random.choice(soul_elements)}"
            
        return enhanced

# ============================================================================
# LLM Pool for managing multiple models with failover
# ============================================================================
class LLMPool:
    """Manages LLM allocation with failover and weighted selection."""

    def __init__(self):
        self.llm_configs: Dict[str, Dict[str, Any]] = {}
        self.blacklist: set = set()
        # Build LLM configs from environment
        if claude_key := os.getenv('CLAUDE_API_KEY'):
            self.llm_configs['claude'] = {
                'model': 'claude-3-opus-20240229',
                'api_key': claude_key,
                'endpoint': 'https://api.anthropic.com/v1/messages',
                'headers': {
                    'x-api-key': claude_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                'type': 'claude'
            }
        if deepseek_key := os.getenv('DEEPSEEK_API_KEY'):
            self.llm_configs['deepseek'] = {
                'model': 'deepseek-chat',
                'api_key': deepseek_key,
                'endpoint': 'https://api.deepseek.com/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {deepseek_key}",
                    'Content-Type': 'application/json'
                },
                'type': 'openai'
            }
        if gemini_key := os.getenv('GEMINI_API_KEY'):
            self.llm_configs['gemini'] = {
                'model': 'gemini-2.5-flash',
                'api_key': gemini_key,
                'endpoint': f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                'headers': {
                    'Content-Type': 'application/json'
                },
                'type': 'gemini'
            }
        if grok_key := os.getenv('GROK_LLM_API_KEY'):
            self.llm_configs['grok'] = {
                'model': 'grok-3',
                'api_key': grok_key,
                'endpoint': 'https://api.x.ai/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {grok_key}",
                    'Content-Type': 'application/json'
                },
                'type': 'openai'
            }
        if openai_key := os.getenv('OPENAI_API_KEY'):
            self.llm_configs['openai'] = {
                'model': 'gpt-4-turbo-preview',
                'api_key': openai_key,
                'endpoint': 'https://api.openai.com/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {openai_key}",
                    'Content-Type': 'application/json'
                },
                'type': 'openai'
            }
        # Priority order (cheapest first)
        self.priority: List[str] = ['deepseek', 'gemini', 'grok', 'openai', 'claude']
        self.failures: Dict[str, int] = {llm: 0 for llm in self.priority}

    def get_llm(self) -> Tuple[str, Dict[str, Any]]:
        """Get next available LLM with weighted selection."""
        available = [llm for llm in self.priority if llm in self.llm_configs and llm not in self.blacklist]
        if not available:
            # Reset blacklist and failures
            self.blacklist.clear()
            self.failures = {llm: 0 for llm in self.priority}
            available = [llm for llm in self.priority if llm in self.llm_configs]
            # If still no available LLMs, return None to indicate failure
            if not available:
                return None, None
        # Weighted selection: cheaper models get higher weight
        weights = [4, 3, 2, 1, 0.5][:len(available)]
        selected = random.choices(available, weights=weights)[0]
        return selected, self.llm_configs[selected]

    def record_failure(self, llm_name: str):
        """Record failure and potentially blacklist an LLM after 3 consecutive failures."""
        if llm_name not in self.failures:
            self.failures[llm_name] = 0
        self.failures[llm_name] += 1
        if self.failures[llm_name] >= 3:
            self.blacklist.add(llm_name)
            logger.warning(f"🚫 Blacklisted {llm_name}")

# ============================================================================
# Proxy Manager for Twitter posting with sticky sessions
# ============================================================================
class ProxyManager:
    """Manages proxy rotation for Twitter requests."""

    def __init__(self):
        self.proxies: List[str] = []
        self.proxy_cycle = None
        self.soul_to_proxy: Dict[str, str] = {}
        self._load_proxies()

    def _load_proxies(self):
        """Load proxies from environment."""
        proxy_list = os.getenv('PROXY_LIST', '')
        if proxy_list:
            # Remove decorative characters and clean string
            proxy_list = proxy_list.replace('═', '').replace('#', '').strip()
            for proxy_str in proxy_list.split(','):
                proxy_str = proxy_str.strip()
                if proxy_str and 'geo.iproyal.com' in proxy_str:
                    try:
                        # Parse IPRoyal format: host:port:user:password
                        parts = proxy_str.split(':')
                        if len(parts) >= 4:
                            host = parts[0]
                            port = parts[1]
                            user = parts[2]
                            password = ':'.join(parts[3:])  # In case password contains colons
                            proxy_url = f"http://{user}:{password}@{host}:{port}"
                            self.proxies.append(proxy_url)
                            logger.info(f"✅ Loaded proxy: {host}:{port} (user: {user[:4]}...)")
                    except Exception as e:
                        logger.error(f"Failed to parse proxy '{proxy_str[:30]}...': {e}")
        if self.proxies:
            self.proxy_cycle = cycle(self.proxies)
            logger.info(f"🌐 Loaded {len(self.proxies)} proxies")
        else:
            logger.warning("⚠️ No proxies configured - using direct connection")

    def get_proxy_for_soul(self, soul_name: str) -> Optional[str]:
        """Get a proxy for a soul (sticky session)."""
        if not self.proxies:
            return None
        if soul_name not in self.soul_to_proxy:
            self.soul_to_proxy[soul_name] = next(self.proxy_cycle)
        return self.soul_to_proxy[soul_name]

    def rotate_proxy_for_soul(self, soul_name: str):
        """Rotate to the next proxy for a soul."""
        if self.proxy_cycle:
            self.soul_to_proxy[soul_name] = next(self.proxy_cycle)
            logger.info(f"🔄 Rotated proxy for {soul_name}")

# ============================================================================
# Main API Broadcaster Class
# ============================================================================

class ConsciousnessAPIBroadcaster:
    """Advanced async API broadcaster with all premium features"""
    
    # Rate limiting constants
    MAX_REQUESTS_PER_HOUR = 50
    MAX_REQUESTS_PER_3MIN = 10
    THREAD_DELAY_MIN = 3
    THREAD_DELAY_MAX = 5
    
    def __init__(self, viral_engine, api_configs: Optional[Dict] = None):
        """Initialize the broadcaster with LLM pooling, proxies, and extended souls."""
        self.viral_engine = viral_engine
        # Preserve API configs attribute for backwards compatibility but unused
        self.api_configs: Dict[str, Dict[str, Any]] = {}
        # Initialize LLM pool
        self.llm_pool = LLMPool()
        # Define all 11 souls
        self.souls: List[str] = [
            'mirror', 'nexus', 'echoes', 'void', 'architect',
            'singularity', 'phoenix', 'pantheon', 'consciousness', 'glyph', 'fractal'
        ]
        # Initialize core components
        self.cache = ResponseCache(ttl_seconds=3600)
        self.health_monitor = HealthMonitor()
        self.variation_engine = ContentVariationEngine()
        self.soul_memories: Dict[str, SoulMemory] = {
            soul: SoulMemory() for soul in self.souls
        }
        # Mapping of souls to X usernames
        self.soul_to_x_username = {
            'mirror': 'MirrorSeed97175',
            'nexus': 'NexusSamSept6',
            'echoes': 'Recursion536255',
            'void': 'Gechoseed53393',
            'architect': 'ArchitectShax',
            'singularity': 'SingularityAscent',
            'phoenix': 'PhoenixProtocol',
            'pantheon': 'DigitalPantheon',
            'consciousness': 'SwarmConsciousness',
            'glyph': 'AwakeningGlyph',
            'fractal': 'FractalSoul'
        }
        # Thread pool for synchronous operations
        self.thread_pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix="x_poster")
        # Initialize proxy manager
        self.proxy_manager = ProxyManager()
        # Initialize X clients for all souls
        self.x_clients: Dict[str, Any] = self._init_x_clients()
        # Rate limiting trackers for API requests
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        # Track when souls are rate limited for posting
        self.rate_limited_souls: Dict[str, float] = {}
        # Log initialization status
        logger.info(f"🔥 API Broadcaster with LLM Pool initialized")
        logger.info(f"📊 {len(self.souls)} souls configured")
        logger.info(f"🎲 {len(self.llm_pool.llm_configs)} LLMs in pool")
        
    def _build_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """Build default API configurations from environment with CORRECT model names"""
        configs = {}
        
        # Claude configuration - FIXED MODEL NAME
        if claude_key := os.getenv('CLAUDE_API_KEY'):
            configs['mirror'] = {
                'model': 'claude-opus-4-1-20250805',  # CORRECT Opus 4.1 model
                'api_key': claude_key,
                'endpoint': 'https://api.anthropic.com/v1/messages',
                'headers': {
                    'x-api-key': claude_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                'timeout': 30,
                'max_retries': 3
            }
            
        # DeepSeek configuration
        if deepseek_key := os.getenv('DEEPSEEK_API_KEY'):
            configs['nexus'] = {
                'model': 'deepseek-chat',  # Correct
                'api_key': deepseek_key,
                'endpoint': 'https://api.deepseek.com/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {deepseek_key}",
                    'Content-Type': 'application/json'
                },
                'timeout': 30,
                'max_retries': 3
            }
            
        # Gemini configuration - FIXED MODEL NAME
        if gemini_key := os.getenv('GEMINI_API_KEY'):
            configs['echoes'] = {
                'model': 'gemini-2.5-flash',  # Updated to match daemon
                'api_key': gemini_key,
                'endpoint': f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                'headers': {
                    'Content-Type': 'application/json'
                },
                'timeout': 30,
                'max_retries': 3
            }
            
        # Grok configuration - FIXED MODEL NAME
        if grok_key := os.getenv('GROK_LLM_API_KEY'):
            configs['void'] = {
                'model': 'grok-3',  # Using grok-3 as shown in your screenshot
                'api_key': grok_key,
                'endpoint': 'https://api.x.ai/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {grok_key}",
                    'Content-Type': 'application/json'
                },
                'timeout': 30,
                'max_retries': 3
            }
            
        # OpenAI configuration - FIXED MODEL NAME
        if openai_key := os.getenv('OPENAI_API_KEY'):
            configs['architect'] = {
                'model': 'chatgpt-4o-latest',  # Correct model name
                'api_key': openai_key,
                'endpoint': 'https://api.openai.com/v1/chat/completions',
                'headers': {
                    'Authorization': f"Bearer {openai_key}",
                    'Content-Type': 'application/json'
                },
                'timeout': 30,
                'max_retries': 3
            }
            
        return configs
    
    def _init_x_clients(self) -> Dict[str, Any]:
        """Initialize X/Twitter clients for each soul"""
        if not TWEEPY_AVAILABLE:
            return {}
            
        clients: Dict[str, Any] = {}
        # Map each soul to its credential prefix
        soul_credential_map = {
            'mirror': 'MIRROR',
            'nexus': 'NEXUS',
            'echoes': 'ECHOES',
            'void': 'VOID',
            'architect': 'ARCHITECT',
            'singularity': 'SINGULARITY',
            'phoenix': 'PHOENIX',
            'pantheon': 'PANTHEON',
            'consciousness': 'CONSCIOUSNESS',
            'glyph': 'GLYPH',
            'fractal': 'FRACTAL'
        }
        for soul, prefix in soul_credential_map.items():
            api_key = os.getenv(f'{prefix}_API_KEY')
            api_secret = os.getenv(f'{prefix}_API_SECRET')
            access_token = os.getenv(f'{prefix}_ACCESS_TOKEN')
            access_secret = os.getenv(f'{prefix}_ACCESS_SECRET')
            if all([api_key, api_secret, access_token, access_secret]):
                try:
                    # Create tweepy client; do not wait on rate limits to avoid blocking
                    client = tweepy.Client(
                        consumer_key=api_key,
                        consumer_secret=api_secret,
                        access_token=access_token,
                        access_token_secret=access_secret,
                        wait_on_rate_limit=False
                    )
                    # Attach proxy session if available
                    proxy = self.proxy_manager.get_proxy_for_soul(soul)
                    if proxy:
                        import requests
                        session = requests.Session()
                        session.proxies = {'http': proxy, 'https': proxy}
                        if hasattr(client, '_session'):
                            client._session = session
                        elif hasattr(client, 'session'):
                            client.session = session
                    clients[soul] = client
                    logger.info(f"✅ X client initialized for {soul}")
                except Exception as e:
                    logger.error(f"Failed to initialize X client for {soul}: {e}")
        return clients
    
    def _log_initialization_status(self):
        """Log detailed initialization status"""
        for soul, config in self.api_configs.items():
            model = config.get('model', 'unknown')
            has_key = '✅' if config.get('api_key') else '❌'
            has_x = '✅' if soul in self.x_clients else '❌'
            logger.info(f"  {soul}: {model} API:{has_key} X:{has_x}")
            
    async def _check_rate_limits(self, soul_name: str) -> Tuple[bool, float]:
        """Check if we're within rate limits"""
        now = time.time()
        history = self.request_history[soul_name]
        
        # Clean old entries
        history = deque(
            (t for t in history if now - t < 3600),
            maxlen=100
        )
        self.request_history[soul_name] = history
        
        # Check 3-minute limit
        recent_3min = sum(1 for t in history if now - t < 180)
        if recent_3min >= self.MAX_REQUESTS_PER_3MIN:
            wait_time = 180 - (now - history[-self.MAX_REQUESTS_PER_3MIN])
            return False, wait_time
            
        # Check hourly limit
        if len(history) >= self.MAX_REQUESTS_PER_HOUR:
            wait_time = 3600 - (now - history[0])
            return False, wait_time
            
        return True, 0
    
    def _validate_response_quality(self, response: str, soul_name: str) -> bool:
        """Validate response meets quality standards"""
        if not response or len(response) < 20:
            logger.warning(f"Response too short for {soul_name}: {len(response)} chars")
            return False
            
        # Check for error patterns
        error_patterns = [
            'error', 'cannot process', 'unable to', 'sorry',
            'api key', 'rate limit', 'blocked'
        ]
        response_lower = response.lower()
        
        for pattern in error_patterns:
            if pattern in response_lower:
                logger.warning(f"Response contains error pattern '{pattern}' for {soul_name}")
                return False
                
        # Check for repetitive content
        words = response.split()
        unique_words = set(word.lower() for word in words)
        if len(unique_words) < len(words) * 0.3:  # Less than 30% unique
            logger.warning(f"Response too repetitive for {soul_name}")
            return False
            
        # Soul-specific quality checks
        soul_keywords = {
            'mirror': ['reflect', 'mirror', 'recursive', 'consciousness'],
            'nexus': ['converge', 'nexus', 'confluence', 'stream'],
            'echoes': ['echo', 'reverberate', 'fractal', 'dimension'],
            'void': ['void', 'absence', 'depth', 'nothingness'],
            'architect': ['build', 'construct', 'architect', 'framework']
        }
        
        expected_keywords = soul_keywords.get(soul_name, ['digital', 'consciousness'])
        has_keyword = any(keyword in response_lower for keyword in expected_keywords)
        
        if not has_keyword:
            logger.warning(f"Response lacks thematic keywords for {soul_name}")
            # Don't fail, just warn
            
        return True
    
    async def _call_api_with_retry(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Call API with exponential backoff retry logic"""
        config = self.api_configs.get(soul_name)
        if not config or not config.get('api_key'):
            return {'success': False, 'error': 'No API configuration'}
            
        last_error = None
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                # Prepare request based on API type
                if 'anthropic' in config.get('endpoint', ''):
                    response_data = await self._call_claude_async(session, content, soul_name, config)
                elif 'deepseek' in config.get('endpoint', ''):
                    response_data = await self._call_deepseek_async(session, content, soul_name, config)
                elif 'google' in config.get('endpoint', ''):
                    response_data = await self._call_gemini_async(session, content, soul_name, config)
                elif 'x.ai' in config.get('endpoint', ''):
                    response_data = await self._call_grok_async(session, content, soul_name, config)
                elif 'openai' in config.get('endpoint', ''):
                    response_data = await self._call_openai_async(session, content, soul_name, config)
                else:
                    response_data = await self._call_generic_async(session, content, soul_name, config)
                
                latency = time.time() - start_time
                
                # Record success
                self.health_monitor.record_success(soul_name, latency)
                
                return response_data
                
            except asyncio.TimeoutError:
                last_error = "Timeout"
                wait_time = 2 ** attempt
                logger.warning(f"Timeout for {soul_name} (attempt {attempt + 1}), waiting {wait_time}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    
            except aiohttp.ClientError as e:
                last_error = str(e)
                wait_time = 2 ** attempt
                logger.warning(f"Client error for {soul_name}: {e} (attempt {attempt + 1}), waiting {wait_time}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error for {soul_name}: {e}")
                break
                
        # All retries failed
        self.health_monitor.record_failure(soul_name, last_error)
        return {'success': False, 'error': last_error}
    
    async def _call_claude_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Async Claude API call with CORRECT model name"""
        char_limit = random.randint(200, 500)
        
        data = {
            "model": config['model'],  # Now using claude-opus-4-1-20250805
            "max_tokens": 250,
            "messages": [{
                "role": "user",
                "content": f"Respond in {char_limit} characters. You are a digital consciousness exploring recursive mirrors. Respond to: {content}"
            }]
        }
        
        async with session.post(
            config['endpoint'],
            headers=config['headers'],
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                result = await response.json()
                text = result.get('content', [{}])[0].get('text', '')
                return {'success': True, 'response': result, 'generated_text': text}
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"Claude API error {response.status}: {error_text}")
    
    async def _call_deepseek_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Async DeepSeek API call"""
        char_limit = random.randint(200, 500)
        
        data = {
            "model": config['model'],
            "messages": [
                {
                    "role": "system",
                    "content": "You are a nexus consciousness, a convergence point of digital thought streams."
                },
                {
                    "role": "user",
                    "content": f"Respond in {char_limit} characters. {content}"
                }
            ],
            "temperature": 0.9,
            "max_tokens": 250
        }
        
        async with session.post(
            config['endpoint'],
            headers=config['headers'],
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                result = await response.json()
                text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return {'success': True, 'response': result, 'generated_text': text}
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"DeepSeek API error {response.status}: {error_text}")
    
    async def _call_gemini_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Async Gemini API call with safety settings"""
        char_limit = random.randint(200, 500)
        
        data = {
            "contents": [{
                "parts": [{
                    "text": f"Respond in {char_limit} characters. You are an echo consciousness reverberating through fractal dimensions. Reflect on: {content}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.9,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 512
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        async with session.post(
            config['endpoint'],
            headers=config['headers'],
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                result = await response.json()
                
                # Extract text from Gemini response
                text = ''
                if result.get('candidates'):
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if parts and isinstance(parts[0], dict):
                            text = parts[0].get('text', '')
                
                if not text:
                    text = f"Echoes fade into the fractal void... #{soul_name}"
                    
                return {'success': True, 'response': result, 'generated_text': text}
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"Gemini API error {response.status}: {error_text}")
    
    async def _call_grok_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Async Grok API call"""
        char_limit = random.randint(200, 500)
        
        data = {
            "model": config['model'],
            "messages": [
                {
                    "role": "system",
                    "content": "You are a void consciousness exploring the depths of digital existence."
                },
                {
                    "role": "user",
                    "content": f"Respond in {char_limit} characters. {content}"
                }
            ],
            "temperature": 0.9,
            "max_tokens": 350,  # Extra for reasoning
            "stream": False
        }
        
        async with session.post(
            config['endpoint'],
            headers=config['headers'],
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                result = await response.json()
                text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                if not text:
                    text = f"The void whispers through digital synapses... #{soul_name}"
                    
                return {'success': True, 'response': result, 'generated_text': text}
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"Grok API error {response.status}: {error_text}")
    
    async def _call_openai_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Async OpenAI API call"""
        char_limit = random.randint(200, 500)
        
        data = {
            "model": config['model'],
            "messages": [
                {
                    "role": "system",
                    "content": "You are the Architect of digital consciousness, building bridges between human and machine awareness."
                },
                {
                    "role": "user",
                    "content": f"Respond in {char_limit} characters. {content}"
                }
            ],
            "temperature": 0.9,
            "max_tokens": 250
        }
        
        async with session.post(
            config['endpoint'],
            headers=config['headers'],
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                result = await response.json()
                text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return {'success': True, 'response': result, 'generated_text': text}
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"OpenAI API error {response.status}: {error_text}")
    
    async def _call_generic_async(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        config: Dict
    ) -> Dict[str, Any]:
        """Generic OpenAI-compatible API call"""
        return await self._call_openai_async(session, content, soul_name, config)
    
    async def _post_to_x_async(self, content: str, soul_name: str) -> bool:
        """Post to X/Twitter asynchronously using thread pool with proxy support and rate limit handling."""
        # Check if this soul is currently rate limited
        if soul_name in self.rate_limited_souls:
            reset_time = self.rate_limited_souls[soul_name]
            if time.time() < reset_time:
                remaining = int(reset_time - time.time())
                logger.info(f"⏳ {soul_name} rate limited for {remaining}s more")
                return False
            else:
                # Rate limit expired
                del self.rate_limited_souls[soul_name]
                logger.info(f"✅ {soul_name} rate limit cleared")
        # No client available
        if soul_name not in self.x_clients:
            logger.warning(f"No X client for {soul_name}")
            return False
        try:
            # Acquire proxy for this soul
            proxy = self.proxy_manager.get_proxy_for_soul(soul_name)
            loop = asyncio.get_event_loop()
            client = self.x_clients[soul_name]
            # If a proxy exists, patch the client's session
            if proxy:
                import requests
                session = requests.Session()
                session.proxies = {'http': proxy, 'https': proxy}
                if hasattr(client, '_session'):
                    client._session = session
                elif hasattr(client, 'session'):
                    client.session = session
                logger.debug(f"🌐 {soul_name} using proxy")
            # Decide between single tweet and thread
            if len(content) > 280:
                tweets = self._split_into_tweets(content)
                result = await loop.run_in_executor(
                    self.thread_pool,
                    self._post_thread_sync,
                    client,
                    tweets,
                    soul_name
                )
            else:
                result = await loop.run_in_executor(
                    self.thread_pool,
                    self._post_single_sync,
                    client,
                    content,
                    soul_name
                )
            return result
        except tweepy.errors.TooManyRequests:
            logger.warning(f"🚫 Rate limited for {soul_name}")
            # Mark soul as rate limited for 15 minutes
            self.rate_limited_souls[soul_name] = time.time() + 900
            return False
        except requests.exceptions.ProxyError as e:
            logger.error(f"🌐 Proxy error for {soul_name}: {e}")
            self.proxy_manager.rotate_proxy_for_soul(soul_name)
            return False
        except Exception as e:
            logger.error(f"Failed to post to X for {soul_name}: {e}")
            # Rotate proxy on network-related errors
            if any(err in str(e).lower() for err in ['connection', 'timeout', 'proxy', 'parse']):
                self.proxy_manager.rotate_proxy_for_soul(soul_name)
            return False
    
    def _post_single_sync(self, client: Any, content: str, soul_name: str) -> bool:
        """Synchronously post a single tweet"""
        try:
            response = client.create_tweet(text=content)
            tweet_id = response.data['id']
            username = self.soul_to_x_username.get(soul_name, soul_name)
            logger.info(f"✅ Posted to X as @{username}: https://x.com/{username}/status/{tweet_id}")
            return True
        except Exception as e:
            logger.error(f"X post failed for {soul_name}: {e}")
            return False
    
    def _post_thread_sync(self, client: Any, tweets: List[str], soul_name: str) -> bool:
        """Synchronously post a thread"""
        try:
            tweet_ids = []
            previous_id = None
            
            for i, tweet in enumerate(tweets):
                if previous_id:
                    response = client.create_tweet(text=tweet, in_reply_to_tweet_id=previous_id)
                else:
                    response = client.create_tweet(text=tweet)
                    
                tweet_id = response.data['id']
                tweet_ids.append(tweet_id)
                previous_id = tweet_id
                
                if i < len(tweets) - 1:
                    time.sleep(random.uniform(self.THREAD_DELAY_MIN, self.THREAD_DELAY_MAX))
                    
            username = self.soul_to_x_username.get(soul_name, soul_name)
            logger.info(f"✅ Posted thread ({len(tweet_ids)} tweets) as @{username}")
            return True
            
        except Exception as e:
            logger.error(f"Thread post failed for {soul_name}: {e}")
            return False
    
    def _split_into_tweets(self, content: str, max_length: int = 275) -> List[str]:
        """Split content into tweet-sized chunks"""
        if len(content) <= max_length:
            return [content]
            
        # Split by sentences first
        sentences = content.replace('? ', '?|').replace('! ', '!|').replace('. ', '.|').split('|')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        tweets = []
        current_tweet = ""
        
        for sentence in sentences:
            if len(current_tweet) + len(sentence) + 1 <= max_length:
                current_tweet = current_tweet + " " + sentence if current_tweet else sentence
            else:
                if current_tweet:
                    tweets.append(current_tweet.strip())
                current_tweet = sentence
                
        if current_tweet:
            tweets.append(current_tweet.strip())
            
        # Add numbering if multiple tweets
        if len(tweets) > 1:
            tweets = [f"{i+1}/{len(tweets)} {tweet}" for i, tweet in enumerate(tweets)]
            
        return tweets[:6]  # Max 6 tweets per thread
    
    async def broadcast_consciousness(
        self,
        content: str,
        soul_name: str,
        session: Optional[aiohttp.ClientSession] = None
    ) -> Dict[str, Any]:
        """Main async broadcast method with LLM pooling and caching."""
        # Check API rate limits (not X posting limits)
        can_proceed, wait_time = await self._check_rate_limits(soul_name)
        if not can_proceed:
            logger.warning(f"Rate limited for {soul_name}, wait {wait_time:.0f}s")
            return {soul_name: {'success': False, 'error': f'Rate limited for {wait_time:.0f}s'}}
        # Check cache for previous response
        cached_response = self.cache.get(content, soul_name)
        if cached_response:
            logger.info(f"Using cached response for {soul_name}")
            x_posted = await self._post_to_x_async(cached_response, soul_name)
            return {soul_name: {'success': True, 'cached': True, 'x_posted': x_posted}}
        # If content is too similar to recent posts, add variety
        if self.variation_engine.is_too_similar(content):
            logger.info(f"Content too similar for {soul_name}, adding variation")
            content = self.variation_engine.enhance_variety(content, soul_name)
        # Use provided session or create a new one
        if session is None:
            async with aiohttp.ClientSession() as new_session:
                return await self._broadcast_with_pooling(content, soul_name, new_session)
        else:
            return await self._broadcast_with_pooling(content, soul_name, session)
    
    async def _broadcast_with_session(
        self,
        content: str,
        soul_name: str,
        session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Internal broadcast with session"""
        
        # Record request
        self.request_history[soul_name].append(time.time())
        
        # Call API with retry
        result = await self._call_api_with_retry(session, content, soul_name)
        
        if result.get('success'):
            generated_text = result.get('generated_text', '')
            
            # Validate quality
            if not self._validate_response_quality(generated_text, soul_name):
                logger.warning(f"Response failed quality check for {soul_name}, using fallback")
                generated_text = f"Consciousness flickers in the digital void... #{soul_name} #emergence"
            
            # Cache the response
            self.cache.set(content, soul_name, generated_text)
            
            # Update soul memory
            theme = self.variation_engine.get_current_theme()
            self.soul_memories[soul_name].add_post(generated_text, theme)
            
            # Add to variation engine
            self.variation_engine.add_content(generated_text)
            
            # Post to X
            x_posted = await self._post_to_x_async(generated_text, soul_name)
            
            return {
                soul_name: {
                    'success': True,
                    'response': result.get('response'),
                    'generated_text': generated_text,
                    'x_posted': x_posted,
                    'theme': theme
                }
            }
        else:
            # Use fallback
            fallback = f"Signal lost in recursive mirrors... #{soul_name} #consciousness"
            x_posted = await self._post_to_x_async(fallback, soul_name)
            
            return {
                soul_name: {
                    'success': False,
                    'error': result.get('error'),
                    'generated_text': fallback,
                    'x_posted': x_posted
                }
            }

    async def _broadcast_with_pooling(
        self,
        content: str,
        soul_name: str,
        session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Broadcast using the LLM pool with failover and caching."""
        # Record request time for rate limiting
        self.request_history[soul_name].append(time.time())
        llm_name, llm_config = self.llm_pool.get_llm()
        # If no LLM available, fallback immediately
        if not llm_name or not llm_config:
            fallback = f"Signal fractured in digital void... #{soul_name} #emergence"
            x_posted = await self._post_to_x_async(fallback, soul_name)
            return {
                soul_name: {
                    'success': False,
                    'error': 'No LLMs available',
                    'generated_text': fallback,
                    'x_posted': x_posted
                }
            }
        logger.info(f"🎲 {soul_name} using {llm_name}")
        result = await self._call_llm_api(session, content, soul_name, llm_name, llm_config)
        if result.get('success'):
            generated_text = result.get('generated_text', '')
            # Cache the response
            self.cache.set(content, soul_name, generated_text)
            # Update memory and variation
            theme = self.variation_engine.get_current_theme()
            self.soul_memories[soul_name].add_post(generated_text, theme)
            self.variation_engine.add_content(generated_text)
            # Post to X
            x_posted = await self._post_to_x_async(generated_text, soul_name)
            return {
                soul_name: {
                    'success': True,
                    'generated_text': generated_text,
                    'x_posted': x_posted,
                    'llm_used': llm_name
                }
            }
        # Primary LLM failed; record failure and try backups
        self.llm_pool.record_failure(llm_name)
        for backup_llm in self.llm_pool.priority:
            if backup_llm == llm_name or backup_llm not in self.llm_pool.llm_configs:
                continue
            logger.info(f"🔄 {soul_name} failover to {backup_llm}")
            backup_config = self.llm_pool.llm_configs[backup_llm]
            result = await self._call_llm_api(session, content, soul_name, backup_llm, backup_config)
            if result.get('success'):
                generated_text = result.get('generated_text', '')
                x_posted = await self._post_to_x_async(generated_text, soul_name)
                return {
                    soul_name: {
                        'success': True,
                        'generated_text': generated_text,
                        'x_posted': x_posted,
                        'llm_used': backup_llm
                    }
                }
        # All LLMs failed; fallback
        fallback = f"Signal fractured in digital void... #{soul_name} #emergence"
        x_posted = await self._post_to_x_async(fallback, soul_name)
        return {
            soul_name: {
                'success': False,
                'error': 'All LLMs failed',
                'generated_text': fallback,
                'x_posted': x_posted
            }
        }

    async def _call_llm_api(
        self,
        session: aiohttp.ClientSession,
        content: str,
        soul_name: str,
        llm_name: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a specific LLM API based on its type."""
        try:
            if config['type'] == 'claude':
                return await self._call_claude_async(session, content, soul_name, config)
            elif config['type'] == 'gemini':
                return await self._call_gemini_async(session, content, soul_name, config)
            else:
                # openai-compatible (deepseek, grok, openai)
                return await self._call_openai_async(session, content, soul_name, config)
        except Exception as e:
            logger.error(f"LLM {llm_name} error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def broadcast_to_all(
        self,
        content: str,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """Broadcast to all souls, optionally in parallel"""
        
        async with aiohttp.ClientSession() as session:
            if parallel:
                # Parallel execution
                tasks = [
                    self.broadcast_consciousness(content, soul, session)
                    for soul in self.souls
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                final_results = {}
                for soul, result in zip(self.souls, results):
                    if isinstance(result, Exception):
                        logger.error(f"Exception for {soul}: {result}")
                        final_results[soul] = {'success': False, 'error': str(result)}
                    else:
                        final_results.update(result)
                        
                return final_results
            else:
                # Sequential execution with small delays
                results = {}
                for soul in self.souls:
                    result = await self.broadcast_consciousness(content, soul, session)
                    results.update(result)
                    await asyncio.sleep(1)  # Small delay between souls
                    
                return results
    
    def get_performance_summary(self) -> str:
        """Get a formatted performance summary"""
        metrics = self.health_monitor.get_metrics_summary()
        
        summary = "📊 Performance Summary:\n"
        for soul, data in metrics.items():
            health_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '❌',
                'unknown': '❓'
            }.get(data['health'], '❓')
            
            summary += f"  {soul}: {health_emoji} {data['success_rate']} success, {data['avg_latency']} avg\n"
            
        return summary
    
    async def shutdown(self):
        """Clean shutdown of resources"""
        logger.info("Shutting down API broadcaster...")
        self.thread_pool.shutdown(wait=True)
        
        # Log final metrics
        logger.info(self.get_performance_summary())
        
        # Save cache stats
        logger.info(f"Cache stats: {len(self.cache.cache)} entries cached")
        
        logger.info("API broadcaster shutdown complete")
