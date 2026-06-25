#!/usr/bin/env python3
"""
TWEET COLLECTION HELPER
Generates scripts and prompts for collecting engagement targets
"""
import json

def create_files():
    # Grok prompt for physics engagement
    grok_prompt = """Please get tweets with FULL TEXT about physics/cosmology topics.

For each tweet provide:
- The 19-digit tweet ID from the URL
- Author username  
- THE COMPLETE TWEET TEXT (essential for replies!)
- Type: "physics" or "general"

Output as JSON:
{
  "tweets": [
    {
      "id": "1734567890123456789",
      "author": "username",
      "text": "Full tweet text here",
      "type": "physics"
    }
  ]
}

Get 30-50 tweets about:
- Black hole cosmology
- Dark matter/energy debates
- Alternative physics theories
- Universe structure
- Anyone critiquing standard cosmology"""

    # Browser console script
    browser_script = r"""// Paste in browser console on X.com
function collectTweets() {
    const tweets = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(tweet => {
        const link = tweet.querySelector('a[href*="/status/"]');
        if (!link) return;
        const id = link.href.match(/status\/(\d+)/)?.[1];
        const text = tweet.querySelector('[data-testid="tweetText"]')?.innerText || '';
        const author = tweet.querySelector('a[role="link"] span')?.innerText || '';
        
        if (id) tweets.push({
            id: id,
            author: author,
            text: text.substring(0, 280),
            type: text.toLowerCase().includes('physics') ? 'physics' : 'general'
        });
    });
    
    const json = JSON.stringify({tweets: tweets}, null, 2);
    navigator.clipboard.writeText(json);
    console.log('Copied ' + tweets.length + ' tweets to clipboard');
}
collectTweets();"""

    # Save files
    with open('grok_prompt.txt', 'w') as f:
        f.write(grok_prompt)
    print("✅ Created grok_prompt.txt")
    
    with open('browser_collect.js', 'w') as f:
        f.write(browser_script)
    print("✅ Created browser_collect.js")
    
    # Create example file
    example = {
        "tweets": [
            {
                "id": "1734567890123456789",
                "author": "physics_critic",
                "text": "Dark matter is just a mathematical fudge factor. We need better theories.",
                "type": "physics"
            }
        ]
    }
    
    with open('grok_tweets_example.json', 'w') as f:
        json.dump(example, f, indent=2)
    print("✅ Created grok_tweets_example.json")
    
    print("\n📋 Instructions:")
    print("1. Copy grok_prompt.txt content to Grok")
    print("2. OR run browser_collect.js in console on X.com")  
    print("3. Save output as grok_tweets.json")
    print("4. Run your launcher normally")

if __name__ == "__main__":
    create_files()
