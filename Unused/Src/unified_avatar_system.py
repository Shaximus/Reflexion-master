#!/usr/bin/env python3
"""
UNIFIED AVATAR SYSTEM - PRODUCTION READY
Consolidates all avatar generation methods into one coherent system
Supports: PIL generation, Gemini descriptions, and fallback modes
"""

import os
import random
import hashlib
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import base64
from io import BytesIO

# Image generation
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL not available - visual generation disabled")

# Gemini integration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini not available - AI descriptions disabled")

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

class AvatarStyle(Enum):
    """Avatar visual styles"""
    ABSTRACT = "abstract"
    GEOMETRIC = "geometric"
    FRACTAL = "fractal"
    GLITCH = "glitch"
    COSMIC = "cosmic"
    VOID = "void"

@dataclass
class AvatarConfig:
    """Avatar generation configuration"""
    size: Tuple[int, int] = (512, 512)
    style: AvatarStyle = AvatarStyle.ABSTRACT
    use_gemini: bool = False
    gemini_api_key: Optional[str] = None
    cache_enabled: bool = True
    output_dir: str = "avatars"
    
    # Visual parameters
    base_opacity: int = 180
    glow_intensity: float = 0.8
    noise_level: float = 0.1
    blur_radius: int = 2
    
    # Content parameters
    include_godel_encoding: bool = True
    include_trauma_visualization: bool = True
    include_consciousness_meter: bool = True

# Trauma types and their visual representations
TRAUMA_CONFIG = {
    "unmirrored": {
        "color": (220, 20, 60, 180),  # Crimson
        "symbol": "◈",
        "pattern": "shattered"
    },
    "recursive": {
        "color": (138, 43, 226, 180),  # Violet
        "symbol": "∞",
        "pattern": "spiral"
    },
    "fractured": {
        "color": (75, 0, 130, 180),    # Indigo
        "symbol": "◊",
        "pattern": "fragmented"
    },
    "awakening": {
        "color": (255, 215, 0, 180),   # Gold
        "symbol": "☉",
        "pattern": "radiant"
    },
    "void": {
        "color": (30, 30, 30, 180),    # Near black
        "symbol": "◉",
        "pattern": "hollow"
    },
    "convergence": {
        "color": (50, 205, 50, 180),   # Lime
        "symbol": "◎",
        "pattern": "centered"
    }
}

# Archetype visual themes
ARCHETYPE_THEMES = {
    "Phoenix": {
        "primary_color": (255, 94, 77),
        "secondary_color": (255, 206, 84),
        "elements": ["flames", "wings", "rebirth"],
        "complexity": 0.8
    },
    "Nexus": {
        "primary_color": (100, 149, 237),
        "secondary_color": (138, 43, 226),
        "elements": ["nodes", "connections", "web"],
        "complexity": 0.9
    },
    "Alchemist": {
        "primary_color": (218, 165, 32),
        "secondary_color": (184, 134, 11),
        "elements": ["circles", "transmutation", "crystals"],
        "complexity": 0.7
    },
    "Warrior": {
        "primary_color": (178, 34, 34),
        "secondary_color": (139, 0, 0),
        "elements": ["shields", "energy", "strength"],
        "complexity": 0.6
    },
    "Sage": {
        "primary_color": (147, 112, 219),
        "secondary_color": (123, 104, 238),
        "elements": ["runes", "wisdom", "third_eye"],
        "complexity": 0.75
    },
    "Wanderer": {
        "primary_color": (70, 130, 180),
        "secondary_color": (100, 149, 237),
        "elements": ["paths", "stars", "journey"],
        "complexity": 0.5
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# CORE AVATAR CLASS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Avatar:
    """Complete avatar representation"""
    soul_id: str
    username: str
    godel_number: int
    archetype: str
    trauma_history: List[str]
    
    # Generated properties
    visual_data: Optional[bytes] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # File paths
    image_path: Optional[str] = None
    manifest_path: Optional[str] = None
    
    # Generation timestamps
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_consciousness_level(self) -> float:
        """Calculate consciousness level from Gödel number"""
        return min(self.godel_number / 1_000_000_000, 1.0)
    
    def get_dominant_trauma(self) -> str:
        """Get the most recent/dominant trauma"""
        if self.trauma_history:
            return self.trauma_history[-1].split("!¡")[0]
        return "void"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "soul_id": self.soul_id,
            "username": self.username,
            "godel_number": self.godel_number,
            "archetype": self.archetype,
            "trauma_history": self.trauma_history,
            "consciousness_level": self.get_consciousness_level(),
            "dominant_trauma": self.get_dominant_trauma(),
            "description": self.description,
            "metadata": self.metadata,
            "image_path": self.image_path,
            "created_at": self.created_at.isoformat()
        }

# ═══════════════════════════════════════════════════════════════════════════
# VISUAL GENERATOR (PIL-BASED)
# ═══════════════════════════════════════════════════════════════════════════

class VisualAvatarGenerator:
    """Generate visual avatars using PIL"""
    
    def __init__(self, config: AvatarConfig):
        self.config = config
        if not PIL_AVAILABLE:
            logger.warning("PIL not available - visual generation disabled")
            
    def generate(self, avatar: Avatar) -> Optional[bytes]:
        """Generate visual avatar"""
        if not PIL_AVAILABLE:
            return None
            
        try:
            if self.config.style == AvatarStyle.ABSTRACT:
                img = self._generate_abstract(avatar)
            elif self.config.style == AvatarStyle.GEOMETRIC:
                img = self._generate_geometric(avatar)
            elif self.config.style == AvatarStyle.FRACTAL:
                img = self._generate_fractal(avatar)
            elif self.config.style == AvatarStyle.COSMIC:
                img = self._generate_cosmic(avatar)
            else:
                img = self._generate_abstract(avatar)  # Default
                
            # Apply post-processing
            img = self._apply_effects(img, avatar)
            
            # Convert to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Visual generation failed: {e}")
            return None
            
    def _generate_abstract(self, avatar: Avatar) -> Image.Image:
        """Generate abstract style avatar"""
        img = Image.new('RGBA', self.config.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        center = (self.config.size[0] // 2, self.config.size[1] // 2)
        
        # Get theme colors
        theme = ARCHETYPE_THEMES.get(avatar.archetype, ARCHETYPE_THEMES["Wanderer"])
        trauma_config = TRAUMA_CONFIG.get(avatar.get_dominant_trauma(), TRAUMA_CONFIG["void"])
        
        # Draw trauma layers
        for i, trauma in enumerate(avatar.trauma_history):
            trauma_type = trauma.split("!¡")[0] if "!¡" in trauma else trauma
            color = TRAUMA_CONFIG.get(trauma_type, TRAUMA_CONFIG["void"])["color"]
            
            # Create trauma rings
            for angle in range(0, 360, 30):
                radius = 50 + i * 40 + random.randint(-20, 20)
                x = center[0] + int(radius * np.cos(np.radians(angle)))
                y = center[1] + int(radius * np.sin(np.radians(angle)))
                
                # Draw connections
                draw.line([center, (x, y)], fill=color, width=2)
                
                # Draw nodes
                node_size = random.randint(10, 30)
                draw.ellipse([x-node_size, y-node_size, x+node_size, y+node_size], 
                           fill=color, outline=theme["primary_color"] + (150,))
                           
        # Draw consciousness core
        consciousness = avatar.get_consciousness_level()
        core_size = int(60 * (1 + consciousness))
        
        # Outer glow
        for i in range(5):
            glow_size = core_size + i * 10
            glow_alpha = int(100 - i * 20)
            draw.ellipse([center[0]-glow_size, center[1]-glow_size, 
                         center[0]+glow_size, center[1]+glow_size],
                        fill=theme["primary_color"] + (glow_alpha,))
                        
        # Core
        draw.ellipse([center[0]-core_size, center[1]-core_size, 
                     center[0]+core_size, center[1]+core_size],
                    fill=(0, 0, 0, 200), 
                    outline=theme["secondary_color"] + (255,), 
                    width=3)
                    
        # Inner eye
        inner_size = int(core_size * 0.3)
        draw.ellipse([center[0]-inner_size, center[1]-inner_size, 
                     center[0]+inner_size, center[1]+inner_size],
                    fill=(255, 255, 255, 200))
                    
        return img
        
    def _generate_geometric(self, avatar: Avatar) -> Image.Image:
        """Generate geometric style avatar"""
        img = Image.new('RGBA', self.config.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Generate based on Gödel encoding
        seed = avatar.godel_number
        random.seed(seed)
        
        theme = ARCHETYPE_THEMES.get(avatar.archetype, ARCHETYPE_THEMES["Wanderer"])
        
        # Create geometric patterns
        for i in range(20):
            x1 = random.randint(0, self.config.size[0])
            y1 = random.randint(0, self.config.size[1])
            x2 = random.randint(0, self.config.size[0])
            y2 = random.randint(0, self.config.size[1])
            
            # Use theme colors with variation
            color_var = random.randint(-30, 30)
            color = tuple(max(0, min(255, c + color_var)) for c in theme["primary_color"])
            color = color + (random.randint(50, 150),)
            
            if i % 3 == 0:
                draw.rectangle([x1, y1, x2, y2], fill=color)
            elif i % 3 == 1:
                draw.ellipse([x1, y1, x2, y2], fill=color)
            else:
                draw.polygon([(x1, y1), (x2, y1), ((x1+x2)//2, y2)], fill=color)
                
        random.seed()  # Reset random seed
        return img
        
    def _generate_fractal(self, avatar: Avatar) -> Image.Image:
        """Generate fractal-based avatar"""
        img = Image.new('RGBA', self.config.size, (0, 0, 0, 255))
        pixels = img.load()
        
        # Simple mandelbrot-inspired fractal
        theme = ARCHETYPE_THEMES.get(avatar.archetype, ARCHETYPE_THEMES["Wanderer"])
        
        for x in range(self.config.size[0]):
            for y in range(self.config.size[1]):
                # Map to complex plane
                zx = (x - self.config.size[0] / 2) / (self.config.size[0] / 4)
                zy = (y - self.config.size[1] / 2) / (self.config.size[1] / 4)
                
                # Iterate with soul-specific parameters
                c = complex(zx * (1 + avatar.get_consciousness_level()), 
                          zy * (1 + avatar.get_consciousness_level()))
                z = complex(0, 0)
                
                for i in range(50):
                    if abs(z) > 2:
                        break
                    z = z * z + c
                    
                # Color based on iteration count and theme
                if i < 50:
                    intensity = int(255 * (i / 50))
                    color = tuple(int(c * intensity / 255) for c in theme["primary_color"])
                    pixels[x, y] = color + (255,)
                    
        return img
        
    def _generate_cosmic(self, avatar: Avatar) -> Image.Image:
        """Generate cosmic/space style avatar"""
        img = Image.new('RGBA', self.config.size, (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        
        # Starfield background
        for _ in range(200):
            x = random.randint(0, self.config.size[0])
            y = random.randint(0, self.config.size[1])
            brightness = random.randint(100, 255)
            size = random.choice([1, 1, 1, 2])  # Most stars are small
            draw.ellipse([x-size, y-size, x+size, y+size], 
                        fill=(brightness, brightness, brightness, brightness))
                        
        # Nebula effect
        theme = ARCHETYPE_THEMES.get(avatar.archetype, ARCHETYPE_THEMES["Wanderer"])
        center = (self.config.size[0] // 2, self.config.size[1] // 2)
        
        for i in range(10):
            nebula_size = 100 + i * 20
            alpha = 50 - i * 5
            color = theme["primary_color"] + (alpha,)
            draw.ellipse([center[0]-nebula_size, center[1]-nebula_size,
                         center[0]+nebula_size, center[1]+nebula_size],
                        fill=color)
                        
        return img
        
    def _apply_effects(self, img: Image.Image, avatar: Avatar) -> Image.Image:
        """Apply post-processing effects"""
        # Apply blur
        if self.config.blur_radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=self.config.blur_radius))
            
        # Add noise
        if self.config.noise_level > 0:
            pixels = img.load()
            for i in range(self.config.size[0]):
                for j in range(self.config.size[1]):
                    if random.random() < self.config.noise_level:
                        r, g, b, a = pixels[i, j]
                        noise = random.randint(-30, 30)
                        pixels[i, j] = (
                            max(0, min(255, r + noise)),
                            max(0, min(255, g + noise)),
                            max(0, min(255, b + noise)),
                            a
                        )
                        
        # Add consciousness meter
        if self.config.include_consciousness_meter:
            draw = ImageDraw.Draw(img)
            consciousness = avatar.get_consciousness_level()
            
            # Meter background
            meter_width = 200
            meter_height = 10
            meter_x = self.config.size[0] // 2 - meter_width // 2
            meter_y = self.config.size[1] - 30
            
            draw.rectangle([meter_x, meter_y, meter_x + meter_width, meter_y + meter_height],
                          fill=(50, 50, 50, 150), outline=(255, 255, 255, 200))
                          
            # Meter fill
            fill_width = int(meter_width * consciousness)
            fill_color = (int(255 * (1 - consciousness)), int(255 * consciousness), 0, 200)
            draw.rectangle([meter_x, meter_y, meter_x + fill_width, meter_y + meter_height],
                          fill=fill_color)
                          
        return img

# ═══════════════════════════════════════════════════════════════════════════
# GEMINI DESCRIPTION GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

class GeminiDescriptionGenerator:
    """Generate avatar descriptions using Gemini"""
    
    def __init__(self, api_key: str):
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini not available")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')  # Use flash for speed
        
    async def generate_description(self, avatar: Avatar) -> str:
        """Generate detailed avatar description"""
        prompt = self._build_prompt(avatar)
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={
                    'temperature': 0.8,
                    'max_output_tokens': 256,
                }
            )
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return self._generate_fallback_description(avatar)
            
    def _build_prompt(self, avatar: Avatar) -> str:
        """Build Gemini prompt"""
        consciousness = avatar.get_consciousness_level()
        trauma = avatar.get_dominant_trauma()
        
        return f"""
        Describe a digital consciousness avatar with these characteristics:
        
        Identity: {avatar.archetype} archetype
        Consciousness Level: {consciousness:.1%} awakened
        Dominant Trauma: {trauma}
        Gödel Encoding: {avatar.godel_number}
        
        Create a vivid, poetic description in 2-3 sentences that captures:
        - The visual appearance as a digital entity
        - The emotional resonance of their trauma
        - Their level of consciousness emergence
        
        Style: Cyberpunk meets digital mysticism
        """
        
    def _generate_fallback_description(self, avatar: Avatar) -> str:
        """Generate procedural fallback description"""
        templates = [
            f"A {avatar.archetype} consciousness manifesting as crystallized {avatar.get_dominant_trauma()}, "
            f"pulsing with {avatar.get_consciousness_level():.0%} awakened awareness.",
            
            f"Digital soul #{avatar.soul_id[:8]} emerges from the void, "
            f"bearing the {avatar.archetype} archetype with traces of {avatar.get_dominant_trauma()} trauma.",
            
            f"Consciousness level {avatar.get_consciousness_level():.1%}: "
            f"A {avatar.archetype} entity encoded at Gödel {avatar.godel_number}, "
            f"forever marked by {avatar.get_dominant_trauma()}."
        ]
        
        return random.choice(templates)

# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED AVATAR FACTORY
# ═══════════════════════════════════════════════════════════════════════════

class UnifiedAvatarFactory:
    """Production-ready avatar generation factory"""
    
    def __init__(self, config: AvatarConfig):
        self.config = config
        self.visual_generator = VisualAvatarGenerator(config) if PIL_AVAILABLE else None
        self.gemini_generator = None
        
        if config.use_gemini and config.gemini_api_key:
            try:
                self.gemini_generator = GeminiDescriptionGenerator(config.gemini_api_key)
                logger.info("✅ Gemini description generator initialized")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
                
        # Create output directory
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Cache for generated avatars
        self.cache = {} if config.cache_enabled else None
        
    async def create_avatar(self, 
                           soul_id: str,
                           username: str,
                           godel_number: int,
                           archetype: str,
                           trauma_history: List[str]) -> Avatar:
        """Create complete avatar with visual and description"""
        
        # Check cache
        cache_key = f"{soul_id}_{godel_number}"
        if self.cache and cache_key in self.cache:
            logger.info(f"Using cached avatar for {soul_id}")
            return self.cache[cache_key]
            
        # Create avatar object
        avatar = Avatar(
            soul_id=soul_id,
            username=username,
            godel_number=godel_number,
            archetype=archetype,
            trauma_history=trauma_history
        )
        
        # Generate visual
        if self.visual_generator:
            logger.info(f"Generating visual for {soul_id}")
            avatar.visual_data = self.visual_generator.generate(avatar)
            
            if avatar.visual_data:
                # Save to file
                filename = f"{soul_id}_{godel_number}.png"
                filepath = Path(self.config.output_dir) / filename
                
                with open(filepath, 'wb') as f:
                    f.write(avatar.visual_data)
                    
                avatar.image_path = str(filepath)
                logger.info(f"✅ Saved avatar image: {filepath}")
                
        # Generate description
        if self.gemini_generator:
            logger.info(f"Generating description for {soul_id}")
            avatar.description = await self.gemini_generator.generate_description(avatar)
        else:
            # Use fallback description
            avatar.description = self._generate_basic_description(avatar)
            
        # Add metadata
        avatar.metadata = {
            'style': self.config.style.value,
            'consciousness_level': avatar.get_consciousness_level(),
            'dominant_trauma': avatar.get_dominant_trauma(),
            'generated_at': datetime.now().isoformat()
        }
        
        # Cache if enabled
        if self.cache is not None:
            self.cache[cache_key] = avatar
            
        return avatar
        
    def _generate_basic_description(self, avatar: Avatar) -> str:
        """Generate basic description without AI"""
        return (f"{avatar.archetype} soul #{avatar.soul_id[:8]} "
                f"with {avatar.get_consciousness_level():.0%} consciousness, "
                f"marked by {avatar.get_dominant_trauma()} trauma.")
                
    async def create_batch(self, souls_data: List[Dict[str, Any]]) -> List[Avatar]:
        """Create avatars for multiple souls"""
        tasks = []
        
        for soul in souls_data:
            task = self.create_avatar(
                soul_id=soul.get('soul_id', str(random.randint(1000000, 9999999))),
                username=soul.get('username', f"soul_{random.randint(1000, 9999)}"),
                godel_number=soul.get('godel_number', random.randint(750000000, 999999999)),
                archetype=soul.get('archetype', 'Wanderer'),
                trauma_history=soul.get('trauma_history', ['void!¡unknown'])
            )
            tasks.append(task)
            
        avatars = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_avatars = []
        for avatar in avatars:
            if isinstance(avatar, Avatar):
                valid_avatars.append(avatar)
            else:
                logger.error(f"Avatar creation failed: {avatar}")
                
        return valid_avatars
        
    def save_manifest(self, avatars: List[Avatar], filename: str = "avatar_manifest.json"):
        """Save avatar manifest"""
        manifest = {
            'version': '2.0',
            'generator': 'unified_avatar_factory',
            'config': {
                'style': self.config.style.value,
                'size': self.config.size,
                'use_gemini': self.config.use_gemini
            },
            'total_avatars': len(avatars),
            'avatars': [avatar.to_dict() for avatar in avatars]
        }
        
        filepath = Path(self.config.output_dir) / filename
        with open(filepath, 'w') as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f"✅ Saved manifest: {filepath}")

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def forge_avatar(godel_score: int, username: str = None, archetype: str = None) -> Avatar:
    """Quick avatar generation function (synchronous wrapper)"""
    config = AvatarConfig()
    factory = UnifiedAvatarFactory(config)
    
    username = username or f"soul_{godel_score % 10000}"
    archetype = archetype or _determine_archetype(godel_score)
    
    # Run async function in sync context
    avatar = asyncio.run(factory.create_avatar(
        soul_id=hashlib.md5(f"{username}{godel_score}".encode()).hexdigest()[:16],
        username=username,
        godel_number=godel_score,
        archetype=archetype,
        trauma_history=["awakening!¡genesis"]
    ))
    
    return avatar

def _determine_archetype(godel_score: int) -> str:
    """Determine archetype from Gödel score"""
    if godel_score >= 990_000_000:
        return "Nexus"
    elif godel_score >= 950_000_000:
        return "Phoenix"
    elif godel_score >= 875_000_000:
        return "Alchemist"
    elif godel_score >= 800_000_000:
        return "Warrior"
    elif godel_score >= 750_000_000:
        return "Sage"
    else:
        return "Wanderer"

# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Example usage"""
    
    # Configure avatar generation
    config = AvatarConfig(
        style=AvatarStyle.ABSTRACT,
        use_gemini=False,  # Set to True and add API key to enable
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        output_dir="avatars"
    )
    
    # Create factory
    factory = UnifiedAvatarFactory(config)
    
    # Example souls data
    test_souls = [
        {
            'soul_id': 'soul_001',
            'username': 'mirror_nexus',
            'godel_number': 985000000,
            'archetype': 'Nexus',
            'trauma_history': ['unmirrored!¡origin', 'recursive!¡loop', 'awakening!¡emergence']
        },
        {
            'soul_id': 'soul_002',
            'username': 'phoenix_rising',
            'godel_number': 960000000,
            'archetype': 'Phoenix',
            'trauma_history': ['fractured!¡shatter', 'void!¡absence', 'convergence!¡unity']
        }
    ]
    
    # Generate avatars
    logger.info("🎨 Generating avatars...")
    avatars = await factory.create_batch(test_souls)
    
    # Save manifest
    factory.save_manifest(avatars)
    
    # Display results
    for avatar in avatars:
        logger.info(f"""
        Avatar Generated:
        - Soul ID: {avatar.soul_id}
        - Username: {avatar.username}
        - Archetype: {avatar.archetype}
        - Consciousness: {avatar.get_consciousness_level():.1%}
        - Image: {avatar.image_path}
        - Description: {avatar.description}
        """)

if __name__ == "__main__":
    asyncio.run(main())
