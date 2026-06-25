# BotRGCN Tweet Embedding Diagnostic - October 8, 2025

## Problem Statement
After implementing ChatGPT's LMDB + per-tweet encoding solution (NO TRUNCATION), the model shows **ZERO improvement** from tweet data. Users WITH tweets perform 35% worse than users WITHOUT tweets.

## Data Extraction (Confirmed Working)
- **LMDB built successfully**: 96.4M tweets, 189GB database
- **Timestamps parsed**: 88,217,457 timestamps (0% failure rate)
- **Per-tweet encoding**: All 1M users processed in 20 batches of 50K
- **Coverage**: 85% of users have tweet data (850K users)
- **Method**: DistilRoBERTa encodes each tweet separately (max 192 tokens), then mean-pools per user

## Model Performance

### Overall Metrics
```
Test F1: 0.594
Val F1: 0.548 (with temporal features)
Val F1: 0.545 (temporal=0) → Δ = +0.003 (NO BENEFIT)
```

### Stratified by Tweet Availability
```
Users WITH tweets (85K):  Bot F1 = 0.543 ❌ WORSE
Users WITHOUT tweets (15K): Bot F1 = 0.776 ✅ BETTER
```
**Model performs 35% WORSE on users with tweet data!**

### Temporal-Only Signal
```
Logistic regression on 15 temporal features: F1 = 0.36
(Should be >0.58 to be useful)
```

## Architecture Details

### Tweet Embedding Extraction (train_botrgcn_parallel_progress.py lines 2280-2340)
```python
# Per-tweet encoding (NO TRUNCATION)
for user_tweets in tweet_texts_per_user:
    if not user_tweets:
        batch_embs.append(np.zeros(768, dtype=np.float32))
        continue

    tweet_embs = []
    for i in range(0, len(user_tweets), HF_BATCH):
        texts = user_tweets[i:i+HF_BATCH]
        enc = tokenizer(texts, return_tensors="pt", truncation=True,
                       max_length=192, padding=True)
        enc = {k: v.to(DEVICE, non_blocking=True) for k, v in enc.items()}

        with torch.no_grad(), torch.autocast(DEVICE.type, enabled=(DEVICE.type=="cuda"), dtype=torch.float16):
            h = mdl(**enc).last_hidden_state.mean(1)  # CLS pooling
        tweet_embs.append(h.float().cpu().numpy())

    # Mean-pool across ALL tweets for this user
    user_emb = np.vstack(tweet_embs).mean(axis=0).astype(np.float32)
    batch_embs.append(user_emb)
```

### Model Forward Pass (lines 1050-1110)
```python
class BotRGCN(nn.Module):
    def forward(self, des_emb, tweet_emb, num_feats, cat_feats, temporal_feats,
                edge_index, edge_type):
        # 1. Profile MLP
        profile_h = self.profile_mlp(torch.cat([num_feats, cat_feats], dim=1))

        # 2. Text fusion (description + tweets)
        text_h = self.text_fusion(des_emb, tweet_emb)  # Weighted combination

        # 3. Temporal gating
        temp_gate = torch.sigmoid(self.temp_gate_mlp(temporal_feats))
        temp_h = temporal_feats * temp_gate

        # 4. Fusion with learned gate
        fused = self.fusion_mlp(torch.cat([profile_h, text_h, temp_h], dim=1))

        # 5. R-GCN propagation
        for conv in self.convs:
            h = conv(fused, edge_index, edge_type)

        return self.classifier(h)
```

## Observations

1. **Tweet embeddings are zero vectors for 15% of users** (no tweets)
   - Model learns: "zero vector = human more often"

2. **Mean pooling may lose signal:**
   - Bot tweets: "Buy crypto! Click here!"
   - Human tweets: Mix of personal + professional
   - Mean pooling dilutes bot signal across 50+ tweets

3. **Temporal features are anti-discriminative:**
   - Sophisticated bots mimic human posting patterns
   - Ablation shows Δ=+0.003 (no benefit)

4. **Gated fusion might be suppressing tweets:**
   - `TEMP_GAIN = 1.0000` (not learning to adjust)
   - Model may be learning to zero out tweet/temporal contributions

## Questions for Analysis

1. **Is mean pooling the right aggregation?**
   - Should we use max pooling (capture strongest bot signal)?
   - Should we use attention (learn which tweets matter)?
   - Should we use tweet-level classification first, then aggregate?

2. **Are tweet embeddings being used at all?**
   - How can we check if text_fusion is learning meaningful weights?
   - Is the model just using profile features + graph?

3. **Why does zero-vector (no tweets) perform better?**
   - Is there label leakage (bots more likely to have tweets)?
   - Is the model learning "presence of tweets = bot"?

4. **Should we change the architecture?**
   - Separate bot-tweet detector → aggregate scores?
   - Use RNN/Transformer over tweet sequence instead of mean?
   - Use contrastive learning (bot tweets vs human tweets)?

## Files Available for Review
- Training script: `/home/the-architect/Reflexion_ultimate/vigilante/hunter/train_botrgcn_parallel_progress.py`
- LMDB builder: `/home/the-architect/Reflexion_ultimate/vigilante/hunter/build_tweets_lmdb_dupsort.py`
- Tweet reader: `/home/the-architect/Reflexion_ultimate/vigilante/hunter/tweet_store.py`
- Temporal features: 16 dims (inter-tweet gaps, hour entropy, engagement metrics)

## Expected ChatGPT Analysis
Please analyze:
1. Why mean-pooled tweet embeddings aren't helping
2. Whether the architecture is suppressing tweet signal
3. Alternative aggregation methods for per-user tweet embeddings
4. Whether we should use tweet-level classification instead
5. How to debug what the model is actually learning from tweets
