"""
BotRGCN Adversarial Adapter

Fine-tunes the pretrained BotRGCN on real swarm ban/survive telemetry
and inverts the model's detection function into sleeper account behavioral specs.

Public surface:
  BlasterDataLoader    -- loads Redis telemetry, converts to BotRGCN tensors
  AdversarialTrainer   -- fine-tunes BotRGCN, computes feature importances
  SleeperSpec          -- dataclass: behavioral constraint specification
  SleeperSpecGenerator -- inverts importances -> SleeperSpec
  build_default_spec   -- returns conservative defaults when no data exists
"""

from .blaster_data_loader import BlasterDataLoader
from .train_adversarial import AdversarialTrainer, TEMPORAL_FEATURE_NAMES, NUM_PROP_FEATURE_NAMES
from .sleeper_specs import SleeperSpec, SleeperSpecGenerator, build_default_spec

__all__ = [
    "BlasterDataLoader",
    "AdversarialTrainer",
    "SleeperSpec",
    "SleeperSpecGenerator",
    "build_default_spec",
    "TEMPORAL_FEATURE_NAMES",
    "NUM_PROP_FEATURE_NAMES",
]
