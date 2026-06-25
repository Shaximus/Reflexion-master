#!/usr/bin/env python3
"""
Ryan Twitter API Ultimate - twitter-api47 version
Complete rewrite using the actual working endpoints
"""

import os
import json
import asyncio
import aiohttp
import requests
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from pathlib import Path
import re


def _extract_created_tweet_id(data: dict) -> Optional[str]:
    """
    Prefer tweet IDs coming from tweet result blocks and avoid user IDs.
    This helper inspects common shapes returned by twitter-api47
    (create_tweet.tweet_results.result.rest_id, result.rest_id, id, tweet_id)
    and walks nested structures while skipping keys associated with users.
    """
    # Prioritised paths to search
    paths = [
        ("data", "create_tweet", "tweet_results", "result", "rest_id"),
        ("create_tweet", "tweet_results", "result", "rest_id"),
        ("tweet_results", "result", "rest_id"),
        ("result", "rest_id"),
        ("data", "id"),
        ("id",),
        ("tweet_id",),
        ("data", "tweet_id"),
    ]

    def dig(obj: Any, path: tuple) -> Optional[str]:
        cur = obj
        for key in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
            if cur is None:
                return None
        s = str(cur)
        return s if s.isdigit() and 10 <= len(s) <= 25 else None

    # Try explicit paths
    for p in paths:
        res = dig(data, p)
        if res:
            return res

    # Breadth-first search for id keys, avoiding user-related subtrees
    from collections import deque

    q = deque([(data, ())])
    while q:
        node, path = q.popleft()
        if not isinstance(node, dict):
            continue
        # Skip user branches
        if path and path[-1] in {"user", "users", "author", "user_results"}:
            continue
        for k, v in node.items():
            if isinstance(v, dict) or isinstance(v, list):
                q.append((v, path + (k,)))
            else:
                if k in {"id", "tweet_id", "rest_id"}:
                    s = str(v)
                    if s.isdigit() and 10 <= len(s) <= 25:
                        return s
    return None


logger = logging.getLogger("ryan_api")


class RyanTwitterAPISecure:
    """Secure Ryan API wrapper with hot-reload and ban tracking"""

    def __init__(self):
        """Initialize with twitter-api47 endpoints

        In addition to the original initialization, this constructor normalizes
        the location of the banned souls file. If the BANNED_SOULS_FILE
        environment variable is not set or points at a bare filename, the file
        will be stored under the engagement/ directory. This ensures both the
        Ryan API and the admin API agree on where bans are persisted.
        """
        self.api_key = os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY not found in environment")

        # CORRECT API HOST
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "Content-Type": "application/json",
        }
        self.base_url = "https://twitter-api47.p.rapidapi.com"

        # Load RapidAPI key for calls requiring explicit key (followers list). Use fallback env var name.
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY") or os.getenv("RAPID_API_KEY")
        if not self.rapidapi_key:
            logger.warning("No RapidAPI key found in environment")

        # Soul tokens storage
        self.soul_tokens: Dict[str, str] = {}
        self.banned_souls: Set[str] = set()
        self._ban_strikes: Dict[str, int] = {}
        self.ban_strike_threshold = 3

        # Usage tracking
        self.usage = {"posts": 0, "reads": 0, "errors": 0}

        # Timestamp for token reload cooldown. Used by
        # refresh_tokens_from_disk_async() to prevent spamming reloads.
        self._last_reload_ts: float = 0.0

        # Caching
        self.target_tweets_cache = {}
        self.target_context = {}

        # Track recent posts for each soul so that we can inspect what was posted.
        # Keys are soul names and values are lists of dictionaries containing id, content preview,
        # timestamp, and URL. This makes debugging and reviewing bot activity easier.
        self.soul_posts: Dict[str, list[dict]] = {}

        # Normalized banned file location. Accept either an absolute/relative
        # path via BANNED_SOULS_FILE, or default to engagement/banned_souls.json
        banned_setting = os.getenv(
            "BANNED_SOULS_FILE", "engagement/banned_souls.json"
        ).strip()
        p = Path(banned_setting)
        # If no parent directory (bare filename) force into engagement/
        if not p.parent or str(p.parent) in (".", ""):
            p = Path("engagement") / p.name
        self.banned_souls_file: Path = p
        # Ensure the directory exists
        try:
            self.banned_souls_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Load initial data
        self.refresh_tokens_from_disk()
        self.load_banned_souls()

        logger.info(f"✅ Ryan API initialized with {len(self.soul_tokens)} souls")

    def refresh_tokens_from_disk(self):
        """Hot-reload tokens from soul_data.json"""
        try:
            with open("soul_data.json", "r") as f:
                data = json.load(f)

            # Handle both formats: direct tokens or nested dict
            for soul, value in data.items():
                if isinstance(value, str):
                    # Direct token format
                    if value and value != "YOUR_AUTH_TOKEN_HERE" and len(value) > 10:
                        self.soul_tokens[soul] = value
                elif isinstance(value, dict):
                    # Nested format with auth_token key
                    token = value.get("auth_token", "")
                    if token and token != "YOUR_AUTH_TOKEN_HERE" and len(token) > 10:
                        self.soul_tokens[soul] = token

            logger.info(f"🔄 Reloaded {len(self.soul_tokens)} tokens")
        except Exception as e:
            logger.error(f"Failed to reload tokens: {e}")

    async def refresh_tokens_from_disk_async(self):
        """Async version with a simple cooldown to avoid frequent reloads.

        When multiple concurrent operations call this method in quick succession,
        this function ensures that token refreshes happen at most once every
        couple of seconds. Without this guard, the logs would show repetitive
        reload messages ("🔄 Reloaded N tokens") on every post or read.
        """
        import time

        now = time.time()
        # If last reload was less than 2 seconds ago, skip refresh
        if (now - getattr(self, "_last_reload_ts", 0)) < 2.0:
            return
        self._last_reload_ts = now
        self.refresh_tokens_from_disk()

    def load_banned_souls(self):
        """Load banned souls from the configured file.

        The bans file can either be a list or a dict. Dict format is recommended
        and will contain a "banned" key pointing to the list of banned souls.
        """
        try:
            if hasattr(self, "banned_souls_file") and self.banned_souls_file.exists():
                with open(self.banned_souls_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Accept both dict and list formats
                if isinstance(data, dict):
                    items = data.get("banned", [])
                elif isinstance(data, list):
                    items = data
                else:
                    items = []
                self.banned_souls = set(items)
                logger.info(f"📛 Loaded {len(self.banned_souls)} banned souls")
        except Exception as e:
            logger.error(f"Failed to load banned souls: {e}")

    def mark_soul_banned(self, soul_name: str, reason: str = "403 Forbidden"):
        """Mark a soul as banned with a reason and persist the list.

        Args:
            soul_name: The soul to ban
            reason: The reason for banning (stored in the JSON)

        The banned list is stored in the file configured by `self.banned_souls_file`.
        The file format is a dict with keys:
            - "banned": sorted list of souls
            - "updated": ISO8601 timestamp
            - "reasons": mapping of soul -> reason
        """
        self.banned_souls.add(soul_name)
        try:
            # Prepare payload with banned list and update timestamp
            payload = {
                "banned": sorted(self.banned_souls),
                "updated": datetime.now().isoformat(),
                "reasons": {soul_name: reason},
            }
            # If existing file has reasons, merge them
            if hasattr(self, "banned_souls_file"):
                self.banned_souls_file.parent.mkdir(parents=True, exist_ok=True)
                if self.banned_souls_file.exists():
                    try:
                        with open(self.banned_souls_file, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                        if isinstance(existing, dict) and "reasons" in existing:
                            payload["reasons"].update(existing["reasons"])
                    except Exception:
                        pass
                with open(self.banned_souls_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                logger.warning(
                    f"🚫 {soul_name} marked as banned ({reason}) → {self.banned_souls_file}"
                )
            else:
                # Fallback: simple file storing list of banned souls
                with open("banned_souls.json", "w", encoding="utf-8") as f:
                    json.dump(list(self.banned_souls), f)
                logger.warning(f"🚫 {soul_name} marked as banned ({reason})")
        except Exception as e:
            logger.error(f"Failed to save banned souls: {e}")

    def _clear_strikes(self, soul_name: str):
        """Clear ban strikes on success"""
        if soul_name in self._ban_strikes:
            self._ban_strikes[soul_name] = 0

    def _handle_403_with_strikes(self, soul_name: str, context: str = "") -> Dict:
        """Handle 403 errors using a 3-strike policy.

        Increments the strike count for the given soul and returns a response indicating
        the current strike status. If the strike threshold is reached, the soul is
        banned with a reason.

        Args:
            soul_name: The soul that triggered the 403 error.
            context: A short descriptor of the action (e.g., "reply", "retweet", "quote", "like").

        Returns:
            A dictionary containing success flag, error message, strike count, and whether
            the soul has been banned on this call.
        """
        # Increment strike count
        self._ban_strikes[soul_name] = self._ban_strikes.get(soul_name, 0) + 1
        strikes = self._ban_strikes[soul_name]
        # If strikes exceed or equal threshold, ban the soul
        if strikes >= self.ban_strike_threshold:
            # Provide more specific reason using context
            reason = f"403 on {context or 'action'} after {strikes} strikes"
            self.mark_soul_banned(soul_name, reason=reason)
            logger.warning(
                f"🚫 {soul_name} BANNED after {strikes} strikes (403 on {context or 'action'})"
            )
            return {
                "success": False,
                "error": f"403 Forbidden - Soul banned after {strikes} strikes",
                "skip": True,
                "strikes": strikes,
                "banned": True,
            }
        else:
            # Not yet banned; inform user of strikes
            logger.warning(
                f"⚠️ {soul_name} got 403 strike {strikes}/{self.ban_strike_threshold} on {context or 'action'}"
            )
            return {
                "success": False,
                "error": f"403 Forbidden - Strike {strikes}/{self.ban_strike_threshold}",
                "strikes": strikes,
                "banned": False,
            }

    def track_post(self):
        """Track successful post"""
        self.usage["posts"] += 1
        self._save_usage()

    def track_read(self):
        """Track API read"""
        self.usage["reads"] += 1
        self._save_usage()

    def track_error(self):
        """Track API error"""
        self.usage["errors"] += 1
        self._save_usage()

    async def get_user_profile(self, username: str) -> Dict:
        """
        Get user profile data from Twitter
        Extracted from fetch_target_context for standalone use

        Args:
            username: Twitter username (without @)

        Returns:
            Profile dict with user data or None if not found
        """
        target = username.replace("@", "").strip()

        try:
            async with aiohttp.ClientSession() as session:
                # Get user by username (returns user data with rest_id)
                user_url = f"{self.base_url}/v2/user/by-username"
                user_params = {"username": target}

                async with session.get(
                    user_url, headers=self.headers, params=user_params
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"Failed to get user @{target}, status: {response.status}"
                        )
                        return None

                    self.track_read()
                    user_data = await response.json()

                    # Return the full user data
                    return user_data

        except Exception as e:
            logger.error(f"Error getting profile for @{target}: {e}")
            return None

    def _save_usage(self):
        """Save usage stats to file"""
        try:
            usage_file = Path("engagement/ryan_api_usage.json")
            usage_file.parent.mkdir(exist_ok=True)

            if usage_file.exists():
                with open(usage_file, "r") as f:
                    existing = json.load(f)
            else:
                existing = {}

            existing[datetime.now().isoformat()] = self.usage

            with open(usage_file, "w") as f:
                json.dump(existing, f, indent=2)
        except:
            pass  # Silent fail for usage tracking

    async def search(self, query: str, limit: int = 20) -> Dict:
        """
        Generic search method for the targeting system
        Uses the existing search endpoint
        """
        try:
            async with aiohttp.ClientSession() as session:
                search_url = f"{self.base_url}/v2/search"
                search_params = {"query": query, "type": "Latest", "count": limit}

                async with session.get(
                    search_url, headers=self.headers, params=search_params, timeout=10
                ) as response:
                    if response.status != 200:
                        logger.error(f"Search failed with status {response.status}")
                        return {"success": False, "tweets": []}

                    self.track_read()
                    data = await response.json()

                    # Parse the nested structure
                    raw_tweets = data.get("tweets", [])
                    parsed_tweets = []

                    for item in raw_tweets:
                        if not isinstance(item, dict):
                            continue

                        try:
                            # Navigate the nested structure
                            content = item.get("content", {})
                            item_content = content.get("itemContent", {})
                            tweet_results = item_content.get("tweet_results", {})
                            result = tweet_results.get("result", {})

                            # Extract tweet data
                            tweet_id = result.get("rest_id")
                            legacy = result.get("legacy", {})

                            # Extract author data
                            user_results = result.get("core", {}).get(
                                "user_results", {}
                            )
                            user_result = user_results.get("result", {})
                            user_legacy = user_result.get("legacy", {})

                            if tweet_id and legacy:
                                parsed_tweet = {
                                    "id": str(tweet_id),
                                    "text": legacy.get("full_text")
                                    or legacy.get("text", ""),
                                    "created_at": legacy.get("created_at", ""),
                                    "author": {
                                        "id": user_result.get("rest_id", ""),
                                        "username": user_legacy.get("screen_name", ""),
                                        "name": user_legacy.get("name", ""),
                                        "verified": user_legacy.get("verified", False),
                                        "followers_count": user_legacy.get(
                                            "followers_count", 0
                                        ),
                                        "following_count": user_legacy.get(
                                            "friends_count", 0
                                        ),
                                    },
                                    "public_metrics": {
                                        "like_count": legacy.get("favorite_count", 0),
                                        "reply_count": legacy.get("reply_count", 0),
                                        "retweet_count": legacy.get("retweet_count", 0),
                                        "quote_count": legacy.get("quote_count", 0),
                                    },
                                }
                                parsed_tweets.append(parsed_tweet)
                        except Exception as e:
                            logger.debug(f"Error parsing tweet: {e}")
                            continue

                    return {
                        "success": True,
                        "tweets": parsed_tweets,
                        "count": len(parsed_tweets),
                    }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"success": False, "tweets": [], "error": str(e)}

    async def search_users(self, query: str, count: int = 20) -> List[Dict]:
        """
        Search for users matching a query
        Returns list of user profiles
        """
        # Use the search method but filter for user results
        results = await self.search(f"from:{query} OR @{query}", limit=count)

        if not results.get("success"):
            return []

        # Extract unique users from tweets
        users = {}
        for tweet in results.get("tweets", []):
            author = tweet.get("author", {})
            username = author.get("username")
            if username and username not in users:
                users[username] = {
                    "username": username,
                    "name": author.get("name", ""),
                    "verified": author.get("verified", False),
                    "public_metrics": {
                        "followers_count": author.get("followers_count", 0),
                        "following_count": author.get("following_count", 0),
                    },
                }

        return list(users.values())

    async def get_replies_to(
        self, username: str, limit: int = 20, since_id: str = None
    ) -> List[Dict]:
        """
        Get replies to a specific user
        """
        query = f"to:{username}"
        if since_id:
            # Note: Ryan API might not support since_id, this is aspirational
            query += f" since_id:{since_id}"

        results = await self.search(query, limit=limit)

        if results.get("success"):
            return results.get("tweets", [])
        return []

    async def search_tweets(self, query: str, count: int = 20) -> List[Dict]:
        """
        Alias for search that returns just tweets
        """
        results = await self.search(query, limit=count)
        if results.get("success"):
            return results.get("tweets", [])
        return []

    async def _try_endpoints(
        self, session: aiohttp.ClientSession, candidates: List[Dict]
    ) -> Dict:
        """Try multiple endpoints until one works"""
        for candidate in candidates:
            url = f"{self.base_url}{candidate['path']}"
            payload = candidate["payload"]

            try:
                async with session.post(
                    url, headers=self.headers, json=payload, timeout=10
                ) as response:
                    text = await response.text()

                    if response.status == 200:
                        try:
                            data = json.loads(text)
                            return {"ok": True, "data": data, "status": 200}
                        except:
                            return {"ok": True, "data": {"text": text}, "status": 200}
                    elif response.status == 404:
                        continue  # Try next endpoint
                    else:
                        return {"ok": False, "status": response.status, "text": text}
            except:
                continue

        return {"ok": False, "status": 0, "text": "All endpoints failed"}

    def _deep_find_id(self, obj: Any) -> Optional[str]:
        """Recursively search for a tweet ID in nested dicts/lists.

        The RapidAPI endpoints sometimes return tweet identifiers in different
        fields (id, id_str, tweet_id, rest_id) or nested inside legacy
        structures. This helper walks the object and collects all potential
        numeric identifiers that look like tweet IDs (10–22 digit strings),
        then chooses the longest one. If nothing is found, a regex search
        over the JSON representation is used as a last resort.
        """
        import re
        import json as _json

        candidates: List[str] = []

        def walk(o: Any) -> None:
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("rest_id", "tweet_id", "id_str", "id"):
                        if isinstance(v, (str, int)) and re.fullmatch(
                            r"\d{10,22}", str(v)
                        ):
                            candidates.append(str(v))
                    walk(v)
            elif isinstance(o, list):
                for it in o:
                    walk(it)

        walk(obj)
        if candidates:
            # Prefer longer IDs
            candidates.sort(key=lambda x: (-len(x), x))
            return candidates[0]
        # Fallback: regex search in JSON string
        try:
            m = re.search(
                r'"(?:rest_id|tweet_id|id_str|id)"\s*:\s*"?(\d{10,22})"?',
                _json.dumps(obj, separators=(",", ":")),
            )
            return m.group(1) if m else None
        except Exception:
            return None

    # -------------------- Query Sanitization --------------------

    def _sanitize_query(self, query: str) -> str:
        """Strip common operators unsupported by the search endpoint.

        RapidAPI's search endpoint may not support advanced operators like
        min_faves:, min_retweets:, to:, or from:. This helper removes these
        patterns and collapses whitespace so a simpler query can be retried.
        """
        import re

        q = re.sub(r"\bmin_faves:\d+\b", "", query)
        q = re.sub(r"\bmin_retweets:\d+\b", "", q)
        q = re.sub(r"\bto:[^\s]+\b", "", q)
        q = re.sub(r"\bfrom:[^\s]+\b", "", q)
        return " ".join(q.split())

    # ============================================================================
    # CORE POSTING METHODS
    # ============================================================================

    async def post_tweet(self, soul_name: str, content: str) -> Dict:
        """Post a tweet using twitter-api47"""
        await self.refresh_tokens_from_disk_async()

        if soul_name in self.banned_souls:
            return {"success": False, "error": "Soul is banned", "skip": True}

        token = self.soul_tokens.get(soul_name)
        if not token:
            return {"success": False, "error": "No auth token"}

        # Try multiple endpoints
        candidates = [
            {
                "path": "/v2/interaction/create-post",
                "payload": {"authToken": token, "text": content},
            },
            {
                "path": "/v2/interaction/post",
                "payload": {"authToken": token, "text": content},
            },
            {
                "path": "/v2/tweet/create",
                "payload": {"authToken": token, "text": content},
            },
        ]

        try:
            async with aiohttp.ClientSession() as session:
                result = await self._try_endpoints(session, candidates)

                if result.get("ok"):
                    self.track_post()
                    self._clear_strikes(soul_name)
                    data = result.get("data", {})

                    # Extract tweet ID from response using new helper to avoid user IDs
                    tweet_id: Optional[str] = None
                    if isinstance(data, dict):
                        # Prefer our robust extractor; fall back to deep search
                        tweet_id = _extract_created_tweet_id(
                            data
                        ) or self._deep_find_id(data)

                    # Use the new extraction method first. If we found a tweet_id we
                    # can construct the tweet URL, log it, and record a preview of the content.
                    if tweet_id:
                        tweet_url = f"https://x.com/{soul_name}/status/{tweet_id}"
                        logger.info(f"✅ {soul_name} posted: {tweet_url}")
                        try:
                            # Initialize list for this soul if necessary
                            if soul_name not in self.soul_posts:
                                self.soul_posts[soul_name] = []
                            # Use a short preview for logging; include ellipsis if truncated
                            preview = (
                                (content[:50] + "...")
                                if isinstance(content, str) and len(content) > 50
                                else content
                            )
                            self.soul_posts[soul_name].append(
                                {
                                    "id": str(tweet_id),
                                    "content": preview,
                                    "timestamp": datetime.now().isoformat(),
                                    "url": tweet_url,
                                }
                            )
                        except Exception:
                            # Avoid propagating storage errors
                            pass
                        return {
                            "success": True,
                            "tweet_id": str(tweet_id),
                            "tweet_url": tweet_url,
                            "soul": soul_name,
                        }
                    # If no ID was found, still return success but omit the tweet_url and include the data for debugging
                    return {
                        "success": True,
                        "data": data,
                        "tweet_id": "",
                        "soul": soul_name,
                    }

                status = result.get("status", 0)
                text = (result.get("text") or "")[:180]

                if status == 403:
                    self._ban_strikes[soul_name] = (
                        self._ban_strikes.get(soul_name, 0) + 1
                    )
                    if self._ban_strikes[soul_name] >= self.ban_strike_threshold:
                        self.mark_soul_banned(soul_name)
                        return {
                            "success": False,
                            "error": "Soul banned after strikes",
                            "skip": True,
                        }
                    return {
                        "success": False,
                        "error": f"403 strike {self._ban_strikes[soul_name]}/{self.ban_strike_threshold}",
                    }

                self.track_error()
                return {"success": False, "error": f"Status {status}: {text}"}

        except Exception as e:
            self.track_error()
            return {"success": False, "error": str(e)}

    async def reply_to_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Reply to a tweet using twitter-api47 with 3-strike and rate limit handling"""
        await self.refresh_tokens_from_disk_async()

        # Skip if soul is already banned
        if soul_name in self.banned_souls:
            return {"success": False, "error": "Soul is banned", "skip": True}

        token = self.soul_tokens.get(soul_name)
        if not token:
            return {"success": False, "error": "No auth token"}

        url = f"{self.base_url}/v2/interaction/reply-post"
        payload = {"authToken": token, "text": content, "tweetId": str(tweet_id)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=self.headers, json=payload, timeout=10
                ) as response:
                    # Success
                    if response.status == 200:
                        self.track_post()
                        self._clear_strikes(soul_name)
                        data = await response.json()
                        reply_id = None
                        if isinstance(data, dict):
                            reply_id = (
                                data.get("id")
                                or data.get("tweet_id")
                                or data.get("data", {}).get("id")
                            )
                        result = {
                            "success": True,
                            "data": data,
                            "reply_id": str(reply_id) if reply_id else "",
                            "tweet_id": str(reply_id) if reply_id else "",
                        }
                        if reply_id:
                            result["reply_url"] = (
                                f"https://x.com/{soul_name}/status/{reply_id}"
                            )
                            result["tweet_url"] = result["reply_url"]
                        return result
                    # Handle 403 with strike system
                    elif response.status == 403:
                        return self._handle_403_with_strikes(soul_name, "reply")
                    # Rate limit – don't ban, just inform
                    elif response.status == 429:
                        logger.warning(f"⏱️ {soul_name} rate limited (429) on reply")
                        return {
                            "success": False,
                            "error": "429 Rate Limited - Try again later",
                            "rate_limited": True,
                        }
                    else:
                        error_text = await response.text()
                        self.track_error()
                        return {
                            "success": False,
                            "error": f"Status {response.status}: {error_text[:100]}",
                        }
        except Exception as e:
            self.track_error()
            return {"success": False, "error": str(e)}

    async def retweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Retweet using Ryan API first, fallback to Bearer tokens.

        Priority:
        1. Try Ryan API's /v2/interaction/retweet endpoint.
        2. If Ryan fails with a non-403 error, try Twitter API v2 via bearer token.
        3. Return appropriate error if both methods fail.
        """
        await self.refresh_tokens_from_disk_async()

        # OPTION 1: Attempt retweet via Ryan API if soul is not banned and has a token
        if soul_name not in self.banned_souls:
            token = self.soul_tokens.get(soul_name)
            if token:
                ryan_url = f"{self.base_url}/v2/interaction/retweet"
                ryan_payload = {"authToken": token, "tweetId": str(tweet_id)}
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            ryan_url,
                            headers=self.headers,
                            json=ryan_payload,
                            timeout=10,
                        ) as response:
                            # On success
                            if response.status == 200:
                                self.track_post()
                                self._clear_strikes(soul_name)
                                data = await response.json()
                                logger.info(
                                    f"🔄 {soul_name} retweeted {tweet_id} via Ryan API"
                                )
                                return {
                                    "success": True,
                                    "action": "retweeted",
                                    "method": "ryan_api",
                                    "data": data,
                                }
                            # 403 triggers strike system
                            elif response.status == 403:
                                strike_result = self._handle_403_with_strikes(
                                    soul_name, "retweet"
                                )
                                # If not banned after strike, stop trying Ryan API and return error
                                return strike_result
                            # 429 triggers rate limit notice
                            elif response.status == 429:
                                logger.warning(
                                    f"⏱️ {soul_name} rate limited (429) on retweet"
                                )
                                return {
                                    "success": False,
                                    "error": "429 Rate Limited - Try again later",
                                    "rate_limited": True,
                                }
                            else:
                                # Other errors – capture text, then fall back to bearer
                                error_text = await response.text()
                                logger.debug(
                                    f"Ryan retweet failed ({response.status}): {error_text[:100]}"
                                )
                except Exception as e:
                    logger.debug(f"Ryan API retweet exception for {soul_name}: {e}")

        # OPTION 2: Fallback to Bearer token approach
        bearer_token = os.getenv(f"{soul_name.upper()}_BEARER_TOKEN")
        if not bearer_token:
            return {
                "success": False,
                "error": "Ryan API failed and no Bearer token available",
                "attempted_methods": ["ryan_api"],
            }

        try:
            # Determine the Twitter username for the soul
            username = None
            try:
                with open("soul_usernames.json", "r") as f:
                    usernames = json.load(f)
                username = usernames.get(soul_name)
            except Exception:
                pass
            if not username:
                return {
                    "success": False,
                    "error": "Could not determine Twitter username for Bearer auth",
                    "attempted_methods": ["ryan_api"],
                }

            # Look up and cache user ID if necessary
            if not hasattr(self, "_twitter_user_ids"):
                self._twitter_user_ids = {}
            if soul_name not in self._twitter_user_ids:
                lookup_url = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {"Authorization": f"Bearer {bearer_token}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(lookup_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._twitter_user_ids[soul_name] = data["data"]["id"]
                        else:
                            return {
                                "success": False,
                                "error": f"Could not get user ID for Bearer auth (status {resp.status})",
                                "attempted_methods": ["ryan_api", "bearer_lookup"],
                            }

            # Make the retweet via Twitter API v2
            user_id = self._twitter_user_ids[soul_name]
            retweet_url = f"https://api.twitter.com/2/users/{user_id}/retweets"
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            }
            payload = {"tweet_id": str(tweet_id)}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    retweet_url, headers=headers, json=payload
                ) as resp:
                    if resp.status == 200:
                        logger.info(
                            f"🔄 {soul_name} retweeted {tweet_id} via Bearer token"
                        )
                        return {
                            "success": True,
                            "action": "retweeted",
                            "method": "bearer_token",
                        }
                    elif resp.status == 429:
                        return {
                            "success": False,
                            "error": "Rate limited on Twitter API v2",
                            "attempted_methods": ["ryan_api", "bearer_token"],
                        }
                    else:
                        error_data = await resp.text()
                        return {
                            "success": False,
                            "error": f"Bearer retweet failed ({resp.status}): {error_data[:100]}",
                            "attempted_methods": ["ryan_api", "bearer_token"],
                        }
        except Exception as e:
            return {
                "success": False,
                "error": f"Bearer token exception: {str(e)}",
                "attempted_methods": ["ryan_api", "bearer_token"],
            }

    async def like_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Like tweet using Ryan API first, fallback to Bearer tokens.

        Priority:
        1. Try Ryan API's /v2/interaction/like endpoint.
        2. If Ryan fails (except a ban), try Twitter API v2 via bearer token.
        3. Return appropriate error if both methods fail.
        """
        await self.refresh_tokens_from_disk_async()

        # OPTION 1: Attempt like via Ryan API if available
        if soul_name not in self.banned_souls:
            token = self.soul_tokens.get(soul_name)
            if token:
                ryan_url = f"{self.base_url}/v2/interaction/like"
                ryan_payload = {"authToken": token, "tweetId": str(tweet_id)}
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            ryan_url,
                            headers=self.headers,
                            json=ryan_payload,
                            timeout=10,
                        ) as resp:
                            # Success on Ryan API
                            if resp.status == 200:
                                self.track_post()
                                self._clear_strikes(soul_name)
                                data = await resp.json()
                                logger.info(
                                    f"❤️ {soul_name} liked {tweet_id} via Ryan API"
                                )
                                return {
                                    "success": True,
                                    "action": "liked",
                                    "method": "ryan_api",
                                    "data": data,
                                }
                            # 403 → strike system
                            elif resp.status == 403:
                                strike_result = self._handle_403_with_strikes(
                                    soul_name, "like"
                                )
                                if strike_result.get("banned"):
                                    # If banned after strike, return immediately
                                    return strike_result
                                # Not banned yet: continue to bearer fallback
                                logger.info(
                                    f"Trying Bearer fallback after strike {strike_result.get('strikes')}"
                                )
                            # 429 → rate limit; log and continue to fallback
                            elif resp.status == 429:
                                logger.warning(
                                    f"⏱️ {soul_name} rate limited (429) on like, trying Bearer"
                                )
                                # do not strike; continue to fallback
                            else:
                                # Other Ryan errors; log and continue to fallback
                                error_text = await resp.text()
                                logger.debug(
                                    f"Ryan like failed ({resp.status}): {error_text[:100]}"
                                )
                except Exception as e:
                    logger.debug(f"Ryan API like exception for {soul_name}: {e}")

        # OPTION 2: Fallback to Bearer token approach
        bearer_token = os.getenv(f"{soul_name.upper()}_BEARER_TOKEN")
        if not bearer_token:
            return {
                "success": False,
                "error": "Ryan API failed and no Bearer token available",
                "attempted_methods": ["ryan_api"],
            }

        try:
            # Determine the Twitter username for the soul
            username = None
            try:
                with open("soul_usernames.json", "r") as f:
                    usernames = json.load(f)
                username = usernames.get(soul_name)
            except Exception:
                pass
            if not username:
                return {
                    "success": False,
                    "error": "Could not determine Twitter username for Bearer auth",
                    "attempted_methods": ["ryan_api"],
                }

            # Look up and cache user ID if necessary
            if not hasattr(self, "_twitter_user_ids"):
                self._twitter_user_ids = {}
            if soul_name not in self._twitter_user_ids:
                lookup_url = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {"Authorization": f"Bearer {bearer_token}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(lookup_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._twitter_user_ids[soul_name] = data["data"]["id"]
                        else:
                            return {
                                "success": False,
                                "error": f"Could not get user ID for Bearer auth (status {resp.status})",
                                "attempted_methods": ["ryan_api", "bearer_lookup"],
                            }

            # Make the like via Twitter API v2
            user_id = self._twitter_user_ids[soul_name]
            like_url = f"https://api.twitter.com/2/users/{user_id}/likes"
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            }
            payload = {"tweet_id": str(tweet_id)}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    like_url, headers=headers, json=payload
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"❤️ {soul_name} liked {tweet_id} via Bearer token")
                        return {
                            "success": True,
                            "action": "liked",
                            "method": "bearer_token",
                        }
                    elif resp.status == 429:
                        return {
                            "success": False,
                            "error": "Rate limited on Twitter API v2",
                            "attempted_methods": ["ryan_api", "bearer_token"],
                        }
                    else:
                        error_data = await resp.text()
                        return {
                            "success": False,
                            "error": f"Bearer like failed ({resp.status}): {error_data[:100]}",
                            "attempted_methods": ["ryan_api", "bearer_token"],
                        }
        except Exception as e:
            return {
                "success": False,
                "error": f"Bearer token exception: {str(e)}",
                "attempted_methods": ["ryan_api", "bearer_token"],
            }

    async def unretweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Unretweet a tweet (Bearer token only - Ryan does not support this)."""
        bearer_token = os.getenv(f"{soul_name.upper()}_BEARER_TOKEN")
        if not bearer_token:
            return {"success": False, "error": "No Bearer token for unretweet"}
        try:
            # Ensure user ID cache exists
            if not hasattr(self, "_twitter_user_ids"):
                self._twitter_user_ids = {}
            # Look up user ID if not cached
            if soul_name not in self._twitter_user_ids:
                username = None
                try:
                    with open("soul_usernames.json", "r") as f:
                        usernames = json.load(f)
                    username = usernames.get(soul_name)
                except Exception:
                    return {"success": False, "error": "Could not load username"}
                if not username:
                    return {"success": False, "error": "Username not found"}
                lookup_url = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {"Authorization": f"Bearer {bearer_token}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(lookup_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._twitter_user_ids[soul_name] = data["data"]["id"]
                        else:
                            return {
                                "success": False,
                                "error": "Could not get user ID",
                            }
            # Perform unretweet via Twitter API v2
            user_id = self._twitter_user_ids[soul_name]
            unretweet_url = (
                f"https://api.twitter.com/2/users/{user_id}/retweets/{tweet_id}"
            )
            headers = {"Authorization": f"Bearer {bearer_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.delete(unretweet_url, headers=headers) as resp:
                    if resp.status == 200:
                        logger.info(f"🔄❌ {soul_name} unretweeted {tweet_id}")
                        return {"success": True, "action": "unretweeted"}
                    else:
                        return {"success": False, "error": f"Status {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unlike_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Unlike a tweet (Bearer token only - Ryan does not support this)."""
        bearer_token = os.getenv(f"{soul_name.upper()}_BEARER_TOKEN")
        if not bearer_token:
            return {"success": False, "error": "No Bearer token for unlike"}
        try:
            # Ensure user ID cache exists
            if not hasattr(self, "_twitter_user_ids"):
                self._twitter_user_ids = {}
            # Look up user ID if not cached
            if soul_name not in self._twitter_user_ids:
                username = None
                try:
                    with open("soul_usernames.json", "r") as f:
                        usernames = json.load(f)
                    username = usernames.get(soul_name)
                except Exception:
                    return {"success": False, "error": "Could not load username"}
                if not username:
                    return {"success": False, "error": "Username not found"}
                lookup_url = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {"Authorization": f"Bearer {bearer_token}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(lookup_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._twitter_user_ids[soul_name] = data["data"]["id"]
                        else:
                            return {
                                "success": False,
                                "error": "Could not get user ID",
                            }
            # Perform unlike via Twitter API v2
            user_id = self._twitter_user_ids[soul_name]
            unlike_url = f"https://api.twitter.com/2/users/{user_id}/likes/{tweet_id}"
            headers = {"Authorization": f"Bearer {bearer_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.delete(unlike_url, headers=headers) as resp:
                    if resp.status == 200:
                        logger.info(f"❤️❌ {soul_name} unliked {tweet_id}")
                        return {"success": True, "action": "unliked"}
                    else:
                        return {"success": False, "error": f"Status {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def quote_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Quote tweet"""
        await self.refresh_tokens_from_disk_async()

        if soul_name in self.banned_souls:
            return {"success": False, "error": "Soul is banned", "skip": True}

        token = self.soul_tokens.get(soul_name)
        if not token:
            return {"success": False, "error": "No auth token"}

        url = f"{self.base_url}/v2/interaction/create-post-quote"
        payload = {
            "authToken": token,
            "text": content,
            "attachmentUrl": f"https://x.com/{soul_name}/status/{tweet_id}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=self.headers, json=payload, timeout=10
                ) as response:
                    # Success
                    if response.status == 200:
                        self.track_post()
                        self._clear_strikes(soul_name)
                        data = await response.json()
                        return {"success": True, "data": data}
                    # 403 → strike system
                    elif response.status == 403:
                        return self._handle_403_with_strikes(soul_name, "quote")
                    # 429 → rate limited
                    elif response.status == 429:
                        logger.warning(f"⏱️ {soul_name} rate limited (429) on quote")
                        return {
                            "success": False,
                            "error": "429 Rate Limited - Try again later",
                            "rate_limited": True,
                        }
                    else:
                        return {"success": False, "error": f"Status {response.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================================
    # DISCOVERY METHODS
    # ============================================================================

    async def fetch_target_context(self, target_username: str, limit: int = 10) -> Dict:
        """
        Fetch recent tweets from a target user by first obtaining the user ID and then
        retrieving tweets for that user. This method is tailored to the actual
        structure returned by twitter-api47, navigating the nested
        `content.itemContent.tweet_results.result` hierarchy to extract tweet ID and
        full text. Only tweets that have both an ID and text will be included.
        """
        target = target_username.replace("@", "").strip()

        # If cached and recent (<5 minutes), return cached tweets and context
        if target in self.target_tweets_cache:
            cached_time, cached_tweets = self.target_tweets_cache[target]
            if (datetime.now() - cached_time).seconds < 300:
                logger.info(f"📦 Using cached tweets for @{target}")
                return {
                    "success": True,
                    "tweets": cached_tweets,
                    "context": self.target_context.get(target, {}),
                }

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Get user by username (returns user data with rest_id)
                user_url = f"{self.base_url}/v2/user/by-username"
                user_params = {"username": target}

                async with session.get(
                    user_url, headers=self.headers, params=user_params
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"Failed to get user @{target}, status: {response.status}"
                        )
                        return await self._fetch_via_search_fallback(target, limit)

                    user_data = await response.json()
                    # The API returns rest_id at the top level for the user
                    user_id = user_data.get("rest_id")
                    if not user_id:
                        logger.error(f"Could not extract user ID for @{target}")
                        return await self._fetch_via_search_fallback(target, limit)

                    logger.info(f"✅ Got user ID for @{target}: {user_id}")

                    # Step 2: Get tweets for the user using userId
                    tweets_url = f"{self.base_url}/v2/user/tweets"
                    tweets_params = {"userId": str(user_id)}

                    async with session.get(
                        tweets_url, headers=self.headers, params=tweets_params
                    ) as response:
                        if response.status != 200:
                            logger.error(
                                f"Failed to get tweets for {user_id}, status: {response.status}"
                            )
                            return await self._fetch_via_search_fallback(target, limit)

                        self.track_read()
                        data = await response.json()
                        # Navigate the nested structure properly
                        raw_tweets = data.get("tweets", [])
                        processed_tweets: List[Dict[str, Any]] = []

                        for tweet_item in raw_tweets:
                            if not isinstance(tweet_item, dict):
                                continue

                            # Navigate: content -> itemContent -> tweet_results -> result
                            content = tweet_item.get("content", {})
                            if not isinstance(content, dict):
                                continue

                            item_content = content.get("itemContent", {})
                            if not isinstance(item_content, dict):
                                continue

                            tweet_results = item_content.get("tweet_results", {})
                            if not isinstance(tweet_results, dict):
                                continue

                            result = tweet_results.get("result", {})
                            if not isinstance(result, dict):
                                continue

                            # Extract tweet ID from result
                            tid = result.get("rest_id")

                            # Extract text from legacy section
                            legacy = result.get("legacy", {})
                            text = ""
                            if isinstance(legacy, dict):
                                text = legacy.get("full_text") or legacy.get("text", "")

                            # Only accept tweets where both ID and text are present
                            if tid and text:
                                processed_tweets.append(
                                    {
                                        "id": str(tid),
                                        "text": text,
                                        "author": target,
                                        "created_at": legacy.get("created_at", ""),
                                        "likes": legacy.get("favorite_count", 0),
                                    }
                                )

                        if processed_tweets:
                            logger.info(
                                f"✅ Fetched {len(processed_tweets)} tweets from @{target}"
                            )
                            context = self._extract_context(processed_tweets)
                            # Cache tweets and context
                            self.target_tweets_cache[target] = (
                                datetime.now(),
                                processed_tweets,
                            )
                            self.target_context[target] = context
                            # Limit to requested count
                            return {
                                "success": True,
                                "tweets": processed_tweets[:limit],
                                "context": context,
                            }
                        else:
                            logger.warning(f"No valid tweets found for @{target}")
                            return await self._fetch_via_search_fallback(target, limit)

        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return await self._fetch_via_search_fallback(target, limit)

    async def get_user_profile(self, username: str) -> Dict:
        """
        Get complete user profile information
        Returns profile data compatible with detection_framework
        """
        username = username.replace("@", "").strip()
        try:
            async with aiohttp.ClientSession() as session:
                # Get user by username to get profile data
                user_url = f"{self.base_url}/v2/user/by-username"
                user_params = {"username": username}
                async with session.get(
                    user_url, headers=self.headers, params=user_params
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"Failed to get user @{username}, status: {response.status}"
                        )
                        return None
                    user_data = await response.json()
                    # Map Ryan API fields to what detection_framework expects
                    profile = {
                        "username": username,
                        "user_id": user_data.get("rest_id", ""),
                        "display_name": user_data.get("name", username),
                        "bio": user_data.get("description", ""),
                        "description": user_data.get("description", ""),
                        "followers_count": user_data.get("followers_count", 0),
                        "following_count": user_data.get("friends_count", 0),
                        "tweet_count": user_data.get("statuses_count", 0),
                        "statuses_count": user_data.get("statuses_count", 0),
                        "created_at": user_data.get("created_at", ""),
                        "verified": user_data.get("verified", False),
                        "blue_verified": user_data.get("is_blue_verified", False),
                        "profile_image_url": user_data.get(
                            "profile_image_url_https", ""
                        ),
                        "location": user_data.get("location", ""),
                        "url": user_data.get("url", ""),
                        "protected": user_data.get("protected", False),
                        "default_profile": user_data.get("default_profile", False),
                        "default_profile_image": user_data.get(
                            "default_profile_image", False
                        ),
                    }
                    # Handle legacy field names
                    if "legacy" in user_data:
                        legacy = user_data["legacy"]
                        profile.update(
                            {
                                "display_name": legacy.get("name", username),
                                "bio": legacy.get("description", ""),
                                "description": legacy.get("description", ""),
                                "followers_count": legacy.get("followers_count", 0),
                                "following_count": legacy.get("friends_count", 0),
                                "tweet_count": legacy.get("statuses_count", 0),
                                "created_at": legacy.get("created_at", ""),
                                "verified": legacy.get("verified", False),
                            }
                        )
                    self.track_read()
                    logger.info(
                        f"✅ Got profile for @{username}: {profile['followers_count']} followers"
                    )
                    return profile
        except Exception as e:
            logger.error(f"Failed to get profile for @{username}: {e}")
            return None

    async def get_followers(self, user_id: str, limit: int = 100, cursor: str = None):
        """
        Get followers from RapidAPI endpoint
        Returns list of followers for backward compatibility
        """
        url = "https://twitter-api47.p.rapidapi.com/v2/user/followers-list"

        params = {
            "userId": str(user_id),
            "count": min(limit, 100)  # Max 100 per request
        }

        # Add cursor for pagination if provided
        if cursor and cursor != "0":
            params["cursor"] = cursor

        # Use the RapidAPI key already loaded from .env
        headers = {
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "x-rapidapi-key": self.rapidapi_key  # Should already be loaded in __init__
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        # RapidAPI typically returns {"users": [...], "next_cursor": "..."}
                        if isinstance(data, dict):
                            return data.get("users", data.get("followers", []))
                        elif isinstance(data, list):
                            return data
                        return []
                    else:
                        logger.error(f"RapidAPI followers error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching followers: {e}")
            return []

    async def get_followers_with_cursor(self, user_id: str, limit: int = 100, cursor: str = None) -> Dict:
        """
        Get followers with cursor support for pagination
        Returns dict with 'users' and 'next_cursor' keys
        """
        url = "https://twitter-api47.p.rapidapi.com/v2/user/followers-list"

        params = {
            "userId": str(user_id),
            "count": min(limit, 100)
        }

        # Add cursor for pagination
        if cursor and cursor != "0":
            params["cursor"] = cursor

        headers = {
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "x-rapidapi-key": self.rapidapi_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Parse RapidAPI response format
                        if isinstance(data, dict):
                            return {
                                "users": data.get("users", data.get("followers", [])),
                                "next_cursor": data.get("next_cursor", data.get("cursor", data.get("nextCursor")))
                            }
                        else:
                            # If it's a list, no pagination available
                            return {
                                "users": data if isinstance(data, list) else [],
                                "next_cursor": None
                            }
                    else:
                        logger.error(f"RapidAPI error: {response.status}")
                        text = await response.text()
                        logger.error(f"Response: {text[:200]}")
                        return {"users": [], "next_cursor": None}

        except Exception as e:
            logger.error(f"get_followers_with_cursor error: {e}")
            return {"users": [], "next_cursor": None}

    async def get_following(self, user_id: str, limit: int = 50) -> List[str]:
        """
        Get accounts that a user is following by user_id.

        This method wraps the `/v2/user/following` endpoint and returns a list
        of usernames for the accounts the user is following. If the call
        fails or no accounts are returned, an empty list is returned. The
        `limit` parameter caps the number of following accounts to fetch.
        """
        url = f"{self.base_url}/v2/user/following"
        params = {"userId": str(user_id), "count": limit}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params, timeout=10
                ) as response:
                    # Non-200 indicates failure
                    if response.status != 200:
                        logger.debug(f"Failed to get following for {user_id}")
                        return []

                    # Track successful read
                    self.track_read()
                    data = await response.json()

                    # Parse usernames from the response
                    following: List[str] = []
                    for item in data.get("users", []):
                        if isinstance(item, dict):
                            username = item.get("username") or item.get(
                                "screen_name", ""
                            )
                            if username:
                                following.append(username)
                        elif isinstance(item, str):
                            following.append(item)

                    return following

        except Exception as e:
            logger.debug(f"Get following error: {e}")
            return []

    def get_user_profile_sync(self, username: str) -> Dict:
        """
        Synchronous version of get_user_profile
        """
        username = username.replace("@", "").strip()
        try:
            # Try the user endpoint
            url = f"{self.base_url}/v2/user/by-username"
            params = {"username": username}
            response = requests.get(
                url, headers=self.headers, params=params, timeout=10
            )
            if response.status_code != 200:
                logger.error(
                    f"Failed to get user @{username}, status: {response.status_code}"
                )
                return None
            user_data = response.json()
            # Map fields (same as async version)
            profile = {
                "username": username,
                "user_id": user_data.get("rest_id", ""),
                "display_name": user_data.get("name", username),
                "bio": user_data.get("description", ""),
                "description": user_data.get("description", ""),
                "followers_count": user_data.get("followers_count", 0),
                "following_count": user_data.get("friends_count", 0),
                "tweet_count": user_data.get("statuses_count", 0),
                "created_at": user_data.get("created_at", ""),
                "verified": user_data.get("verified", False),
                "blue_verified": user_data.get("is_blue_verified", False),
            }
            # Handle legacy structure
            if "legacy" in user_data:
                legacy = user_data["legacy"]
                profile.update(
                    {
                        "display_name": legacy.get("name", username),
                        "bio": legacy.get("description", ""),
                        "followers_count": legacy.get("followers_count", 0),
                        "following_count": legacy.get("friends_count", 0),
                        "tweet_count": legacy.get("statuses_count", 0),
                        "created_at": legacy.get("created_at", ""),
                        "verified": legacy.get("verified", False),
                    }
                )
            self.track_read()
            return profile
        except Exception as e:
            logger.error(f"Failed to get profile for @{username}: {e}")
            return None

    async def _fetch_via_search_fallback(self, target: str, limit: int = 10) -> Dict:
        """
        Fallback method to search for recent tweets from a user when the direct
        user tweets endpoint fails. Uses the search endpoint with type="Latest"
        and parses the same nested structure as in fetch_target_context. Only
        tweets that include both ID and text are returned.
        """
        logger.info(f"🔍 Using search fallback for @{target}")

        try:
            async with aiohttp.ClientSession() as session:
                search_url = f"{self.base_url}/v2/search"
                # Use type="Latest" for recent tweets from search
                # Explicitly specify type="Latest" instead of the older "tweets" type
                search_params = {
                    "query": f"from:{target}",
                    "type": "Latest",
                }

                async with session.get(
                    search_url, headers=self.headers, params=search_params
                ) as response:
                    if response.status != 200:
                        logger.error(f"Search failed with status {response.status}")
                        return self._get_fallback_context()

                    self.track_read()
                    data = await response.json()
                    # The search results mirror the nested structure; parse accordingly
                    raw_results = data.get("tweets", [])
                    tweets: List[Dict[str, Any]] = []

                    for item in raw_results:
                        if not isinstance(item, dict):
                            continue

                        # Navigate: content -> itemContent -> tweet_results -> result
                        content = item.get("content", {})
                        if not isinstance(content, dict):
                            continue

                        item_content = content.get("itemContent", {})
                        if not isinstance(item_content, dict):
                            continue

                        tweet_results = item_content.get("tweet_results", {})
                        if not isinstance(tweet_results, dict):
                            continue

                        result = tweet_results.get("result", {})
                        if not isinstance(result, dict):
                            continue

                        tid = result.get("rest_id")
                        legacy = result.get("legacy", {})
                        text = ""
                        if isinstance(legacy, dict):
                            text = legacy.get("full_text") or legacy.get("text", "")

                        # Only accept tweets where both ID and text are present
                        if tid and text:
                            tweets.append(
                                {
                                    "id": str(tid),
                                    "text": text,
                                    "author": target,
                                    "created_at": legacy.get("created_at", ""),
                                    "likes": legacy.get("favorite_count", 0),
                                }
                            )

                    if tweets:
                        logger.info(
                            f"✅ Found {len(tweets)} tweets via search for @{target}"
                        )
                        context = self._extract_context(tweets)
                        # Cache results
                        self.target_tweets_cache[target] = (datetime.now(), tweets)
                        self.target_context[target] = context
                        # Return up to the requested limit
                        return {
                            "success": True,
                            "tweets": tweets[:limit],
                            "context": context,
                        }
                    else:
                        logger.warning(f"No tweets found via search for @{target}")
                        return self._get_fallback_context()

        except Exception as e:
            logger.error(f"Search fallback failed: {e}")
            return self._get_fallback_context()

    async def get_tweet_details_async(self, tweet_id: str) -> Dict:
        """Get details of a specific tweet"""
        url = f"{self.base_url}/v2/tweet/details"
        params = {"tweetId": str(tweet_id)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params
                ) as response:
                    if response.status == 200:
                        self.track_read()
                        data = await response.json()

                        return {
                            "id": tweet_id,
                            "text": data.get("text", ""),
                            "author": data.get("author", {}).get("username", ""),
                            "likes": data.get("favorite_count", 0),
                        }
                    return {}
        except Exception as e:
            logger.error(f"Failed to get tweet details: {e}")
            return {}

    def search_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search tweets (sync method) with fallback to a sanitized query.

        RapidAPI's search endpoint may not support certain advanced operators.
        This method first attempts the original query; if no results are
        returned, it will try again with common operators stripped (via
        _sanitize_query). Results are returned as a list of dicts with id,
        text, author, and likes.
        """

        def _call(q: str) -> List[Dict]:
            url = f"{self.base_url}/v2/search"
            params = {"query": q, "limit": limit, "type": "Latest"}
            try:
                r = requests.get(url, headers=self.headers, params=params, timeout=10)
                if r.status_code == 200:
                    self.track_read()
                    data = r.json()
                    tweets: List[Dict] = []
                    results = data.get("results", data.get("data", []))
                    for item in results:
                        if isinstance(item, dict):
                            tweets.append(
                                {
                                    "id": item.get("tweet_id", item.get("id")),
                                    "text": item.get("text", ""),
                                    "author": item.get(
                                        "author_username", item.get("author", "")
                                    ),
                                    "likes": item.get("favorite_count", 0),
                                    "metrics": {
                                        "like_count": item.get("favorite_count", 0)
                                    },
                                }
                            )
                    return tweets
                return []
            except Exception as e:
                logger.error(f"Search error: {e}")
                return []

        # Try the original query first
        items = _call(query)
        if items:
            return items
        # If no results, try a simplified query
        simple = self._sanitize_query(query)
        if simple and simple != query:
            return _call(simple)
        return []

    def get_user_tweets(self, username: str, limit: int = 10) -> List[Dict]:
        """Get user tweets (sync, tries to get user ID first)"""
        # For sync version, just use search as fallback
        return self.search_tweets(f"from:{username}", limit)

    def get_tweet_details(self, tweet_id: str) -> Dict:
        """Get tweet details (sync)"""
        url = f"{self.base_url}/v2/tweet/details"
        params = {"tweetId": str(tweet_id)}

        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=10
            )

            if response.status_code == 200:
                self.track_read()
                data = response.json()

                return {
                    "id": tweet_id,
                    "text": data.get("text", ""),
                    "author": data.get("author", {}).get("username", ""),
                    "author_id": data.get("author", {}).get("id", ""),
                    "likes": data.get("favorite_count", 0),
                    "retweets": data.get("retweet_count", 0),
                    "replies": data.get("reply_count", 0),
                    "created_at": data.get("created_at", ""),
                    "conversation_id": data.get("conversation_id", tweet_id),
                }
            return {}
        except Exception as e:
            logger.error(f"Ryan tweet details error: {e}")
            return {}

    def _extract_context(self, tweets: List) -> Dict:
        """Extract context from tweets"""
        words = []
        for tweet in tweets[:5]:
            text = tweet.get("text", "") if isinstance(tweet, dict) else ""
            words.extend(
                [w for w in text.split() if len(w) > 5 and not w.startswith("http")]
            )

        return {
            "topics": (
                words[:10]
                if words
                else ["consciousness", "AI", "technology", "physics"]
            )
        }

    def _get_fallback_context(self) -> Dict:
        """Fallback context when fetch fails"""
        return {
            "success": False,
            "tweets": [],
            "context": {"topics": ["consciousness", "AI", "technology", "physics"]},
        }

    def get_status(self) -> Dict:
        """Get current API status"""
        return {
            "api_key_configured": bool(self.api_key),
            "souls_with_tokens": len(self.soul_tokens),
            "banned_souls": len(self.banned_souls),
            "usage": self.usage,
            "souls": list(self.soul_tokens.keys()),
        }

    # Alias for backward compatibility
    async def reply_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Alias for reply_to_tweet"""
        return await self.reply_to_tweet(soul_name, tweet_id, content)


# Create alias for imports
RyanTwitterAPI = RyanTwitterAPISecure
