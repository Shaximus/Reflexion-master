"""
AdversarialTrainer

Fine-tunes a pretrained BotRGCN on real ban/survive data from the swarm,
teaching the model Twitter's specific detection function.

Pipeline:
  1. Load pretrained weights from botrgcn_t16_best.pt
  2. Optionally freeze des/tweet branches
  3. Train with FocalLoss, AdamW, ReduceLROnPlateau
  4. Early stopping on validation F1
  5. Compute gradient-based feature importance
  6. Serialize model + training log
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit

logger = logging.getLogger("botrgcn_adapter.trainer")

# BotRGCN classes -- imported lazily in _load_botrgcn() so the heavy
# torch-geometric import only happens when actually needed.

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
_MODELS_DIR = Path("/home/shax/Projects/core-tech/Reflexion-master/models")
_MODEL_SAVE_PATH    = _MODELS_DIR / "botrgcn_adversarial_best.pt"
_NORM_SAVE_PATH     = _MODELS_DIR / "adversarial_norm.json"
_TRAIN_LOG_PATH     = _MODELS_DIR / "adversarial_training_log.json"

# ---------------------------------------------------------------------------
# Temporal feature names (aligns with BotRGCN 16-dim vector)
# ---------------------------------------------------------------------------
TEMPORAL_FEATURE_NAMES = [
    # Original 16 slots [0-15]
    "median_gap_min", "std_gap_min", "cv_gap", "burst_ratio",
    "hour_entropy", "weekend_ratio",
    "retweet_ratio", "url_ratio", "hashtag_density", "mention_density",
    "log_avg_retweets", "log_avg_replies", "log_avg_likes",
    "log_engagement_std", "engagement_cv",
    "has_tweets",
    # Session behavior (Scribe-aware) [16-21]
    "session_action_diversity", "avg_dwell_time_ms", "session_duration_cv",
    "impression_action_ratio", "avg_actions_per_session", "scroll_impression_ratio",
    # Social graph dynamics [22-25]
    "follow_velocity_per_day", "unfollow_ratio",
    "reply_thread_depth_avg", "follow_back_ratio",
    # Red flag indicators [26-28]
    "rate_limit_events_per_day", "error_rate", "ad_impression_ratio",
]

NUM_PROP_FEATURE_NAMES = [
    "follower_count", "following_count", "total_likes_received",
    "total_tweets", "username_length", "account_age_days",
]


class FocalLoss(nn.Module):
    """Focal Loss for class imbalance (few banned accounts initially)."""

    def __init__(self, alpha: float = 0.75, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = F.cross_entropy(inputs, targets, reduction="none")
        pt = torch.exp(-bce)
        alpha_t = torch.where(targets == 1, self.alpha, 1 - self.alpha)
        loss = alpha_t * (1 - pt) ** self.gamma * bce
        return loss.mean()


class AdversarialTrainer:
    """
    Fine-tunes BotRGCN on real swarm ban/survive telemetry.

    Usage::

        trainer = AdversarialTrainer(pretrained_weights_path="path/to/botrgcn_t16_best.pt")
        data    = await trainer.load_data()
        results = trainer.train(data, epochs=50)
    """

    def __init__(
        self,
        pretrained_weights_path: str,
        device: str = "cuda",
    ) -> None:
        self.pretrained_weights_path = Path(pretrained_weights_path)
        self.device = torch.device(
            device if torch.cuda.is_available() else "cpu"
        )
        if self.device.type != device:
            logger.warning(
                "Requested device '%s' unavailable; using '%s'", device, self.device
            )
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public: load data via BlasterDataLoader
    # ------------------------------------------------------------------

    async def load_data(self) -> Dict[str, Any]:
        """Pull swarm telemetry from Redis and convert to BotRGCN tensors.

        Stores the BlasterDataLoader instance and raw export on self so that
        train() can re-normalize temporal/num_prop after the train/val split
        to prevent data leakage (fitting normalization stats on ALL data
        instead of just training data).
        """
        from .blaster_data_loader import BlasterDataLoader  # noqa: PLC0415

        self._loader = BlasterDataLoader()
        self._export = await self._loader.load_from_snapshots()
        tensors = self._loader.prepare_botrgcn_tensors(self._export)

        # Persist normalization params for inference
        norm = self._loader.get_temporal_norm_params()
        if norm:
            _NORM_SAVE_PATH.write_text(json.dumps(norm, indent=2))
            logger.info("Normalization params saved to %s", _NORM_SAVE_PATH)

        return tensors

    # ------------------------------------------------------------------
    # Public: training pipeline
    # ------------------------------------------------------------------

    def train(
        self,
        data: Dict[str, Any],
        epochs: int = 50,
        lr: float = 0.001,
        patience: int = 10,
        freeze_text_branches: bool = True,
    ) -> Dict[str, Any]:
        """
        Fine-tune BotRGCN on swarm data.

        Returns dict with: test_metrics, feature_importances, best_threshold,
        dataset_size, model_version, epochs_trained.

        If dataset is too small (<20 samples) skips training and returns
        feature importances from the pretrained model.
        """
        N = data.get("N", 0)
        logger.info("Training on N=%d samples", N)

        if N < 5:
            logger.warning(
                "Dataset too small (%d samples) -- returning pretrained feature importances", N
            )
            model = self._load_botrgcn(higher_dropout=False)
            importances = self.compute_feature_importance(model, data)
            return {
                "test_metrics": {},
                "feature_importances": importances,
                "best_threshold": 0.5,
                "dataset_size": N,
                "model_version": "pretrained_only",
                "epochs_trained": 0,
                "skipped": True,
            }

        # Build model
        model = self._load_botrgcn(higher_dropout=(N < 100))

        if freeze_text_branches:
            self._freeze_text_branches(model)
            logger.info("Frozen des and tweet branches")

        model.to(self.device)

        # Train / val split (stratified)
        labels_np = data["labels"].numpy()
        train_idx, val_idx = self._stratified_split(labels_np)

        logger.info(
            "Split: train=%d val=%d  (banned: train=%d val=%d)",
            len(train_idx), len(val_idx),
            int(labels_np[train_idx].sum()),
            int(labels_np[val_idx].sum()),
        )

        # Re-normalize temporal and num_prop using ONLY training indices
        # to prevent data leakage (validation stats leaking into normalization).
        # The loader has _normalize_temporal() and _scale_num_prop() that
        # accept train_indices but prepare_botrgcn_tensors() doesn't pass them.
        if hasattr(self, "_loader") and self._loader is not None and \
                hasattr(self, "_export") and self._export is not None:
            loader = self._loader
            export = self._export
            features = export.get("features")
            account_ids = export.get("account_ids", [])

            if features is not None and len(features) > 0:
                try:
                    # Rebuild raw matrices from export data, then normalize
                    # with train_indices to prevent leakage
                    temporal_raw = loader._build_temporal_matrix(features, account_ids)
                    temporal_normed, norm_params = loader._normalize_temporal(
                        temporal_raw, train_indices=train_idx
                    )
                    data["temporal"] = torch.from_numpy(temporal_normed)
                    # Update saved norm params with leak-free version
                    if norm_params:
                        _NORM_SAVE_PATH.write_text(json.dumps(norm_params, indent=2))
                    logger.info("Re-normalized temporal with train-only stats (leak-free)")

                    num_prop_raw = loader._build_num_prop_matrix(features, account_ids)
                    num_prop_scaled, _ = loader._scale_num_prop(
                        num_prop_raw, train_indices=train_idx
                    )
                    data["num_prop"] = torch.from_numpy(num_prop_scaled)
                    logger.info("Re-normalized num_prop with train-only stats (leak-free)")
                except Exception as exc:
                    logger.warning(
                        "Could not re-normalize with train-only stats: %s "
                        "-- proceeding with all-data normalization", exc
                    )

        # Move tensors to device
        des        = data["des"].to(self.device)
        tweet      = data["tweet"].to(self.device)
        num_prop   = data["num_prop"].to(self.device)
        cat_prop   = data["cat_prop"].to(self.device)
        temporal   = data["temporal"].to(self.device)
        edge_index = data["edge_index"].to(self.device)
        edge_type  = data["edge_type"].to(self.device)
        labels_all = data["labels"].to(self.device)

        criterion = FocalLoss(alpha=0.75, gamma=2.0)
        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=lr,
            weight_decay=0.05,
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="max", factor=0.5, patience=3, min_lr=1e-6
        )

        best_val_f1    = 0.0
        epochs_no_impr = 0
        best_state     = None
        train_log: List[Dict[str, Any]] = []

        train_t = torch.tensor(train_idx, dtype=torch.long)
        val_t   = torch.tensor(val_idx,   dtype=torch.long)

        for epoch in range(1, epochs + 1):
            # --- Training step ---
            model.train()
            # Augment a COPY of temporal; only modify training indices in-place
            # Continuous cols: 0-14 and 16-28 (skip binary col 15 = has_tweets)
            temporal_aug = temporal.clone()
            continuous_cols = list(range(0, 15)) + list(range(16, 29))
            noise = torch.randn(len(train_t), len(continuous_cols), device=self.device) * 0.1
            temporal_aug[train_t.unsqueeze(1), torch.tensor(continuous_cols, device=self.device)] += noise

            optimizer.zero_grad(set_to_none=True)

            # Pass full graph to model (transductive: RGCN needs all nodes)
            logits = model(
                des, tweet,
                num_prop, cat_prop,
                temporal_aug,
                edge_index, edge_type,
            )
            # Slice logits for training nodes only
            loss = criterion(logits[train_t], labels_all[train_t])

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            # --- Validation step ---
            model.eval()
            with torch.no_grad():
                val_logits = model(
                    des, tweet, num_prop, cat_prop, temporal,
                    edge_index, edge_type,
                )[val_t]
                val_probs = F.softmax(val_logits, dim=1)[:, 1].cpu().numpy()
                val_preds = (val_probs >= 0.5).astype(int)
                val_true  = labels_np[val_idx]

            val_f1 = f1_score(val_true, val_preds, average="binary", zero_division=0)
            scheduler.step(val_f1)

            epoch_log = {
                "epoch": epoch,
                "loss": float(loss.item()),
                "val_f1": float(val_f1),
                "lr": float(optimizer.param_groups[0]["lr"]),
            }
            train_log.append(epoch_log)

            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                epochs_no_impr = 0
                best_state = {
                    k: v.cpu().clone() for k, v in model.state_dict().items()
                }
                logger.info(
                    "Epoch %3d | loss=%.4f val_f1=%.4f  [NEW BEST]",
                    epoch, loss.item(), val_f1,
                )
            else:
                epochs_no_impr += 1
                if epoch % 5 == 0:
                    logger.info(
                        "Epoch %3d | loss=%.4f val_f1=%.4f  (no impr %d/%d)",
                        epoch, loss.item(), val_f1, epochs_no_impr, patience,
                    )

            if epochs_no_impr >= patience:
                logger.info("Early stopping at epoch %d (patience=%d)", epoch, patience)
                break

        # Restore best
        if best_state is not None:
            model.load_state_dict(best_state)

        # Save model
        torch.save(model.state_dict(), _MODEL_SAVE_PATH)
        logger.info("Best model saved to %s", _MODEL_SAVE_PATH)

        # --- Test on validation set only (avoids inflated train+val metrics) ---
        model.eval()
        with torch.no_grad():
            all_logits = model(
                des, tweet, num_prop, cat_prop, temporal,
                edge_index, edge_type,
            )
            val_probs_final = F.softmax(all_logits[val_t], dim=1)[:, 1].cpu().numpy()

        val_true_final = labels_np[val_idx]
        best_threshold, best_f1 = self._find_best_threshold(val_true_final, val_probs_final)
        val_preds_final = (val_probs_final >= best_threshold).astype(int)

        test_metrics = self._compute_metrics(val_true_final, val_preds_final, val_probs_final)
        logger.info("Final metrics: %s", test_metrics)

        # Feature importances from best model
        importances = self.compute_feature_importance(model, data)

        # Save training log
        log_payload = {
            "trained_at": time.time(),
            "dataset_size": N,
            "epochs_trained": len(train_log),
            "best_val_f1": best_val_f1,
            "best_threshold": best_threshold,
            "test_metrics": test_metrics,
            "feature_importances": importances,
            "epoch_log": train_log,
        }
        _TRAIN_LOG_PATH.write_text(json.dumps(log_payload, indent=2))
        logger.info("Training log saved to %s", _TRAIN_LOG_PATH)

        return {
            "test_metrics":       test_metrics,
            "feature_importances": importances,
            "best_threshold":     best_threshold,
            "dataset_size":       N,
            "model_version":      "adversarial_v1",
            "epochs_trained":     len(train_log),
            "best_val_f1":        best_val_f1,
        }

    # ------------------------------------------------------------------
    # Public: generate spec from training results and store to Redis
    # ------------------------------------------------------------------

    async def generate_and_store_spec(
        self,
        results: Dict[str, Any],
        redis_client: "aioredis.Redis",
        safety_margin: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Close the feedback loop: take training results (feature importances)
        and generate + store a SleeperSpec to Redis.

        This is the critical wiring that connects:
          training output -> spec generation -> Redis -> fingerprint consumption

        Parameters
        ----------
        results : dict
            Return value from self.train(), must contain "feature_importances".
        redis_client : aioredis.Redis
            Redis connection for storing the spec.
        safety_margin : float
            How much to tighten constraints beyond naive inversion.

        Returns
        -------
        dict with keys: spec (SleeperSpec), fingerprint_params (dict),
        redis_keys_written (list of str).
        """
        from .sleeper_specs import SleeperSpecGenerator  # noqa: PLC0415

        importances = results.get("feature_importances", {})
        if not importances:
            logger.warning("No feature importances in results -- cannot generate spec")
            return {"spec": None, "fingerprint_params": None, "redis_keys_written": []}

        gen = SleeperSpecGenerator(importances)
        spec = gen.generate_spec(
            safety_margin=safety_margin,
            model_version=results.get("model_version", "unknown"),
            dataset_size=results.get("dataset_size", 0),
            model_accuracy=results.get("test_metrics", {}).get("accuracy", 0.0),
        )

        # Store to Redis (latest + history)
        await gen.store_spec(redis_client, spec)

        # Generate fingerprint constraint overrides
        params = gen.generate_fingerprint_params(spec)

        # Also store fingerprint params directly for FingerprintGenerator consumption
        import json as _json
        _FINGERPRINT_OVERRIDES_KEY = "botrgcn:fingerprint_overrides:latest"
        await redis_client.set(_FINGERPRINT_OVERRIDES_KEY, _json.dumps(params, default=str))

        redis_keys_written = [
            "botrgcn:sleeper_spec:latest",
            "botrgcn:sleeper_spec:history",
            _FINGERPRINT_OVERRIDES_KEY,
        ]
        logger.info(
            "Closed-loop spec generated and stored to Redis: %s",
            redis_keys_written,
        )

        return {
            "spec": spec,
            "fingerprint_params": params,
            "redis_keys_written": redis_keys_written,
        }

    async def run_closed_loop(
        self,
        redis_client: "aioredis.Redis",
        epochs: int = 50,
        safety_margin: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Execute the full closed-loop pipeline:
          1. Load data from Redis snapshots
          2. Train the model
          3. Generate spec from feature importances
          4. Store spec to Redis
          5. Return everything

        This is the single entry point that closes the loop:
          training output -> spec -> Redis -> fingerprint generator reads it
        """
        # Step 1: Load data
        data = await self.load_data()
        logger.info("Loaded data: N=%d", data.get("N", 0))

        # Step 2: Train
        results = self.train(data, epochs=epochs)
        logger.info(
            "Training complete: epochs=%d, f1=%.4f",
            results.get("epochs_trained", 0),
            results.get("best_val_f1", 0.0),
        )

        # Step 3-4: Generate spec and store to Redis
        spec_result = await self.generate_and_store_spec(
            results, redis_client, safety_margin=safety_margin
        )

        return {
            **results,
            "spec": spec_result.get("spec"),
            "fingerprint_params": spec_result.get("fingerprint_params"),
            "redis_keys_written": spec_result.get("redis_keys_written", []),
        }

    # ------------------------------------------------------------------
    # Public: feature importance via gradient attribution
    # ------------------------------------------------------------------

    def compute_feature_importance(
        self, model: nn.Module, data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Gradient-based feature attribution.

        For each input modality, computes d(bot_logit)/d(input) averaged
        over all samples and dimensions, giving a per-feature importance score.

        Returns dict mapping feature_name -> mean |gradient| score.
        """
        if data.get("N", 0) == 0:
            return {name: 0.0 for name in TEMPORAL_FEATURE_NAMES + NUM_PROP_FEATURE_NAMES}

        model.eval()
        model.to(self.device)

        des        = data["des"].to(self.device)
        tweet      = data["tweet"].to(self.device)
        num_prop   = data["num_prop"].to(self.device)
        cat_prop   = data["cat_prop"].to(self.device)
        temporal   = data["temporal"].to(self.device)
        edge_index = data["edge_index"].to(self.device)
        edge_type  = data["edge_type"].to(self.device)

        # Enable gradient tracking for attribution targets
        temporal_g  = temporal.detach().requires_grad_(True)
        num_prop_g  = num_prop.detach().requires_grad_(True)

        logits = model(
            des, tweet, num_prop_g, cat_prop, temporal_g,
            edge_index, edge_type,
        )
        # Bot logit is index 1; average over all nodes
        bot_score = logits[:, 1].mean()
        bot_score.backward()

        # Temporal importances: mean(|grad|) per feature dim
        temporal_grads = temporal_g.grad.abs().mean(dim=0).detach().cpu().numpy()
        num_grads      = num_prop_g.grad.abs().mean(dim=0).detach().cpu().numpy()

        importances: Dict[str, float] = {}
        for i, name in enumerate(TEMPORAL_FEATURE_NAMES):
            importances[name] = float(temporal_grads[i])

        for i, name in enumerate(NUM_PROP_FEATURE_NAMES):
            importances[name] = float(num_grads[i])

        # Normalize so values sum to 1
        total = sum(importances.values()) + 1e-9
        importances = {k: v / total for k, v in importances.items()}

        logger.info(
            "Top-5 feature importances: %s",
            sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5],
        )
        return importances

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_botrgcn(self, higher_dropout: bool = False) -> nn.Module:
        """
        Import BotRGCN from the hunter module and load pretrained weights.
        Falls back gracefully if weights file is missing.
        """
        try:
            from botrgcn_adapter.botrgcn_model import (  # noqa: PLC0415
                BotRGCN,
            )
        except ImportError as exc:
            raise ImportError(
                "Cannot import BotRGCN from botrgcn_adapter.botrgcn_model. "
                "Ensure botrgcn_model.py is in the botrgcn_adapter directory."
            ) from exc

        dropout = 0.5 if higher_dropout else 0.3
        model = BotRGCN(
            des_size=768, tweet_size=768,
            num_prop_size=6, cat_prop_size=3,
            temporal_size=42,
            embed_dim=128,
            dropout=dropout,
            modality_dropout_p=0.10,
            temp_gain_init=1.0,
            disable_gate=False,
        )

        if not self.pretrained_weights_path.exists():
            logger.warning(
                "Pretrained weights not found at %s -- training from scratch",
                self.pretrained_weights_path,
            )
            return model

        try:
            state = torch.load(
                self.pretrained_weights_path,
                map_location="cpu",
                weights_only=True,
            )
            missing, unexpected = model.load_state_dict(state, strict=False)
            if missing:
                logger.warning("Missing keys in pretrained weights: %s", missing[:5])
            if unexpected:
                logger.warning("Unexpected keys in pretrained weights: %s", unexpected[:5])
            logger.info(
                "Loaded pretrained weights from %s", self.pretrained_weights_path
            )
        except Exception as exc:
            logger.error(
                "Failed to load pretrained weights: %s -- training from scratch", exc
            )

        return model

    @staticmethod
    def _freeze_text_branches(model: nn.Module) -> None:
        """Freeze des and tweet encoder weights."""
        for name, param in model.named_parameters():
            if name.startswith("linear_des") or name.startswith("linear_tweet"):
                param.requires_grad = False

    @staticmethod
    def _stratified_split(
        labels: np.ndarray,
        val_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Stratified 80/20 split; handles edge cases with very few samples."""
        n = len(labels)
        unique_classes = np.unique(labels)
        class_counts = np.bincount(labels.astype(int))

        if n < 4 or len(unique_classes) < 2 or class_counts.min() < 2:
            # Not enough for stratified split; just split sequentially
            split = max(1, int(n * 0.8))
            return np.arange(split), np.arange(split, n)

        splitter = StratifiedShuffleSplit(
            n_splits=1, test_size=val_size, random_state=random_state
        )
        train_idx, val_idx = next(splitter.split(np.zeros(n), labels))
        return train_idx, val_idx

    @staticmethod
    def _augment_temporal(
        temporal: torch.Tensor, noise_std: float = 0.1
    ) -> torch.Tensor:
        """
        Add Gaussian noise to continuous cols 0-14 and 16-28.
        Col 15 (has_tweets bit) is left untouched.
        """
        noise = torch.randn_like(temporal) * noise_std
        noise[:, 15] = 0.0  # preserve binary bit
        return temporal + noise

    @staticmethod
    def _find_best_threshold(
        y_true: np.ndarray, y_probs: np.ndarray
    ) -> Tuple[float, float]:
        """Sweep thresholds 0.1-0.9 and return the one with the highest F1."""
        best_t   = 0.5
        best_f1  = 0.0
        for t in np.arange(0.1, 0.91, 0.05):
            preds = (y_probs >= t).astype(int)
            f1 = f1_score(y_true, preds, average="binary", zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t  = float(t)
        return best_t, best_f1

    @staticmethod
    def _compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: np.ndarray,
    ) -> Dict[str, float]:
        metrics: Dict[str, float] = {
            "f1":        float(f1_score(y_true, y_pred, average="binary", zero_division=0)),
            "precision": float(precision_score(y_true, y_pred, average="binary", zero_division=0)),
            "recall":    float(recall_score(y_true, y_pred, average="binary", zero_division=0)),
            "accuracy":  float((y_true == y_pred).mean()),
        }
        if len(np.unique(y_true)) > 1:
            try:
                metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob))
            except ValueError:
                metrics["roc_auc"] = 0.0
        return metrics
