"""Pytest configuration for services tests."""
import sys
from pathlib import Path

# Add src/ to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
