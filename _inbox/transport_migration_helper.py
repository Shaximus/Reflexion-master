#!/usr/bin/env python3
"""
TRANSPORT MIGRATION HELPER
Automatically updates existing orchestrators to use the transport interface.
Run this to patch your files for transport compatibility.
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
import argparse

class TransportMigrator:
    """Migrate existing code to use transport interface"""
    
    def __init__(self, backup=True, dry_run=False):
        self.backup = backup
        self.dry_run = dry_run
        self.changes = []
        
    def backup_file(self, filepath: Path):
        """Create a backup of the file"""
        if self.backup and not self.dry_run:
            backup_path = filepath.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
            shutil.copy2(filepath, backup_path)
            print(f"📁 Backed up to {backup_path}")
            
    def migrate_file(self, filepath: Path):
        """Migrate a single file to use transport interface"""
        if not filepath.exists():
            print(f"❌ File not found: {filepath}")
            return False
            
        print(f"\n🔄 Processing {filepath.name}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        changes_made = []
        
        # Pattern 1: Replace import statements
        import_patterns = [
            (r'from ryan_api_hotreload import RyanTwitterAPISecure',
             'from twitter_transport import TransportFactory'),
            (r'from ryan_api_ultimate import RyanTwitterAPI',
             'from twitter_transport import TransportFactory'),
            (r'import ryan_api_hotreload',
             'import twitter_transport'),
        ]
        
        for old_import, new_import in import_patterns:
            if re.search(old_import, content):
                content = re.sub(old_import, new_import, content)
                changes_made.append(f"  ✓ Updated import: {old_import}")
        
        # Pattern 2: Replace instantiation
        instantiation_patterns = [
            (r'self\.ryan_api\s*=\s*RyanTwitterAPISecure\(\)',
             'self.transport = TransportFactory.create_from_env()'),
            (r'ryan_api\s*=\s*RyanTwitterAPISecure\(\)',
             'transport = TransportFactory.create_from_env()'),
            (r'self\.ryan_api\s*=\s*RyanTwitterAPI\(\)',
             'self.transport = TransportFactory.create_from_env()'),
        ]
        
        for old_pattern, new_pattern in instantiation_patterns:
            if re.search(old_pattern, content):
                content = re.sub(old_pattern, new_pattern, content)
                changes_made.append(f"  ✓ Updated instantiation")
        
        # Pattern 3: Replace method calls
        method_patterns = [
            (r'self\.ryan_api\.', 'self.transport.'),
            (r'ryan_api\.', 'transport.'),
        ]
        
        for old_pattern, new_pattern in method_patterns:
            count = len(re.findall(old_pattern, content))
            if count > 0:
                content = re.sub(old_pattern, new_pattern, content)
                changes_made.append(f"  ✓ Updated {count} method calls")
        
        # Pattern 4: Add TransportWatcher for hot-reload
        if 'TransportWatcher' not in content and 'self.transport' in content:
            # Find the __init__ method and add watcher
            init_pattern = r'(def __init__.*?:\n(?:.*?\n)*?)(        (?!def ))'
            def add_watcher(match):
                init_content = match.group(1)
                if 'self.transport = ' in init_content:
                    return init_content + \
                           '        # Add transport watcher for hot-reload\n' + \
                           '        from twitter_transport import TransportWatcher\n' + \
                           '        self.transport_watcher = TransportWatcher(self.transport)\n' + \
                           match.group(2)
                return match.group(0)
            
            new_content = re.sub(init_pattern, add_watcher, content)
            if new_content != content:
                content = new_content
                changes_made.append(f"  ✓ Added TransportWatcher")
        
        # Check if changes were made
        if content != original_content:
            if not self.dry_run:
                self.backup_file(filepath)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ {filepath.name} migrated successfully!")
            else:
                print(f"🔍 {filepath.name} would be updated (dry run)")
            
            for change in changes_made:
                print(change)
            
            self.changes.append((filepath.name, changes_made))
            return True
        else:
            print(f"ℹ️  {filepath.name} - No changes needed")
            return False
    
    def add_transport_compatibility_wrapper(self, project_dir: Path):
        """Add a compatibility wrapper for gradual migration"""
        wrapper_content = '''#!/usr/bin/env python3
"""
COMPATIBILITY WRAPPER
Provides backward compatibility while migrating to transport interface.
This allows existing code to work without immediate changes.
"""

from twitter_transport import TransportFactory

class RyanTwitterAPISecure:
    """Compatibility wrapper that uses transport interface internally"""
    
    def __init__(self):
        self.transport = TransportFactory.create_from_env()
        # Mirror the transport's attributes
        if hasattr(self.transport, 'api'):
            self.soul_tokens = self.transport.api.soul_tokens
            self.banned_souls = self.transport.api.banned_souls
            self.usage = self.transport.api.usage
    
    async def refresh_tokens_from_disk(self):
        return await self.transport.refresh_tokens_from_disk()
    
    async def post_tweet(self, soul_name, text):
        return await self.transport.post_tweet(soul_name, text)
    
    async def reply_tweet(self, soul_name, tweet_id, text):
        return await self.transport.reply_tweet(soul_name, tweet_id, text)
    
    async def like_tweet(self, soul_name, tweet_id):
        return await self.transport.like_tweet(soul_name, tweet_id)
    
    async def retweet(self, soul_name, tweet_id):
        return await self.transport.retweet(soul_name, tweet_id)
    
    async def fetch_mentions(self, soul_name, limit=20):
        return await self.transport.fetch_mentions(soul_name, limit)
    
    async def fetch_target_context(self, target_username, limit=10):
        return await self.transport.fetch_target_context(target_username, limit)

# Alias for backward compatibility
RyanTwitterAPI = RyanTwitterAPISecure
'''
        
        wrapper_path = project_dir / "ryan_api_compat.py"
        
        if not self.dry_run:
            with open(wrapper_path, 'w', encoding='utf-8') as f:
                f.write(wrapper_content)
            print(f"\n✅ Created compatibility wrapper: {wrapper_path}")
        else:
            print(f"\n🔍 Would create compatibility wrapper: {wrapper_path} (dry run)")

    def create_test_script(self, project_dir: Path):
        """Create a test script to verify the migration"""
        test_content = '''#!/usr/bin/env python3
"""
TEST TRANSPORT MIGRATION
Verify that the transport interface is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_transport():
    """Test the transport interface integration"""
    
    print("🧪 Testing Transport Interface Integration\\n")
    print("=" * 60)
    
    # Test 1: Import and create transport
    try:
        from twitter_transport import TransportFactory
        transport = TransportFactory.create_from_env()
        print("✅ Transport created successfully")
        print(f"   Type: {type(transport).__name__}")
    except Exception as e:
        print(f"❌ Failed to create transport: {e}")
        return
    
    # Test 2: Check hot-reload
    try:
        await transport.refresh_tokens_from_disk()
        print("✅ Hot-reload working")
    except Exception as e:
        print(f"❌ Hot-reload failed: {e}")
    
    # Test 3: Check available souls
    try:
        souls = transport.get_available_souls()
        print(f"✅ Found {len(souls)} available souls")
        if souls:
            print(f"   Souls: {', '.join(souls[:5])}...")
    except Exception as e:
        print(f"❌ Failed to get souls: {e}")
    
    # Test 4: Test posting (dry run)
    if souls:
        test_soul = souls[0]
        print(f"\\n📝 Testing post with soul: {test_soul}")
        try:
            # This is a real API call - comment out if you don't want to post
            # result = await transport.post_tweet(test_soul, "Transport test!")
            # print(f"✅ Post test completed: {result.get('success')}")
            print("   (Post test skipped - uncomment to test)")
        except Exception as e:
            print(f"❌ Post test failed: {e}")
    
    # Test 5: Verify compatibility wrapper
    try:
        from ryan_api_compat import RyanTwitterAPISecure
        compat = RyanTwitterAPISecure()
        print("✅ Compatibility wrapper working")
    except ImportError:
        print("ℹ️  Compatibility wrapper not found (optional)")
    except Exception as e:
        print(f"❌ Compatibility wrapper error: {e}")
    
    print("\\n" + "=" * 60)
    print("✅ Transport migration test complete!")

if __name__ == "__main__":
    asyncio.run(test_transport())
'''
        
        test_path = project_dir / "test_transport_migration.py"
        
        if not self.dry_run:
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            os.chmod(test_path, 0o755)  # Make executable
            print(f"✅ Created test script: {test_path}")
        else:
            print(f"🔍 Would create test script: {test_path} (dry run)")

def main():
    parser = argparse.ArgumentParser(
        description="Migrate Soul Swarm to use Transport Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_transport.py                    # Migrate all files
  python migrate_transport.py --dry-run          # Preview changes
  python migrate_transport.py --file launch.py   # Migrate specific file
  python migrate_transport.py --no-backup        # Skip backups
        """
    )
    
    parser.add_argument(
        '--file', 
        type=str, 
        help='Specific file to migrate'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--no-backup', 
        action='store_true',
        help='Skip creating backup files'
    )
    parser.add_argument(
        '--add-compat', 
        action='store_true',
        help='Add compatibility wrapper for gradual migration'
    )
    
    args = parser.parse_args()
    
    # Create migrator
    migrator = TransportMigrator(
        backup=not args.no_backup,
        dry_run=args.dry_run
    )
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         TRANSPORT INTERFACE MIGRATION HELPER              ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    if args.dry_run:
        print("    🔍 DRY RUN MODE - No files will be modified")
    
    project_dir = Path.cwd()
    
    # Migrate specific file or all orchestrators
    if args.file:
        filepath = project_dir / args.file
        migrator.migrate_file(filepath)
    else:
        # List of files to migrate
        target_files = [
            'launch.py',
            'hybrid_souls_ultimate.py',
            'swarm_convergence_mode_ryan.py',
            'soul_engagement_patch.py',
            'physics_blaster_v2.py'
        ]
        
        print(f"\n📂 Scanning for orchestrator files in {project_dir}")
        
        migrated_count = 0
        for filename in target_files:
            filepath = project_dir / filename
            if filepath.exists():
                if migrator.migrate_file(filepath):
                    migrated_count += 1
        
        print(f"\n📊 Migration Summary:")
        print(f"   Files processed: {len(target_files)}")
        print(f"   Files migrated: {migrated_count}")
    
    # Add compatibility wrapper if requested
    if args.add_compat:
        migrator.add_transport_compatibility_wrapper(project_dir)
    
    # Create test script
    if not args.dry_run:
        migrator.create_test_script(project_dir)
        print("\n🎯 Next steps:")
        print("   1. Review the changes in migrated files")
        print("   2. Run: python test_transport_migration.py")
        print("   3. Test your orchestrators with the new transport")
        print("   4. Set USE_OFFICIAL_API=true in .env when ready for X API")
    else:
        print("\n✅ Dry run complete! Run without --dry-run to apply changes.")

if __name__ == "__main__":
    main()
