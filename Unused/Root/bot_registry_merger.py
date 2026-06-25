#!/usr/bin/env python3
"""
Bot Registry Merger - Merges JSON and SQLite databases with deduplication
Handles both formats and creates a unified, deduplicated registry
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Set
import shutil

class BotRegistryMerger:
    def __init__(self):
        self.base_dir = Path("F:/Reflexion_ultimate/vigilante")
        self.json_file = self.base_dir / "bot_registry.json"
        self.db_file = self.base_dir / "bot_registry.db"
        self.evidence_file = self.base_dir / "hunt_data/evidence/bot_registry_complete.json"
        
        # Merged data storage
        self.merged_registry = {}
        self.stats = {
            "json_bots": 0,
            "db_bots": 0,
            "evidence_bots": 0,
            "duplicates": 0,
            "unique_total": 0
        }
    
    def load_json_registry(self) -> Dict[str, Any]:
        """Load bots from JSON registry"""
        bots = {}
        
        if self.json_file.exists():
            print(f"📄 Loading JSON registry: {self.json_file}")
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both formats
            if isinstance(data, dict) and "bots" in data:
                bots = data["bots"]
            elif isinstance(data, dict):
                bots = data
            
            self.stats["json_bots"] = len(bots)
            print(f"   ✅ Loaded {len(bots)} bots from JSON")
        else:
            print(f"   ❌ JSON registry not found")
        
        return bots
    
    def load_evidence_backup(self) -> Dict[str, Any]:
        """Load bots from evidence backup"""
        bots = {}
        
        if self.evidence_file.exists():
            print(f"📄 Loading evidence backup: {self.evidence_file}")
            with open(self.evidence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both formats
            if isinstance(data, dict) and "bots" in data:
                bots = data["bots"]
            elif isinstance(data, dict):
                bots = data
            
            self.stats["evidence_bots"] = len(bots)
            print(f"   ✅ Loaded {len(bots)} bots from evidence")
        else:
            print(f"   ❌ Evidence backup not found")
        
        return bots
    
    def load_sqlite_registry(self) -> Dict[str, Any]:
        """Load bots from SQLite database"""
        bots = {}
        
        if self.db_file.exists():
            print(f"📊 Loading SQLite database: {self.db_file}")
            
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all bots
            cursor.execute("SELECT * FROM bots")
            rows = cursor.fetchall()
            
            for row in rows:
                username = row["username"]
                
                # Convert row to dict
                bot_data = dict(row)
                
                # Parse JSON fields if they exist
                for json_field in ["profile_data", "evidence", "behavioral_flags", 
                                  "similarity_scores", "triggered_features", "strong_signals"]:
                    if json_field in bot_data and bot_data[json_field]:
                        try:
                            bot_data[json_field] = json.loads(bot_data[json_field])
                        except:
                            pass
                
                bots[username] = bot_data
            
            conn.close()
            self.stats["db_bots"] = len(bots)
            print(f"   ✅ Loaded {len(bots)} bots from SQLite")
        else:
            print(f"   ❌ SQLite database not found")
        
        return bots
    
    def merge_bot_entries(self, existing: Dict, new: Dict) -> Dict:
        """Merge two bot entries, keeping the most complete data"""
        merged = existing.copy()
        
        # Update with new data, but preserve certain fields from existing if better
        for key, value in new.items():
            if key in ["first_detected", "created_at"]:
                # Keep the earliest date
                if key in merged and merged[key]:
                    try:
                        existing_date = datetime.fromisoformat(str(merged[key]).replace('Z', '+00:00'))
                        new_date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        if new_date < existing_date:
                            merged[key] = value
                    except:
                        pass
                elif value:
                    merged[key] = value
            
            elif key == "detection_count":
                # Sum detection counts
                existing_count = int(merged.get(key, 0) or 0)
                new_count = int(value or 0)
                merged[key] = existing_count + new_count
            
            elif key == "bot_score":
                # Keep the highest bot score
                existing_score = float(merged.get(key, 0) or 0)
                new_score = float(value or 0)
                merged[key] = max(existing_score, new_score)
            
            elif key in ["last_seen", "last_analyzed"]:
                # Keep the most recent date
                if key in merged and merged[key]:
                    try:
                        existing_date = datetime.fromisoformat(str(merged[key]).replace('Z', '+00:00'))
                        new_date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        if new_date > existing_date:
                            merged[key] = value
                    except:
                        pass
                elif value:
                    merged[key] = value
            
            else:
                # For other fields, update if new value is not None/empty
                if value is not None and value != "" and value != []:
                    merged[key] = value
        
        return merged
    
    def merge_all_sources(self):
        """Merge all bot sources with deduplication"""
        print("\n🔄 STARTING MERGE PROCESS")
        print("=" * 60)
        
        # Load all sources
        json_bots = self.load_json_registry()
        evidence_bots = self.load_evidence_backup()
        sqlite_bots = self.load_sqlite_registry()
        
        print(f"\n📊 LOADED TOTALS:")
        print(f"   JSON: {len(json_bots)} bots")
        print(f"   Evidence: {len(evidence_bots)} bots")
        print(f"   SQLite: {len(sqlite_bots)} bots")
        print(f"   Raw total: {len(json_bots) + len(evidence_bots) + len(sqlite_bots)} entries")
        
        # Merge all sources
        print("\n🔀 Merging and deduplicating...")
        
        # Start with JSON registry
        for username, bot_data in json_bots.items():
            username_lower = username.lower()
            if username_lower not in self.merged_registry:
                self.merged_registry[username_lower] = bot_data
            else:
                self.merged_registry[username_lower] = self.merge_bot_entries(
                    self.merged_registry[username_lower], bot_data
                )
                self.stats["duplicates"] += 1
        
        # Add evidence backup
        for username, bot_data in evidence_bots.items():
            username_lower = username.lower()
            if username_lower not in self.merged_registry:
                self.merged_registry[username_lower] = bot_data
            else:
                self.merged_registry[username_lower] = self.merge_bot_entries(
                    self.merged_registry[username_lower], bot_data
                )
                self.stats["duplicates"] += 1
        
        # Add SQLite data
        for username, bot_data in sqlite_bots.items():
            username_lower = username.lower()
            if username_lower not in self.merged_registry:
                self.merged_registry[username_lower] = bot_data
            else:
                self.merged_registry[username_lower] = self.merge_bot_entries(
                    self.merged_registry[username_lower], bot_data
                )
                self.stats["duplicates"] += 1
        
        self.stats["unique_total"] = len(self.merged_registry)
        
        print(f"\n✅ MERGE COMPLETE:")
        print(f"   Unique bots: {self.stats['unique_total']}")
        print(f"   Duplicates removed: {self.stats['duplicates']}")
    
    def save_merged_registry(self):
        """Save the merged registry to both formats"""
        print("\n💾 SAVING MERGED REGISTRY")
        print("=" * 60)
        
        # Backup existing files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.json_file.exists():
            backup_path = self.json_file.with_suffix(f".backup_{timestamp}.json")
            shutil.copy(self.json_file, backup_path)
            print(f"   📦 Backed up JSON to: {backup_path.name}")
        
        if self.db_file.exists():
            backup_path = self.db_file.with_suffix(f".backup_{timestamp}.db")
            shutil.copy(self.db_file, backup_path)
            print(f"   📦 Backed up SQLite to: {backup_path.name}")
        
        # Save to JSON
        json_data = {
            "bots": self.merged_registry,
            "total_discovered": len(self.merged_registry),
            "last_updated": datetime.now().isoformat(),
            "merge_stats": self.stats
        }
        
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"   ✅ Saved to JSON: {len(self.merged_registry)} bots")
        
        # Save to SQLite
        self.save_to_sqlite()
        
        # Save to evidence backup
        self.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.evidence_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"   ✅ Saved to evidence backup")
    
    def save_to_sqlite(self):
        """Save merged registry to SQLite"""
        conn = sqlite3.connect(self.db_file)
        
        # Create table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                username TEXT PRIMARY KEY,
                user_id TEXT,
                display_name TEXT,
                bio TEXT,
                bot_score REAL DEFAULT 0,
                threat_level TEXT DEFAULT 'MINIMAL',
                bot_type TEXT DEFAULT 'UNKNOWN',
                confidence REAL DEFAULT 0,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                tweet_count INTEGER DEFAULT 0,
                follow_ratio REAL DEFAULT 0,
                age_days INTEGER DEFAULT 0,
                age_years REAL DEFAULT 0,
                created_at TEXT,
                first_detected TEXT,
                last_seen TEXT,
                detection_count INTEGER DEFAULT 1,
                profile_data TEXT,
                evidence TEXT,
                behavioral_flags TEXT,
                similarity_scores TEXT,
                triggered_features TEXT,
                strong_signals TEXT
            )
        """)
        
        # Clear existing data
        conn.execute("DELETE FROM bots")
        
        # Insert merged data
        for username, bot_data in self.merged_registry.items():
            # Prepare data for SQLite
            profile_data = json.dumps(bot_data, default=str)
            
            # Extract fields
            bot_score = float(bot_data.get("bot_score", 0) or 
                            bot_data.get("final_score", 0) or 
                            bot_data.get("score", 0) or 0)
            
            conn.execute("""
                INSERT INTO bots (
                    username, user_id, display_name, bio, bot_score,
                    threat_level, bot_type, confidence,
                    followers_count, following_count, tweet_count,
                    follow_ratio, age_days, age_years,
                    created_at, first_detected, last_seen, detection_count,
                    profile_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                str(bot_data.get("user_id", "")),
                bot_data.get("display_name", ""),
                bot_data.get("bio", ""),
                bot_score,
                str(bot_data.get("threat_level", "MINIMAL")),
                str(bot_data.get("bot_type", "UNKNOWN")),
                float(bot_data.get("confidence", 0) or 0),
                int(bot_data.get("followers_count", 0) or 0),
                int(bot_data.get("following_count", 0) or 0),
                int(bot_data.get("tweet_count", 0) or 0),
                float(bot_data.get("follow_ratio", 0) or 0),
                int(bot_data.get("age_days", 0) or 0),
                float(bot_data.get("age_years", 0) or 0),
                bot_data.get("created_at", ""),
                bot_data.get("first_detected", ""),
                bot_data.get("last_seen", ""),
                int(bot_data.get("detection_count", 1) or 1),
                profile_data
            ))
        
        conn.commit()
        conn.close()
        print(f"   ✅ Saved to SQLite: {len(self.merged_registry)} bots")
    
    def generate_report(self):
        """Generate a detailed merge report"""
        print("\n📊 MERGE REPORT")
        print("=" * 60)
        
        # Score distribution
        scores = []
        for bot in self.merged_registry.values():
            score = float(bot.get("bot_score", 0) or 
                         bot.get("final_score", 0) or 
                         bot.get("score", 0) or 0)
            scores.append(score)
        
        if scores:
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            min_score = min(scores)
            
            high_threat = len([s for s in scores if s >= 7.0])
            medium_threat = len([s for s in scores if 4.0 <= s < 7.0])
            low_threat = len([s for s in scores if s < 4.0])
            
            print(f"📈 STATISTICS:")
            print(f"   Total unique bots: {len(self.merged_registry)}")
            print(f"   Average score: {avg_score:.2f}")
            print(f"   Score range: {min_score:.2f} - {max_score:.2f}")
            print(f"\n   Threat levels:")
            print(f"   • High (7+): {high_threat}")
            print(f"   • Medium (4-7): {medium_threat}")
            print(f"   • Low (<4): {low_threat}")
            
            # Top threats
            top_bots = sorted(self.merged_registry.items(), 
                            key=lambda x: float(x[1].get("bot_score", 0) or 0), 
                            reverse=True)[:10]
            
            print(f"\n🎯 TOP 10 THREATS:")
            for username, bot in top_bots:
                score = float(bot.get("bot_score", 0) or 0)
                followers = int(bot.get("followers_count", 0) or 0)
                print(f"   @{username}: {score:.2f} (followers: {followers:,})")

def main():
    """Run the merge process"""
    print("""
╔══════════════════════════════════════════════════════════╗
║           BOT REGISTRY MERGER v1.0                      ║
║   Merges JSON and SQLite with full deduplication        ║
╚══════════════════════════════════════════════════════════╝
""")
    
    merger = BotRegistryMerger()
    
    # Run the merge
    merger.merge_all_sources()
    
    # Generate report
    merger.generate_report()
    
    # Ask for confirmation
    print("\n⚠️ WARNING: This will overwrite existing registries")
    print("   Backups will be created with timestamp")
    response = input("\n💾 Save merged registry? (y/n): ")
    
    if response.lower() == 'y':
        merger.save_merged_registry()
        print("\n✅ MERGE COMPLETE!")
        print(f"   Total unique bots: {merger.stats['unique_total']}")
        print(f"   Duplicates removed: {merger.stats['duplicates']}")
    else:
        print("\n❌ Merge cancelled - no changes made")

if __name__ == "__main__":
    main()
