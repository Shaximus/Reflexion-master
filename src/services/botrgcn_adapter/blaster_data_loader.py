"""
BlasterDataLoader

Loads real ban/survive telemetry from the swarm snapshot Redis store and
converts it into the exact tensor format that BotRGCN expects for fine-tuning.

Seven modalities produced:
  des       [N, 768]  -- DistilRoBERTa account bio embeddings
                         (PLACEHOLDER: returns zero vectors until real bio text
                          is collected. Requires storing actual bio text in
                          AccountIdentitySnapshot instead of just has_bio bool.
                          See snapshot_collector.py collect_identity_snapshot().)
  tweet     [N, 768]  -- DistilRoBERTa tweet-history embeddings
                         (PLACEHOLDER: returns zero vectors until real tweet text
                          is stored. The snapshot pipeline currently aggregates
                          tweet stats but discards the raw text. To fix: store raw
                          tweet text in Redis alongside behavioral snapshots during
                          snapshot collection in snapshot_collector.py.)
  num_prop  [N, 6]    -- numeric profile features (StandardScaler)
  cat_prop  [N, 3]    -- categorical profile features (binary)
  temporal  [N, 42]   -- ALL 42 behavioral features mapped 1-to-1, RAW values
                         (z-score normalized). No manual feature engineering --
                         the neural network learns its own transforms.
  edge_index[2, E]    -- COO graph edges
  edge_type [E]       -- 0=following, 1=follower
  labels    [N]       -- 0=survived, 1=banned

Design principle: Every feature collected by BEHAVIORAL_FEATURE_FIELDS maps
directly to exactly one temporal tensor dimension. No sqrt, log1p, ratio
computation, or other manual transforms are applied. The GNN's hidden layers
(GELU activations, BatchNorm) can learn any nonlinear transform that helps.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis.asyncio as aioredis
import torch
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("botrgcn_adapter.data_loader")

# ---------------------------------------------------------------------------
# Path bootstrap: make account_snapshots importable without install
# ---------------------------------------------------------------------------
_SERVICES_DIR = Path(__file__).parent.parent
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))

from account_snapshots import TrainingDataExporter, BEHAVIORAL_FEATURE_FIELDS  # noqa: E402

# ---------------------------------------------------------------------------
# Field index lookup (built once at import time)
# ---------------------------------------------------------------------------
_F = {name: idx for idx, name in enumerate(BEHAVIORAL_FEATURE_FIELDS)}


class BlasterDataLoader:
    """
    Loads swarm telemetry from Redis and prepares BotRGCN-formatted tensors.

    Usage::

        loader = BlasterDataLoader()
        export  = await loader.load_from_snapshots()
        tensors = loader.prepare_botrgcn_tensors(export)
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: str = os.environ.get("REDIS_PASSWORD", ""),
    ) -> None:
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password

        self._tokenizer = None
        self._text_model = None
        self._text_device: Optional[str] = None

        self._temporal_norm: Optional[Dict[str, Any]] = None
        self._num_scaler: Optional[StandardScaler] = None

    # ------------------------------------------------------------------
    # Public: load from Redis
    # ------------------------------------------------------------------

    async def load_from_snapshots(self, min_age_hours: float = 24.0) -> Dict[str, Any]:
        """Pull all ban events + survivor snapshots from Redis."""
        redis = aioredis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=True,
        )
        try:
            exporter = TrainingDataExporter(redis)

            logger.info("Fetching training data from Redis snapshots...")
            export = await exporter.export_training_data(min_age_hours=min_age_hours)

            logger.info("Fetching graph data from Redis snapshots...")
            graph = await exporter.export_graph_data()

            logger.info("Fetching identity snapshots for bio text...")
            identity_export = await exporter.export_identity_features()

            export["graph"] = graph
            export["identity_raw"] = identity_export.get("raw_snapshots", [])

            logger.info(
                "Loaded: banned=%d survived=%d nodes=%d edges=%d",
                len(export.get("banned", [])),
                len(export.get("survived", [])),
                len(graph.get("nodes", [])),
                len(graph.get("edges", [])),
            )
        finally:
            await redis.aclose()

        return export

    # ------------------------------------------------------------------
    # Public: convert to BotRGCN tensors
    # ------------------------------------------------------------------

    def prepare_botrgcn_tensors(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert raw export dict to the 7 tensors BotRGCN.forward() expects,
        plus labels and aligned account_ids.

        Returns dict with keys: des, tweet, num_prop, cat_prop, temporal,
        edge_index, edge_type, labels, account_ids, N, norm_params.
        """
        features: np.ndarray = export_data["features"]
        labels: np.ndarray   = export_data["labels"]
        account_ids: List[str] = export_data["account_ids"]
        N = len(account_ids)

        if N == 0:
            logger.warning("Empty dataset -- returning zero-shaped tensors")
            return self._empty_tensors()

        logger.info("Preparing BotRGCN tensors for N=%d accounts", N)

        # 1. Temporal [N, 42] -- direct 1-to-1 mapping of ALL behavioral features
        temporal_raw = self._build_temporal_matrix(features, account_ids)
        temporal_normed, norm_params = self._normalize_temporal(temporal_raw)

        # 2. Numeric profile [N, 6]
        num_prop_raw = self._build_num_prop_matrix(features, account_ids, export_data)
        num_prop_scaled, scaler = self._scale_num_prop(num_prop_raw)

        # 3. Categorical profile [N, 3]
        cat_prop = self._build_cat_prop_matrix(export_data, account_ids)

        # 4. Text embeddings [N, 768] each
        bio_texts   = self._collect_bio_texts(export_data, account_ids)
        tweet_texts = self._collect_tweet_texts(export_data, account_ids)

        logger.info("Encoding bios with DistilRoBERTa...")
        des_emb   = self._encode_text(bio_texts,   batch_size=32)

        logger.info("Encoding tweet histories with DistilRoBERTa...")
        tweet_emb = self._encode_text(tweet_texts, batch_size=32)

        # 5. Graph [2, E] / [E]
        edge_index, edge_type = self._build_graph(export_data, account_ids)

        self._temporal_norm = norm_params
        self._num_scaler = scaler

        result = {
            "des":        torch.from_numpy(des_emb).float(),
            "tweet":      torch.from_numpy(tweet_emb).float(),
            "num_prop":   torch.from_numpy(num_prop_scaled).float(),
            "cat_prop":   torch.from_numpy(cat_prop).float(),
            "temporal":   torch.from_numpy(temporal_normed).float(),
            "edge_index": edge_index,
            "edge_type":  edge_type,
            "labels":     torch.from_numpy(labels.astype(np.int64)),
            "account_ids": account_ids,
            "N": N,
            "norm_params": norm_params,
        }

        logger.info(
            "Tensor shapes: des=%s tweet=%s num=%s cat=%s temporal=%s "
            "edge_index=%s edge_type=%s labels=%s",
            tuple(result["des"].shape),
            tuple(result["tweet"].shape),
            tuple(result["num_prop"].shape),
            tuple(result["cat_prop"].shape),
            tuple(result["temporal"].shape),
            tuple(result["edge_index"].shape) if result["edge_index"] is not None else None,
            tuple(result["edge_type"].shape)  if result["edge_type"]  is not None else None,
            tuple(result["labels"].shape),
        )
        return result

    # ------------------------------------------------------------------
    # Internal: temporal feature mapping (DIRECT 1-to-1)
    # ------------------------------------------------------------------

    # Number of temporal features = number of behavioral feature fields.
    # This is the single source of truth for temporal tensor width.
    TEMPORAL_SIZE: int = len(BEHAVIORAL_FEATURE_FIELDS)  # 42

    def _build_temporal_matrix(
        self, features: np.ndarray, account_ids: List[str]
    ) -> np.ndarray:
        """
        Direct 1-to-1 mapping: every BEHAVIORAL_FEATURE_FIELDS entry gets
        exactly one temporal tensor slot, in the same order, with RAW values.

        NO manual feature engineering is applied -- no sqrt, log1p, ratio
        computation, Laplace smoothing, or unit conversions. The neural
        network (TemporalMLP with GELU activations and BatchNorm) learns
        whatever nonlinear transforms are useful from the raw signal.

        Slot mapping (42 dimensions, order matches BEHAVIORAL_FEATURE_FIELDS):
          -- Temporal (8) --
          [0]  total_tweets
          [1]  tweets_last_hour                 ** NEW (was dropped) **
          [2]  tweets_last_24h                  ** NEW (was dropped) **
          [3]  avg_gap_between_tweets_seconds
          [4]  gap_variance
          [5]  burst_count
          [6]  hour_entropy
          [7]  weekend_ratio
          -- Content (9) --
          [8]  original_tweet_count
          [9]  retweet_count
          [10] reply_count                      ** NEW (was dropped) **
          [11] quote_count                      ** NEW (was dropped) **
          [12] url_ratio
          [13] hashtag_density
          [14] mention_density
          [15] avg_tweet_length                 ** NEW (was dropped) **
          [16] shield_cta_ratio                 ** NEW (was dropped) **
          -- Engagement received (4) --
          [17] total_likes_received
          [18] total_replies_received
          [19] total_retweets_received
          [20] engagement_variance
          -- Profile evolution (5) --
          [21] follower_count
          [22] following_count
          [23] follow_ratio                     ** NEW (was dropped) **
          [24] account_age_hours
          -- Network (4) --
          [25] follows_real_humans              ** NEW (was dropped) **
          [26] follows_swarm_accounts           ** NEW (was dropped) **
          [27] followed_by_real                 ** NEW (was dropped) **
          [28] followed_by_swarm               ** NEW (was dropped) **
          -- Session behavior (Scribe-aware) (6) --
          [29] session_action_diversity
          [30] avg_dwell_time_ms
          [31] session_duration_cv
          [32] impression_action_ratio
          [33] avg_actions_per_session
          [34] scroll_impression_ratio
          -- Social graph dynamics (4) --
          [35] follow_velocity_per_day
          [36] unfollow_ratio
          [37] reply_thread_depth_avg
          [38] follow_back_ratio
          -- Red flag indicators (3) --
          [39] rate_limit_events_per_day
          [40] error_rate
          [41] ad_impression_ratio

        Previously dropped features now mapped (11 total):
          tweets_last_hour, tweets_last_24h, reply_count, quote_count,
          avg_tweet_length, shield_cta_ratio, follow_ratio,
          follows_real_humans, follows_swarm_accounts, followed_by_real,
          followed_by_swarm

        Previously applied manual transforms now REMOVED:
          - sqrt(gap_variance)/60  -> raw gap_variance
          - avg_gap_seconds/60     -> raw avg_gap_between_tweets_seconds
          - Laplace smoothed burst_ratio  -> raw burst_count
          - Laplace smoothed retweet_ratio -> raw retweet_count
          - log1p(engagement/tweets) -> raw engagement counts
          - log1p(sqrt(engagement_variance)) -> raw engagement_variance
          - Coefficient of variation derivations -> removed (NN can learn)
          - has_tweets binary flag -> removed (NN can learn from total_tweets==0)
          - avg_dwell_time_ms/1000 -> raw avg_dwell_time_ms
          - min(impression_action_ratio, 100) cap -> raw value
          - account_age_hours/24 -> raw account_age_hours
        """
        N = len(account_ids)
        n_features = self.TEMPORAL_SIZE  # 42
        T = np.zeros((N, n_features), dtype=np.float32)

        for i in range(N):
            row = features[i]
            # Direct 1-to-1: each feature index maps to the same tensor slot
            for j in range(n_features):
                T[i, j] = float(row[j])

        return T

    def _normalize_temporal(
        self, T: np.ndarray, train_indices: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Z-score normalize all 42 temporal columns.

        All columns are treated as continuous since the manual has_tweets
        binary flag has been removed (the network can learn thresholds from
        raw total_tweets values). Z-score normalization is applied to all
        42 feature dimensions.

        If train_indices is provided, compute means/stds from training
        rows only but apply the normalization to ALL rows (prevents
        data leakage from validation/test set into normalization stats).
        """
        normed = T.copy()
        N, D = T.shape

        # All columns are continuous -- direct 1-to-1 raw features
        continuous_cols = list(range(D))
        n_continuous = D

        if N > 1:
            if train_indices is not None and len(train_indices) > 1:
                means = T[train_indices].mean(axis=0)
                stds  = T[train_indices].std(axis=0)
            else:
                means = T.mean(axis=0)
                stds  = T.std(axis=0)
        else:
            means = np.zeros(n_continuous, dtype=np.float32)
            stds  = np.ones(n_continuous,  dtype=np.float32)

        stds = np.where(stds < 1e-9, 1.0, stds)
        normed = (T - means) / stds

        norm_params: Dict[str, Any] = {
            "means":           means.tolist(),
            "stds":            stds.tolist(),
            "continuous_cols": continuous_cols,
            "feature_names":   list(BEHAVIORAL_FEATURE_FIELDS),
            "version":         "direct_v3",
        }
        return normed.astype(np.float32), norm_params

    # ------------------------------------------------------------------
    # Internal: numeric profile mapping
    # ------------------------------------------------------------------

    def _build_num_prop_matrix(
        self, features: np.ndarray, account_ids: List[str],
        export_data: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Numeric profile features from behavioral + identity data.

        [0] follower_count       -- from behavioral features (raw, no scaling)
        [1] following_count      -- from behavioral features (raw)
        [2] total_likes_received -- from behavioral features (raw)
        [3] total_tweets         -- from behavioral features (raw)
        [4] username_length      -- length of Twitter username from identity
                                    snapshot (NOT internal soul ID length).
                                    BUG FIX: Previously used len(account_id)
                                    which is the internal soul ID, not the
                                    Twitter username.
        [5] account_age_hours    -- from behavioral features (raw, no /24 conversion)

        Note: follower_count, following_count, total_likes_received,
        total_tweets, and account_age_hours also appear in the temporal
        tensor (slots 21, 22, 17, 0, 24 respectively). This intentional
        duplication lets the model learn different representations in
        different subnetworks. StandardScaler is applied to num_prop.
        """
        # Build twitter_username lookup from identity snapshots
        username_map: Dict[str, str] = {}
        if export_data is not None:
            for identity_dict in export_data.get("identity_raw", []):
                aid = identity_dict.get("account_id", "")
                tw_username = identity_dict.get("twitter_username", "")
                if aid and tw_username:
                    username_map[aid] = tw_username

        N = len(account_ids)
        P = np.zeros((N, 6), dtype=np.float32)
        for i, aid in enumerate(account_ids):
            row = features[i]
            P[i, 0] = float(row[_F["follower_count"]])
            P[i, 1] = float(row[_F["following_count"]])
            P[i, 2] = float(row[_F["total_likes_received"]])
            P[i, 3] = float(row[_F["total_tweets"]])
            # FIX: Use actual Twitter username length, not soul ID length
            twitter_username = username_map.get(aid, aid)
            P[i, 4] = float(len(twitter_username))
            P[i, 5] = float(row[_F["account_age_hours"]])
        return P

    def _scale_num_prop(
        self, P: np.ndarray, train_indices: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, StandardScaler]:
        """Fit StandardScaler on numeric profile props.

        If train_indices is provided, fit on training rows only but
        transform ALL rows (prevents data leakage).
        """
        scaler = StandardScaler()
        if P.shape[0] > 1:
            if train_indices is not None and len(train_indices) > 1:
                scaler.fit(P[train_indices])
            else:
                scaler.fit(P)
            P_scaled = scaler.transform(P).astype(np.float32)
        else:
            scaler.fit(P)
            P_scaled = P.astype(np.float32)
        return P_scaled, scaler

    # ------------------------------------------------------------------
    # Internal: categorical profile mapping
    # ------------------------------------------------------------------

    def _build_cat_prop_matrix(
        self, export_data: Dict[str, Any], account_ids: List[str]
    ) -> np.ndarray:
        """
        [0] 0.0  -- swarm accounts are never verified
        [1] 0.0  -- swarm accounts are public (not protected)
        [2] has_bio from identity snapshot (1.0 / 0.0)
        """
        has_bio_map: Dict[str, float] = {}
        for identity_dict in export_data.get("identity_raw", []):
            aid = identity_dict.get("account_id", "")
            if aid:
                has_bio_map[aid] = 1.0 if identity_dict.get("has_bio", False) else 0.0

        N = len(account_ids)
        C = np.zeros((N, 3), dtype=np.float32)
        for i, aid in enumerate(account_ids):
            C[i, 0] = 0.0
            C[i, 1] = 0.0
            C[i, 2] = has_bio_map.get(aid, 0.0)
        return C

    # ------------------------------------------------------------------
    # Internal: text collection for embedding
    # ------------------------------------------------------------------

    def _collect_bio_texts(
        self, export_data: Dict[str, Any], account_ids: List[str]
    ) -> List[str]:
        """Collect actual bio text from identity snapshots for embedding.

        Reads bio_text from export_data["identity_raw"] if available (stored by
        snapshot_collector.py). Falls back to empty string for accounts without
        stored bio text. Empty strings produce zero vectors after DistilRoBERTa encoding.

        Returns:
            List of bio texts, one per account_id. Order matches account_ids input.
        """
        # Build lookup from identity_raw if available
        bio_map: Dict[str, str] = {}
        for identity_dict in export_data.get("identity_raw", []):
            aid = identity_dict.get("account_id", "")
            # Try multiple possible key names (snapshot_collector may use different field)
            bio_text = identity_dict.get(
                "bio_text",
                identity_dict.get("description", "")
            )
            if aid and bio_text:
                bio_map[aid] = bio_text

        collected = []
        for aid in account_ids:
            text = bio_map.get(aid, "")
            collected.append(text)

        # Log stats (not warning anymore - empty bios are valid for swarm accounts)
        non_empty = sum(1 for t in collected if t.strip())
        logger.info(
            "Bio collection: %d/%d accounts have non-empty bio text (%.1f%%)",
            non_empty, len(account_ids),
            100.0 * non_empty / len(account_ids) if account_ids else 0.0,
        )

        return collected

    def _collect_tweet_texts(
        self, export_data: Dict[str, Any], account_ids: List[str]
    ) -> List[str]:
        """PLACEHOLDER: Returns empty strings -> zero vectors for all accounts.

        Previously, this method generated synthetic prose from 6 numeric
        features (total_tweets, original_tweet_count, retweet_count, url_ratio,
        hashtag_density, mention_density) and passed them through DistilRoBERTa.
        This was removed because:

        1. Those 6 numbers are already in the temporal tensor (slots 0, 8, 9,
           12, 13, 14) and the network sees them directly.
        2. Encoding numbers as English prose through a language model is a
           768-dimensional re-encoding of information already available in 6
           dimensions -- pure redundancy.
        3. The language model cannot capture tweet style, sentiment, or
           linguistic patterns from stats-as-prose.

        TO MAKE THIS WORK with real tweet text:

        1. In snapshot_collector.py: When fetch_target_context() retrieves up
           to 50 recent tweets, store the raw tweet text (not just aggregate
           stats). Add a Redis key `snapshot:tweets:{account_id}` containing
           a JSON list of tweet text strings.

        2. In training_exporter.py: Add an export method that reads
           `snapshot:tweets:{account_id}` and includes raw text in the
           export dict under a "tweet_texts" key mapping account_id -> [str].

        3. In this method: Concatenate the stored tweets per account:
               tweet_map = export_data.get("tweet_texts", {})
               return [" ".join(tweet_map.get(aid, [])) for aid in account_ids]

        Until those changes are made, this produces [N, 768] zero vectors.
        """
        logger.warning(
            "Tweet text collection returns empty strings for all %d accounts. "
            "The tweet embedding modality is non-functional until actual tweet "
            "text is stored during snapshot collection. Synthetic prose "
            "generation has been removed (it re-encoded 6 numbers already in "
            "the temporal tensor). See docstring for required changes.",
            len(account_ids),
        )
        return [""] * len(account_ids)

    # ------------------------------------------------------------------
    # Internal: text encoding
    # ------------------------------------------------------------------

    def _ensure_text_model(self, device: Optional[str] = None) -> None:
        """Lazy-load DistilRoBERTa; falls back to CPU on CUDA OOM."""
        if self._tokenizer is not None:
            return

        from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

        model_name = "distilroberta-base"
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info("Loading %s on %s...", model_name, device)
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

        try:
            self._text_model = (
                AutoModel.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                )
                .to(device)
                .eval()
            )
            self._text_device = device
        except RuntimeError:
            logger.warning("CUDA OOM loading text model; falling back to CPU")
            self._text_model = (
                AutoModel.from_pretrained(model_name, torch_dtype=torch.float32)
                .to("cpu")
                .eval()
            )
            self._text_device = "cpu"

        logger.info("Text model loaded on %s", self._text_device)

    def _encode_text(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Batch-encode texts with DistilRoBERTa -> [N, 768] float32.
        Empty texts produce zero vectors.
        """
        self._ensure_text_model()
        device    = self._text_device
        use_amp   = (device == "cuda")
        N         = len(texts)
        embeddings = np.zeros((N, 768), dtype=np.float32)

        for start in range(0, N, batch_size):
            batch_texts = texts[start : start + batch_size]
            cleaned     = [t if t.strip() else " " for t in batch_texts]
            empty_mask  = [not t.strip() for t in batch_texts]

            try:
                inputs = self._tokenizer(
                    cleaned,
                    return_tensors="pt",
                    truncation=True,
                    max_length=128,
                    padding=True,
                )
                inputs = {k: v.to(device, non_blocking=True) for k, v in inputs.items()}

                with torch.no_grad():
                    if use_amp:
                        with torch.autocast("cuda", dtype=torch.float16):
                            hidden = self._text_model(**inputs).last_hidden_state
                    else:
                        hidden = self._text_model(**inputs).last_hidden_state
                    vecs = hidden.mean(dim=1).to("cpu", non_blocking=True).float().numpy()

                for j, (is_empty, vec) in enumerate(zip(empty_mask, vecs)):
                    embeddings[start + j] = 0.0 if is_empty else vec

            except RuntimeError as exc:
                if "out of memory" in str(exc).lower() and device == "cuda":
                    logger.warning("CUDA OOM during text encoding batch %d; retrying on CPU", start)
                    torch.cuda.empty_cache()
                    inputs_cpu = self._tokenizer(
                        cleaned,
                        return_tensors="pt",
                        truncation=True,
                        max_length=128,
                        padding=True,
                    )
                    model_cpu = self._text_model.to("cpu")
                    with torch.no_grad():
                        hidden_cpu = model_cpu(**inputs_cpu).last_hidden_state
                        vecs_cpu = hidden_cpu.mean(dim=1).float().numpy()
                    self._text_model.to(device)
                    for j, (is_empty, vec) in enumerate(zip(empty_mask, vecs_cpu)):
                        embeddings[start + j] = 0.0 if is_empty else vec
                else:
                    logger.error("Text encoding error in batch %d: %s", start, exc)

            if (start // batch_size) % 10 == 0:
                logger.debug("Encoded %d/%d texts", min(start + batch_size, N), N)

        return embeddings

    # ------------------------------------------------------------------
    # Internal: graph construction
    # ------------------------------------------------------------------

    def _build_graph(
        self, export_data: Dict[str, Any], account_ids: List[str]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Convert export_graph_data() output to edge_index [2,E] / edge_type [E].
        Relation 0 = following / swarm_to_swarm, 1 = follower.
        Falls back to self-loops when no edges exist.
        """
        graph      = export_data.get("graph", {})
        nodes      = graph.get("nodes", [])
        raw_edges  = graph.get("edges", [])
        raw_etypes = graph.get("edge_types", [])

        N = len(account_ids)

        if not raw_edges:
            logger.info("Empty graph -- using self-loop placeholder edges")
            idx = torch.arange(N, dtype=torch.long)
            return torch.stack([idx, idx], dim=0), torch.zeros(N, dtype=torch.long)

        all_nodes   = list(dict.fromkeys(account_ids + list(nodes)))
        node_to_idx = {n: i for i, n in enumerate(all_nodes)}

        src_list: List[int] = []
        dst_list: List[int] = []
        et_list:  List[int] = []

        for edge, etype in zip(raw_edges, raw_etypes):
            if not isinstance(edge, (list, tuple)) or len(edge) < 2:
                continue

            src_id, dst_id = edge[0], edge[1]

            if isinstance(src_id, int) and isinstance(dst_id, int):
                src_node = nodes[src_id] if src_id < len(nodes) else None
                dst_node = nodes[dst_id] if dst_id < len(nodes) else None
            else:
                src_node = str(src_id)
                dst_node = str(dst_id)

            if src_node is None or dst_node is None:
                continue

            si = node_to_idx.get(src_node)
            di = node_to_idx.get(dst_node)
            if si is None or di is None:
                continue

            if isinstance(etype, int):
                rel = min(int(etype), 1)
            elif "follower" in str(etype) and "following" not in str(etype):
                rel = 1
            else:
                rel = 0

            src_list.append(si)
            dst_list.append(di)
            et_list.append(rel)

        if not src_list:
            idx = torch.arange(N, dtype=torch.long)
            return torch.stack([idx, idx], dim=0), torch.zeros(N, dtype=torch.long)

        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
        edge_type  = torch.tensor(et_list, dtype=torch.long)
        logger.info("Graph: %d nodes, %d edges", len(all_nodes), len(src_list))
        return edge_index, edge_type

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_tensors() -> Dict[str, Any]:
        return {
            "des":         torch.zeros(0, 768),
            "tweet":       torch.zeros(0, 768),
            "num_prop":    torch.zeros(0, 6),
            "cat_prop":    torch.zeros(0, 3),
            "temporal":    torch.zeros(0, BlasterDataLoader.TEMPORAL_SIZE),
            "edge_index":  torch.zeros(2, 0, dtype=torch.long),
            "edge_type":   torch.zeros(0, dtype=torch.long),
            "labels":      torch.zeros(0, dtype=torch.long),
            "account_ids": [],
            "N":           0,
            "norm_params": {},
        }

    def get_temporal_norm_params(self) -> Optional[Dict[str, Any]]:
        return self._temporal_norm

    def get_num_scaler(self) -> Optional[StandardScaler]:
        return self._num_scaler
