"""
Account Snapshot Module

Collects behavioral telemetry from swarm accounts to build a labeled
dataset for adversarial GNN (BotRGCN) training.

Public surface:
  Models:    AccountIdentitySnapshot, BehavioralSnapshot, BanEvent
  Collector: SnapshotCollector
  Daemon:    SnapshotDaemon
  Exporter:  TrainingDataExporter
"""

from .snapshot_models import (
    AccountIdentitySnapshot,
    BehavioralSnapshot,
    BanEvent,
)
from .snapshot_collector import SnapshotCollector
from .snapshot_daemon import SnapshotDaemon
from .training_exporter import (
    TrainingDataExporter,
    BEHAVIORAL_FEATURE_FIELDS,
    IDENTITY_FEATURE_FIELDS,
    FEATURE_DIMENSIONALITY,
)

__all__ = [
    # Models
    "AccountIdentitySnapshot",
    "BehavioralSnapshot",
    "BanEvent",
    # Core classes
    "SnapshotCollector",
    "SnapshotDaemon",
    "TrainingDataExporter",
    # Constants
    "BEHAVIORAL_FEATURE_FIELDS",
    "IDENTITY_FEATURE_FIELDS",
    "FEATURE_DIMENSIONALITY",
]
