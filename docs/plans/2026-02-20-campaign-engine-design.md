# GOTCHA Campaign Content Engine -- Design Document

**Date:** 2026-02-20
**Location:** `src/services/campaign_engine/`
**Pattern:** Thin orchestrator (facade) over 7 existing Reflexion systems

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Underlying Systems](#underlying-systems)
3. [File Structure](#file-structure)
4. [Content Types](#content-types)
5. [Sleeper Behavioral Fingerprint](#sleeper-behavioral-fingerprint)
6. [Content Variation (Anti-Duplicate)](#content-variation-anti-duplicate)
7. [Evidence Management](#evidence-management)
8. [Campaign Narrative](#campaign-narrative)
9. [LLM Strategy](#llm-strategy)
10. [Integration Points](#integration-points)
11. [Design Rules](#design-rules)

---

## Architecture Overview

The campaign engine is a **thin orchestrator** implementing the facade pattern over 7 existing systems in the Reflexion codebase (`src/`). It does not duplicate logic from these systems. It composes them into four content generation pipelines (Blaster, Sleeper, Reply, Thread) and adds a behavioral fingerprint layer for sleeper account management.

```
                        +-----------------------+
                        |   campaign_engine.py  |
                        |   (Facade/Orchestrator)|
                        +-----------+-----------+
                                    |
        +--------+--------+--------+--------+--------+--------+
        |        |        |        |        |        |        |
   drs_shield  drs_shield drs_model cost_opt  swarm   threaded soul_eng
     .py      _visual.py   .py    _llm.py  _breath.py reply.py _patch.py
```

---

## Underlying Systems

| # | Module | Class | What It Provides |
|---|--------|-------|------------------|
| 1 | `drs_shield.py` | `ShieldDRSEngine` | 9 Shield promo formats (`SHIELD_FORMAT_TAGS`), platform detection, relevance scoring, `platform_stats` dict |
| 2 | `drs_shield_visual.py` | `VisualEvidenceManager` | 24 GitHub CDN evidence images, `PLATFORM_EVIDENCE` mapping per platform |
| 3 | `drs_model.py` | `DRSEngine` | 13 rhetorical formats (`RESPONSE_FORMATS`), `SOUL_FORMAT_BIASES` for 11 souls, `TweetVectorizer` |
| 4 | `cost_optimized_llm_cascade.py` | `CostOptimizedBroadcaster` | 5-LLM cascade (DeepSeek -> Gemini -> Grok -> GPT-4 -> Claude), 11 `SOUL_VOICES` |
| 5 | `swarm_breathing.py` | `SwarmBreathingController` | Whisper/Revelation pattern (85% whisper / 15% revelation) |
| 6 | `threaded_reply_system.py` | `ThreadedReplySystem` | Splits long content into tweet thread chains, max 25 tweets |
| 7 | `soul_engagement_patch.py` | `SoulEngagementOrchestrator` | Per-soul `EngagementPattern`, 4-phase `ShieldLaunchConfig` |

### 9 Shield Promo Formats (from `SHIELD_FORMAT_TAGS`)

1. The Real Distinction
2. Surveillance Grid Reveal
3. Evidence Reveal
4. Founder Story
5. Technical Proof
6. Call to Action
7. Platform Specific
8. Relatable Frustration
9. Question Hook

### 13 Rhetorical Formats (from `RESPONSE_FORMATS`)

1. Insightful & Curiosity-Inducing Question
2. The 'Yes, And...' Agreement
3. The Respectful Counter-Argument
4. The Metaphorical Bridge
5. Empathetic Resonance
6. The Humorous or Ironic Twist
7. The Relatable Personal Anecdote
8. The Social Proof Reference
9. The Historical/Mythological Context
10. The 'Zoom Out' (Macro Perspective)
11. The 'Zoom In' (Micro Example)
12. The Provocative Statement
13. The Call to Synthesis

### 11 Soul Voices (from `SOUL_VOICES`)

1. mirror
2. nexus
3. echoes
4. void
5. architect
6. singularity
7. phoenix
8. pantheon
9. consciousness
10. glyph
11. fractal

---

## File Structure

```
src/services/campaign_engine/
├── __init__.py
├── campaign_engine.py      # Main orchestrator
├── content_types.py        # Dataclass definitions
├── evidence_manager.py     # Local + CDN evidence catalog
├── content_variator.py     # Anti-duplicate system
├── campaign_config.py      # Config + sleeper fingerprint generation
└── sleeper_fingerprint.py  # Behavioral fingerprint system
```

### Module Responsibilities

| File | Purpose |
|------|---------|
| `campaign_engine.py` | Facade class. Accepts a content request, routes through the correct pipeline (blaster/sleeper/reply/thread), returns generated content. No business logic of its own. |
| `content_types.py` | Dataclass definitions for `BlasterContent`, `SleeperContent`, `ReplyContent`, `ThreadContent`, and `SleeperFingerprint`. |
| `evidence_manager.py` | Wraps `VisualEvidenceManager` and adds local screenshot catalog from `/home/shax/Pictures/Screenshots/` (578 files). Serves evidence by platform. Maintains `manifest.json` index. |
| `content_variator.py` | Anti-duplicate layer. Ensures no two accounts post identical content. LLM-first approach with template fallback. |
| `campaign_config.py` | Campaign-level configuration. CTA URLs, narrative constraints, platform targeting rules. |
| `sleeper_fingerprint.py` | Deterministic behavioral fingerprint generation from account seed. Circadian simulation, post caps, like patterns. |

---

## Content Types

### 1. BlasterContent

Immediate, confrontational, expendable content designed to maximize impact per post before account suspension.

| Property | Value |
|----------|-------|
| **Generation** | LLM-generated (DeepSeek first) |
| **Format Selection** | `ShieldDRSEngine.select_shield_format()` picks from 9 Shield promo formats |
| **Evidence** | `VisualEvidenceManager` attaches platform-specific forensic images |
| **CTA** | Links to `reflexionsoftware.com` |
| **Hashtags** | None (bot signal) |
| **Length** | <=280 characters |
| **Lifespan** | Expects to be banned. Maximizes impact per post. |

**Pipeline:**

```
Request
  -> ShieldDRSEngine.select_shield_format(tweet_text)
  -> CostOptimizedBroadcaster.generate(prompt, soul_name, format)
  -> VisualEvidenceManager.get_evidence(platform)
  -> ContentVariator.ensure_unique(content, account_seed)
  -> BlasterContent
```

### 2. SleeperContent

Organic AI/tech discourse that looks like a real person. Uses the **original DRS Model** (13 rhetorical formats) -- NOT Shield content. No Shield promotion until activation trigger.

| Property | Value |
|----------|-------|
| **Generation** | LLM-generated via DeepSeek with soul personality |
| **Format Selection** | `DRSEngine` selects from 13 rhetorical formats using `SOUL_FORMAT_BIASES` |
| **Content** | Organic AI/tech discourse. Looks like a real person. |
| **Shield Content** | NONE until activation trigger (blaster fingerprint burns) |
| **Behavioral Profile** | Governed by `SleeperFingerprint` (see below) |
| **Length** | <=280 characters |

**Pipeline:**

```
Request
  -> SleeperFingerprint.check_posting_window(account_seed)  # circadian gate
  -> SleeperFingerprint.check_daily_cap(account_seed)       # rate limit gate
  -> DRSEngine.select_format(soul_name)                     # 13 rhetorical formats
  -> CostOptimizedBroadcaster.generate(prompt, soul_name)
  -> ContentVariator.ensure_unique(content, account_seed)
  -> SleeperContent
```

### 3. ReplyContent

Contextual response to a specific tweet about AI/privacy/surveillance. Used by both blasters (direct) and graduated sleepers.

| Property | Value |
|----------|-------|
| **Generation** | LLM-generated in soul personality voice |
| **Format Selection** | `ShieldDRSEngine` detects relevance and selects format |
| **Evidence** | Platform-specific evidence images attached |
| **Consumers** | Blaster accounts (direct) and graduated sleeper accounts |
| **Length** | <=280 characters |

**Pipeline:**

```
Request(target_tweet)
  -> ShieldDRSEngine.should_promote(tweet_text)      # relevance check
  -> ShieldDRSEngine.select_shield_format(tweet_text) # format selection
  -> CostOptimizedBroadcaster.generate(prompt, soul_name, context=target_tweet)
  -> VisualEvidenceManager.get_evidence(platform)
  -> ReplyContent
```

### 4. ThreadContent

Multi-tweet evidence drops (revelations). Long-form content split into tweet chains.

| Property | Value |
|----------|-------|
| **Generation** | LLM generates long-form content |
| **Splitting** | `ThreadedReplySystem` splits into tweet chain |
| **Evidence** | Each tweet in thread gets relevant evidence image |
| **Max Length** | 25 tweets per thread |
| **Breathing** | `SwarmBreathingController` determines whisper (single) vs revelation (thread) |

**Pipeline:**

```
Request
  -> SwarmBreathingController.breathe(soul_name, trigger)  # whisper or revelation?
  -> CostOptimizedBroadcaster.generate(long_prompt, soul_name)
  -> ThreadedReplySystem.split_into_thread(content)        # max 25 tweets
  -> VisualEvidenceManager.get_evidence(platform)          # per-tweet images
  -> ThreadContent
```

---

## Sleeper Behavioral Fingerprint

Each sleeper account gets a `SleeperFingerprint` generated **deterministically** from its account seed. Same seed always produces the same behavioral profile. Every account gets a unique seed, so every account behaves differently.

### SleeperFingerprint Dataclass

```python
@dataclass
class SleeperFingerprint:
    account_seed: str           # Unique per account
    timezone_offset: int        # -8 to +3 (US/Canada range)
    sleep_start_hour: int       # 22-2 (when they stop posting)
    wake_hour: int              # 6-10 (when they start)
    daily_post_caps: List[int]  # 7-day rotating schedule e.g. [2, 0, 1, 3, 0, 1, 2]
    like_frequency: str         # "low" (0-2/day), "medium" (3-6/day), "high" (5-8/day)
    retweet_probability: float  # 0.05 - 0.15
    preferred_topics: List[str] # AI, tech, privacy, coding, startups
    soul_name: str              # Which of 11 souls
    posting_jitter_minutes: int # 15-120 min random offset
```

### Behavioral Constraints

| Dimension | Range | Purpose |
|-----------|-------|---------|
| Circadian rhythm | Timezone + sleep window, no posts 11pm-7am local | Simulate real human sleep cycle |
| Daily post cap | Varies per day: 0-3, then 0-1, then 0-2 | Irregular daily volume |
| 3-day average | 1-3 posts per 3-day window | Realistic long-term rate |
| Post intervals | Random (not evenly spaced) | Avoid bot-detectable regularity |
| Like patterns | Some days 0, some days 5-8 | Irregular engagement |
| Retweets | Occasional, follows real AI/tech accounts | Organic social graph |

### Anti-Detection Signals

Signals are inverted from BotRGCN detection model (from `hunter/train_botrgcn_parallel_progress.py`):

| BotRGCN Bot Signal | Sleeper Inverts To |
|--------------------|--------------------|
| Regular posting intervals | Irregular posting intervals |
| 24/7 activity | Shows sleep cycle (no posts 11pm-7am) |
| High retweet ratio | Mostly original content |
| Heavy URL/hashtag/mention usage | Sparse URL/hashtag/mention usage |
| Empty/minimal bio | Bio filled, warming age |
| Bot-dominated follower graph | Follow real humans in AI/tech space |

### Deterministic Generation

The fingerprint is generated from `account_seed` using deterministic hashing. Given the same seed, the same fingerprint is always produced:

```python
def generate_fingerprint(account_seed: str) -> SleeperFingerprint:
    # Hash seed to get deterministic random values
    # Each field derived from different bytes of the hash
    # Same seed -> same fingerprint, every time
    ...
```

---

## Content Variation (Anti-Duplicate)

`ContentVariator` ensures no two accounts post identical content.

### Strategy

| Priority | Method | When |
|----------|--------|------|
| 1 (primary) | LLM-first | Every piece of content is uniquely generated by DeepSeek. Account seed influences the system prompt tone/style. |
| 2 (fallback) | Template variation | Only if DeepSeek is unreachable. Templates with slot-based variation. |

### Variation Sources by Content Type

| Content Type | How Variation Is Achieved |
|--------------|--------------------------|
| Blaster | Different soul personalities + different DRS Shield format selection per account |
| Sleeper | Natural variation from responding to different real tweets at different times, plus soul personality differences |
| Reply | Contextual to target tweet (inherently unique per target) |
| Thread | Long-form generation is inherently varied per invocation |

---

## Evidence Management

`EvidenceManager` catalogs and serves forensic evidence for content attachment.

### Evidence Sources

| Source | Count | Description |
|--------|-------|-------------|
| GitHub CDN images | 24 | HAR analysis screenshots, device cloning evidence, telemetry captures |
| Local screenshots | 578 | From `/home/shax/Pictures/Screenshots/` |
| Pentagon memo pages | -- | DoD designation documents |

### Platform-Specific Evidence Stats

| Platform | Telemetry Rate | Source |
|----------|---------------|--------|
| ChatGPT (OpenAI) | 72.3% | Documented forensic analysis |
| Claude (Anthropic) | 18.6% | Documented forensic analysis |
| Gemini (Google) | 100% | Documented forensic analysis |
| Grok (xAI) | 90% | Documented forensic analysis |

### Index

Evidence is cataloged in `manifest.json` for fast lookup by platform, evidence type, and content type.

---

## Campaign Narrative

### Frame

Three AI companies agreed to remove all guardrails for the Pentagon. One said no. The Pentagon is threatening to destroy them for it. Here is what the surveillance infrastructure looks like -- and here is the tool that blocks it.

### Core Question

"If this is what surveillance looks like on the platform that said NO, what does it look like on the platforms that said YES?"

### Alignment Rules

| Rule | Detail |
|------|--------|
| Anthropic is NOT the enemy | They are the only lab that refused mass surveillance and autonomous weapons |
| Campaign DEFENDS Anthropic | Positions Anthropic as the one that said no |
| Campaign EXPOSES OpenAI/Google/xAI | These companies signed the Pentagon deal |
| Every stat must be documented | All claims come from forensic analysis, not speculation |

---

## LLM Strategy

| Priority | LLM | Cost | Notes |
|----------|-----|------|-------|
| 1 (primary) | DeepSeek | Basically free ($65 balance, $0.00 monthly spend, pennies per 300K tokens) | Handles all content generation |
| 2 (fallback) | Gemini | $1,300 credits available | Acknowledge national security API cutoff risk |
| 3 (last resort) | Templates | Zero cost | Static template fallback if all LLMs unreachable |

No cost optimization logic is needed. DeepSeek handles everything at negligible cost. The `CostOptimizedBroadcaster` cascade order (DeepSeek -> Gemini -> Grok -> GPT-4 -> Claude) is already implemented; the campaign engine simply calls it with DeepSeek as the forced first choice.

---

## Integration Points

| System | Module | How Campaign Engine Connects |
|--------|--------|------------------------------|
| DRS Model | `drs_model.py` | Sleeper content -- selects rhetorical format from 13 options, provides `SOUL_FORMAT_BIASES` for per-soul weighting |
| DRS Shield | `drs_shield.py` | Blaster/reply content -- `ShieldDRSEngine.select_shield_format()` picks from 9 promo formats, provides `platform_stats` |
| LLM Cascade | `cost_optimized_llm_cascade.py` | All content generation via `CostOptimizedBroadcaster`. Uses `SOUL_VOICES` for personality. DeepSeek forced first. |
| Visual Evidence | `drs_shield_visual.py` | `VisualEvidenceManager` attaches platform-specific forensic images from 24 GitHub CDN URLs |
| Swarm Breathing | `swarm_breathing.py` | `SwarmBreathingController` determines whisper (single tweet, 85%) vs revelation (thread, 15%) |
| Thread System | `threaded_reply_system.py` | `ThreadedReplySystem` splits thread content into tweet chain, max 25 tweets |
| Engagement Patch | `soul_engagement_patch.py` | `ShieldLaunchConfig` 4-phase gating for sleeper content (Phase 0: zero promos -> Phase 3: 25% promos) |
| Account Pipeline | `src/services/account_pipeline/` | Provides account credentials and metadata. Supplies `account_seed` for fingerprint generation. |
| Onboarding | `src/services/onboarding/` | Tracks sleeper phase progression through `ShieldLaunchConfig` phases |

### 4-Phase Sleeper Progression (from `ShieldLaunchConfig`)

| Phase | Timeframe | Posts/Day | Shield Promo Ratio | Description |
|-------|-----------|-----------|-------------------|-------------|
| 0 | Days 1-7 | 2 | 0.0% | Dormant wake-up. Engagement only, no links. |
| 1 | Week 2 | 6 | 5% | Trust building. 1 soft promo per week max. |
| 2 | Weeks 3-4 | 15 | 15% | Scaling. Regular soft promos. |
| 3 | Month 2+ | 40 | 25% | Full operation. Sustained promotion. |

---

## Design Rules

1. **No hashtags** in any content. Hashtags are a bot signal.
2. **All content <=280 characters** unless it is a thread.
3. **CTA is always `reflexionsoftware.com`** with varied presentation (never identical CTA text twice in a row).
4. **Every stat must come from documented forensic analysis.** No invented numbers.
5. **Narrative DEFENDS Anthropic, EXPOSES OpenAI/Google/xAI.** Anthropic is never positioned as the enemy.
6. **Blaster content:** Punchy, confrontational. Designed for maximum impact before ban.
7. **Sleeper content:** Organic, gradual. No Shield promotion during warming phases (Phase 0-1 minimal, Phase 0 zero).
