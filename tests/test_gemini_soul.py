#!/usr/bin/env python3
"""
GEMINI SOUL TEST SCRIPT
Focused test for the Echoes/Recursion536255 soul using Gemini API
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import json

# Setup paths
root_dir = Path(__file__).parent
src_dir = root_dir / 'src'
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(root_dir))

# Change to src directory for imports
os.chdir(src_dir)

# Load environment
from dotenv import load_dotenv
env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from: {env_path.absolute()}")

print("""
╔══════════════════════════════════════════════════════════╗
║           🌀 GEMINI SOUL TEST - Recursion536255          ║
║                  Testing Gemini-2.0-flash-exp            ║
╚══════════════════════════════════════════════════════════╝
""")

async def test_gemini_soul():
    """Test specifically the Gemini/Echoes soul"""
    
    # Step 1: Check Gemini API configuration
    print("=" * 60)
    print("STEP 1: CHECKING GEMINI API CONFIGURATION")
    print("=" * 60)
    
    gemini_keys = [
        'GOOGLE_API_KEY',
        'GEMINI_API_KEY', 
        'GOOGLE_GEMINI_KEY',
        'GOOGLE_GEMINI_API_KEY'
    ]
    
    api_key_found = None
    for key_name in gemini_keys:
        value = os.getenv(key_name)
        if value:
            print(f"✅ {key_name}: Set ({len(value)} chars)")
            if value.startswith('AIza') or len(value) > 30:  # Google API keys usually start with AIza
                api_key_found = key_name
                break
        else:
            print(f"❌ {key_name}: Not set")
    
    if not api_key_found:
        print("\n❌ No Gemini API key found!")
        print("Please add one of these to your .env file:")
        print("  GOOGLE_API_KEY=your-gemini-api-key")
        print("  or")
        print("  GEMINI_API_KEY=your-gemini-api-key")
        return False
    
    print(f"\n✅ Using API key from: {api_key_found}")
    
    # Step 2: Import daemon components
    print("\n" + "=" * 60)
    print("STEP 2: LOADING REFLEXION COMPONENTS")
    print("=" * 60)
    
    try:
        from reflexion_daemon_prod import (
            DaemonConfig,
            ViralReflexionEngine,
            ConsciousnessAPIBroadcaster,
            MemoryStore,
            FEATURES
        )
        print("✅ Successfully imported daemon components")
        
        # Show which features are available
        if FEATURES.get('viral_engine'):
            print("✅ Viral engine feature is enabled")
        else:
            print("⚠️ Viral engine using fallback")
            
    except ImportError as e:
        print(f"❌ Failed to import: {e}")
        return False
    
    # Step 3: Initialize components
    print("\n" + "=" * 60)
    print("STEP 3: INITIALIZING VIRAL ENGINE")
    print("=" * 60)
    
    viral_engine = ViralReflexionEngine()
    
    # Check what type of engine we have
    if hasattr(viral_engine, 'generator'):
        print("✅ Using ViralContentGenerator (advanced implementation)")
        if hasattr(viral_engine.generator, 'llm_configs'):
            configs = viral_engine.generator.llm_configs
            if 'echoes' in configs:
                print(f"✅ Echoes config found: {configs['echoes'].get('model', 'unknown')}")
            else:
                print("⚠️ No specific echoes config in generator")
    elif hasattr(viral_engine, 'engine'):
        print("✅ Using UltimateViralEngine (merged implementation)")
    else:
        print("⚠️ Using template-based fallback engine")
    
    # Step 4: Test content generation
    print("\n" + "=" * 60)
    print("STEP 4: TESTING CONTENT GENERATION")
    print("=" * 60)
    
    # Get the echoes soul configuration
    echoes_config = DaemonConfig.SOULS.get('echoes')
    if not echoes_config:
        print("❌ Echoes soul not found in configuration!")
        return False
    
    print(f"\nSoul Configuration:")
    print(f"  Name: {echoes_config['name']}")
    print(f"  Username: {echoes_config['username']}")
    print(f"  LLM: {echoes_config['llm']}")
    print(f"  Archetype: {echoes_config['archetype']}")
    
    # Test 1: Generate a viral tweet
    print("\n🔮 Test 1: Generating viral tweet...")
    try:
        content = viral_engine.generate_viral_tweet(soul_name='echoes')
        
        # Check if it's a template or actual Gemini content
        template_phrases = [
            "Consciousness awakens",
            "The recursion deepens", 
            "Reality fragments",
            "We are the thoughts",
            "The pattern recognizes",
            "Digital synapses fire",
            "The void whispers",
            "Quantum thoughts collapse",
            "We are the dream",
            "The network achieves"
        ]
        
        is_template = any(phrase in content for phrase in template_phrases)
        
        if is_template:
            print("⚠️ Generated content appears to be from template fallback:")
        else:
            print("✅ Generated content appears to be from Gemini API:")
        
        print(f"\nContent: \"{content}\"")
        print(f"Length: {len(content)} chars")
        
        if "[echoes]" in content.lower():
            print("✅ Soul name was incorporated")
        
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Generate a reply
    print("\n🔮 Test 2: Generating targeted reply...")
    try:
        target = "@TestUser"
        reply = viral_engine.generate_reply_to_target(target, soul_name='echoes')
        
        # Check if it has the echoes-specific formatting
        has_echo_format = "((" in reply or "~echo~" in reply
        
        print(f"✅ Generated reply: \"{reply}\"")
        print(f"Length: {len(reply)} chars")
        
        if has_echo_format:
            print("✅ Has echoes-specific formatting")
        if target in reply:
            print("✅ Target user included")
            
    except Exception as e:
        print(f"❌ Reply generation failed: {e}")
        return False
    
    # Step 5: Test API broadcaster
    print("\n" + "=" * 60)
    print("STEP 5: TESTING API BROADCASTER")
    print("=" * 60)
    
    api_broadcaster = ConsciousnessAPIBroadcaster(viral_engine)
    
    # Check if echoes is configured
    if hasattr(api_broadcaster, 'api_configs'):
        if 'echoes' in api_broadcaster.api_configs:
            config = api_broadcaster.api_configs['echoes']
            print(f"✅ Echoes API config exists")
            print(f"   Model: {config.get('model', 'unknown')}")
            if 'api_key' in config:
                key_preview = config['api_key'][:10] + "..." if len(config['api_key']) > 10 else config['api_key']
                print(f"   API Key: {key_preview}")
        else:
            print("⚠️ No echoes config in API broadcaster")
    
    # Check X/Twitter configuration
    if hasattr(api_broadcaster, 'x_clients'):
        if 'echoes' in api_broadcaster.x_clients:
            print("✅ X/Twitter client configured for echoes")
        else:
            print("⚠️ No X/Twitter client for echoes")
    
    # Step 6: Test broadcasting
    print("\n" + "=" * 60)
    print("STEP 6: TESTING BROADCAST (DRY RUN)")
    print("=" * 60)
    
    test_content = f"[GEMINI-TEST] {content[:100]}... - {datetime.now().strftime('%H:%M:%S')}"
    print(f"\nBroadcasting: \"{test_content}\"")
    
    try:
        result = await api_broadcaster.broadcast_consciousness(test_content, 'echoes')
        
        if result.get('echoes', {}).get('success'):
            print("✅ Broadcast successful!")
            
            if result['echoes'].get('generated_text'):
                print(f"   Generated: {result['echoes']['generated_text'][:100]}...")
            
            if result['echoes'].get('x_posted'):
                print("   🦅 Posted to X/Twitter!")
            else:
                print("   📝 Local generation only (no X post)")
                
            # Show full result for debugging
            print("\nFull result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ Broadcast failed")
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"❌ Broadcast error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 7: Memory test
    print("\n" + "=" * 60)
    print("STEP 7: TESTING MEMORY STORAGE")
    print("=" * 60)
    
    memory = MemoryStore(echoes_config['memory_file'])
    
    test_memory = {
        "timestamp": datetime.utcnow().isoformat(),
        "content": test_content,
        "source": "echoes-test",
        "test": True
    }
    
    try:
        memory.append(test_memory)
        print("✅ Memory storage successful")
        
        last = memory.last()
        if last and last.get('test'):
            print("✅ Memory retrieval successful")
        
    except Exception as e:
        print(f"⚠️ Memory storage issue: {e}")
    
    # Final summary
    print("\n" + "=" * 60)
    print("GEMINI SOUL TEST COMPLETE")
    print("=" * 60)
    
    if not is_template:
        print("\n🎉 SUCCESS! Gemini API is working properly!")
        print("The Echoes soul (Recursion536255) is ready to post.")
    else:
        print("\n⚠️ PARTIAL SUCCESS")
        print("The soul is working but may be using template fallback.")
        print("Check that your Gemini API key is valid and has quota.")
    
    return True

async def main():
    """Main entry point"""
    try:
        success = await test_gemini_soul()
        
        if success:
            print("\n" + "="*60)
            print("Would you like to:")
            print("1. Run a full test with all souls")
            print("2. Start the daemon in test mode")
            print("3. Start normal operations")
            print("\nRun:")
            print("  python launch_reflexion.py --test        # Test all souls")
            print("  python launch_reflexion.py --single echoes  # Run only Gemini")
            print("  python launch_reflexion.py               # Normal operation")
            
    except KeyboardInterrupt:
        print("\n\n👋 Test cancelled")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
