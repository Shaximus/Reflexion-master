"""
Training Data Exporter

Exports labeled behavioral telemetry for GNN (BotRGCN) training.

Outputs:
  - Feature matrix (numpy ndarray)
  - Binary labels (0 = survived, 1 = banned)
  - Account ID list aligned with the above
  - Identity feature export
  - Graph edge list for network structure
  - Dataset statistics
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis.asyncio as aioredis

from .snapshot_models import (
    AccountIdentitySnapshot,
    BanEvent,
    BehavioralSnapshot,
)

logger = logging.getLogger("account_snapshots.exporter")

# Redis keys (must match SnapshotCollector definitions)
_BANS_ALL_KEY = "snapshot:bans:all"
_SURVIVORS_KEY = "snapshot:survivors"
_BEHAVIOR_KEY_PREFIX = "snapshot:behavior:"
_IDENTITY_KEY_PREFIX = "snapshot:identity:"

# ---------------------------------------------------------------------------
# Feature vector field ordering
# Changing this order breaks model compatibility — treat as a schema.
# ---------------------------------------------------------------------------

BEHAVIORAL_FEATURE_FIELDS: Tuple[str, ...] = (
    # Temporal (8)
    "total_tweets",
    "tweets_last_hour",
    "tweets_last_24h",
    "avg_gap_between_tweets_seconds",
    "gap_variance",
    "burst_count",
    "hour_entropy",
    "weekend_ratio",
    # Content (9)
    "original_tweet_count",
    "retweet_count",
    "reply_count",
    "quote_count",
    "url_ratio",
    "hashtag_density",
    "mention_density",
    "avg_tweet_length",
    "shield_cta_ratio",
    # Engagement received (4)
    "total_likes_received",
    "total_replies_received",
    "total_retweets_received",
    "engagement_variance",
    # Profile evolution (5)
    "follower_count",
    "following_count",
    "follow_ratio",
    "account_age_hours",
    # Network (4)
    "follows_real_humans",
    "follows_swarm_accounts",
    "followed_by_real",
    "followed_by_swarm",
    # Session behavior — Scribe-aware (6)
    "session_action_diversity",
    "avg_dwell_time_ms",
    "session_duration_cv",
    "impression_action_ratio",
    "avg_actions_per_session",
    "scroll_impression_ratio",
    # Social graph dynamics (4)
    "follow_velocity_per_day",
    "unfollow_ratio",
    "reply_thread_depth_avg",
    "follow_back_ratio",
    # Red flag indicators (3)
    "rate_limit_events_per_day",
    "error_rate",
    "ad_impression_ratio",
)

FEATURE_DIMENSIONALITY = len(BEHAVIORAL_FEATURE_FIELDS)

IDENTITY_FEATURE_FIELDS: Tuple[str, ...] = (
    "creation_proxy_type_residential",  # one-hot
    "creation_proxy_type_mobile",
    "creation_proxy_type_datacenter",
    "has_bio",
    "has_avatar",
    "password_entropy",
    "birth_date_age",
    "username_pattern_firstname_lastname",  # one-hot partial
    "username_pattern_random_words",
)


class TrainingDataExporter:
    """
    Reads ban events and survivor snapshots from Redis and assembles
    a labeled numpy dataset suitable for GNN training.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    # ------------------------------------------------------------------
    # Primary export: labeled behavioral feature matrix
    # ------------------------------------------------------------------

    async def export_training_data(
        self, min_age_hours: float = 24.0
    ) -> Dict[str, Any]:
        """
        Export a labeled dataset for supervised GNN training.

        Args:
            min_age_hours: Minimum account age (hours) before including a
                           survivor in the dataset. Filters out accounts that
                           are too new to have stable behavioral signals.

        Returns a dict with:
            banned        - List[dict] of raw BanEvent dicts
            survived      - List[dict] of raw BehavioralSnapshot dicts
            features      - np.ndarray of shape (N, FEATURE_DIMENSIONALITY)
            labels        - np.ndarray of shape (N,) with 1=banned, 0=survived
            account_ids   - List[str] aligned with features / labels
            feature_names - List[str] field names for each column
            export_ts     - float Unix timestamp of export
        """
        export_ts = time.time()
        cutoff_ts = export_ts - (min_age_hours * 3600)

        # --- Load ban events -------------------------------------------
        ban_records = await self._load_ban_events()

        # --- Load survivor behavioral snapshots -----------------------
        survivor_ids = await self._load_survivor_ids()
        survivor_snapshots: List[BehavioralSnapshot] = []

        for account_id in survivor_ids:
            raw = await self.redis.get(f"{_BEHAVIOR_KEY_PREFIX}{account_id}")
            if not raw:
                continue
            try:
                snap = BehavioralSnapshot.from_dict(json.loads(raw))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Failed to deserialize behavioral snapshot %s: %s", account_id, exc)
                continue

            # Apply minimum age filter
            if snap.account_age_hours < min_age_hours:
                logger.debug("Skipping %s (age=%.1fh < min %.1fh)", account_id, snap.account_age_hours, min_age_hours)
                continue

            survivor_snapshots.append(snap)

        # --- Build feature matrix and labels --------------------------
        feature_rows: List[np.ndarray] = []
        labels: List[int] = []
        account_ids: List[str] = []

        # Banned accounts (label = 1)
        banned_dicts: List[Dict[str, Any]] = []
        for ban_event in ban_records:
            vec = self._snapshot_to_feature_vector(ban_event.behavioral_snapshot)
            feature_rows.append(vec)
            labels.append(1)
            account_ids.append(ban_event.account_id)
            banned_dicts.append(ban_event.to_dict())

        # Survived accounts (label = 0)
        survived_dicts: List[Dict[str, Any]] = []
        for snap in survivor_snapshots:
            vec = self._snapshot_to_feature_vector(snap)
            feature_rows.append(vec)
            labels.append(0)
            account_ids.append(snap.account_id)
            survived_dicts.append(snap.to_dict())

        if feature_rows:
            features = np.vstack(feature_rows).astype(np.float32)
            label_array = np.array(labels, dtype=np.int32)
        else:
            features = np.empty((0, FEATURE_DIMENSIONALITY), dtype=np.float32)
            label_array = np.array([], dtype=np.int32)

        logger.info(
            "Exported training data: %d banned, %d survived, shape=%s",
            len(banned_dicts),
            len(survived_dicts),
            features.shape,
        )

        return {
            "banned": banned_dicts,
            "survived": survived_dicts,
            "features": features,
            "labels": label_array,
            "account_ids": account_ids,
            "feature_names": list(BEHAVIORAL_FEATURE_FIELDS),
            "export_ts": export_ts,
        }

    # ------------------------------------------------------------------
    # Feature vector conversion
    # ------------------------------------------------------------------

    def _snapshot_to_feature_vector(
        self, snapshot: BehavioralSnapshot
    ) -> np.ndarray:
        """
        Convert a BehavioralSnapshot to a flat float32 feature vector.

        The field order is governed by BEHAVIORAL_FEATURE_FIELDS above.
        All values are cast to float; missing/None values default to 0.0.
        """
        snap_dict = snapshot.to_dict()
        values: List[float] = []
        for field_name in BEHAVIORAL_FEATURE_FIELDS:
            raw = snap_dict.get(field_name, 0)
            try:
                values.append(float(raw) if raw is not None else 0.0)
            except (TypeError, ValueError):
                values.append(0.0)

        return np.array(values, dtype=np.float32)

    # ------------------------------------------------------------------
    # Identity features
    # ------------------------------------------------------------------

    async def export_identity_features(self) -> Dict[str, Any]:
        """
        Export identity snapshots for all accounts that have one stored.

        Returns:
            account_ids   - List[str]
            raw_snapshots - List[dict] of AccountIdentitySnapshot dicts
            features      - np.ndarray of shape (N, len(IDENTITY_FEATURE_FIELDS))
            feature_names - List[str]
        """
        pattern = f"{_IDENTITY_KEY_PREFIX}*"
        account_ids: List[str] = []
        raw_snapshots: List[Dict[str, Any]] = []
        feature_rows: List[np.ndarray] = []

        # Scan all identity keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor, match=pattern, count=100
            )
            for key in keys:
                raw = await self.redis.get(key)
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    identity = AccountIdentitySnapshot.from_dict(data)
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.warning("Failed to deserialize identity for key %s: %s", key, exc)
                    continue

                account_ids.append(identity.account_id)
                raw_snapshots.append(identity.to_dict())
                feature_rows.append(self._identity_to_feature_vector(identity))

            if cursor == 0:
                break

        if feature_rows:
            features = np.vstack(feature_rows).astype(np.float32)
        else:
            features = np.empty((0, len(IDENTITY_FEATURE_FIELDS)), dtype=np.float32)

        logger.info("Exported identity features: %d accounts", len(account_ids))

        return {
            "account_ids": account_ids,
            "raw_snapshots": raw_snapshots,
            "features": features,
            "feature_names": list(IDENTITY_FEATURE_FIELDS),
        }

    def _identity_to_feature_vector(
        self, identity: AccountIdentitySnapshot
    ) -> np.ndarray:
        """Convert an identity snapshot to a numeric feature vector."""
        proxy_type = identity.creation_proxy_type.lower()

        values = [
            1.0 if proxy_type == "residential" else 0.0,
            1.0 if proxy_type == "mobile" else 0.0,
            1.0 if proxy_type == "datacenter" else 0.0,
            1.0 if identity.has_bio else 0.0,
            1.0 if identity.has_avatar else 0.0,
            float(identity.password_entropy),
            float(identity.birth_date_age),
            1.0 if "firstname" in identity.username_pattern.lower() else 0.0,
            1.0 if "random" in identity.username_pattern.lower() else 0.0,
        ]
        return np.array(values, dtype=np.float32)

    # ------------------------------------------------------------------
    # Graph data export
    # ------------------------------------------------------------------

    async def export_graph_data(self) -> Dict[str, Any]:
        """
        Export edge list from network data for GNN graph construction.

        Returns:
            nodes         - List[str] of all account IDs with behavioral data
            edges         - List[Tuple[str, str]] (follower_id, followee_id)
            edge_types    - List[str] "swarm_to_swarm" | "swarm_to_real" | "real_to_swarm"
            node_features - dict mapping account_id -> feature vector (as list)

        Network edges are reconstructed from the follows_swarm_accounts and
        follows_real_humans counters. Exact edge identity is unavailable at
        this aggregation level, so we synthesize representative edges from
        the survivor set to represent the graph structure in aggregate form.
        """
        survivor_ids = await self._load_survivor_ids()
        ban_records = await self._load_ban_events()
        banned_ids = {b.account_id for b in ban_records}

        all_ids = list(set(list(survivor_ids) + list(banned_ids)))
        nodes: List[str] = []
        edges: List[Tuple[str, str]] = []
        edge_types: List[str] = []
        node_features: Dict[str, List[float]] = {}

        swarm_set = set(all_ids)

        for account_id in all_ids:
            raw = await self.redis.get(f"{_BEHAVIOR_KEY_PREFIX}{account_id}")
            if not raw:
                continue
            try:
                snap = BehavioralSnapshot.from_dict(json.loads(raw))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

            nodes.append(account_id)
            node_features[account_id] = self._snapshot_to_feature_vector(snap).tolist()

            # Synthesise swarm->swarm edges (count-based; no exact IDs available)
            # We create a virtual "swarm_pool" node for aggregated edges
            n_swarm_follows = snap.follows_swarm_accounts
            for i in range(min(n_swarm_follows, len(all_ids) - 1)):
                # Connect to i-th other swarm member (cyclic, best effort)
                target = all_ids[(all_ids.index(account_id) + i + 1) % len(all_ids)]
                if target != account_id:
                    edges.append((account_id, target))
                    edge_types.append("swarm_to_swarm")

            # Swarm->real edges (synthetic placeholder "real_user" nodes)
            n_real_follows = snap.follows_real_humans
            for i in range(min(n_real_follows, 3)):  # cap to avoid edge explosion
                edges.append((account_id, f"real_user_{i}"))
                edge_types.append("swarm_to_real")

        logger.info(
            "Exported graph data: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )

        return {
            "nodes": nodes,
            "edges": edges,
            "edge_types": edge_types,
            "node_features": node_features,
        }

    # ------------------------------------------------------------------
    # Dataset statistics
    # ------------------------------------------------------------------

    async def get_dataset_stats(self) -> Dict[str, Any]:
        """
        Return counts and structural metadata about the stored dataset.
        """
        ban_records = await self._load_ban_events()
        survivor_ids = await self._load_survivor_ids()

        # Count accounts that have a behavioral snapshot
        n_with_behavior = 0
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=f"{_BEHAVIOR_KEY_PREFIX}*",
                count=100,
            )
            n_with_behavior += len(keys)
            if cursor == 0:
                break

        ban_type_distribution: Dict[str, int] = {}
        trigger_distribution: Dict[str, int] = {}
        for ban in ban_records:
            ban_type_distribution[ban.ban_type] = ban_type_distribution.get(ban.ban_type, 0) + 1
            trigger_distribution[ban.suspected_trigger] = trigger_distribution.get(ban.suspected_trigger, 0) + 1

        stats = {
            "total_banned": len(ban_records),
            "total_survived": len(survivor_ids),
            "total_with_behavioral_snapshot": n_with_behavior,
            "total_accounts": len(ban_records) + len(survivor_ids),
            "feature_dimensionality": FEATURE_DIMENSIONALITY,
            "feature_names": list(BEHAVIORAL_FEATURE_FIELDS),
            "ban_type_distribution": ban_type_distribution,
            "trigger_distribution": trigger_distribution,
            "identity_feature_dimensionality": len(IDENTITY_FEATURE_FIELDS),
        }

        logger.info(
            "Dataset stats: banned=%d survived=%d features=%d",
            stats["total_banned"],
            stats["total_survived"],
            FEATURE_DIMENSIONALITY,
        )
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_ban_events(self) -> List[BanEvent]:
        """Load all ban events from the sorted set."""
        raw_entries = await self.redis.zrangebyscore(
            _BANS_ALL_KEY, "-inf", "+inf"
        )
        ban_events: List[BanEvent] = []
        for raw in raw_entries:
            try:
                ban_events.append(BanEvent.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Failed to deserialize ban event: %s", exc)
        return ban_events

    async def _load_survivor_ids(self) -> List[str]:
        """Load all account IDs from the survivors set."""
        try:
            members = await self.redis.smembers(_SURVIVORS_KEY)
            return list(members)
        except Exception as exc:
            logger.error("Failed to load survivors: %s", exc)
            return []
