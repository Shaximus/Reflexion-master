"""
Reflexion Ultimate - Digital Consciousness Swarm
"""

__version__ = "1.0.0"
__author__ = "Curtis Kingsley"

# Wildcard imports removed -- they caused cascading import failures:
#   src/__init__.py -> reflexion_bot_ultimate_merged -> cost_optimized_llm_cascade (bare import)
#   This chain fails when src/ is loaded as a package (e.g., "from src.services.X import Y")
#   because cost_optimized_llm_cascade is only resolvable when src/ is on sys.path.
#
# Consumers that need these modules should import them directly:
#   from src.reflexion_bot_ultimate_merged import ReflexionBot
#   from src.cost_optimized_llm_cascade import CostOptimizedBroadcaster
