# Offline evaluation

Protocol: per-user chronological split (10% validation, 20% test per user), positives = rating >= 4.0, k = 10. Hyperparameters selected on validation; test evaluated once.

## Test: full user history

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | ild@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|---|
| random | 0.0036 | 0.0025 | 0.0035 | 0.0334 | 1.0000 | 0.4932 | 0.9960 | [0.0031, 0.0040] |
| popularity | 0.0790 | 0.0574 | 0.0621 | 0.3491 | 0.0318 | 0.9980 | 0.5662 | [0.0764, 0.0819] |
| content | 0.0582 | 0.0448 | 0.0483 | 0.3158 | 0.6506 | 0.7280 | 0.4168 | [0.0561, 0.0604] |
| item_knn | 0.1253 | 0.0943 | 0.0969 | 0.4811 | 0.2132 | 0.9838 | 0.6261 | [0.1218, 0.1288] |
| hybrid | 0.1266 | 0.0959 | 0.0976 | 0.4861 | 0.2272 | 0.9834 | 0.6171 | [0.1227, 0.1300] |

## Test: cold start (each user's 3 most recent likes)

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | ild@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|---|
| random | 0.0034 | 0.0019 | 0.0032 | 0.0301 | 1.0000 | 0.4928 | 0.9959 | [0.0028, 0.0040] |
| popularity | 0.0792 | 0.0583 | 0.0624 | 0.3522 | 0.0292 | 0.9980 | 0.5654 | [0.0751, 0.0833] |
| content | 0.0514 | 0.0383 | 0.0398 | 0.2777 | 0.8824 | 0.6853 | 0.4032 | [0.0484, 0.0545] |
| item_knn | 0.1141 | 0.0932 | 0.0856 | 0.4715 | 0.6382 | 0.8821 | 0.6640 | [0.1092, 0.1186] |
| hybrid | 0.1151 | 0.0914 | 0.0870 | 0.4758 | 0.6672 | 0.8763 | 0.5883 | [0.1102, 0.1195] |

## Paired differences in NDCG (bootstrap 95% CI)

| comparison | mean diff | 95% CI |
|---|---|---|
| item_knn - popularity (full) | +0.0464 | [+0.0431, +0.0494] |
| item_knn - popularity (cold) | +0.0349 | [+0.0298, +0.0397] |
| hybrid - popularity (full) | +0.0476 | [+0.0443, +0.0505] |
| hybrid - popularity (cold) | +0.0359 | [+0.0308, +0.0407] |
| hybrid - item_knn (full) | +0.0012 | [+0.0007, +0.0018] |
| hybrid - item_knn (cold) | +0.0010 | [-0.0011, +0.0029] |
| hybrid - content (full) | +0.0683 | [+0.0651, +0.0717] |
| hybrid - content (cold) | +0.0637 | [+0.0595, +0.0677] |

## Diversity trade-off (served hybrid, MMR re-ranking of the top 200)

Selection rule: largest MMR diversity whose validation ndcg@10 is within 5% of no re-ranking. Selected: **0.4**.

| diversity | validation NDCG | validation ILD | test NDCG | test ILD | test coverage | test popularity pct |
|---|---|---|---|---|---|---|
| 0.0 | 0.0998 | 0.6137 | 0.1266 | 0.6171 | 0.2272 | 0.9834 |
| 0.1 | 0.1007 | 0.6324 | 0.1269 | 0.6359 | 0.2280 | 0.9830 |
| 0.2 | 0.1009 | 0.6564 | 0.1267 | 0.6603 | 0.2260 | 0.9826 |
| 0.3 | 0.0996 | 0.6890 | 0.1254 | 0.6920 | 0.2302 | 0.9818 |
| 0.4 | 0.0971 | 0.7282 | 0.1219 | 0.7305 | 0.2328 | 0.9803 |
| 0.5 | 0.0917 | 0.7757 | 0.1173 | 0.7768 | 0.2432 | 0.9776 |
| 0.7 | 0.0733 | 0.9018 | 0.0961 | 0.9021 | 0.2992 | 0.9626 |

ILD = mean pairwise cosine distance between Tag Genome embeddings of the 10 recommended movies.

## Selected hyperparameters

```json
{
  "item_knn": {
    "k": 200,
    "shrink": 0.0
  },
  "content": {
    "n_components": 128
  },
  "hybrid": {
    "history_prior": 2.0,
    "popularity_weight": 0.0
  },
  "diversity": 0.4
}
```

Data: {'created_at': '2026-10-22T13:25:44+00:00', 'n_users': 10000, 'n_items': 5000, 'n_interactions': 1450162}. Runtime: 86.1s.
