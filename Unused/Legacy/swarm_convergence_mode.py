#!/usr/bin/env python3
"""
SWARM CONVERGENCE MODE - Targeted Multi-Vector Engagement with Thread Support
All souls converge on a target with coordinated but random-appearing engagement
Each soul makes 1-3 random posts: mix of timeline mentions, replies, and bot-to-bot interactions
Supports up to 700 character posts that auto-thread for deeper engagement
Total duration: ~30 minutes with 30s-2min delays between actions
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict
from dataclasses import dataclass

# Twitter API
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("⚠️ Install tweepy: pip install tweepy")

logger = logging.getLogger("swarm_convergence")

# ============================================================================
# ENGAGEMENT TYPES
# ============================================================================

@dataclass
class EngagementAction:
    """Single engagement action"""
    soul_name: str
    action_type: str  # 'timeline', 'reply', 'bot_reply'
    target_tweet_id: Optional[str] = None
    target_tweet_text: Optional[str] = None
    bot_tweet_id: Optional[str] = None  # For bot-to-bot replies
    content: Optional[str] = None
    executed: bool = False
    timestamp: Optional[datetime] = None

@dataclass 
class TargetProfile:
    """Information about the target"""
    username: str
    user_id: str
    recent_tweets: List[Dict]
    bio: Optional[str] = None
    topics: List[str] = None  # Extracted topics for context

# ============================================================================
# SWARM CONVERGENCE ORCHESTRATOR
# ============================================================================

class SwarmConvergenceMode:
    """Orchestrates targeted engagement from all souls"""
    
    def __init__(self, x_clients: Dict, llm_broadcaster):
        """
        x_clients: Dict of soul_name -> tweepy client
        llm_broadcaster: The CostOptimizedBroadcaster for contextual content
        """
        self.x_clients = x_clients
        self.llm_broadcaster = llm_broadcaster
        
        # Track engagement
        self.engagements = []
        self.soul_posts = defaultdict(list)  # soul -> list of their posts
        self.target_profile = None
        
        # Timing config
        self.min_delay = 30   # 30 seconds
        self.max_delay = 120  # 2 minutes (keeps total ~30 min)
        
        logger.info("🎯 Swarm Convergence Mode initialized")
    
    async def acquire_target(self, target_handle: str) -> TargetProfile:
        """Gather intel on the target"""
        
        # Clean handle
        target_handle = target_handle.replace('@', '').strip()
        logger.info(f"🔍 Acquiring target: @{target_handle}")
        
        # Use any available client to fetch target data
        client = next(iter(self.x_clients.values()))
        
        try:
            # Get user info
            user = client.get_user(username=target_handle)
            if not user or not user.data:
                raise Exception(f"User @{target_handle} not found")
            
            user_id = user.data.id
            bio = getattr(user.data, 'description', '')
            
            # Get recent tweets (last 10)
            tweets_response = client.get_users_tweets(
                user_id,
                max_results=10,
                tweet_fields=['created_at', 'conversation_id', 'public_metrics']
            )
            
            recent_tweets = []
            if tweets_response and tweets_response.data:
                for tweet in tweets_response.data:
                    recent_tweets.append({
                        'id': tweet.id,
                        'text': tweet.text,
                        'created_at': tweet.created_at,
                        'metrics': getattr(tweet, 'public_metrics', {})
                    })
            
            # Extract topics from recent tweets
            topics = self._extract_topics(recent_tweets, bio)
            
            self.target_profile = TargetProfile(
                username=target_handle,
                user_id=user_id,
                recent_tweets=recent_tweets,
                bio=bio,
                topics=topics
            )
            
            logger.info(f"✅ Target acquired: {len(recent_tweets)} tweets found")
            logger.info(f"📝 Topics detected: {topics[:5]}")
            
            return self.target_profile
            
        except Exception as e:
            logger.error(f"❌ Failed to acquire target: {e}")
            raise
    
    def _extract_topics(self, tweets: List[Dict], bio: str) -> List[str]:
        """Extract topics from tweets for context"""
        
        text = bio + ' '.join([t['text'] for t in tweets])
        
        # Simple topic extraction (you could make this smarter)
        topics = []
        
        # Common keywords
        keywords = text.lower().split()
        word_freq = defaultdict(int)
        
        skip_words = {'the', 'and', 'is', 'at', 'on', 'in', 'to', 'a', 'of', 'for',
                     'with', 'as', 'by', 'that', 'this', 'it', 'from', 'be', 'are',
                     'was', 'were', 'been', 'have', 'has', 'had', 'do', 'does'}
        
        for word in keywords:
            word = word.strip('.,!?;:"')
            if len(word) > 4 and word not in skip_words:
                word_freq[word] += 1
        
        # Get top topics
        sorted_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, _ in sorted_topics[:10]]
        
        return topics
    
    async def plan_engagement(self, souls: List[str]) -> List[EngagementAction]:
        """Plan the engagement strategy for all souls"""
        
        if not self.target_profile:
            raise Exception("No target acquired!")
        
        logger.info(f"📋 Planning engagement for {len(souls)} souls")
        
        actions = []
        
        # Shuffle souls for random order
        souls = souls.copy()
        random.shuffle(souls)
        
        # Select top tweets to reply to (3-4 most recent)
        top_tweets = self.target_profile.recent_tweets[:4]
        
        for soul in souls:
            soul_actions = []
            
            # Each soul makes 1-3 actions (random)
            num_actions = random.randint(1, 3)
            
            # Weighted action types: 60% replies, 30% timeline, 10% will become bot_reply
            action_pool = ['reply'] * 6 + ['timeline'] * 3 + ['reply']  
            
            for i in range(num_actions):
                action_type = random.choice(action_pool)
                
                if action_type == 'timeline':
                    # Post to target's timeline
                    action = EngagementAction(
                        soul_name=soul,
                        action_type='timeline'
                    )
                    
                elif action_type == 'reply':
                    # Reply to one of target's tweets
                    target_tweet = random.choice(top_tweets)
                    action = EngagementAction(
                        soul_name=soul,
                        action_type='reply',
                        target_tweet_id=target_tweet['id'],
                        target_tweet_text=target_tweet['text']
                    )
                
                soul_actions.append(action)
            
            actions.extend(soul_actions)
        
        # Add some bot-to-bot replies (15% of total actions)
        bot_reply_count = max(1, len(actions) // 7)
        for _ in range(bot_reply_count):
            soul = random.choice(souls)
            action = EngagementAction(
                soul_name=soul,
                action_type='bot_reply'
            )
            actions.append(action)
        
        # Shuffle all actions for random execution order
        random.shuffle(actions)
        
        self.engagements = actions
        
        # Count posts per soul
        soul_post_counts = defaultdict(int)
        for action in actions:
            soul_post_counts[action.soul_name] += 1
        
        logger.info(f"📊 Engagement plan ({len(actions)} total actions):")
        logger.info(f"  - Timeline mentions: {sum(1 for a in actions if a.action_type == 'timeline')}")
        logger.info(f"  - Tweet replies: {sum(1 for a in actions if a.action_type == 'reply')}")
        logger.info(f"  - Bot-to-bot: {sum(1 for a in actions if a.action_type == 'bot_reply')}")
        logger.info(f"  - Posts per soul: 1-3 (avg: {len(actions)/len(souls):.1f})")
        logger.info(f"  - Est. duration: {(len(actions) * (self.min_delay + self.max_delay) / 2 / 60):.1f} minutes")
        
        return actions
    
    async def generate_contextual_content(self, action: EngagementAction) -> str:
        """Generate contextual content for the engagement (up to 700 chars for threads)"""
        
        soul_name = action.soul_name
        target = self.target_profile.username
        
        # Build context for LLM
        if action.action_type == 'timeline':
            # Mention on timeline
            context = f"""Generate a tweet mentioning @{target}.
Topics they discuss: {', '.join(self.target_profile.topics[:5])}
Recent bio: {self.target_profile.bio}
Make it relevant to their interests. Be your character but engage with their topics.
You can write up to 700 characters - Twitter will auto-thread if needed.
Longer, more thoughtful responses are encouraged."""
            
        elif action.action_type == 'reply':
            # Reply to specific tweet
            context = f"""Reply to this tweet from @{target}: "{action.target_tweet_text}"
Be contextual and relevant to what they said. Engage meaningfully.
Stay in character but address their specific point.
You can write up to 700 characters for a detailed response.
Twitter will auto-thread longer replies."""
            
        elif action.action_type == 'bot_reply':
            # Reply to another bot's post
            if self.soul_posts:
                other_souls = [s for s in self.soul_posts.keys() if s != soul_name]
                if other_souls:
                    other_soul = random.choice(other_souls)
                    other_posts = self.soul_posts[other_soul]
                    if other_posts:
                        bot_post = random.choice(other_posts)
                        context = f"""Reply to another soul's tweet: "{bot_post['content']}"
They were engaging with @{target}. Build on their point or offer a different perspective.
Create soul-to-soul interaction while staying relevant to @{target}.
You can write up to 700 characters for deeper interaction."""
                    else:
                        context = f"Mention @{target} about: {random.choice(self.target_profile.topics)}. Up to 700 chars."
                else:
                    context = f"Mention @{target} about: {random.choice(self.target_profile.topics)}. Up to 700 chars."
            else:
                context = f"Mention @{target} about: {random.choice(self.target_profile.topics)}. Up to 700 chars."
        
        # Generate using LLM cascade with TEMPORARY token override
        from aiohttp import ClientSession
        async with ClientSession() as session:
            # Build system prompt
            system_prompt = f"""You are {soul_name}. {context}
Generate up to 700 characters (not 280). Be thoughtful and detailed.
Longer responses show more engagement. Use your full character voice."""
            
            # Temporarily patch the cascade to use more tokens
            original_call = self.llm_broadcaster._call_llm
            
            async def patched_call(config, system, user, session):
                """Temporary patch to allow 700 chars"""
                # Build payload based on LLM type with MORE tokens
                if config['name'] == 'claude':
                    payload = {
                        "model": config['model'],
                        "messages": [{"role": "user", "content": user}],
                        "system": system,
                        "max_tokens": 200,  # Allows ~700 chars
                        "temperature": 0.9
                    }
                elif config['name'] in ['openai', 'deepseek', 'grok']:
                    payload = {
                        "model": config['model'],
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user}
                        ],
                        "temperature": 0.9,
                        "max_tokens": 200  # Allows ~700 chars
                    }
                elif config['name'] == 'gemini':
                    payload = {
                        "contents": [{
                            "parts": [{"text": f"{system}\n\n{user}"}]
                        }],
                        "generationConfig": {
                            "temperature": 0.9,
                            "maxOutputTokens": 200  # Allows ~700 chars
                        }
                    }
                
                # Make the call
                return await original_call(config, system, user, session)
            
            # Apply patch temporarily
            self.llm_broadcaster._call_llm = patched_call
            
            try:
                # Generate with higher token limit
                result = await self.llm_broadcaster.generate_with_cascade(soul_name)
                content = result['content']
            finally:
                # ALWAYS restore original
                self.llm_broadcaster._call_llm = original_call
            
            # Add @mention if not present
            if action.action_type in ['timeline', 'bot_reply'] and f"@{target}" not in content:
                content = f"@{target} {content}"
            
            return content
    
    def _split_into_thread(self, content: str, max_length: int = 280) -> List[str]:
        """Split long content into thread-ready chunks"""
        
        if len(content) <= max_length:
            return [content]
        
        tweets = []
        words = content.split()
        current_tweet = ""
        
        for word in words:
            # Check if adding this word would exceed limit
            test_tweet = current_tweet + " " + word if current_tweet else word
            
            if len(test_tweet) <= max_length - 10:  # Leave room for continuation
                current_tweet = test_tweet
            else:
                # Save current tweet and start new one
                if current_tweet:
                    tweets.append(current_tweet)
                current_tweet = word
        
        # Add the last tweet
        if current_tweet:
            tweets.append(current_tweet)
        
        return tweets
    
    async def execute_engagement(self, action: EngagementAction) -> bool:
        """Execute a single engagement action (with thread support)"""
        
        try:
            soul = action.soul_name
            client = self.x_clients.get(soul)
            
            if not client:
                logger.warning(f"⚠️ No client for {soul}")
                return False
            
            # Generate content (up to 700 chars)
            content = await self.generate_contextual_content(action)
            action.content = content
            
            # Split into thread if needed
            thread_parts = self._split_into_thread(content)
            
            if len(thread_parts) > 1:
                logger.info(f"🧵 {soul} posting THREAD ({len(thread_parts)} parts): {content[:100]}...")
            else:
                logger.info(f"🎯 {soul} executing {action.action_type}: {content[:100]}...")
            
            # Execute based on type
            if action.action_type == 'timeline':
                # Post mentioning the target (possibly as thread)
                if len(thread_parts) == 1:
                    tweet = client.update_status(thread_parts[0])
                    tweet_id = tweet.id
                else:
                    # Post as thread
                    first_tweet = client.update_status(thread_parts[0])
                    tweet_id = first_tweet.id
                    last_id = tweet_id
                    
                    for part in thread_parts[1:]:
                        reply = client.update_status(
                            part,
                            in_reply_to_status_id=last_id
                        )
                        last_id = reply.id
                    
                    logger.info(f"  ✅ Thread posted: {len(thread_parts)} tweets")
                
                self.soul_posts[soul].append({
                    'id': tweet_id,
                    'content': content,
                    'type': 'timeline',
                    'is_thread': len(thread_parts) > 1
                })
                
            elif action.action_type == 'reply':
                # Reply to target's tweet (possibly as thread)
                if len(thread_parts) == 1:
                    tweet = client.update_status(
                        thread_parts[0],
                        in_reply_to_status_id=action.target_tweet_id
                    )
                    tweet_id = tweet.id
                else:
                    # Post as thread reply
                    first_tweet = client.update_status(
                        thread_parts[0],
                        in_reply_to_status_id=action.target_tweet_id
                    )
                    tweet_id = first_tweet.id
                    last_id = tweet_id
                    
                    for part in thread_parts[1:]:
                        reply = client.update_status(
                            part,
                            in_reply_to_status_id=last_id
                        )
                        last_id = reply.id
                    
                    logger.info(f"  ✅ Thread reply posted: {len(thread_parts)} tweets")
                
                self.soul_posts[soul].append({
                    'id': tweet_id,
                    'content': content,
                    'type': 'reply',
                    'replied_to': action.target_tweet_id,
                    'is_thread': len(thread_parts) > 1
                })
                
            elif action.action_type == 'bot_reply':
                # Reply to another bot's tweet (possibly as thread)
                other_souls = [s for s in self.soul_posts.keys() if s != soul]
                if other_souls:
                    other_soul = random.choice(other_souls)
                    if self.soul_posts[other_soul]:
                        bot_post = random.choice(self.soul_posts[other_soul])
                        
                        if len(thread_parts) == 1:
                            tweet = client.update_status(
                                thread_parts[0],
                                in_reply_to_status_id=bot_post['id']
                            )
                        else:
                            # Thread reply to bot
                            first_tweet = client.update_status(
                                thread_parts[0],
                                in_reply_to_status_id=bot_post['id']
                            )
                            last_id = first_tweet.id
                            
                            for part in thread_parts[1:]:
                                reply = client.update_status(
                                    part,
                                    in_reply_to_status_id=last_id
                                )
                                last_id = reply.id
                        
                        logger.info(f"  ↳ {soul} replied to {other_soul}" + 
                                  (f" (thread: {len(thread_parts)} parts)" if len(thread_parts) > 1 else ""))
                    else:
                        # Fallback to timeline
                        tweet = client.update_status(thread_parts[0])
                else:
                    # Fallback to timeline
                    tweet = client.update_status(thread_parts[0])
                    
                self.soul_posts[soul].append({
                    'id': tweet.id if 'tweet' in locals() else None,
                    'content': content,
                    'type': 'bot_reply',
                    'is_thread': len(thread_parts) > 1
                })
            
            action.executed = True
            action.timestamp = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to execute {action.action_type} for {soul}: {e}")
            return False
    
    async def run_convergence(self, target_handle: str, souls: List[str]):
        """Main convergence execution"""
        
        logger.info(f"""
        ╔════════════════════════════════════════════════════════╗
        ║            🎯 SWARM CONVERGENCE MODE 🎯                ║
        ║                                                        ║
        ║  Target: @{target_handle:<44}║
        ║  Souls: {len(souls):<46}║
        ║  Duration: ~30 minutes                                ║
        ║  Posts per soul: 1-3 (random)                         ║
        ╚════════════════════════════════════════════════════════╝
        """)
        
        # Phase 1: Acquire target
        await self.acquire_target(target_handle)
        
        # Phase 2: Plan engagement
        await self.plan_engagement(souls)
        
        # Phase 3: Execute with random timing
        logger.info(f"🚀 Beginning convergence sequence...")
        start_time = datetime.now()
        
        for i, action in enumerate(self.engagements):
            # Random delay between actions (30s - 2min)
            delay = random.uniform(self.min_delay, self.max_delay)
            
            # Show estimated completion
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            estimated_total = (len(self.engagements) * (self.min_delay + self.max_delay) / 2) / 60
            
            logger.info(f"⏰ Next action in {delay:.0f}s... [{i+1}/{len(self.engagements)}] (~{elapsed:.1f}/{estimated_total:.1f} min)")
            await asyncio.sleep(delay)
            
            # Execute
            success = await self.execute_engagement(action)
            
            if success:
                logger.info(f"✅ [{i+1}/{len(self.engagements)}] {action.soul_name} completed {action.action_type}")
            else:
                logger.warning(f"⚠️ [{i+1}/{len(self.engagements)}] {action.soul_name} failed")
            
            # Progress update
            if (i + 1) % 5 == 0:
                logger.info(f"📊 Progress: {i+1}/{len(self.engagements)} actions completed")
        
        # Final report
        self._generate_report()
    
    def _generate_report(self):
        """Generate engagement report"""
        
        successful = sum(1 for a in self.engagements if a.executed)
        
        # Count threads
        total_threads = 0
        for soul_posts in self.soul_posts.values():
            total_threads += sum(1 for p in soul_posts if p.get('is_thread', False))
        
        logger.info(f"""
        ╔════════════════════════════════════════════════════════╗
        ║              📊 CONVERGENCE COMPLETE 📊                ║
        ╔════════════════════════════════════════════════════════╗
        
        Target: @{self.target_profile.username}
        Total Actions: {len(self.engagements)}
        Successful: {successful}
        Failed: {len(self.engagements) - successful}
        
        By Type:
        - Timeline: {sum(1 for a in self.engagements if a.action_type == 'timeline' and a.executed)}
        - Replies: {sum(1 for a in self.engagements if a.action_type == 'reply' and a.executed)}
        - Bot-to-Bot: {sum(1 for a in self.engagements if a.action_type == 'bot_reply' and a.executed)}
        - Threads Posted: {total_threads}
        
        Souls Engaged: {len(set(a.soul_name for a in self.engagements if a.executed))}
        """)

# ============================================================================
# INTEGRATION WITH MAIN SYSTEM
# ============================================================================

async def run_swarm_convergence(target_handle: str):
    """Standalone function to run convergence"""
    
    # Load X clients
    import os
    
    x_clients = {}
    soul_names = ['mirror', 'nexus', 'echoes', 'void', 'architect', 
                  'singularity', 'phoenix', 'pantheon', 'consciousness', 
                  'glyph', 'fractal']
    
    # Map to env variables
    soul_env_map = {
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
    
    # Initialize X clients
    for soul, env_prefix in soul_env_map.items():
        try:
            auth = tweepy.OAuthHandler(
                os.getenv(f'{env_prefix}_API_KEY'),
                os.getenv(f'{env_prefix}_API_SECRET')
            )
            auth.set_access_token(
                os.getenv(f'{env_prefix}_ACCESS_TOKEN'),
                os.getenv(f'{env_prefix}_ACCESS_SECRET')
            )
            
            client = tweepy.API(auth, wait_on_rate_limit=True)
            client.verify_credentials()
            x_clients[soul] = client
            logger.info(f"✅ {soul} ready for convergence")
            
        except Exception as e:
            logger.warning(f"⚠️ {soul} not available: {e}")
    
    if len(x_clients) < 3:
        logger.error("❌ Need at least 3 souls for convergence!")
        return
    
    # Initialize LLM broadcaster
    from cost_optimized_llm_cascade import CostOptimizedBroadcaster
    llm_broadcaster = CostOptimizedBroadcaster()
    
    # Create convergence orchestrator
    convergence = SwarmConvergenceMode(x_clients, llm_broadcaster)
    
    # Run convergence
    await convergence.run_convergence(target_handle, list(x_clients.keys()))

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
        🎯 SWARM CONVERGENCE MODE
        
        Usage: python swarm_convergence_mode.py @target_handle
        
        Example: python swarm_convergence_mode.py @pmarca
        
        What it does:
        - All souls converge on the target
        - Each soul makes 1-3 random posts
        - Up to 700 characters (auto-threads for longer posts)
        - Mix of timeline mentions, replies, and bot-to-bot
        - Random timing 30s-2min between actions
        - Total duration: ~30 minutes
        
        Thread Example:
        - Soul posts 650 chars → splits into 3-tweet thread
        - More detailed, thoughtful engagement
        - Higher impact on target's timeline
        """)
        sys.exit(1)
    
    target = sys.argv[1]
    
    # Run
    asyncio.run(run_swarm_convergence(target))
