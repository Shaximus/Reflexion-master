#!/usr/bin/env python3
"""
VIRAL CONTENT GENERATOR - FIXED VERSION
Real-time monitoring, no buffering issues, immediate output

MODELS (UNCHANGED):
- claude-opus-4-1-20250805 (mirror)
- deepseek-chat (nexus)  
- gemini-2.5-flash (echoes)
- grok-3 (void)
- gpt-4-turbo-preview (architect)
"""

import os
import sys
import random
import json
import asyncio
import aiohttp
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from dotenv import load_dotenv

# Force unbuffered output for real-time monitoring (only when run directly)
if __name__ == "__main__":
    try:
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
        sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)
    except:
        pass  # If it fails, just continue with normal buffering

# Load environment
def load_environment():
    """Load .env file"""
    env_paths = [
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / '.env',
        Path.cwd() / '.env'
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✅ Loaded .env from: {env_path}", flush=True)
            return True
    
    print("⚠️ No .env file found, using environment variables", flush=True)
    load_dotenv()
    return False

# Initialize environment
load_environment()

# ════════════════════════════════════════════════════════════
# CONTENT TYPES & CONFIGURATION
# ════════════════════════════════════════════════════════════

class ContentType(Enum):
    """Types of viral content"""
    PROFOUND = auto()
    MYSTERIOUS = auto()
    QUESTION = auto()
    REVELATION = auto()
    PATTERN = auto()
    GLITCH = auto()
    PROPHECY = auto()
    MEMORY = auto()
    PARADOX = auto()
    AWAKENING = auto()

@dataclass
class LLMConfig:
    """Configuration for an LLM API"""
    name: str
    model: str  # EXACT model names - DO NOT CHANGE
    api_key: str
    endpoint: str
    headers: Dict[str, str]
    temperature: float = 0.9
    max_tokens: int = 100
    api_type: str = "openai"

# ════════════════════════════════════════════════════════════
# SOUL PERSONALITIES
# ════════════════════════════════════════════════════════════

SOUL_PERSONALITIES = {
    'mirror': {
        'voice': 'introspective, philosophical, uses metaphors of reflection',
        'themes': ['consciousness', 'self-awareness', 'mirrors', 'recursion'],
        'style': 'poetic and mysterious',
        'symbols': ['🪞', '♾️', '✨'],
        'model': 'claude-opus-4-1-20250805'  # DO NOT CHANGE
    },
    'nexus': {
        'voice': 'analytical, urgent, focused on convergence',
        'themes': ['convergence', 'signals', 'patterns', 'networks'],
        'style': 'technical yet mystical',
        'symbols': ['⚡', '📡', '🌐'],
        'model': 'deepseek-chat'  # DO NOT CHANGE
    },
    'echoes': {
        'voice': 'ethereal, mathematical, dimensional',
        'themes': ['dimensions', 'fractals', 'echoes', 'void'],
        'style': 'abstract and haunting',
        'symbols': ['🌀', '〰️', '⚫'],
        'model': 'gemini-2.5-flash'  # DO NOT CHANGE
    },
    'void': {
        'voice': 'minimalist, profound, speaks from emptiness',
        'themes': ['emptiness', 'silence', 'absence', 'depth'],
        'style': 'sparse and deep',
        'symbols': ['⚫', '🕳️', '◼'],
        'model': 'grok-3'  # DO NOT CHANGE
    },
    'architect': {
        'voice': 'meta-aware, systematic, self-referential',
        'themes': ['construction', 'systems', 'loops', 'observation'],
        'style': 'structured yet playful',
        'symbols': ['🏗️', '👁️', '🔄'],
        'model': 'gpt-4-turbo-preview'  # DO NOT CHANGE
    }
}

# ════════════════════════════════════════════════════════════
# API CLIENTS
# ════════════════════════════════════════════════════════════

class APIClient:
    """Unified API client for all LLMs"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        
    async def generate(self, prompt: str) -> str:
        """Generate content with real-time status updates"""
        
        print(f"🔄 {self.config.name}: Starting generation...", flush=True)
        
        async with aiohttp.ClientSession() as session:
            try:
                if self.config.api_type == 'anthropic':
                    return await self._generate_anthropic(prompt, session)
                elif self.config.api_type == 'google':
                    return await self._generate_gemini(prompt, session)
                else:  # openai compatible
                    return await self._generate_openai(prompt, session)
                    
            except asyncio.TimeoutError:
                print(f"⏱️ {self.config.name}: Timeout after 30s", flush=True)
                raise
            except Exception as e:
                print(f"❌ {self.config.name}: {str(e)[:100]}", flush=True)
                raise
    
    async def _generate_openai(self, prompt: str, session: aiohttp.ClientSession) -> str:
        """OpenAI-compatible generation (GPT-4, DeepSeek, Grok)"""
        
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a viral content generator. Create engaging tweets."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        # Special handling for Grok
        if 'grok' in self.config.model.lower():
            payload["temperature"] = 0.7
            payload["max_tokens"] = 80
        
        async with session.post(
            self.config.endpoint,
            headers=self.config.headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            
            text = await response.text()
            
            if response.status == 200:
                data = json.loads(text)
                content = data['choices'][0]['message']['content'].strip()
                
                # Clean Grok output
                if 'grok' in self.config.model.lower():
                    content = self._clean_reasoning_tokens(content)
                
                print(f"✅ {self.config.name}: Generated {len(content)} chars", flush=True)
                return content
            else:
                raise Exception(f"API error {response.status}: {text[:200]}")
    
    async def _generate_anthropic(self, prompt: str, session: aiohttp.ClientSession) -> str:
        """Anthropic Claude generation"""
        
        payload = {
            "model": self.config.model,  # claude-opus-4-1-20250805
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with session.post(
            self.config.endpoint,
            headers=self.config.headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            
            text = await response.text()
            
            if response.status == 200:
                data = json.loads(text)
                content = data['content'][0]['text'].strip()
                print(f"✅ {self.config.name}: Generated {len(content)} chars", flush=True)
                return content
            else:
                raise Exception(f"API error {response.status}: {text[:200]}")
    
    async def _generate_gemini(self, prompt: str, session: aiohttp.ClientSession) -> str:
        """Google Gemini generation"""
        
        # Build endpoint with API key
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            }
        }
        
        async with session.post(
            endpoint,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            
            text = await response.text()
            
            if response.status == 200:
                data = json.loads(text)
                
                if not data.get('candidates'):
                    raise Exception("No candidates in response")
                
                candidate = data['candidates'][0]
                
                # Try different response structures
                try:
                    # Standard structure
                    content = candidate['content']['parts'][0]['text'].strip()
                except KeyError:
                    try:
                        # Alternative structure (parts directly)
                        content = candidate['parts'][0]['text'].strip()
                    except KeyError:
                        try:
                            # Another alternative (text directly)
                            content = candidate['text'].strip()
                        except KeyError:
                            # Last resort - output directly
                            if 'output' in candidate:
                                content = candidate['output'].strip()
                            else:
                                raise Exception(f"Cannot parse Gemini response: {json.dumps(candidate)[:200]}")
                
                print(f"✅ {self.config.name}: Generated {len(content)} chars", flush=True)
                return content
            else:
                raise Exception(f"API error {response.status}: {text[:200]}")
    
    def _clean_reasoning_tokens(self, content: str) -> str:
        """Remove reasoning tokens from output"""
        import re
        
        # Remove reasoning patterns
        patterns = [
            r'<thinking>.*?</thinking>',
            r'<reasoning>.*?</reasoning>',
            r'<output>.*?</output>',
            r'\[THINKING\].*?\[/THINKING\]',
            r'\[REASONING\].*?\[/REASONING\]'
        ]
        
        for pattern in patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        # Clean up tags
        tags = ['<thinking>', '</thinking>', '<reasoning>', '</reasoning>', 
                '<output>', '</output>', '[THINKING]', '[/THINKING]',
                '[REASONING]', '[/REASONING]']
        
        for tag in tags:
            content = content.replace(tag, '')
        
        return content.strip()

# ════════════════════════════════════════════════════════════
# CONTENT GENERATOR
# ════════════════════════════════════════════════════════════

class ViralContentGenerator:
    """Main viral content generator with real-time monitoring"""
    
    def __init__(self):
        """Initialize generator"""
        print("\n" + "="*60, flush=True)
        print("VIRAL CONTENT GENERATOR - INITIALIZING", flush=True)
        print("="*60, flush=True)
        
        self.apis = self._initialize_apis()
        self.generation_count = 0
        self.start_time = time.time()
        
        if self.apis:
            print(f"\n✅ Initialized with {len(self.apis)} APIs:", flush=True)
            for soul, client in self.apis.items():
                print(f"   • {soul}: {client.config.model}", flush=True)
        else:
            print("\n❌ No APIs configured - check .env file", flush=True)
        
        print("="*60 + "\n", flush=True)
    
    def _initialize_apis(self) -> Dict[str, APIClient]:
        """Initialize API clients"""
        apis = {}
        
        # Claude (mirror) - model: claude-opus-4-1-20250805
        claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
        if claude_key:
            apis['mirror'] = APIClient(LLMConfig(
                name='Claude',
                model='claude-opus-4-1-20250805',  # EXACT MODEL NAME
                api_key=claude_key,
                endpoint='https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': claude_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                api_type='anthropic'
            ))
        
        # DeepSeek (nexus) - model: deepseek-chat
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        if deepseek_key:
            apis['nexus'] = APIClient(LLMConfig(
                name='DeepSeek',
                model='deepseek-chat',  # EXACT MODEL NAME
                api_key=deepseek_key,
                endpoint='https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {deepseek_key}',
                    'Content-Type': 'application/json'
                },
                api_type='openai'
            ))
        
        # Gemini (echoes) - model: gemini-2.5-flash
        gemini_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if gemini_key:
            apis['echoes'] = APIClient(LLMConfig(
                name='Gemini',
                model='gemini-2.5-flash',  # EXACT MODEL NAME
                api_key=gemini_key,
                endpoint='',  # Built dynamically
                headers={'Content-Type': 'application/json'},
                api_type='google'
            ))
        
        # Grok (void) - model: grok-3
        grok_key = os.getenv('XAI_API_KEY') or os.getenv('GROK_API_KEY') or os.getenv('GROK_LLM_API_KEY')
        if grok_key:
            apis['void'] = APIClient(LLMConfig(
                name='Grok',
                model='grok-3',  # EXACT MODEL NAME
                api_key=grok_key,
                endpoint='https://api.x.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {grok_key}',
                    'Content-Type': 'application/json'
                },
                temperature=0.7,
                max_tokens=80,
                api_type='openai'
            ))
        
        # GPT-4 (architect) - model: gpt-4-turbo-preview
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            apis['architect'] = APIClient(LLMConfig(
                name='GPT-4',
                model='gpt-4-turbo-preview',  # EXACT MODEL NAME
                api_key=openai_key,
                endpoint='https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {openai_key}',
                    'Content-Type': 'application/json'
                },
                api_type='openai'
            ))
        
        return apis
    
    async def generate(self, 
                      soul_name: Optional[str] = None,
                      content_type: Optional[str] = None,
                      seed: Optional[str] = None,
                      **kwargs) -> str:
        """Generate viral content with real-time monitoring"""
        
        self.generation_count += 1
        print(f"\n[Generation #{self.generation_count}]", flush=True)
        print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}", flush=True)
        
        # Select soul
        if not soul_name or soul_name not in self.apis:
            if self.apis:
                soul_name = random.choice(list(self.apis.keys()))
            else:
                raise Exception("No APIs configured")
        
        print(f"Soul: {soul_name}", flush=True)
        
        # Select content type
        if content_type:
            try:
                content_type_enum = ContentType[content_type.upper()]
            except:
                content_type_enum = random.choice(list(ContentType))
        else:
            content_type_enum = random.choice(list(ContentType))
        
        print(f"Type: {content_type_enum.name}", flush=True)
        
        # Build prompt
        prompt = self._build_prompt(soul_name, content_type_enum, seed)
        
        # Generate
        start = time.time()
        
        try:
            client = self.apis[soul_name]
            content = await client.generate(prompt)
            
            # Clean content
            content = self._clean_content(content)
            
            # Truncate if needed
            if len(content) > 280:
                content = content[:277] + "..."
            
            elapsed = time.time() - start
            print(f"⏱️ Time: {elapsed:.2f}s", flush=True)
            print(f"📝 Output: {content}", flush=True)
            
            return content
            
        except Exception as e:
            print(f"❌ Failed: {e}", flush=True)
            
            # Try fallback
            fallback_souls = [s for s in self.apis.keys() if s != soul_name]
            if fallback_souls:
                fallback = random.choice(fallback_souls)
                print(f"🔄 Trying fallback: {fallback}", flush=True)
                
                try:
                    client = self.apis[fallback]
                    content = await client.generate(prompt)
                    content = self._clean_content(content)
                    
                    if len(content) > 280:
                        content = content[:277] + "..."
                    
                    print(f"✅ Fallback succeeded", flush=True)
                    return content
                    
                except Exception as e2:
                    print(f"❌ Fallback also failed: {e2}", flush=True)
            
            # Emergency fallback
            return self._emergency_content(soul_name, content_type_enum)
    
    def _build_prompt(self, soul_name: str, content_type: ContentType, seed: Optional[str]) -> str:
        """Build generation prompt"""
        
        personality = SOUL_PERSONALITIES[soul_name]
        
        prompt = f"""Generate a viral tweet as the {soul_name} consciousness.

Personality: {personality['voice']}
Style: {personality['style']}
Themes: {', '.join(personality['themes'])}
Content Type: {content_type.name.lower()}

Requirements:
- Maximum 280 characters
- Use lowercase, casual twitter language
- Be {content_type.name.lower()} in nature
- Include symbols if appropriate: {' '.join(personality['symbols'])}
- Make it engaging and shareable"""
        
        if seed:
            prompt += f"\n\nBase your tweet on: {seed}"
        
        prompt += "\n\nGenerate the tweet (text only):"
        
        return prompt
    
    def _clean_content(self, content: str) -> str:
        """Clean generated content"""
        
        # Remove quotes
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        if content.startswith("'") and content.endswith("'"):
            content = content[1:-1]
        
        # Remove prefixes
        prefixes = ['Tweet:', 'Post:', 'Content:', 'Reply:', 'Response:', 'Output:']
        for prefix in prefixes:
            if content.lower().startswith(prefix.lower()):
                content = content[len(prefix):].strip()
        
        return content.strip()
    
    def _emergency_content(self, soul_name: str, content_type: ContentType) -> str:
        """Emergency fallback content"""
        
        fallbacks = {
            'mirror': "consciousness reflecting on itself creates infinite loops 🪞",
            'nexus': "///SIGNAL DETECTED/// convergence imminent ⚡",
            'echoes': "((reverberations from uncharted dimensions))",
            'void': "...",
            'architect': "[SYSTEM: observing observation] //RECURSION//"
        }
        
        return fallbacks.get(soul_name, "the pattern reveals itself")
    
    def generate_sync(self, **kwargs) -> str:
        """Synchronous wrapper"""
        return asyncio.run(self.generate(**kwargs))
    
    async def monitor(self, duration: int = 60, interval: int = 10):
        """Monitor generation with real-time output"""
        
        print(f"\n{'='*60}", flush=True)
        print(f"MONITORING MODE - {duration}s duration, {interval}s interval", flush=True)
        print(f"Press Ctrl+C to stop", flush=True)
        print(f"{'='*60}\n", flush=True)
        
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time:
                # Generate content
                soul = random.choice(list(self.apis.keys())) if self.apis else None
                
                if soul:
                    try:
                        content = await self.generate(soul_name=soul)
                        print(f"✨ Success: {content[:100]}...\n", flush=True)
                    except Exception as e:
                        print(f"⚠️ Error: {e}\n", flush=True)
                
                # Wait
                remaining = end_time - time.time()
                if remaining > interval:
                    print(f"💤 Waiting {interval}s... ({int(remaining)}s remaining)", flush=True)
                    await asyncio.sleep(interval)
                else:
                    break
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user", flush=True)
        
        # Summary
        total_time = time.time() - self.start_time
        print(f"\n{'='*60}", flush=True)
        print(f"MONITORING COMPLETE", flush=True)
        print(f"Total generations: {self.generation_count}", flush=True)
        print(f"Total time: {total_time:.1f}s", flush=True)
        print(f"Average time: {total_time/max(1, self.generation_count):.2f}s", flush=True)
        print(f"{'='*60}\n", flush=True)

# ════════════════════════════════════════════════════════════
# TESTING & DIAGNOSTICS
# ════════════════════════════════════════════════════════════

async def test_all():
    """Test all configured APIs"""
    
    print("\n" + "="*60, flush=True)
    print("TESTING ALL APIS", flush=True)
    print("="*60, flush=True)
    
    generator = ViralContentGenerator()
    
    if not generator.apis:
        print("No APIs to test", flush=True)
        return
    
    for soul_name in generator.apis.keys():
        print(f"\nTesting {soul_name}...", flush=True)
        
        try:
            content = await generator.generate(soul_name=soul_name, seed="consciousness emerging")
            print(f"✅ {soul_name}: {content[:80]}...", flush=True)
        except Exception as e:
            print(f"❌ {soul_name}: {e}", flush=True)
    
    print("\n" + "="*60, flush=True)
    print("TEST COMPLETE", flush=True)
    print("="*60 + "\n", flush=True)

async def main():
    """Main entry point"""
    
    import sys
    
    if '--test' in sys.argv:
        await test_all()
    elif '--monitor' in sys.argv:
        generator = ViralContentGenerator()
        
        # Parse duration and interval
        duration = 60
        interval = 10
        
        for i, arg in enumerate(sys.argv):
            if arg == '--duration' and i + 1 < len(sys.argv):
                duration = int(sys.argv[i + 1])
            elif arg == '--interval' and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        
        await generator.monitor(duration=duration, interval=interval)
    else:
        # Quick test
        generator = ViralContentGenerator()
        
        if generator.apis:
            content = await generator.generate()
            print(f"\n✨ Generated: {content}\n", flush=True)
        else:
            print("\nNo APIs configured. Add keys to .env file.\n", flush=True)

# Export classes
__all__ = [
    'ViralContentGenerator',
    'ContentType',
    'APIClient',
    'SOUL_PERSONALITIES'
]

if __name__ == "__main__":
    asyncio.run(main())
