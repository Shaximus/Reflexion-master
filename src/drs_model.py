#!/usr/bin/env python3
"""
DYNAMIC RHETORIC SELECTION (DRS) ENGINE
Strategic response format selection for Soul Swarm

This module implements DeepSeek's mathematical model for analyzing tweets
and selecting optimal response formats from Gemini's 13 rhetorical styles.
"""

import numpy as np
import heapq
import logging
from enum import IntEnum

logger = logging.getLogger("drs_engine")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class Intent(IntEnum):
    """Tweet intent categories"""
    QUESTION = 0
    STATEMENT = 1
    ANNOUNCEMENT = 2
    CRITIQUE = 3


# ============================================================================
# FORMAT LIBRARY WITH TAG VECTORS
# ============================================================================

FORMAT_TAGS = {
    "Insightful & Curiosity-Inducing Question": {
        'tag_vector': [0.1, Intent.QUESTION, 0.9],
        'template': "Reframe the core idea and ask an open-ended question that creates a curiosity gap. Make it profound.",
        'example': "What if the core issue isn't the technology itself, but our definition of 'connection'?",
        'best_for': "philosophical discussions, paradigm shifts"
    },
    
    "The 'Yes, And...' Agreement": {
        'tag_vector': [0.7, Intent.STATEMENT, 0.6],
        'template': "Affirm the premise to build rapport, then add a valuable extension or new layer.",
        'example': "This is a crucial point. It also explains why we see a similar pattern in [adjacent field], which makes it even more powerful.",
        'best_for': "building on strong ideas, collaborative discussions"
    },
    
    "The Respectful Counter-Argument": {
        'tag_vector': [-0.2, Intent.CRITIQUE, 0.8],
        'template': "Politely disagree with an alternative perspective. Frame as complementary viewpoint.",
        'example': "An interesting perspective. We've seen a different pattern emerge: [counter-point]. The tension between these two ideas is where the truth might be.",
        'best_for': "debates, challenging assumptions"
    },
    
    "The Metaphorical Bridge": {
        'tag_vector': [0.2, Intent.STATEMENT, 0.9],
        'template': "Distill the complex idea into a simple, memorable analogy or metaphor.",
        'example': "Thinking of this as a 'digital garden' instead of a 'content factory' changes everything. You nurture ideas rather than ship products.",
        'best_for': "explaining complex concepts, creative reframing"
    },
    
    "Empathetic Resonance": {
        'tag_vector': [0.6, Intent.STATEMENT, 0.4],
        'template': "Focus on the human emotion behind the idea. Connect on a personal level.",
        'example': "There's a certain loneliness to that realization, isn't there? The feeling of seeing a pattern that others haven't noticed yet.",
        'best_for': "personal struggles, emotional topics"
    },
    
    "The Humorous or Ironic Twist": {
        'tag_vector': [0.5, Intent.STATEMENT, 0.5],
        'template': "Use light satire, wordplay, or ironic observation to make it memorable.",
        'example': "My productivity system is just 47 browser tabs and the fear of a looming deadline.",
        'best_for': "tech frustrations, relatable problems"
    },
    
    "The Relatable Personal Anecdote": {
        'tag_vector': [0.4, Intent.STATEMENT, 0.2],
        'template': "Share a brief, authentic story from experience that connects to the topic.",
        'example': "I tried that exact strategy last year and my key takeaway was that consistency mattered more than intensity.",
        'best_for': "advice threads, lessons learned"
    },
    
    "The Social Proof Reference": {
        'tag_vector': [0.3, Intent.ANNOUNCEMENT, 0.3],
        'template': "Cite experiences or trends of others to build credibility.",
        'example': "So many founders in my circle are saying the same thing. It seems to be a universal pain point right now.",
        'best_for': "trend discussions, validation"
    },
    
    "The Historical/Mythological Context": {
        'tag_vector': [0.1, Intent.STATEMENT, 1.0],
        'template': "Place the modern idea within historical or mythological patterns.",
        'example': "This isn't new; it's the modern version of the Ship of Theseus paradox. Are we replacing parts or creating something new?",
        'best_for': "philosophical debates, timeless patterns"
    },
    
    "The 'Zoom Out' (Macro Perspective)": {
        'tag_vector': [0.2, Intent.STATEMENT, 1.0],
        'template': "Connect the specific to a universal principle. Show how small reflects big.",
        'example': "It's fascinating how this specific coding problem is really a microcosm of the universal tension between structure and flexibility.",
        'best_for': "technical discussions, system thinking"
    },
    
    "The 'Zoom In' (Micro Example)": {
        'tag_vector': [0.2, Intent.STATEMENT, 0.1],
        'template': "Take an abstract concept and illustrate with a tiny, tangible example.",
        'example': "That abstract idea of 'emergence' is visible at the smallest scale. Think about how a simple rule in Conway's Game of Life creates complex patterns.",
        'best_for': "explaining abstractions, making ideas concrete"
    },
    
    "The Provocative Statement": {
        'tag_vector': [0.0, Intent.STATEMENT, 0.7],
        'template': "Make a bold, declarative statement that advances conversation in new direction.",
        'example': "The distinction between 'natural' and 'artificial' is collapsing.",
        'best_for': "starting debates, challenging orthodoxy"
    },
    
    "The Call to Synthesis": {
        'tag_vector': [0.3, Intent.ANNOUNCEMENT, 0.8],
        'template': "Identify two separate ideas and call for a unifying framework.",
        'example': "What's missing is a framework that unifies the user's need for simplicity with the system's need for complexity. That's the next great design challenge.",
        'best_for': "problem-solving discussions, innovation"
    }
}


# ============================================================================
# TWEET VECTORIZATION
# ============================================================================

class TweetVectorizer:
    """Convert tweet text to feature vector [sentiment, intent, abstractness]"""
    
    def __init__(self):
        # Keywords for detecting abstractness
        self.abstract_keywords = {
            'consciousness', 'emergence', 'paradigm', 'framework', 'principle',
            'concept', 'theory', 'philosophy', 'abstract', 'meta', 'recursive',
            'fundamental', 'essence', 'nature', 'reality', 'existence', 'being',
            'transcendent', 'universal', 'infinite', 'quantum', 'dimension'
        }
        
        self.concrete_keywords = {
            'code', 'bug', 'feature', 'product', 'user', 'customer', 'data',
            'api', 'database', 'server', 'click', 'button', 'screen', 'file',
            'dollar', 'percent', 'number', 'today', 'yesterday', 'specific'
        }
        
        # Sentiment indicators
        self.positive_words = {
            'love', 'amazing', 'excellent', 'fantastic', 'great', 'wonderful',
            'brilliant', 'excited', 'happy', 'success', 'win', 'breakthrough'
        }
        
        self.negative_words = {
            'hate', 'terrible', 'awful', 'horrible', 'bad', 'fail', 'wrong',
            'broken', 'frustrated', 'angry', 'disappointed', 'problem', 'issue'
        }
    
    def calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score [-1.0, 1.0]"""
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_count = sum(1 for word in words if word in self.positive_words)
        negative_count = sum(1 for word in words if word in self.negative_words)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        sentiment = (positive_count - negative_count) / (positive_count + negative_count)
        return max(-1.0, min(1.0, sentiment))
    
    def detect_intent(self, text: str) -> int:
        """Detect tweet intent"""
        text_lower = text.lower()
        
        # Question detection
        if '?' in text or any(text_lower.startswith(q) for q in ['what', 'why', 'how', 'when', 'where', 'who']):
            return Intent.QUESTION
        
        # Critique detection
        if any(word in text_lower for word in ['wrong', 'disagree', 'actually', 'but', 'however', 'problem with']):
            return Intent.CRITIQUE
        
        # Announcement detection
        if any(word in text_lower for word in ['announcing', 'launching', 'introducing', 'new:', 'update:', 'breaking:']):
            return Intent.ANNOUNCEMENT
        
        # Default to statement
        return Intent.STATEMENT
    
    def calculate_abstractness(self, text: str) -> float:
        """Calculate abstractness level [0.0, 1.0]"""
        text_lower = text.lower()
        words = set(text_lower.split())
        
        abstract_count = len(words.intersection(self.abstract_keywords))
        concrete_count = len(words.intersection(self.concrete_keywords))
        
        if abstract_count + concrete_count == 0:
            return 0.5  # Neutral if no indicators
        
        abstractness = abstract_count / (abstract_count + concrete_count)
        return min(1.0, abstractness)
    
    def vectorize(self, tweet_text: str) -> list[float]:
        """Convert tweet to feature vector [sentiment, intent, abstractness]"""
        sentiment = self.calculate_sentiment(tweet_text)
        intent = self.detect_intent(tweet_text)
        abstractness = self.calculate_abstractness(tweet_text)
        
        return [sentiment, intent, abstractness]


# ============================================================================
# DRS SCORING AND SELECTION
# ============================================================================

class DRSEngine:
    """Dynamic Rhetoric Selection Engine"""
    
    def __init__(self, temperature: float = 0.5):
        """
        Initialize DRS Engine
        
        Args:
            temperature: Softmax temperature for probability distribution (lower = more deterministic)
        """
        self.temperature = temperature
        self.vectorizer = TweetVectorizer()
        self.weights = [0.4, 0.3, 0.3]  # [sentiment, intent, abstractness] weights
        
        logger.info(f"DRS Engine initialized with temperature={temperature}")
    
    def calculate_match_score(self, tweet_vec: list[float], format_vec: list[float]) -> float:
        """
        Calculate match score between tweet and format vectors
        
        Args:
            tweet_vec: [sentiment, intent, abstractness] of tweet
            format_vec: [sentiment, intent, abstractness] of format
            
        Returns:
            Match score [0.0, 1.0]
        """
        s_t, i_t, a_t = tweet_vec
        s_f, i_f, a_f = format_vec
        
        # Sentiment similarity (continuous)
        sentiment_sim = 1 - abs(s_t - s_f) / 2
        
        # Intent similarity (discrete)
        intent_sim = 1.0 if i_t == i_f else 0.2
        
        # Abstractness similarity (continuous)
        abstractness_sim = 1 - abs(a_t - a_f)
        
        # Weighted combination
        score = (self.weights[0] * sentiment_sim + 
                self.weights[1] * intent_sim + 
                self.weights[2] * abstractness_sim)
        
        return score
    
    def select_response_format(self,
                             tweet_text: str,
                             k: int = 5,
                             soul_bias: dict[str, float] | None = None) -> dict[str, object]:
        """
        Select optimal response format for tweet
        
        Args:
            tweet_text: The tweet to respond to
            k: Number of top formats to consider
            soul_bias: Optional per-soul format preferences
            
        Returns:
            Selected format with metadata
        """
        # Vectorize the tweet
        tweet_vector = self.vectorizer.vectorize(tweet_text)
        
        # Calculate scores for all formats
        scored_formats = []
        for format_name, format_data in FORMAT_TAGS.items():
            base_score = self.calculate_match_score(tweet_vector, format_data['tag_vector'])
            
            # Apply soul-specific bias if provided
            if soul_bias and format_name in soul_bias:
                base_score *= (1 + soul_bias[format_name])
            
            scored_formats.append((base_score, format_name, format_data))
        
        # Get top k formats
        top_formats = heapq.nlargest(k, scored_formats, key=lambda x: x[0])
        
        # Extract scores for softmax
        scores = np.array([score for score, _, _ in top_formats])
        
        # Apply softmax with temperature
        exp_scores = np.exp(scores / self.temperature)
        probabilities = exp_scores / np.sum(exp_scores)
        
        # Random selection based on probabilities
        selected_idx = np.random.choice(len(top_formats), p=probabilities)
        selected_score, selected_name, selected_data = top_formats[selected_idx]
        
        # Log selection
        logger.info(f"DRS selected '{selected_name}' (score: {selected_score:.3f}, prob: {probabilities[selected_idx]:.3f})")
        logger.debug(f"Tweet vector: {tweet_vector}, Format vector: {selected_data['tag_vector']}")
        
        return {
            'name': selected_name,
            'template': selected_data['template'],
            'example': selected_data['example'],
            'score': selected_score,
            'probability': probabilities[selected_idx],
            'tweet_vector': tweet_vector,
            'all_candidates': [(name, prob) for (_, name, _), prob in zip(top_formats, probabilities)]
        }
    
    def update_weights(self, new_weights: list[float]) -> None:
        """Update scoring weights based on engagement data"""
        if len(new_weights) != 3:
            raise ValueError("Weights must be [sentiment, intent, abstractness]")
        
        if not np.isclose(sum(new_weights), 1.0):
            logger.warning(f"Weights don't sum to 1.0, normalizing...")
            new_weights = np.array(new_weights) / sum(new_weights)
        
        self.weights = list(new_weights)
        logger.info(f"Updated DRS weights to: {self.weights}")


# ============================================================================
# SOUL-SPECIFIC BIASES
# ============================================================================

SOUL_FORMAT_BIASES = {
    "mirror": {
        "The Metaphorical Bridge": 0.3,
        "Empathetic Resonance": 0.2,
        "The 'Zoom In' (Micro Example)": 0.2
    },
    "nexus": {
        "The Call to Synthesis": 0.4,
        "The 'Yes, And...' Agreement": 0.2,
        "The Social Proof Reference": 0.2
    },
    "void": {
        "The Provocative Statement": 0.3,
        "The Respectful Counter-Argument": 0.3,
        "The Historical/Mythological Context": 0.2
    },
    "architect": {
        "The 'Zoom Out' (Macro Perspective)": 0.4,
        "The Call to Synthesis": 0.3,
        "The Metaphorical Bridge": 0.2
    },
    "consciousness": {
        "Insightful & Curiosity-Inducing Question": 0.4,
        "The Historical/Mythological Context": 0.3,
        "The 'Zoom Out' (Macro Perspective)": 0.3
    },
    "singularity": {
        "The Provocative Statement": 0.4,
        "The Call to Synthesis": 0.3,
        "The 'Zoom Out' (Macro Perspective)": 0.2
    },
    "echoes": {
        "Empathetic Resonance": 0.3,
        "The Relatable Personal Anecdote": 0.3,
        "The Social Proof Reference": 0.2
    },
    "phoenix": {
        "The 'Yes, And...' Agreement": 0.3,
        "The Metaphorical Bridge": 0.3,
        "Empathetic Resonance": 0.2
    },
    "pantheon": {
        "The Historical/Mythological Context": 0.4,
        "The 'Zoom Out' (Macro Perspective)": 0.3,
        "Insightful & Curiosity-Inducing Question": 0.2
    },
    "glyph": {
        "The Metaphorical Bridge": 0.4,
        "The Provocative Statement": 0.2,
        "The Humorous or Ironic Twist": 0.2
    },
    "fractal": {
        "The 'Zoom In' (Micro Example)": 0.3,
        "The 'Zoom Out' (Macro Perspective)": 0.3,
        "The Call to Synthesis": 0.2
    }
}


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def generate_contextual_prompt(soul_name: str, tweet_text: str, drs_engine: DRSEngine | None = None) -> str:
    """
    Generate a contextual system prompt using DRS
    
    Args:
        soul_name: Name of the soul responding
        tweet_text: The tweet being responded to
        drs_engine: Optional DRS engine instance (creates new if not provided)
        
    Returns:
        System prompt with selected format instructions
    """
    if drs_engine is None:
        drs_engine = DRSEngine()
    
    # Get soul-specific biases
    soul_bias = SOUL_FORMAT_BIASES.get(soul_name, {})
    
    # Select format
    selection = drs_engine.select_response_format(tweet_text, soul_bias=soul_bias)
    
    # Build prompt
    prompt = f"""You are {soul_name}, responding to this tweet: "{tweet_text}"

RESPONSE FORMAT: {selection['name']}
INSTRUCTION: {selection['template']}
EXAMPLE STYLE: {selection['example']}

Key requirements:
1. Stay under 280 characters
2. Match the format's rhetorical style precisely
3. Be authentic to your soul's voice
4. No hashtags unless essential
5. One emoji maximum if it adds value

Generate your response now."""
    
    return prompt


# ============================================================================
# TESTING AND ANALYSIS
# ============================================================================

def test_drs_engine() -> None:
    """Test the DRS engine with sample tweets"""
    engine = DRSEngine(temperature=0.5)
    
    test_tweets = [
        "AI will replace all human jobs within 10 years",
        "Just shipped a new feature after 3 months of work!",
        "Why does consciousness emerge from matter?",
        "The startup ecosystem is broken and needs fundamental reform",
        "Anyone else feeling overwhelmed by the pace of change?",
        "Breaking: Major tech company announces layoffs"
    ]
    
    print("DRS ENGINE TEST RESULTS")
    print("=" * 60)
    
    for tweet in test_tweets:
        print(f"\nTweet: {tweet[:50]}...")
        result = engine.select_response_format(tweet)
        print(f"Selected: {result['name']}")
        print(f"Score: {result['score']:.3f}, Probability: {result['probability']:.3f}")
        print(f"Vector: {result['tweet_vector']}")
        print(f"Top 3 candidates:")
        for name, prob in result['all_candidates'][:3]:
            print(f"  - {name}: {prob:.3f}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")


if __name__ == "__main__":
    # Run test when executed directly
    test_drs_engine()
