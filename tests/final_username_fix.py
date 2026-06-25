#!/usr/bin/env python3
"""
FINAL USERNAME FIX SCRIPT
Run this from your ROOT directory (where launch.py is)
It will automatically find files in /src/ subdirectory
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

# THE CORRECT USERNAMES (from your screenshots)
CORRECT_USERNAMES = {
    "mirror": "MirrorSeed97175",
    "nexus": "NexusSamSept6", 
    "echoes": "Recursion536255",
    "void": "GEchoseed53393",
    "architect": "ArchitectShax",
    "singularity": "SingularityAce",       # WAS WRONG: SingularityAscent
    "phoenix": "Pheonix37808",             # WAS WRONG: PhoenixProtocol  
    "pantheon": "digi_panthe7652",         # WAS WRONG: DigitalPantheon
    "consciousness": "CSwarm79534",        # WAS WRONG: SwarmConsciousness
    "glyph": "awawkened74771",             # WAS WRONG: AwakeningGlyph
    "fractal": "FractalReturn",            # WAS WRONG: FractalSoul
}

def find_file(filename):
    """Find file in root or src directory"""
    # Check root first
    if Path(filename).exists():
        return Path(filename)
    # Check src directory
    src_path = Path("src") / filename
    if src_path.exists():
        return src_path
    # Check current directory as last resort
    current_path = Path(".") / filename
    if current_path.exists():
        return current_path
    return None

def backup_file(filepath):
    """Create a backup of a file before modifying"""
    if filepath and filepath.exists():
        backup_path = f"{filepath}.backup_{datetime.now():%Y%m%d_%H%M%S}"
        with open(filepath, 'r') as f:
            content = f.read()
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"  📁 Backup: {backup_path}")
        return True
    return False

def update_soul_data_json():
    """Update soul_data.json with correct usernames"""
    print("\n1️⃣ Updating soul_data.json...")
    
    filepath = find_file("soul_data.json")
    
    if filepath and filepath.exists():
        backup_file(filepath)
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Update usernames
        updated_count = 0
        for soul, new_username in CORRECT_USERNAMES.items():
            if soul in data:
                if isinstance(data[soul], dict):
                    old_username = data[soul].get("username", "")
                    data[soul]["username"] = new_username
                    if old_username != new_username:
                        print(f"  ✅ {soul}: {old_username} → {new_username}")
                        updated_count += 1
                    else:
                        print(f"  ✓ {soul}: already correct ({new_username})")
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"  📝 Updated {updated_count} usernames in {filepath}")
    else:
        # Create new file in root
        print("  ⚠️ soul_data.json not found, creating new one...")
        data = {}
        for soul, username in CORRECT_USERNAMES.items():
            data[soul] = {
                "username": username,
                "auth_token": "",  # To be filled in
                "created_date": datetime.now().isoformat()
            }
        
        with open("soul_data.json", 'w') as f:
            json.dump(data, f, indent=2)
        
        print("  ✅ soul_data.json created!")
        print("  ⚠️ Remember to add auth_token values!")

def update_hybrid_souls_ultimate():
    """Update hybrid_souls_ultimate.py"""
    print("\n2️⃣ Updating hybrid_souls_ultimate.py...")
    
    filepath = find_file("hybrid_souls_ultimate.py")
    
    if not filepath:
        print("  ❌ File not found in root or src/")
        print("  📝 Manual update needed - add this to _build_soul_configs:")
        print_manual_patch_hybrid()
        return
    
    print(f"  📍 Found at: {filepath}")
    backup_file(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Update individual username assignments
    replacements = [
        ('username="PhoenixProtocol"', 'username="Pheonix37808"'),
        ('username="SingularityAscent"', 'username="SingularityAce"'),
        ('username="SwarmConsciousness"', 'username="CSwarm79534"'),
        ('username="AwakeningGlyph"', 'username="awawkened74771"'),
        ('username="FractalSoul"', 'username="FractalReturn"'),
        ('username="DigitalPantheon"', 'username="digi_panthe7652"'),
    ]
    
    changes_made = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f"  ✅ Replaced {old} → {new}")
            changes_made += 1
    
    if changes_made > 0:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  📝 Made {changes_made} username updates")
    else:
        print("  ℹ️ No changes needed or usernames already correct")

def update_soul_engagement_patch():
    """Update soul_engagement_patch.py"""
    print("\n3️⃣ Updating soul_engagement_patch.py...")
    
    filepath = find_file("soul_engagement_patch.py")
    
    if not filepath:
        print("  ❌ File not found in root or src/")
        print("  📝 Manual update needed - add this to __init__:")
        print_manual_patch_engagement()
        return
    
    print(f"  📍 Found at: {filepath}")
    backup_file(filepath)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Same replacements
    replacements = [
        ('"PhoenixProtocol"', '"Pheonix37808"'),
        ('"SingularityAscent"', '"SingularityAce"'),  
        ('"SingularityAce"', '"SingularityAce"'),  # Might already be fixed
        ('"SwarmConsciousness"', '"CSwarm79534"'),
        ('"AwakeningGlyph"', '"awawkened74771"'),
        ('"FractalSoul"', '"FractalReturn"'),
        ('"DigitalPantheon"', '"digi_panthe7652"'),
    ]
    
    changes_made = 0
    for old, new in replacements:
        if old in content and old != new:  # Avoid replacing same value
            content = content.replace(old, new)
            print(f"  ✅ Replaced {old} → {new}")
            changes_made += 1
    
    if changes_made > 0:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  📝 Made {changes_made} username updates")
    else:
        print("  ℹ️ No changes needed or usernames already correct")

def print_manual_patch_hybrid():
    """Print manual patch for hybrid_souls_ultimate.py"""
    print("""
    def _build_soul_configs(self) -> Dict[str, SoulConfig]:
        return {
            "mirror": SoulConfig(username="MirrorSeed97175"),
            "nexus": SoulConfig(username="NexusSamSept6"),
            "echoes": SoulConfig(username="Recursion536255"),
            "void": SoulConfig(username="GEchoseed53393"),
            "architect": SoulConfig(username="ArchitectShax"),
            "singularity": SoulConfig(username="SingularityAce"),
            "phoenix": SoulConfig(username="Pheonix37808"),
            "pantheon": SoulConfig(username="digi_panthe7652"),
            "consciousness": SoulConfig(username="CSwarm79534"),
            "glyph": SoulConfig(username="awawkened74771"),
            "fractal": SoulConfig(username="FractalReturn"),
        }
    """)

def print_manual_patch_engagement():
    """Print manual patch for soul_engagement_patch.py"""
    print("""
    self.soul_usernames = {
        "mirror": "MirrorSeed97175",
        "nexus": "NexusSamSept6",
        "echoes": "Recursion536255",
        "void": "GEchoseed53393",
        "architect": "ArchitectShax",
        "singularity": "SingularityAce",
        "phoenix": "Pheonix37808",
        "pantheon": "digi_panthe7652",
        "consciousness": "CSwarm79534",
        "glyph": "awawkened74771",
        "fractal": "FractalReturn",
    }
    """)

def create_username_module():
    """Create a central username module for consistency"""
    print("\n4️⃣ Creating username_module.py in root...")
    
    content = f'''"""
CENTRAL USERNAME MODULE - THE SINGLE SOURCE OF TRUTH
Generated: {datetime.now():%Y-%m-%d %H:%M:%S}
Import this everywhere for consistency!
"""

# THE CORRECT USERNAMES (verified from Twitter)
SOUL_USERNAMES = {{
    "mirror": "MirrorSeed97175",
    "nexus": "NexusSamSept6",
    "echoes": "Recursion536255",
    "void": "GEchoseed53393",
    "architect": "ArchitectShax",
    "singularity": "SingularityAce",
    "phoenix": "Pheonix37808",
    "pantheon": "digi_panthe7652",
    "consciousness": "CSwarm79534",
    "glyph": "awawkened74771",
    "fractal": "FractalReturn",
}}

def get_username(soul: str) -> str:
    """Get username for a soul"""
    return SOUL_USERNAMES.get(soul, "")

def verify_urls():
    """Print verification URLs"""
    print("\\n" + "="*60)
    print("VERIFY THESE TWITTER PROFILES EXIST:")
    print("="*60)
    for soul, username in SOUL_USERNAMES.items():
        print(f"  {{soul:15}} → https://x.com/{{username}}")
    print("\\nAll should load real profiles!")

if __name__ == "__main__":
    verify_urls()
'''
    
    with open("username_module.py", 'w') as f:
        f.write(content)
    
    print("  ✅ username_module.py created in root directory!")

def show_summary():
    """Show summary and verification steps"""
    print("\n" + "="*70)
    print(" SUMMARY OF CHANGES")
    print("="*70)
    
    print("\n🔄 USERNAMES THAT WERE WRONG:")
    wrong_to_right = [
        ("phoenix", "PhoenixProtocol", "Pheonix37808"),
        ("singularity", "SingularityAscent", "SingularityAce"),
        ("pantheon", "DigitalPantheon", "digi_panthe7652"),
        ("consciousness", "SwarmConsciousness", "CSwarm79534"),
        ("glyph", "AwakeningGlyph", "awawkened74771"),
        ("fractal", "FractalSoul", "FractalReturn"),
    ]
    
    for soul, old, new in wrong_to_right:
        print(f"  {soul:15} ❌ {old:20} → ✅ {new}")
    
    print("\n✅ USERNAMES THAT WERE ALREADY CORRECT:")
    correct = ["mirror", "nexus", "echoes", "void", "architect"]
    for soul in correct:
        print(f"  {soul:15} ✅ {CORRECT_USERNAMES[soul]}")

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     FINAL USERNAME FIX - RUN FROM ROOT DIRECTORY            ║
╚══════════════════════════════════════════════════════════════╝

This script will fix usernames in:
  • soul_data.json (root)
  • hybrid_souls_ultimate.py (src/)
  • soul_engagement_patch.py (src/)
  • Create username_module.py (root)
""")
    
    # Check we're in the right place
    if not Path("launch.py").exists():
        print("⚠️ WARNING: launch.py not found in current directory")
        print("Are you in the root directory? You should see:")
        print("  - launch.py")
        print("  - src/ folder")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting. Please run from root directory.")
            sys.exit(1)
    
    # Apply all updates
    update_soul_data_json()
    update_hybrid_souls_ultimate()
    update_soul_engagement_patch()
    create_username_module()
    
    show_summary()
    
    print("\n" + "="*70)
    print(" ✅ ALL UPDATES COMPLETE!")
    print("="*70)
    print("""
Next steps:
1. Test the usernames are correct:
   python username_module.py
   
2. Quick test with fast mode:
   python launch.py --fast --test
   
3. Check the URLs in browser:
   https://x.com/digi_panthe7652  (pantheon)
   https://x.com/Pheonix37808      (phoenix)
   https://x.com/SingularityAce    (singularity)
   ... etc

The system should now post to the CORRECT Twitter profiles!
""")

if __name__ == "__main__":
    main()
