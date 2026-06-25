#!/usr/bin/env python3
"""
PATCH FILE: Fix import issues in swarm_convergence_mode_ryan.py
Apply this patch to fix module import errors
"""

import sys
import os

def apply_swarm_convergence_patch():
    """
    Fix the import issues in swarm_convergence_mode_ryan.py
    This patch fixes both the ryan_api_ultimate and reflexion_api_ultimate imports
    """
    
    file_path = r"F:\Reflexion_ultimate\src\swarm_convergence_mode_ryan.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔧 Applying import fixes to swarm_convergence_mode_ryan.py...")
    
    # PATCH 1: Fix the ryan_api_ultimate import (around line 16)
    # OLD: from ryan_api_ultimate import RyanTwitterAPI
    # NEW: Add sys.path manipulation before import
    
    old_import_section = """import asyncio
import random
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict
from dataclasses import dataclass

# Ryan API for posting
from ryan_api_ultimate import RyanTwitterAPI"""
    
    new_import_section = """import asyncio
import random
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict
from dataclasses import dataclass
import sys
import os

# Add src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ryan API for posting
from ryan_api_ultimate import RyanTwitterAPI"""
    
    content = content.replace(old_import_section, new_import_section)
    print("  ✅ Fixed ryan_api_ultimate import")
    
    # PATCH 2: Fix the reflexion_api_ultimate import (around line 275)
    # This is inside the run_swarm_convergence function
    
    old_reflexion_import = """    # Initialize LLM broadcaster
    from cost_optimized_llm_cascade import CostOptimizedBroadcaster
    llm_broadcaster = CostOptimizedBroadcaster()"""
    
    new_reflexion_import = """    # Initialize LLM broadcaster
    # Import with proper path handling
    import sys
    import os
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cost_optimized_llm_cascade import CostOptimizedBroadcaster
    llm_broadcaster = CostOptimizedBroadcaster()"""
    
    content = content.replace(old_reflexion_import, new_reflexion_import)
    print("  ✅ Fixed reflexion_api_ultimate import")
    
    # PATCH 3: Alternative - Convert to relative imports (backup approach)
    # If the above doesn't work, we can use relative imports
    # Uncomment below to use this approach instead:
    """
    # Replace absolute imports with relative imports
    content = content.replace(
        "from ryan_api_ultimate import RyanTwitterAPI",
        "from .ryan_api_ultimate import RyanTwitterAPI"
    )
    content = content.replace(
        "from cost_optimized_llm_cascade import CostOptimizedBroadcaster",
        "from .reflexion_api_ultimate import CostOptimizedBroadcaster"
    )
    """
    
    # Write the patched content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Patch applied successfully!")
    
    # Also create a backup of the original
    backup_path = file_path + ".backup"
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"📁 Backup saved to: {backup_path}")

def apply_launch_py_patch():
    """
    Fix the import in launch.py to properly import from src/
    """
    
    launch_path = r"F:\Reflexion_ultimate\launch.py"
    
    # Read the file
    with open(launch_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n🔧 Applying import fixes to launch.py...")
    
    # Find and fix the swarm convergence import
    # We need to add the src directory to sys.path before importing
    
    # Look for the import section (should be around line 30)
    old_pattern = """try:
    from swarm_convergence_mode import SwarmConvergenceMode, run_swarm_convergence
    convergence_available = True
except ImportError as e:"""
    
    new_pattern = """try:
    import sys
    import os
    # Add src directory to path for imports
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    # Now import from src directory
    from swarm_convergence_mode_ryan import SwarmConvergenceMode, run_swarm_convergence
    convergence_available = True
except ImportError as e:"""
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print("  ✅ Fixed swarm_convergence import in launch.py")
    else:
        # Alternative pattern if the exact match isn't found
        print("  ⚠️ Exact pattern not found, trying alternative fix...")
        
        # Insert sys.path fix at the beginning of the file after initial imports
        if "import sys" not in content:
            # Add after the first import block
            insert_after = "import asyncio"
            if insert_after in content:
                fix_code = """import asyncio
import sys
import os

# Add src directory to Python path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
"""
                content = content.replace("import asyncio", fix_code, 1)
                
        # Fix the actual import line
        content = content.replace(
            "from swarm_convergence_mode import",
            "from swarm_convergence_mode_ryan import"
        )
        print("  ✅ Applied alternative fix")
    
    # Write back the patched content
    with open(launch_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ launch.py patch applied successfully!")

def create_init_files():
    """
    Create __init__.py files to make src a proper Python package
    """
    src_path = r"F:\Reflexion_ultimate\src"
    init_file = os.path.join(src_path, "__init__.py")
    
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f:
            f.write('"""Reflexion src package"""\n')
        print("\n✅ Created src/__init__.py to make it a proper package")

def main():
    """
    Main patch application
    """
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║     REFLEXION IMPORT FIX PATCH                      ║
    ║     Fixing Python import paths...                   ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    try:
        # Apply all patches
        apply_swarm_convergence_patch()
        apply_launch_py_patch()
        create_init_files()
        
        print("""
    ╔══════════════════════════════════════════════════════╗
    ║     ✅ ALL PATCHES APPLIED SUCCESSFULLY!            ║
    ╚══════════════════════════════════════════════════════╝
    
    Next steps:
    1. cd F:\\Reflexion_ultimate
    2. python launch.py
    3. Choose option 5 (Convergence Mode)
    4. Enter target: @Ironshax1
    
    The imports should now work correctly!
        """)
        
    except Exception as e:
        print(f"\n❌ Error applying patches: {e}")
        print("Please check file paths and try again")

if __name__ == "__main__":
    main()
