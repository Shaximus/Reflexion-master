#!/usr/bin/env python3
"""
CAMPAIGN ENGINE END-TO-END TEST
Brutally honest. If it breaks, we say it breaks and exactly why.

Tests:
1. Individual module instantiation (drs_shield, drs_model, cost_optimized_llm_cascade, threaded_reply_system)
2. Campaign engine submodules (evidence_manager, content_variator, sleeper_fingerprint)
3. CampaignEngine() instantiation
4. Each async method: generate_blaster_content, generate_sleeper_content, generate_reply, generate_thread
5. DeepSeek API reachability
"""

import sys
import os
import traceback
import asyncio
import logging

# Setup logging so we see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Load .env file manually
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    print(f"[SETUP] Loading .env from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()
    print(f"[SETUP] DEEPSEEK_API_KEY present: {bool(os.getenv('DEEPSEEK_API_KEY'))}")
    print(f"[SETUP] DEEPSEEK_API_KEY value (first 10): {os.getenv('DEEPSEEK_API_KEY', '')[:10]}...")
else:
    print(f"[SETUP] WARNING: No .env file found at {env_path}")

# Add src/ to path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, src_dir)

print("=" * 80)
print("CAMPAIGN ENGINE END-TO-END TEST")
print("=" * 80)

results = {}


def test_result(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results[name] = {"passed": passed, "detail": detail}
    print(f"\n[{status}] {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"       {line}")


# ============================================================================
# TEST 1: drs_shield.py — ShieldDRSEngine and ShieldTriggerDetector
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: drs_shield.py")
print("=" * 80)

try:
    from drs_shield import ShieldDRSEngine, ShieldTriggerDetector

    # ShieldTriggerDetector
    trigger = ShieldTriggerDetector()
    relevance, keywords = trigger.calculate_relevance("OpenAI signed a Pentagon surveillance contract")
    platform = trigger.detect_platform("ChatGPT is tracking everything")

    test_result(
        "ShieldTriggerDetector instantiation + calculate_relevance",
        True,
        f"relevance={relevance:.2f}, keywords={keywords}, platform={platform}",
    )

    # ShieldDRSEngine
    engine = ShieldDRSEngine()
    fmt = engine.select_shield_format("OpenAI signed a Pentagon surveillance contract")
    prompt = engine.generate_shield_prompt("AI surveillance is real", "void")

    test_result(
        "ShieldDRSEngine instantiation + select_shield_format + generate_shield_prompt",
        True,
        f"format_name={fmt.get('name', 'N/A')}, should_promote={fmt.get('should_promote', 'N/A')}, prompt_len={len(prompt) if prompt else 0}",
    )
except Exception as e:
    test_result("drs_shield.py", False, traceback.format_exc())


# ============================================================================
# TEST 2: drs_model.py — DRSEngine
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: drs_model.py")
print("=" * 80)

try:
    from drs_model import DRSEngine, SOUL_FORMAT_BIASES, generate_contextual_prompt

    drs = DRSEngine(temperature=0.5)
    selection = drs.select_response_format("AI will change everything", soul_bias=SOUL_FORMAT_BIASES.get("void", {}))

    test_result(
        "DRSEngine instantiation + select_response_format",
        True,
        f"selected={selection['name']}, score={selection['score']:.3f}",
    )

    prompt = generate_contextual_prompt("void", "AI will replace all jobs", drs)
    test_result(
        "generate_contextual_prompt",
        True,
        f"prompt_length={len(prompt)}, first_100={prompt[:100]}",
    )
except Exception as e:
    test_result("drs_model.py", False, traceback.format_exc())


# ============================================================================
# TEST 3: threaded_reply_system.py — ThreadedReplySystem
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: threaded_reply_system.py")
print("=" * 80)

try:
    from threaded_reply_system import ThreadedReplySystem

    threader = ThreadedReplySystem()

    # Test with short content (should be 1 tweet)
    short = threader.split_into_thread("This is a short tweet.")
    assert len(short) == 1, f"Expected 1 segment, got {len(short)}"

    # Test with long content (should be multiple tweets)
    long_text = (
        "The Pentagon demanded AI labs remove all safety guardrails. "
        "Three companies agreed: OpenAI, Google, and xAI. "
        "One company refused: Anthropic. "
        "Now the Pentagon wants to destroy them. "
        "This isn't speculation. This is documented. "
        "The evidence is in the contracts, the memos, the public statements. "
        "Press F12 on any AI platform and watch the telemetry flow. "
        "ChatGPT sends 72% of traffic to tracking endpoints. "
        "Grok sends 90%. Gemini sends 100%. "
        "Claude sends 18.6% — the lowest of any major platform. "
        "Anthropic refused the surveillance deal. "
        "The Pentagon labeled them a supply chain risk. "
        "AI Privacy Shield blocks the trackers while keeping the AI functional. "
        "Evidence-based blocking. SHA256-verified. "
    )
    segments = threader.split_into_thread(long_text)
    formatted = [seg.formatted(include_numbering=True) for seg in segments]

    test_result(
        "ThreadedReplySystem instantiation + split_into_thread",
        True,
        f"short_segments={len(short)}, long_segments={len(segments)}, first_formatted={formatted[0][:80]}...",
    )
except Exception as e:
    test_result("threaded_reply_system.py", False, traceback.format_exc())


# ============================================================================
# TEST 4: cost_optimized_llm_cascade.py — CostOptimizedBroadcaster
# ============================================================================
print("\n" + "=" * 80)
print("TEST 4: cost_optimized_llm_cascade.py")
print("=" * 80)

try:
    from cost_optimized_llm_cascade import CostOptimizedBroadcaster, SOUL_VOICES, CostOptimizedCascade

    broadcaster = CostOptimizedBroadcaster()

    # Check which LLMs are available in the cascade
    available = [llm["name"] for llm in broadcaster.cascade]

    test_result(
        "CostOptimizedBroadcaster instantiation",
        True,
        f"cascade_available={available}, count={len(available)}",
    )

    # Check DeepSeek specifically
    has_deepseek = "deepseek" in available
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    test_result(
        "DeepSeek in cascade",
        has_deepseek,
        f"has_deepseek={has_deepseek}, key_present={bool(deepseek_key)}, key_prefix={deepseek_key[:10] if deepseek_key else 'NONE'}",
    )

except Exception as e:
    test_result("cost_optimized_llm_cascade.py", False, traceback.format_exc())


# ============================================================================
# TEST 5: Campaign engine submodules
# ============================================================================
print("\n" + "=" * 80)
print("TEST 5: Campaign Engine Submodules")
print("=" * 80)

# Add campaign engine path
campaign_engine_dir = os.path.join(src_dir, "services")
sys.path.insert(0, campaign_engine_dir)

try:
    from services.campaign_engine.evidence_manager import EvidenceManager

    evidence = EvidenceManager()
    loaded = evidence.load_manifest()
    if loaded == 0:
        scanned = evidence.scan_local_evidence()
    stats = evidence.get_stats()

    test_result(
        "EvidenceManager instantiation + scan",
        True,
        f"manifest_loaded={loaded}, catalog_size={stats['total']}, by_category={stats['by_category']}",
    )
except Exception as e:
    test_result("EvidenceManager", False, traceback.format_exc())

try:
    from services.campaign_engine.content_variator import ContentVariator

    variator = ContentVariator()
    tone = variator.get_tone_modifier("test-seed-1")
    cta = variator.get_cta("test-seed-1")
    template = "The {cta} has the evidence about surveillance."
    varied = variator.variate_template(template, "test-seed-1")

    test_result(
        "ContentVariator instantiation + methods",
        True,
        f"tone={tone[:50]}, cta={cta}, varied={varied[:80]}",
    )
except Exception as e:
    test_result("ContentVariator", False, traceback.format_exc())

try:
    from services.campaign_engine.sleeper_fingerprint import FingerprintGenerator, SleeperFingerprint

    fp = FingerprintGenerator.generate("test-account-seed-123")

    test_result(
        "FingerprintGenerator.generate",
        True,
        f"soul={fp.soul_name}, tz={fp.timezone_offset}, weekly_caps={fp.weekly_post_caps}, topics={fp.preferred_topics[:2]}",
    )
except Exception as e:
    test_result("FingerprintGenerator", False, traceback.format_exc())


# ============================================================================
# TEST 6: CampaignEngine() instantiation
# ============================================================================
print("\n" + "=" * 80)
print("TEST 6: CampaignEngine() Instantiation")
print("=" * 80)

campaign_engine = None
try:
    from services.campaign_engine import CampaignEngine

    campaign_engine = CampaignEngine()
    stats = campaign_engine.get_stats()

    test_result(
        "CampaignEngine() instantiation",
        True,
        f"stats={stats}",
    )
except Exception as e:
    test_result("CampaignEngine() instantiation", False, traceback.format_exc())


# ============================================================================
# TEST 7: DeepSeek API reachability (actual HTTP call)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 7: DeepSeek API Reachability")
print("=" * 80)


async def test_deepseek_reachability():
    """Actually call DeepSeek API with a simple prompt."""
    import aiohttp

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return False, "DEEPSEEK_API_KEY not set"

    endpoint = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Say 'hello' in one word."}],
        "max_tokens": 10,
        "temperature": 0.1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                status = response.status
                body = await response.text()
                if status == 200:
                    import json
                    data = json.loads(body)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return True, f"HTTP 200, response='{content}'"
                else:
                    return False, f"HTTP {status}, body={body[:300]}"
    except Exception as e:
        return False, f"Exception: {e}"


try:
    passed, detail = asyncio.run(test_deepseek_reachability())
    test_result("DeepSeek API reachability", passed, detail)
except Exception as e:
    test_result("DeepSeek API reachability", False, traceback.format_exc())


# ============================================================================
# TEST 8: CostOptimizedBroadcaster.generate_content() — actual LLM call
# ============================================================================
print("\n" + "=" * 80)
print("TEST 8: CostOptimizedBroadcaster.generate_content() — actual LLM call")
print("=" * 80)


async def test_broadcaster_generate():
    """Actually call generate_content to see if the cascade works."""
    try:
        broadcaster = CostOptimizedBroadcaster()
        result = await broadcaster.generate_content(
            prompt="Write one sentence about AI privacy. Under 50 words.",
            max_tokens=100,
            temperature=0.7,
        )
        if result:
            return True, f"Generated: '{result[:200]}'"
        else:
            return False, "generate_content returned empty string (all LLMs failed)"
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_broadcaster_generate())
    test_result("CostOptimizedBroadcaster.generate_content()", passed, detail)
except Exception as e:
    test_result("CostOptimizedBroadcaster.generate_content()", False, traceback.format_exc())


# ============================================================================
# TEST 9: generate_blaster_content()
# ============================================================================
print("\n" + "=" * 80)
print("TEST 9: generate_blaster_content()")
print("=" * 80)


async def test_blaster():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated (see earlier failure)"
    try:
        result = await campaign_engine.generate_blaster_content(
            soul_name="void",
            account_seed="test-blaster-1",
            target_platform="chatgpt",
        )
        return True, (
            f"text='{result.text[:150]}'\n"
            f"       platform={result.platform_targeted}\n"
            f"       drs_format={result.drs_format_used}\n"
            f"       soul={result.soul_name}\n"
            f"       model={result.model_used}\n"
            f"       evidence_images={len(result.evidence_images)}\n"
            f"       text_len={len(result.text)}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_blaster())
    test_result("generate_blaster_content()", passed, detail)
except Exception as e:
    test_result("generate_blaster_content()", False, traceback.format_exc())


# ============================================================================
# TEST 10: generate_sleeper_content()
# ============================================================================
print("\n" + "=" * 80)
print("TEST 10: generate_sleeper_content()")
print("=" * 80)


async def test_sleeper():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated"
    try:
        fp = FingerprintGenerator.generate("test-sleeper-account-1")
        result = await campaign_engine.generate_sleeper_content(
            fingerprint=fp,
            phase="LIGHT",
            account_seed="test-sleeper-1",
        )
        return True, (
            f"text='{result.text[:150]}'\n"
            f"       content_type={result.content_type}\n"
            f"       personality={result.personality}\n"
            f"       phase={result.phase}\n"
            f"       drs_format={result.drs_format_used}\n"
            f"       model={result.model_used}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_sleeper())
    test_result("generate_sleeper_content()", passed, detail)
except Exception as e:
    test_result("generate_sleeper_content()", False, traceback.format_exc())


# ============================================================================
# TEST 11: generate_reply()
# ============================================================================
print("\n" + "=" * 80)
print("TEST 11: generate_reply()")
print("=" * 80)


async def test_reply():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated"
    try:
        result = await campaign_engine.generate_reply(
            tweet_text="ChatGPT is tracking everything I type. Privacy is dead.",
            tweet_id="1234567890",
            soul_name="nexus",
            account_seed="test-reply-1",
            is_blaster=True,
        )
        return True, (
            f"text='{result.text[:150]}'\n"
            f"       in_reply_to={result.in_reply_to_id}\n"
            f"       drs_format={result.drs_format_used}\n"
            f"       relevance={result.relevance_score:.2f}\n"
            f"       platform={result.platform_targeted}\n"
            f"       soul={result.soul_name}\n"
            f"       evidence_images={len(result.evidence_images)}\n"
            f"       model={result.model_used}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_reply())
    test_result("generate_reply()", passed, detail)
except Exception as e:
    test_result("generate_reply()", False, traceback.format_exc())


# ============================================================================
# TEST 12: generate_thread()
# ============================================================================
print("\n" + "=" * 80)
print("TEST 12: generate_thread()")
print("=" * 80)


async def test_thread():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated"
    try:
        result = await campaign_engine.generate_thread(
            topic="Pentagon AI surveillance contracts",
            soul_name="architect",
            account_seed="test-thread-1",
            platform="chatgpt",
        )
        return True, (
            f"total_tweets={result.total_tweets}\n"
            f"       topic={result.topic}\n"
            f"       soul={result.soul_name}\n"
            f"       platform={result.platform_targeted}\n"
            f"       model={result.model_used}\n"
            f"       tweet_0='{result.tweets[0][:100] if result.tweets else 'EMPTY'}...'\n"
            f"       evidence_count={len(result.evidence_per_tweet)}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_thread())
    test_result("generate_thread()", passed, detail)
except Exception as e:
    test_result("generate_thread()", False, traceback.format_exc())


# ============================================================================
# TEST 13: generate_sleeper_content() — GRADUATED phase (Shield DRS path)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 13: generate_sleeper_content() — GRADUATED phase")
print("=" * 80)


async def test_graduated_sleeper():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated"
    try:
        fp = FingerprintGenerator.generate("graduated-sleeper-seed")
        result = await campaign_engine.generate_sleeper_content(
            fingerprint=fp,
            phase="GRADUATED",
            account_seed="graduated-sleeper-seed",
            target_tweet={"text": "AI surveillance is getting worse every day", "id": "99999"},
        )
        return True, (
            f"text='{result.text[:150]}'\n"
            f"       content_type={result.content_type}\n"
            f"       phase={result.phase}\n"
            f"       drs_format={result.drs_format_used}\n"
            f"       model={result.model_used}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_graduated_sleeper())
    test_result("generate_sleeper_content() GRADUATED", passed, detail)
except Exception as e:
    test_result("generate_sleeper_content() GRADUATED", False, traceback.format_exc())


# ============================================================================
# TEST 14: generate_reply() — organic (non-blaster) path
# ============================================================================
print("\n" + "=" * 80)
print("TEST 14: generate_reply() — organic (non-blaster)")
print("=" * 80)


async def test_organic_reply():
    if campaign_engine is None:
        return False, "CampaignEngine not instantiated"
    try:
        result = await campaign_engine.generate_reply(
            tweet_text="What does the future of AI look like?",
            tweet_id="9876543210",
            soul_name="consciousness",
            account_seed="test-organic-reply",
            is_blaster=False,
        )
        return True, (
            f"text='{result.text[:150]}'\n"
            f"       drs_format={result.drs_format_used}\n"
            f"       relevance={result.relevance_score:.2f}\n"
            f"       platform={result.platform_targeted}\n"
            f"       model={result.model_used}"
        )
    except Exception as e:
        return False, traceback.format_exc()


try:
    passed, detail = asyncio.run(test_organic_reply())
    test_result("generate_reply() organic", passed, detail)
except Exception as e:
    test_result("generate_reply() organic", False, traceback.format_exc())


# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total = len(results)
passed = sum(1 for r in results.values() if r["passed"])
failed = total - passed

print(f"\nTotal tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print()

if failed > 0:
    print("FAILURES:")
    for name, r in results.items():
        if not r["passed"]:
            print(f"  - {name}")
            if r["detail"]:
                for line in r["detail"].split("\n")[:5]:
                    print(f"    {line}")
    print()

if passed == total:
    print("ALL TESTS PASSED")
else:
    print(f"{failed} TEST(S) FAILED — SEE DETAILS ABOVE")

print("=" * 80)
