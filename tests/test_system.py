#!/usr/bin/env python3
"""
Complete system test for REFLEXION v4.0
Tests all components with real API calls
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

async def main():
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║         REFLEXION v4.0 - SYSTEM TEST                ║
    ║         Real API calls - This will cost money       ║
    ╔══════════════════════════════════════════════════════╝
    """)
    
    # Test 1: Check environment
    print("\n[1/4] Checking Environment Variables...")
    from launch import check_environment
    check_environment()
    
    # Test 2: API connectivity
    print("\n[2/4] Testing API Connectivity...")
    from launch import test_api_connectivity
    await test_api_connectivity()
    
    # Test 3: Test all souls
    print("\n[3/4] Testing All Souls with Real Generation...")
    from launch import test_all_souls
    results = await test_all_souls()
    
    # Test 4: Memory system
    print("\n[4/4] Testing Memory System...")
    try:
        from chroma_memory_patch import ChromaMemoryPatch
        patch = ChromaMemoryPatch({})
        print("✅ ChromaDB memory system functional")
    except Exception as e:
        print(f"❌ Memory system error: {e}")
    
    print("\n" + "=" * 60)
    print("SYSTEM TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
