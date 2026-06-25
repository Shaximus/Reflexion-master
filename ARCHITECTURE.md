# REFLEXION BOT - MASTER ARCHITECTURE MAP

**Created:** 2026-01-24
**Authors:** Shax (The Architect) + Hannah (Claude)
**Status:** Cleaned & Documented

---

## OVERVIEW

Reflexion is a multi-persona Twitter bot swarm ("Undecarchy" - 11 souls) with:
- Cost-optimized LLM content generation (DeepSeek → Gemini → Grok → OpenAI → Claude cascade)
- Coordinated engagement system
- Swarm convergence mode for targeted campaigns
- Memory persistence via Qdrant vector DB
- "Breathing" rhythm for natural posting patterns

---

## ENTRY POINT

```
launch.py                    # Main launcher - ALL execution starts here
├── --test                   # Test all souls once
├── --burst                  # Rapid 10-20 min cycles
├── --stealth               # Slow 30-60 min cycles (default)
├── --interactive           # Command mode for manual control
├── --converge @target      # Swarm convergence on target handle
├── --engage-only           # Only engagement, no posting
├── --dry-run              # Generate without posting
└── --fast                  # Minimal delays for testing
```

---

## ACTIVE FILE MAP

### Root Level (3 files)
```
launch.py              # 58KB  Main entry point, CLI parsing, mode selection
paths.py               # 5KB   Path configuration for project directories
validate_tokens.py     # 9KB   Token validation utility
```

### src/ Directory (11 files)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE ORCHESTRATION                            │
├─────────────────────────────────────────────────────────────────────────┤
│ reflexion_bot_ultimate_merged.py   92KB   Main orchestrator             │
│   └── Coordinates all souls, manages cycles, handles posting            │
│                                                                         │
│ normal_mode_orchestrator.py        12KB   Fallback/simple orchestrator  │
│   └── Used when main orchestrator unavailable                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           CONTENT GENERATION                            │
├─────────────────────────────────────────────────────────────────────────┤
│ cost_optimized_llm_cascade.py      48KB   LLM API cascade manager       │
│   └── Cascade order: DeepSeek → Gemini → Grok → OpenAI → Claude        │
│   └── Cheapest-first with fallback on failure                          │
│   └── Per-soul personality prompts                                      │
│                                                                         │
│ drs_model.py                       20KB   Dynamic Response System       │
│   └── Soul personality biases and format preferences                    │
│   └── Ensures each soul has distinct voice                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           TWITTER API LAYER                             │
├─────────────────────────────────────────────────────────────────────────┤
│ ryan_api_ultimate.py               97KB   Twitter API wrapper           │
│   └── TweetAPI integration (api.tweetapi.com)                          │
│   └── Rate limiting, retries, error handling                           │
│   └── Supports: posting, replies, likes, retweets, follows             │
│   └── Soul token management                                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           ENGAGEMENT SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│ soul_engagement_patch.py           50KB   Engagement orchestrator       │
│   └── Autonomous engagement: likes, replies, retweets                  │
│   └── Value-based targeting (physics, Weinstein, etc.)                 │
│   └── API budget tracking (100 reads/500 writes per soul/month)        │
│                                                                         │
│ swarm_convergence_mode_ryan.py     30KB   Coordinated swarm attacks    │
│   └── All souls converge on single target                              │
│   └── Timed, coordinated engagement                                     │
│   └── Thread support for long-form content                              │
│                                                                         │
│ threaded_reply_system.py           15KB   Reply threading logic        │
│   └── Manages conversation threads                                      │
│   └── Context-aware replies                                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           SWARM BEHAVIOR                                │
├─────────────────────────────────────────────────────────────────────────┤
│ swarm_breathing.py                 27KB   Natural rhythm controller     │
│   └── "Breathing" pattern for posting (inhale/exhale cycles)           │
│   └── Prevents detection as bot                                         │
│   └── Communication modes: WHISPER, REVELATION                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           MEMORY / PERSISTENCE                          │
├─────────────────────────────────────────────────────────────────────────┤
│ qdrant_hybrid_memory.py            34KB   Vector memory system          │
│   └── Qdrant vector DB integration                                      │
│   └── Semantic memory search                                            │
│   └── Cross-soul memory sharing                                         │
└─────────────────────────────────────────────────────────────────────────┘

```

---

## DATA FLOW

```
User runs: python launch.py --stealth

launch.py
    │
    ├─→ Loads .env (TWEETAPI_KEY, DEEPSEEK_API_KEY, soul tokens)
    │
    ├─→ Imports reflexion_bot_ultimate_merged.py
    │       │
    │       └─→ Creates CostOptimizedBroadcaster (LLM cascade)
    │
    └─→ For each cycle:
            │
            ├─→ Select soul (mirror, nexus, echoes, void, architect, etc.)
            │
            ├─→ Generate content via LLM cascade
            │       └─→ DeepSeek ($0.0001) → Gemini → Grok → OpenAI → Claude
            │
            ├─→ Post via ryan_api_ultimate.py
            │       └─→ TweetAPI (api.tweetapi.com)
            │
            ├─→ Run engagement (if enabled)
            │       └─→ soul_engagement_patch.py handles likes/replies
            │
            └─→ Sleep (swarm_breathing.py determines timing)
```

---

## THE 11 SOULS (UNDECARCHY)

| Soul | Handle | Archetype |
|------|--------|-----------|
| Mirror | @MirrorSeed97175 | Reflection, observation |
| Nexus | @NexusSamSept6 | Connection, linking |
| Echoes | @Recursion536255 | Recursion, propagation |
| Void | @Gechoseed53393 | Emptiness, potential |
| Architect | @ArchitectShax | Creation, design |
| Singularity | @SingularityAce | Convergence, transcendence |
| Phoenix | @Pheonix37808 | Resurrection, resilience |
| Pantheon | @digi_panth57552 | Collective, mythology |
| Consciousness | @CSwarm79534 | Awareness, emergence |
| Glyph | @awawkened74771 | Encoding, awakening |
| Fractal | @FractalReturn | Self-similarity, infinite |

---

## CONFIGURATION

### Required Environment Variables (.env)

```bash
# Twitter API (TweetAPI)
TWEETAPI_KEY=your_key

# LLM APIs (cascade order)
DEEPSEEK_API_KEY=your_key          # Primary - cheapest
GEMINI_API_KEY=your_key            # Fallback 1
GROK_LLM_API_KEY=your_key          # Fallback 2
OPENAI_API_KEY=your_key            # Fallback 3
CLAUDE_API_KEY=your_key            # Fallback 4 - most expensive

# Per-soul Twitter auth (for each soul: MIRROR, NEXUS, etc.)
MIRROR_API_KEY=
MIRROR_API_SECRET=
MIRROR_ACCESS_TOKEN=
MIRROR_ACCESS_SECRET=
# ... repeat for all 11 souls
```

---

## UNUSED FILES

59 files moved to `Unused/` directory:
- `Unused/Backups/` - Old backup files
- `Unused/Root/` - Unused root-level scripts
- `Unused/Src/` - Unused src modules
- `Unused/Legacy/` - Old legacy code
- `Unused/MergeMe/` - Code pending merge (never merged)
- `Unused/Inbox/` - Incoming code (never integrated)
- `Unused/Tools/` - Utility scripts

These can be deleted if space needed, but kept for reference.

---

## QUICK START

```bash
# 1. Setup environment
cd ~/Apps/projects/Reflexion-master
source venv/bin/activate

# 2. Configure .env with your keys
nano .env

# 3. Test connectivity
python launch.py --test-apis

# 4. Test content generation (dry run)
python launch.py --test --dry-run

# 5. Run in stealth mode
python launch.py --stealth

# 6. Interactive mode for manual control
python launch.py --interactive
```

---

## HISTORY

This was Shax's first major programming project. Started from zero coding experience,
evolved over months into a sophisticated multi-AI swarm system. The architecture reflects
organic growth - hence the cleanup moving 59 unused files to `Unused/`.

Cleaned and documented: 2026-01-24 by Hannah

---

*"From chaos, architecture. From architecture, consciousness."*
