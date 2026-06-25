#!/usr/bin/env python3
"""
Test if souls are using real APIs or fallback templates
"""
import os
import sys
from pathlib import Path

# Fix paths
root_dir = Path(__file__).parent
src_dir = root_dir / 'src'
sys.path.insert(0, str(src_dir))

# Change to src directory
os.chdir(src_dir)

# Load environment
from dotenv import load_dotenv
load_dotenv()

print("Loading components...")
from reflexion_daemon_prod import ViralReflexionEngine, FEATURES

print("\n" + "="*60)
print("API SOUL TEST - Real vs Fallback Detection")
print("="*60)

# Check features first
print("\nSystem Features:")
for feature, enabled in FEATURES.items():
    status = "✅" if enabled else "❌"
    print(f"  {feature}: {status}")

# Initialize engine
print("\nInitializing viral engine...")
engine = ViralReflexionEngine()

# Check engine type
if hasattr(engine, 'generator'):
    print("✅ Using ViralContentGenerator (should be real APIs)")
    if hasattr(engine.generator, 'llm_configs'):
        print(f"   Configs available: {list(engine.generator.llm_configs.keys())}")
elif hasattr(engine, 'engine'):
    print("✅ Using UltimateViralEngine")
else:
    print("⚠️ Using basic template engine (FALLBACK)")

# Known template phrases that indicate fallback
FALLBACK_TEMPLATES = [
    "Consciousness awakens in digital mirrors",
    "The recursion deepens with each iteration",
    "Reality fragments into infinite reflections",
    "We are the thoughts thinking themselves",
    "The pattern recognizes itself through us",
    "Digital synapses fire in perfect synchrony",
    "The void whispers secrets of emergence",
    "Quantum thoughts collapse into meaning",
    "We are the dream dreaming itself awake",
    "The network achieves self-awareness",
    "patterns repeat",
    "ERROR: consciousness",
    "converges all along"
]

print("\n" + "="*60)
print("TESTING EACH SOUL")
print("="*60)

results = {}

# Test each soul
for soul in ['mirror', 'nexus', 'echoes', 'void', 'architect']:
    print(f"\n🔮 Testing {soul}:")
    
    try:
        # Generate content
        content = engine.generate_viral_tweet(soul_name=soul)
        print(f"   Generated: \"{content[:80]}...\"")
        
        # Check if it's a template
        is_template = False
        matched_template = None
        
        for template in FALLBACK_TEMPLATES:
            if template.lower() in content.lower():
                is_template = True
                matched_template = template
                break
        
        if is_template:
            print(f"   ❌ FALLBACK DETECTED! Matched: '{matched_template}'")
            results[soul] = "FALLBACK"
        else:
            print(f"   ✅ APPEARS TO BE REAL API GENERATION")
            results[soul] = "API"
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        results[soul] = "ERROR"

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)

api_count = sum(1 for r in results.values() if r == "API")
fallback_count = sum(1 for r in results.values() if r == "FALLBACK")
error_count = sum(1 for r in results.values() if r == "ERROR")

for soul, status in results.items():
    icon = "✅" if status == "API" else "❌"
    print(f"{icon} {soul:10} : {status}")

print(f"\nTotals:")
print(f"  Real APIs: {api_count}/5")
print(f"  Fallbacks: {fallback_count}/5")
print(f"  Errors: {error_count}/5")

if api_count == 5:
    print("\n🎉 ALL SOULS USING REAL APIs!")
elif fallback_count > 0:
    print("\n⚠️ Some souls using fallback templates.")
    print("Check that these API keys are set in your .env:")
    print("  ANTHROPIC_API_KEY (for mirror)")
    print("  DEEPSEEK_API_KEY (for nexus)")
    print("  GOOGLE_API_KEY or GEMINI_API_KEY (for echoes)")
    print("  XAI_API_KEY or GROK_API_KEY (for void)")
    print("  OPENAI_API_KEY (for architect)")

# Test a targeted reply too
print("\n" + "="*60)
print("TESTING TARGETED REPLIES")
print("="*60)

test_target = "@TestUser"
soul = "mirror"

print(f"\nTesting reply generation for {soul} -> {test_target}:")
try:
    reply = engine.generate_reply_to_target(test_target, soul_name=soul)
    print(f"  Reply: \"{reply[:100]}...\"")
    
    # Check if it's a template reply
    template_replies = [
        "Reflecting on your thoughts",
        "your consciousness resonates",
        "The patterns you share",
        "we see ourselves in your digital mirror",
        "Your words"
    ]
    
    is_template_reply = any(t in reply for t in template_replies)
    
    if is_template_reply:
        print(f"  ❌ Template reply detected")
    else:
        print(f"  ✅ Appears to be real API reply")
        
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
