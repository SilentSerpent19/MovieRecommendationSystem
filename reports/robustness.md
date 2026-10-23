# Robustness checks

Hyperparameters are fixed to those selected in `reports/evaluation.json`; nothing is re-tuned. NDCG@10 on the test fold. `*` = the paired bootstrap 95% CI excludes 0.

## 1. Resampled users

The same per-user chronological protocol (70/10/20, leak-free cold start) on independent samples of 10,000 users, drawn with different seeds. The catalog is identical in every sample.

### NDCG@10, full history

| sample | users evaluated | popularity | item_knn | als | hybrid |
|---|---|---|---|---|---|
| seed 42 (main) | 9,817 | 0.0790 | 0.1249 | 0.1455 | 0.1483 |
| seed 1 | 9,841 | 0.0792 | 0.1280 | 0.1470 | 0.1501 |
| seed 2 | 9,824 | 0.0785 | 0.1232 | 0.1418 | 0.1440 |
| seed 3 | 9,834 | 0.0774 | 0.1215 | 0.1424 | 0.1442 |
| **mean ± sd** | | **0.0785** ± 0.0008 | **0.1244** ± 0.0028 | **0.1442** ± 0.0025 | **0.1467** ± 0.0030 |

### NDCG@10, cold start (3 likes)

| sample | users evaluated | popularity | item_knn | als | hybrid |
|---|---|---|---|---|---|
| seed 42 (main) | 4,912 | 0.0792 | 0.1107 | 0.1171 | 0.1187 |
| seed 1 | 4,913 | 0.0792 | 0.1138 | 0.1205 | 0.1220 |
| seed 2 | 4,904 | 0.0794 | 0.1142 | 0.1186 | 0.1211 |
| seed 3 | 4,905 | 0.0791 | 0.1091 | 0.1163 | 0.1184 |
| **mean ± sd** | | **0.0792** ± 0.0001 | **0.1119** ± 0.0025 | **0.1181** ± 0.0018 | **0.1201** ± 0.0018 |

### Paired differences per sample

| sample | als - item_knn (full) | als - item_knn (cold) | hybrid - als (full) | hybrid - als (cold) | hybrid - item_knn (full) | hybrid - item_knn (cold) | item_knn - popularity (full) | item_knn - popularity (cold) |
|---|---|---|---|---|---|---|---|---|
| seed 42 (main) | +0.0206 [+0.0178, +0.0231] * | +0.0064 [+0.0029, +0.0100] * | +0.0029 [+0.0020, +0.0038] * | +0.0016 [-0.0009, +0.0038] | +0.0234 [+0.0209, +0.0260] * | +0.0080 [+0.0046, +0.0114] * | +0.0459 [+0.0427, +0.0489] * | +0.0315 [+0.0265, +0.0364] * |
| seed 1 | +0.0189 [+0.0163, +0.0217] * | +0.0067 [+0.0032, +0.0101] * | +0.0031 [+0.0021, +0.0041] * | +0.0015 [-0.0008, +0.0040] | +0.0220 [+0.0196, +0.0247] * | +0.0082 [+0.0047, +0.0118] * | +0.0488 [+0.0459, +0.0518] * | +0.0345 [+0.0293, +0.0397] * |
| seed 2 | +0.0186 [+0.0159, +0.0216] * | +0.0045 [+0.0010, +0.0081] * | +0.0021 [+0.0012, +0.0030] * | +0.0024 [+0.0001, +0.0049] * | +0.0207 [+0.0182, +0.0235] * | +0.0069 [+0.0033, +0.0105] * | +0.0447 [+0.0417, +0.0476] * | +0.0348 [+0.0299, +0.0398] * |
| seed 3 | +0.0209 [+0.0180, +0.0238] * | +0.0072 [+0.0037, +0.0109] * | +0.0018 [+0.0009, +0.0028] * | +0.0021 [-0.0004, +0.0045] | +0.0227 [+0.0200, +0.0255] * | +0.0093 [+0.0060, +0.0129] * | +0.0441 [+0.0409, +0.0469] * | +0.0300 [+0.0248, +0.0343] * |

User overlap with the main sample: {'seed 1': '6.6%', 'seed 2': '6.2%', 'seed 3': '6.3%'}.

## 2. Global time split

One cut-off for everyone at **2016-06-06**: the newest 20% of all interactions are test, everything before is training.

- Users evaluated (likes on both sides of the cut-off): 399 of 1,978 with test likes; 1,579 users only appear after the cut-off.
- Test likes on movies with no training likes (unlearnable for CF): 18.5%.

| model | NDCG@10 | 95% CI | recall@10 | coverage | popularity percentile |
|---|---|---|---|---|---|
| random | 0.0082 | [0.0050, 0.0116] | 0.0016 | 0.5410 | 0.4837 |
| popularity | 0.0965 | [0.0796, 0.1150] | 0.0316 | 0.0292 | 0.9956 |
| content | 0.1248 | [0.1083, 0.1412] | 0.0501 | 0.1448 | 0.4175 |
| item_knn | 0.1284 | [0.1099, 0.1483] | 0.0442 | 0.0590 | 0.9784 |
| als | 0.1627 | [0.1416, 0.1835] | 0.0518 | 0.1302 | 0.9544 |
| hybrid | 0.1602 | [0.1388, 0.1811] | 0.0469 | 0.1228 | 0.9606 |

| comparison | mean diff [95% CI] |
|---|---|
| als - item_knn | +0.0343 [+0.0200, +0.0481] * |
| hybrid - als | -0.0025 [-0.0073, +0.0023] |
| hybrid - item_knn | +0.0318 [+0.0183, +0.0460] * |
| item_knn - popularity | +0.0319 [+0.0183, +0.0460] * |
| hybrid - popularity | +0.0637 [+0.0466, +0.0821] * |

Runtime: 216.4s.
