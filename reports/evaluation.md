# Offline evaluation

Protocol: per-user chronological split (10% validation, 20% test per user), positives = rating >= 4.0, k = 10. Hyperparameters selected on validation; test evaluated once.

## Test: full user history

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | ild@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|---|
| random | 0.0036 | 0.0025 | 0.0035 | 0.0334 | 1.0000 | 0.4932 | 0.9960 | [0.0031, 0.0040] |
| popularity | 0.0790 | 0.0574 | 0.0621 | 0.3491 | 0.0318 | 0.9980 | 0.5662 | [0.0764, 0.0819] |
| content | 0.0582 | 0.0448 | 0.0483 | 0.3158 | 0.6506 | 0.7280 | 0.4168 | [0.0561, 0.0604] |
| item_knn | 0.1249 | 0.0944 | 0.0968 | 0.4837 | 0.2256 | 0.9833 | 0.6212 | [0.1211, 0.1284] |
| als | 0.1455 | 0.1118 | 0.1146 | 0.5584 | 0.2172 | 0.9714 | 0.7228 | [0.1417, 0.1491] |
| hybrid | 0.1483 | 0.1143 | 0.1167 | 0.5643 | 0.2184 | 0.9753 | 0.6987 | [0.1446, 0.1520] |

## Test: cold start (each user's 3 most recent likes)

| model | ndcg@10 | recall@10 | precision@10 | hit_rate@10 | coverage | popularity_percentile@10 | ild@10 | NDCG 95% CI |
|---|---|---|---|---|---|---|---|---|
| random | 0.0034 | 0.0019 | 0.0032 | 0.0301 | 1.0000 | 0.4928 | 0.9959 | [0.0028, 0.0040] |
| popularity | 0.0792 | 0.0583 | 0.0624 | 0.3522 | 0.0292 | 0.9980 | 0.5654 | [0.0751, 0.0833] |
| content | 0.0514 | 0.0383 | 0.0398 | 0.2777 | 0.8824 | 0.6853 | 0.4032 | [0.0484, 0.0545] |
| item_knn | 0.1107 | 0.0901 | 0.0830 | 0.4617 | 0.6492 | 0.8736 | 0.6650 | [0.1057, 0.1152] |
| als | 0.1171 | 0.0941 | 0.0876 | 0.4835 | 0.2344 | 0.9584 | 0.6971 | [0.1122, 0.1218] |
| hybrid | 0.1187 | 0.0928 | 0.0896 | 0.4927 | 0.3866 | 0.9421 | 0.5777 | [0.1138, 0.1231] |

## Paired differences in NDCG (bootstrap 95% CI)

| comparison | mean diff | 95% CI |
|---|---|---|
| item_knn - popularity (full) | +0.0459 | [+0.0427, +0.0489] |
| item_knn - popularity (cold) | +0.0315 | [+0.0265, +0.0364] |
| als - popularity (full) | +0.0665 | [+0.0624, +0.0700] |
| als - popularity (cold) | +0.0379 | [+0.0325, +0.0433] |
| als - item_knn (full) | +0.0206 | [+0.0178, +0.0231] |
| als - item_knn (cold) | +0.0064 | [+0.0029, +0.0100] |
| hybrid - popularity (full) | +0.0693 | [+0.0657, +0.0727] |
| hybrid - popularity (cold) | +0.0395 | [+0.0344, +0.0442] |
| hybrid - als (full) | +0.0029 | [+0.0020, +0.0038] |
| hybrid - als (cold) | +0.0016 | [-0.0009, +0.0038] |
| hybrid - item_knn (full) | +0.0234 | [+0.0209, +0.0260] |
| hybrid - item_knn (cold) | +0.0080 | [+0.0046, +0.0114] |
| hybrid - content (full) | +0.0901 | [+0.0866, +0.0935] |
| hybrid - content (cold) | +0.0672 | [+0.0629, +0.0713] |

## Diversity trade-off (served hybrid, MMR re-ranking of the top 200)

Selection rule: largest MMR diversity whose validation ndcg@10 is within 5% of no re-ranking. Selected: **0.4**.

| diversity | validation NDCG | validation ILD | test NDCG | test ILD | test coverage | test popularity pct |
|---|---|---|---|---|---|---|
| 0.0 | 0.1146 | 0.6911 | 0.1483 | 0.6987 | 0.2184 | 0.9753 |
| 0.1 | 0.1143 | 0.7058 | 0.1477 | 0.7138 | 0.2170 | 0.9751 |
| 0.2 | 0.1132 | 0.7257 | 0.1467 | 0.7335 | 0.2168 | 0.9748 |
| 0.3 | 0.1125 | 0.7516 | 0.1441 | 0.7602 | 0.2208 | 0.9740 |
| 0.4 | 0.1098 | 0.7890 | 0.1408 | 0.7982 | 0.2264 | 0.9721 |
| 0.5 | 0.1036 | 0.8453 | 0.1328 | 0.8510 | 0.2408 | 0.9680 |
| 0.7 | 0.0803 | 0.9575 | 0.1044 | 0.9604 | 0.3110 | 0.9485 |

ILD = mean pairwise cosine distance between Tag Genome embeddings of the 10 recommended movies.

## Selected hyperparameters

```json
{
  "item_knn": {
    "k": 100,
    "shrink": 0.0
  },
  "content": {
    "n_components": 128
  },
  "als": {
    "factors": 64,
    "alpha": 2.0,
    "reg": 30.0
  },
  "hybrid": {
    "history_prior": 2.0,
    "popularity_weight": 0.1
  },
  "diversity": 0.4
}
```

Data: {'created_at': '2026-10-22T13:25:44+00:00', 'n_users': 10000, 'n_items': 5000, 'n_interactions': 1450162}. Runtime: 303.0s.
