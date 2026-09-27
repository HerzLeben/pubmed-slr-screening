# 検索式 — PMID 33746596

状態：案（人の承認待ち。承認まで `fetch_pubmed.py` で取得しない）
作成：2026-09-27、query-builder（2回目。人の指示で P AND I の形に作り直し）
上限：2021/02/18（`datetype=pdat`、`mindate=1800/01/01`）

## 式（演算子6、コネクタで式全体を試験済み）
```
("Multiple Myeloma"[Mesh] OR "multiple myeloma"[tiab] OR "plasma cell myeloma"[tiab]) AND ("Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CART"[tiab])
```

| 確認の経路 | 上限あり | 上限なし |
|---|---|---|
| コネクタ `search_articles` | 418 | — |
| E-utilities esearch（retmax=0、2026-09-27） | 418 | 2,395 |

esearch の query_translation：
`("Multiple Myeloma"[MeSH Terms] OR "Multiple Myeloma"[Title/Abstract] OR "plasma cell myeloma"[Title/Abstract]) AND ("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "CAR-T"[Title/Abstract] OR "CART"[Title/Abstract]) AND 1800/01/01:2021/02/18[Date - Publication]`

## ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| P（multiple myeloma） | `"Multiple Myeloma"[Mesh] OR "multiple myeloma"[tiab] OR "plasma cell myeloma"[tiab]` | 2 |
| I（CAR-T） | `"Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CART"[tiab]` | 3 |

R/R・評価項目・研究デザインはブロックにしない（人が決定。スクリーニングで判定する）。

## 試行の記録（2回目、すべて date_from=1800/01/01、date_to=2021/02/18）
query_translation のうち query-builder が省略して返したものは「（省略）」と書く。
| # | 式 | total_count | query_translation | 理由 |
|---|---|---|---|---|
| 1 | `"Multiple Myeloma"[Mesh] OR "multiple myeloma"[tiab] OR "plasma cell myeloma"[tiab]` | 54,451 | `("Multiple Myeloma"[MeSH Terms] OR "Multiple Myeloma"[Title/Abstract] OR "plasma cell myeloma"[Title/Abstract]) AND 1800/01/01:2021/02/18[Date - Publication]` | P の初期案 |
| 2 | `"Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-T cell"[tiab] OR "CAR T cell"[tiab] OR "CART"[tiab]` | 14,198 | （省略）"CAR-T" と "CAR T"、"CAR-T cell" と "CAR T cell" が同じ `"car t"`・`"car t cell"` に展開 | 重複語の確認 |
| 3 | `"CAR-T cells"[tiab] OR "CAR T cells"[tiab] OR "chimeric antigen receptor T cell"[tiab] OR "chimeric antigen receptor T-cell"[tiab]` | 3,569 | `("car t cells"[Title/Abstract] OR "car t cells"[Title/Abstract] OR "chimeric antigen receptor t cell"[Title/Abstract] OR "chimeric antigen receptor t cell"[Title/Abstract]) AND ...` | 追加候補語の重複確認 |
| 4 | #1 OR `"myeloma"[tiab]` | 62,957 | （省略） | 単独の myeloma の寄与 |
| 5 | `"chimeric antigen receptor"[tiab]` | 4,691 | `"chimeric antigen receptor"[Title/Abstract] AND ...` | 包含の確認の基準値 |
| 6 | `"chimeric antigen receptor"[tiab] OR "chimeric antigen receptor T cell"[tiab]` | 4,691 | （省略） | #5 と同数 → 後者は含まれるので削る |
| 7 | `"CAR-T cell"[tiab]` | 2,621 | `"CAR-T cell"[Title/Abstract] AND ...` | 単数形の件数 |
| 8 | `"CAR-T cells"[tiab]` | 2,893 | `"CAR-T cells"[Title/Abstract] AND ...` | 複数形の件数 |
| 9 | `"CAR-T"[tiab]` | 4,494 | `"CAR-T"[Title/Abstract] AND ...` | 包含の確認の基準値 |
| 10 | `"CAR-T"[tiab] OR "CAR-T cell"[tiab] OR "CAR-T cells"[tiab]` | 4,494 | （省略） | #9 と同数 → cell・cells は含まれるので削る |
| 11 | I 確定案（4語） | 14,198 | `("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "CAR-T"[Title/Abstract] OR "CART"[Title/Abstract]) AND ...` | #2 と同数 → 削っても件数は減らない |
| 12 | P（3語）AND I（4語） | 418 | 上の esearch と同じ | 本検索の候補 |
| 13 | P（4語、myeloma を追加）AND I | 436 | （省略） | myeloma の影響（+18） |
| 14 | `"CART"[tiab]` | 9,907 | `"CART"[Title/Abstract] AND ...` | CART の広さ |
| 15 | P AND `"CART"[tiab]` | 128 | （省略） | CART の寄与 |
| 16 | P AND I（CART を除く3語） | 415 | （省略） | CART の純増分は3件 |
| 17 | P AND I（採用） | 418 | 上の esearch と同じ | 最終案 |

## 1回目の案（採らなかった。R/R ブロックあり）
| # | 式 | total_count | query_translation |
|---|---|---|---|
| v1-1 | `("multiple myeloma"[MeSH Terms] OR "multiple myeloma"[tiab] OR "plasma cell myeloma"[tiab] OR myeloma[tiab]) AND (relapsed[tiab] OR relapse[tiab] OR refractory[tiab] OR "RRMM"[tiab] OR recurrence[MeSH Terms])` | 6,853 | 各語が [Title/Abstract]・[MeSH Terms] にそのまま展開 |
| v1-2 | `("Receptors, Chimeric Antigen"[MeSH Terms] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-Ts"[tiab] OR "CART"[tiab] OR "CAR T-cell"[tiab] OR "CAR T cell"[tiab] OR "CAR-T cell"[tiab])` | 14,207 | "CAR-T"・"CAR T" → `"car t"`、3つの cell の表記 → `"car t cell"` |
| v1-3 | v1-1 AND v1-2 | 220（上限なし 1,482。esearch でも同数） | `... AND 1800/01/01:2021/02/18[Date - Publication]` |

## 未決・気になる点
- 単独の `"myeloma"[tiab]` は入れていない（人の指示「P は multiple myeloma の語だけ」に従った）。入れると +18件（418→436）。query-builder が抄録を見たのは増えた18件のうち1件だけ
- `"CART"[tiab]` は人の指示で残す。単独では 9,907件と広いが、P と組むと純増は3件
- 上位200件は relevance 順（`fetch_pubmed.py` の `sort=relevance`）。418件のうち218件は取らない
