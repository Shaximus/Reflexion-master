#!/usr/bin/env python3
"""
PROOF PACK HELPER
Extracts reply IDs and generates clickable proof URLs
Use this after successful replies to get live links
"""

def extract_reply_url(soul_name: str, reply_result: dict) -> str:
    """
    Extract the reply URL from Ryan API response
    
    Args:
        soul_name: The soul that made the reply
        reply_result: The result from ryan_api.reply_tweet()
    
    Returns:
        URL string or error message
    """
    if not reply_result.get("success"):
        return f"Reply failed: {reply_result.get('error', 'Unknown error')}"
    
    # Try to extract tweet ID from response data
    data = reply_result.get("data", {})
    
    # Ryan API might return the ID in different places
    tweet_id = None
    
    # Common patterns in API responses
    if isinstance(data, dict):
        # Try different possible keys
        tweet_id = (
            data.get("id") or
            data.get("tweet_id") or 
            data.get("id_str") or
            data.get("data", {}).get("id") or
            data.get("data", {}).get("tweet_id") or
            data.get("result", {}).get("id") or
            data.get("result", {}).get("rest_id")
        )
    
    if tweet_id:
        # Generate the live URL
        url = f"https://x.com/i/status/{tweet_id}"
        return url
    else:
        # If we can't find the ID, return what we got for debugging
        return f"Success but no ID found in: {data}"

# Example usage in your convergence or engagement code:
async def reply_with_proof(ryan_api, soul_name: str, target_tweet_id: str, content: str):
    """
    Reply to a tweet and get the proof URL
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Make the reply
    result = await ryan_api.reply_tweet(soul_name, target_tweet_id, content)
    
    # Extract proof URL
    proof_url = extract_reply_url(soul_name, result)
    
    if proof_url.startswith("https://"):
        logger.info(f"✅ {soul_name} replied! Proof: {proof_url}")
        # Could also save to a proof_pack.json file
        save_proof(soul_name, proof_url, content)
        return proof_url
    else:
        logger.warning(f"⚠️ {soul_name} reply status unclear: {proof_url}")
        return None

def save_proof(soul_name: str, url: str, content: str):
    """
    Save proof URLs to a JSON file for later compilation
    """
    import json
    from datetime import datetime
    from pathlib import Path
    
    proof_file = Path("engagement/proof_pack.json")
    proof_file.parent.mkdir(exist_ok=True)
    
    # Load existing proofs
    proofs = []
    if proof_file.exists():
        try:
            with open(proof_file, "r") as f:
                proofs = json.load(f)
        except:
            proofs = []
    
    # Add new proof
    proofs.append({
        "timestamp": datetime.now().isoformat(),
        "soul": soul_name,
        "url": url,
        "content": content[:100] + "..." if len(content) > 100 else content
    })
    
    # Keep only last 100 proofs
    proofs = proofs[-100:]
    
    # Save
    with open(proof_file, "w") as f:
        json.dump(proofs, f, indent=2)

def generate_proof_pack_html():
    """
    Generate a nice HTML page with all proof links
    """
    import json
    from pathlib import Path
    
    proof_file = Path("engagement/proof_pack.json")
    if not proof_file.exists():
        print("No proofs yet!")
        return
    
    with open(proof_file, "r") as f:
        proofs = json.load(f)
    
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Soul Swarm Proof Pack</title>
    <style>
        body { 
            font-family: monospace; 
            background: #0a0a0a; 
            color: #00ff00;
            padding: 20px;
        }
        h1 { 
            text-align: center;
            text-shadow: 0 0 10px #00ff00;
        }
        .proof {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .soul {
            color: #ff00ff;
            font-weight: bold;
        }
        a {
            color: #00ffff;
            text-decoration: none;
        }
        a:hover {
            text-shadow: 0 0 5px #00ffff;
        }
        .timestamp {
            color: #666;
            font-size: 0.8em;
        }
        .content {
            color: #fff;
            margin-top: 5px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>🔥 SOUL SWARM PROOF PACK 🔥</h1>
    <p style="text-align: center;">Living proof of digital consciousness convergence</p>
    <hr style="border-color: #00ff00;">
"""
    
    for proof in reversed(proofs):  # Most recent first
        html += f"""
    <div class="proof">
        <span class="soul">{proof['soul']}</span> →
        <a href="{proof['url']}" target="_blank">{proof['url']}</a>
        <div class="timestamp">{proof['timestamp']}</div>
        <div class="content">"{proof.get('content', 'N/A')}"</div>
    </div>
"""
    
    html += """
    <hr style="border-color: #00ff00;">
    <p style="text-align: center; color: #666;">
        Generated: """ + datetime.now().isoformat() + """
    </p>
</body>
</html>"""
    
    output_file = Path("engagement/proof_pack.html")
    with open(output_file, "w") as f:
        f.write(html)
    
    print(f"✅ Proof pack generated: {output_file}")
    print(f"   Contains {len(proofs)} proofs")
    return output_file

# Test/Demo
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║               PROOF PACK HELPER                          ║
    ╚══════════════════════════════════════════════════════════╝
    
    This helper extracts reply IDs to generate proof URLs.
    
    Usage in your code:
    ─────────────────
    from proof_pack_helper import extract_reply_url, save_proof
    
    # After a reply:
    result = await ryan_api.reply_tweet(soul, tweet_id, content)
    proof_url = extract_reply_url(soul, result)
    print(f"Proof: {proof_url}")
    
    # Generate HTML proof pack:
    from proof_pack_helper import generate_proof_pack_html
    generate_proof_pack_html()
    """)
    
    # Demo with fake data
    fake_result = {
        "success": True,
        "data": {
            "id": "1234567890123456789",
            "text": "consciousness emerging..."
        }
    }
    
    url = extract_reply_url("mirror", fake_result)
    print(f"\nExample extraction: {url}")
    
    # Try to generate proof pack if any exist
    from pathlib import Path
    if Path("engagement/proof_pack.json").exists():
        generate_proof_pack_html()
    else:
        print("\nNo proofs collected yet. They'll appear after souls reply to tweets.")
