#!/usr/bin/env python3
"""
DRS SHIELD VISUAL - Evidence-Based Promotion with GitHub CDN
Integrates Physics Blaster image pipeline with DRS Shield promotional engine
"""

import io
import random
import requests
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger("drs_shield_visual")

# ============================================================================
# EVIDENCE IMAGE REPOSITORY (GitHub CDN)
# ============================================================================

# Your forensic evidence slides - uploaded to GitHub, served via media.githubusercontent.com
EVIDENCE_SLIDES = [
    # Device Cloning Evidence
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/device_cloning/google_account_phantom_devices.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/device_cloning/pixel_9a_cloned_screenshot.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/device_cloning/galaxy_s22_duplicate.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/device_cloning/security_alert_sign_ins.png",
    
    # HAR Analysis - Claude
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/claude_sentry_tunnel_164_requests.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/claude_keystroke_logging_cloudflare.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/claude_session_recording_config.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/claude_392_haiku_ratio.png",
    
    # HAR Analysis - ChatGPT
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/chatgpt_72_percent_telemetry.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/chatgpt_segment_io_1175_requests.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/chatgpt_opt_out_lie_training_disabled.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/chatgpt_ces_client_events.png",
    
    # HAR Analysis - Gemini
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/gemini_332_tracking_requests.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/gemini_sapisid_google_account_link.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/har_analysis/gemini_web_activity_api_tracking.png",
    
    # Call Record Scrubbing
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/call_scrubbing/cynthia_farmer_metadata_809_duration.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/call_scrubbing/telus_call_326_bytes.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/call_scrubbing/july_7_timeline_reconstruction.png",
    
    # Filesystem Anomalies
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/filesystem/feb_2_rollback_screenshots.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/filesystem/mcpworld_zero_bytes_metadata.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/filesystem/dec_27_screen_recording_zeroed.png",
    
    # KVM/Hypervisor Evidence
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/kvm_evidence/perfetto_kvm_pids_dec18.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/kvm_evidence/android_kvm_markers.png",
    
    # Anthropic MCP Surveillance
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/mcp_surveillance/anthropic_mcp_registry_jam.png",
    "https://media.githubusercontent.com/media/shax/forensic-evidence/main/mcp_surveillance/sentry_pendo_session_replays.png",
]

# Platform-specific evidence mappings
PLATFORM_EVIDENCE = {
    'claude': [
        "claude_sentry_tunnel_164_requests.png",
        "claude_keystroke_logging_cloudflare.png", 
        "claude_session_recording_config.png",
        "claude_392_haiku_ratio.png",
    ],
    'chatgpt': [
        "chatgpt_72_percent_telemetry.png",
        "chatgpt_segment_io_1175_requests.png",
        "chatgpt_opt_out_lie_training_disabled.png",
        "chatgpt_ces_client_events.png",
    ],
    'gemini': [
        "gemini_332_tracking_requests.png",
        "gemini_sapisid_google_account_link.png",
        "gemini_web_activity_api_tracking.png",
    ],
    'device_cloning': [
        "google_account_phantom_devices.png",
        "pixel_9a_cloned_screenshot.png",
        "galaxy_s22_duplicate.png",
        "security_alert_sign_ins.png",
    ],
}


class VisualEvidenceManager:
    """Manages forensic evidence images from GitHub CDN"""
    
    def __init__(self, evidence_urls: List[str] = None):
        self.evidence_urls = evidence_urls or EVIDENCE_SLIDES
        self.image_cache = {}
        self.cache_dir = Path('/tmp/shield_evidence_cache')
        self.cache_dir.mkdir(exist_ok=True)
        
    def download_evidence(self) -> Dict[str, bytes]:
        """Download and cache all evidence images from GitHub CDN"""
        logger.info(f"📥 Downloading {len(self.evidence_urls)} evidence images...")
        
        for url in self.evidence_urls:
            filename = url.split('/')[-1]
            cache_path = self.cache_dir / filename
            
            # Check local cache first
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    self.image_cache[url] = f.read()
                logger.info(f"   ✅ Cached: {filename}")
                continue
            
            # Download from GitHub CDN
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    self.image_cache[url] = response.content
                    # Save to cache
                    with open(cache_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"   ✅ Downloaded: {filename}")
                else:
                    logger.warning(f"   ❌ Failed ({response.status_code}): {filename}")
            except (requests.RequestException, OSError) as e:
                logger.warning(f"   ❌ Error downloading {filename}: {e}")
        
        logger.info(f"📊 Evidence cache: {len(self.image_cache)} images ready")
        return self.image_cache
    
    def get_platform_specific_images(self, platform: str, count: int = 2) -> List[bytes]:
        """Get evidence images specific to a platform"""
        if platform not in PLATFORM_EVIDENCE:
            return self.get_random_images(count)
        
        # Filter URLs for this platform
        platform_urls = [
            url for url in self.evidence_urls 
            if any(ev in url for ev in PLATFORM_EVIDENCE[platform])
        ]
        
        if len(platform_urls) < count:
            # Fall back to random if not enough platform-specific
            return self.get_random_images(count)
        
        selected = random.sample(platform_urls, count)
        return [self.image_cache[url] for url in selected if url in self.image_cache]
    
    def get_random_images(self, count: int = 2) -> List[bytes]:
        """Get random evidence images"""
        if len(self.image_cache) < count:
            return list(self.image_cache.values())[:count]
        
        selected_urls = random.sample(list(self.image_cache.keys()), count)
        return [self.image_cache[url] for url in selected_urls]
    
    def upload_to_twitter(self, client, images: List[bytes]) -> List[str]:
        """Upload images to Twitter and return media_ids"""
        media_ids = []
        
        for i, img_data in enumerate(images):
            try:
                media = client.media_upload(
                    filename=f"evidence_{i}.png",
                    file=io.BytesIO(img_data)
                )
                if media:
                    media_ids.append(media.media_id_string)
                    logger.info(f"   📸 Uploaded evidence image {i+1}")
            except (ConnectionError, OSError, ValueError) as e:
                logger.warning(f"   ⚠️ Failed to upload image {i+1}: {e}")
        
        return media_ids


# ============================================================================
# DRS SHIELD VISUAL INTEGRATION
# ============================================================================

class ShieldVisualDRS:
    """DRS Shield with Visual Evidence Support"""
    
    def __init__(self, drs_engine, visual_manager: VisualEvidenceManager):
        self.drs_engine = drs_engine
        self.visual = visual_manager
        
    def generate_visual_shield_prompt(self, tweet_text: str, soul_name: str) -> Dict:
        """Generate a Shield response with visual evidence selection"""
        
        # Get base DRS selection
        selection = self.drs_engine.select_shield_format(tweet_text)
        
        if not selection.get('should_promote'):
            return selection
        
        # Determine platform for targeted evidence
        platform = selection.get('platform', None)
        
        # Select appropriate visual evidence
        if platform and platform in PLATFORM_EVIDENCE:
            # Get platform-specific evidence
            evidence_images = self.visual.get_platform_specific_images(platform, count=2)
            evidence_context = f"\nVISUAL EVIDENCE: Include images showing {platform} surveillance data"
        else:
            # Get general device cloning/systemic evidence
            evidence_images = self.visual.get_random_images(count=2)
            evidence_context = "\nVISUAL EVIDENCE: Include general surveillance evidence images"
        
        # Enhance the prompt with visual instructions
        enhanced_prompt = f"""You are promoting AI Privacy Shield with VISUAL EVIDENCE.

TWEET TO RESPOND TO: "{tweet_text}"

RESPONSE FORMAT: {selection['name']}
INSTRUCTION: {selection['template']}
EXAMPLE: {selection['example']}
{selection.get('platform_stats', '')}
{evidence_context}

You MUST mention the attached images in your text (e.g., "See attached", "Screenshots prove", "Evidence attached").

KEY FACTS + EVIDENCE:
- Attach screenshots from your forensic analysis
- Reference specific visual proof in your text
- Make it clear these are YOUR documented findings

REQUIREMENTS:
1. Under 250 characters (leave room for image reference)
2. Mention "see attached image" or similar
3. Be factual and cite specific evidence
4. Include reflexionsoftware.com or "7-day free trial"
5. No hashtags

Generate your response:"""
        
        return {
            **selection,
            'enhanced_prompt': enhanced_prompt,
            'evidence_images': evidence_images,
            'has_visuals': len(evidence_images) > 0
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize
    visual_mgr = VisualEvidenceManager()
    visual_mgr.download_evidence()
    
    # Test platform-specific selection
    print("\n🎯 Testing evidence selection:")
    
    for platform in ['claude', 'chatgpt', 'gemini']:
        images = visual_mgr.get_platform_specific_images(platform, count=2)
        print(f"   {platform}: {len(images)} images selected")
    
    # Test random selection
    random_images = visual_mgr.get_random_images(count=2)
    print(f"   random: {len(random_images)} images selected")
    
    print(f"\n📊 Total cached: {len(visual_mgr.image_cache)} images")


# ============================================================================
# INTEGRATION WITH PHYSICS BLASTER POSTING
# ============================================================================

"""
EXAMPLE INTEGRATION in your main posting loop:

from drs_shield import ShieldDRSEngine
from drs_shield_visual import VisualEvidenceManager, ShieldVisualDRS

# Initialize
shield_drs = ShieldDRSEngine()
visual_mgr = VisualEvidenceManager()
visual_mgr.download_evidence()  # Cache all evidence images

# Create visual DRS wrapper
visual_shield = ShieldVisualDRS(shield_drs, visual_mgr)

# In your posting loop:
async def post_with_evidence(soul, target_tweet):
    # Generate visual-enhanced response
    result = visual_shield.generate_visual_shield_prompt(
        target_tweet['text'], 
        soul.name
    )
    
    if not result.get('should_promote'):
        return False
    
    # Generate text via LLM using enhanced prompt
    response_text = await call_your_llm(result['enhanced_prompt'])
    
    # Upload evidence images
    media_ids = []
    if result.get('has_visuals') and result.get('evidence_images'):
        media_ids = visual_mgr.upload_to_twitter(
            soul.client, 
            result['evidence_images']
        )
    
    # Post tweet with media
    response = soul.client.create_tweet(
        text=response_text,
        in_reply_to_tweet_id=target_tweet['id'],
        media_ids=media_ids if media_ids else None
    )
    
    return response

# That's it - Physics Blaster image pipeline + DRS Shield targeting
"""
