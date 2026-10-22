# Offline evaluation

Protocol: per-user chronological split (10% validation, 20% test per user), positives = rating >= 4.0, k = 10. Hyperparameters selected on validation; test evaluated once.

## Test: full user history

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|
| random | 0.0035 | 0.0022 | 0.0033 | 0.0314 | 0.8978 | 0.4958 | [0.0031, 0.0040] |
| popularity | 0.0777 | 0.0573 | 0.0608 | 0.3414 | 0.0318 | 0.9980 | [0.0749, 0.0806] |
| content | 0.0575 | 0.0447 | 0.0473 | 0.3096 | 0.6504 | 0.7263 | [0.0554, 0.0595] |
| item_knn | 0.1232 | 0.0942 | 0.0943 | 0.4740 | 0.2122 | 0.9840 | [0.1199, 0.1267] |
| hybrid | 0.1249 | 0.0966 | 0.0954 | 0.4808 | 0.2274 | 0.9833 | [0.1216, 0.1284] |

## Test: cold start (each user's 3 most recent likes)

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|
| random | 0.0035 | 0.0022 | 0.0033 | 0.0314 | 0.8978 | 0.4958 | [0.0031, 0.0040] |
| popularity | 0.0777 | 0.0573 | 0.0608 | 0.3414 | 0.0318 | 0.9980 | [0.0749, 0.0806] |
| content | 0.0519 | 0.0393 | 0.0391 | 0.2761 | 0.9528 | 0.6852 | [0.0498, 0.0541] |
| item_knn | 0.1204 | 0.0983 | 0.0886 | 0.4861 | 0.7140 | 0.9106 | [0.1170, 0.1238] |
| hybrid | 0.1202 | 0.0956 | 0.0888 | 0.4870 | 0.7444 | 0.8959 | [0.1169, 0.1236] |

## Paired differences in NDCG (bootstrap 95% CI)

| comparison | mean diff | 95% CI |
|---|---|---|
| item_knn - popularity (full) | +0.0455 | [+0.0425, +0.0486] |
| item_knn - popularity (cold) | +0.0427 | [+0.0391, +0.0462] |
| hybrid - popularity (full) | +0.0472 | [+0.0442, +0.0503] |
| hybrid - popularity (cold) | +0.0425 | [+0.0388, +0.0462] |
| hybrid - item_knn (full) | +0.0016 | [+0.0011, +0.0022] |
| hybrid - item_knn (cold) | -0.0002 | [-0.0017, +0.0013] |
| hybrid - content (full) | +0.0674 | [+0.0641, +0.0708] |
| hybrid - content (cold) | +0.0683 | [+0.0654, +0.0712] |

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
  }
}
```

Data: {'created_at': '2026-10-22T13:25:44+00:00', 'n_users': 10000, 'n_items': 5000, 'n_interactions': 1450162}. Runtime: 55.5s.
