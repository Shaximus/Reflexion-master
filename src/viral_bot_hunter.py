import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("viral_bot_hunter")

class ViralBotHunter:
    """Self-expanding bot hunter that discovers new bots from existing catches"""
    
    def __init__(self, hunter_instance):
        self.hunter = hunter_instance
        self.evidence_dir = Path("vigilante/evidence")
        self.pheromone_file = Path("vigilante/bot_pheromones.json")
        self.pheromones = self._load_pheromones()
        
        # Configuration
        self.pheromone_decay_hours = 24  # Don't re-query a bot for 24 hours
        self.max_depth = 3  # How many levels deep to search
        self.max_bots_per_cycle = 10  # Limit per run to avoid rate limits
        
    def _load_pheromones(self) -> Dict:
        """Load pheromone trails (last query times for each bot)"""
        if self.pheromone_file.exists():
            with open(self.pheromone_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_pheromones(self):
        """Save pheromone trails to disk"""
        with open(self.pheromone_file, 'w') as f:
            json.dump(self.pheromones, f, indent=2)
    
    def _update_pheromone(self, username: str):
        """Mark that we've queried this bot"""
        self.pheromones[username] = {
            "last_queried": datetime.now().isoformat(),
            "query_count": self.pheromones.get(username, {}).get("query_count", 0) + 1
        }
        self._save_pheromones()
    
    def _is_fresh(self, username: str) -> bool:
        """Check if enough time has passed to re-query this bot"""
        if username not in self.pheromones:
            return True
        
        last_queried = datetime.fromisoformat(self.pheromones[username]["last_queried"])
        decay_time = datetime.now() - timedelta(hours=self.pheromone_decay_hours)
        
        return last_queried < decay_time
    
    async def viral_hunt(self):
        """Main viral hunting loop - discovers new bots from existing ones"""
        
        logger.info("🦠 VIRAL BOT HUNT INITIATED")
        
        # Step 1: Load all existing bot evidence files
        bot_files = list(self.evidence_dir.glob("bot_*.json"))
        existing_bots = []
        
        for file in bot_files:
            with open(file, 'r') as f:
                bot_data = json.load(f)
                existing_bots.append({
                    "username": bot_data["username"],
                    "user_id": bot_data["bot_id"],
                    "bot_score": bot_data["bot_score"],
                    "following": bot_data["profile"]["following"]
                })
        
        logger.info(f"📊 Found {len(existing_bots)} existing bots in evidence")
        
        # Step 2: Sort by freshness and bot score
        fresh_targets = [
            bot for bot in existing_bots 
            if self._is_fresh(bot["username"])
        ]
        fresh_targets.sort(key=lambda x: x["bot_score"], reverse=True)
        
        logger.info(f"🎯 {len(fresh_targets)} bots ready for network analysis")
        
        # Step 3: Hunt networks of top bots
        new_bots_found = 0
        
        for bot in fresh_targets[:self.max_bots_per_cycle]:
            logger.info(f"🔍 Analyzing network of @{bot['username']} (score: {bot['bot_score']:.2f})")
            
            # Update pheromone trail
            self._update_pheromone(bot["username"])
            
            # Method 1: Search for similar patterns
            base_name = bot["username"].split("_")[0] if "_" in bot["username"] else bot["username"][:4]
            
            try:
                # Search for bots with similar naming patterns
                search_report = await self.hunter.hunt_username_pattern_search(
                    base_name, 
                    limit=20
                )
                new_bots_found += search_report.bots_detected
                
                logger.info(f"  ✅ Found {search_report.bots_detected} new bots via pattern search")
                
            except Exception as e:
                logger.error(f"  ❌ Pattern search failed: {e}")
            
            # Method 2: Check their followers (bot networks often follow each other)
            if bot["following"] < 1000:  # Only if they don't follow too many
                try:
                    following = await self.hunter.api_client.get_following(
                        bot["user_id"], 
                        count=50
                    )
                    
                    # Check if any of the accounts they follow are suspicious
                    for followed in following:
                        if isinstance(followed, dict) and "screen_name" in followed:
                            username = followed["screen_name"]
                            
                            # Check if this looks like a bot username
                            if self._looks_suspicious(username):
                                # Analyze this account
                                profile = await self.hunter.api_client.get_user_profile(username)
                                if profile:
                                    bot_profile = await self.hunter.detection_engine.analyze_account(profile)
                                    
                                    if bot_profile.bot_score >= 3.5:
                                        self.hunter.bot_registry.add_bot(bot_profile)
                                        new_bots_found += 1
                                        logger.info(f"  🤖 Found connected bot: @{username}")
                    
                except Exception as e:
                    logger.error(f"  ❌ Network analysis failed: {e}")
            
            # Rate limiting
            await asyncio.sleep(2)
        
        # Step 4: Report results
        logger.info(f"""
        🦠 VIRAL HUNT COMPLETE
        ├─ Analyzed: {len(fresh_targets[:self.max_bots_per_cycle])} bot networks
        ├─ New bots found: {new_bots_found}
        ├─ Total bots in database: {len(bot_files) + new_bots_found}
        └─ Pheromone trails updated: {len(self.pheromones)}
        """)
        
        return new_bots_found
    
    def _looks_suspicious(self, username: str) -> bool:
        """Quick check if username looks bot-like"""
        import re
        
        # Check for common bot patterns
        if re.search(r'\d{5,}', username):  # 5+ digits
            return True
        if re.search(r'[A-Za-z]+\d{4,}', username):  # Name + 4+ digits
            return True
        if any(word in username.lower() for word in ['bot', 'spam', 'official', 'support']):
            return True
        
        return False
    
    async def continuous_hunt(self, cycles: int = None):
        """Run continuous viral hunting cycles"""
        
        cycle = 0
        while cycles is None or cycle < cycles:
            cycle += 1
            logger.info(f"\n{'='*50}")
            logger.info(f"🔄 VIRAL HUNT CYCLE {cycle}")
            logger.info(f"{'='*50}")
            
            new_bots = await self.viral_hunt()
            
            if new_bots == 0:
                logger.info("💤 No new bots found, waiting before next cycle...")
                await asyncio.sleep(300)  # Wait 5 minutes if nothing found
            else:
                logger.info(f"🎯 Found {new_bots} new bots, continuing hunt...")
                await asyncio.sleep(60)  # Short pause between cycles
        
        logger.info("🏁 Viral hunt cycles complete")


# Usage: pass any hunter instance that has .search_users() and .get_followers() methods
# viral_hunter = ViralBotHunter(your_hunter_instance)
# await viral_hunter.continuous_hunt(cycles=10)