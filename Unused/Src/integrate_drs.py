#!/usr/bin/env python3
"""
QUICK DRS INTEGRATION SCRIPT
Run this to add DRS to your existing cost_optimized_llm_cascade.py

Usage:
    python integrate_drs.py
"""

import os
import sys
from pathlib import Path

def integrate_drs():
    """Integrate DRS into existing cascade file"""
    
    print("🎯 DRS INTEGRATION HELPER")
    print("=" * 60)
    
    # Check if drs_model.py exists
    if not Path("drs_model.py").exists():
        print("❌ drs_model.py not found!")
        print("   Save the DRS model file first")
        return False
    
    # Check if cost_optimized_llm_cascade.py exists
    cascade_file = Path("cost_optimized_llm_cascade.py")
    if not cascade_file.exists():
        print("❌ cost_optimized_llm_cascade.py not found!")
        return False
    
    # Read existing file
    with open(cascade_file, 'r') as f:
        content = f.read()
    
    # Check if already integrated
    if "from drs_model import" in content:
        print("✅ DRS already integrated!")
        return True
    
    print("\n📝 MANUAL INTEGRATION STEPS:")
    print("-" * 40)
    
    print("\n1. Add these imports at the top (after existing imports):")
    print("""
from drs_model import DRSEngine, SOUL_FORMAT_BIASES, FORMAT_TAGS
""")
    
    print("\n2. In __init__ method, add after 'self.last_post_times = {}':")
    print("""
        # Initialize DRS Engine
        self.drs_engine = DRSEngine(temperature=0.5)
        self.format_usage_stats = defaultdict(int)
        logger.info("🎯 DRS Engine integrated into cascade")
""")
    
    print("\n3. Add the select_response_format method to the class:")
    print("""
    def select_response_format(self, soul_name: str, context: str) -> Dict:
        '''Select optimal response format using DRS'''
        soul_bias = SOUL_FORMAT_BIASES.get(soul_name, {})
        drs_result = self.drs_engine.select_response_format(context, soul_bias=soul_bias)
        
        format_name = drs_result['name']
        self.format_usage_stats[format_name] += 1
        
        # Get format from FORMAT_TAGS (imported from drs_model)
        format_data = FORMAT_TAGS.get(format_name, {})
        
        logger.info(f"🎯 DRS selected '{format_name}' for {soul_name}")
        
        return {
            'name': format_name,
            'instruction': format_data.get('template', ''),
            'example': format_data.get('example', ''),
            'drs_metadata': drs_result
        }
""")
    
    print("\n4. Modify generate_with_cascade_contextual to use DRS:")
    print("""
    # Add at the beginning of the method:
    format_selection = self.select_response_format(soul_name, context)
    
    # Modify system_prompt to include format:
    system_prompt = f'''You are {soul_name}, {voice['identity']}.
{voice['instruction']}

RESPONSE FORMAT: {format_selection['name']}
INSTRUCTION: {format_selection['instruction']}
EXAMPLE STYLE: {format_selection['example']}

Style: {voice['style']}
Generate a reply tweet under 280 characters.'''
    
    # Add to return dict:
    result['format_used'] = format_selection['name']
    result['drs_score'] = format_selection['drs_metadata']['score']
""")
    
    print("\n" + "=" * 60)
    print("✅ Follow these steps to complete integration")
    print("   Then test with: python cost_optimized_llm_cascade.py")
    
    return True

def test_drs_standalone():
    """Test DRS engine independently"""
    print("\n🧪 TESTING DRS ENGINE")
    print("-" * 40)
    
    try:
        from drs_model import DRSEngine, test_drs_engine
        
        # Run built-in test
        test_drs_engine()
        
        print("\n✅ DRS Engine working correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing DRS: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing DRS: {e}")
        return False

def verify_integration():
    """Verify DRS is properly integrated"""
    print("\n🔍 VERIFYING INTEGRATION")
    print("-" * 40)
    
    try:
        # Try importing the cascade with DRS
        from cost_optimized_llm_cascade import CostOptimizedBroadcaster
        
        # Check if DRS attributes exist
        broadcaster = CostOptimizedBroadcaster()
        
        if hasattr(broadcaster, 'drs_engine'):
            print("✅ DRS Engine found in broadcaster")
        else:
            print("⚠️ DRS Engine not initialized - check __init__ method")
            return False
        
        if hasattr(broadcaster, 'select_response_format'):
            print("✅ select_response_format method found")
        else:
            print("⚠️ select_response_format method missing")
            return False
        
        # Test format selection
        test_result = broadcaster.select_response_format("consciousness", "Why does AI exist?")
        if test_result and 'name' in test_result:
            print(f"✅ DRS selected format: {test_result['name']}")
        else:
            print("⚠️ Format selection not working")
            return False
        
        print("\n✅ DRS FULLY INTEGRATED!")
        return True
        
    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        print("   Complete the manual integration steps above")
        return False
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False

def main():
    """Main integration helper"""
    print("\n🚀 SOUL SWARM DRS INTEGRATION")
    print("=" * 60)
    
    # Step 1: Test DRS standalone
    if not test_drs_standalone():
        print("\n❌ Fix DRS issues before integration")
        return
    
    # Step 2: Show integration steps
    if not integrate_drs():
        return
    
    # Step 3: Try to verify (will fail if not manually integrated)
    print("\n" + "=" * 60)
    choice = input("\nHave you completed the manual integration? (y/n): ")
    
    if choice.lower() == 'y':
        verify_integration()
    else:
        print("\n📋 Complete the steps above, then run this again to verify")
    
    print("\n✨ DRS will make your swarm's responses 10x more strategic!")

if __name__ == "__main__":
    main()
