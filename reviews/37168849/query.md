# 検索式 — PMID 37168849

状態：承認済み（2026-09-27、人が式と上限を承認）
作成：2026-09-27、query-builder（1回目）＋本体で重複語を削った
上限：2023/04/24（`datetype=pdat`、`mindate=1800/01/01`）

## 式（演算子8、コネクタで式全体を試験済み）
```
("Leukemia, Myeloid, Acute"[Mesh] OR "acute myeloid leukemia"[tiab] OR "acute myeloid leukaemia"[tiab] OR "acute myelogenous leukemia"[tiab] OR "AML"[tiab]) AND ("Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CART"[tiab])
```

| 確認の経路 | 上限あり | 上限なし |
|---|---|---|
| コネクタ `search_articles` | 473 | — |
| E-utilities esearch（retmax=0、2026-09-27） | 473 | 929 |

esearch の件数は、削る前の8語の式（#4）と、4語にした採用の式（#7）のどちらも 473／929。

query_translation（#6、コネクタ）：
`("leukemia, myeloid, acute"[MeSH Terms] OR "acute myeloid leukemia"[Title/Abstract] OR "acute myeloid leukaemia"[Title/Abstract] OR "acute myelogenous leukemia"[Title/Abstract] OR "AML"[Title/Abstract]) AND ("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "CAR-T"[Title/Abstract] OR "CART"[Title/Abstract]) AND 1800/01/01:2023/04/24[Date - Publication]`

## ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| P（AML） | `"Leukemia, Myeloid, Acute"[Mesh] OR "acute myeloid leukemia"[tiab] OR "acute myeloid leukaemia"[tiab] OR "acute myelogenous leukemia"[tiab] OR "AML"[tiab]` | 4 |
| I（CAR-T） | `"Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CART"[tiab]` | 3 |

R/R・評価項目・研究デザインはブロックにしない（人が決定）。I ブロックは 33746596 と同じ。

## 試行の記録（すべて date_from=1800/01/01、date_to=2023/04/24）
| # | 誰が | 式 | total_count | query_translation | 理由 |
|---|---|---|---|---|---|
| 1 | query-builder | P のみ | 90,014 | `("leukemia, myeloid, acute"[MeSH Terms] OR "acute myeloid leukemia"[Title/Abstract] OR "acute myeloid leukaemia"[Title/Abstract] OR "acute myelogenous leukemia"[Title/Abstract] OR "AML"[Title/Abstract]) AND 1800/01/01:2023/04/24[Date - Publication]` | P の規模 |
| 2 | query-builder | `"Receptors, Chimeric Antigen"[Mesh] OR "chimeric antigen receptor"[tiab] OR "CAR T"[tiab] OR "CAR-T"[tiab] OR "CART"[tiab] OR "CAR T-cell"[tiab] OR "CAR-T cell"[tiab] OR "chimeric antigen receptor T cell"[tiab]` | 20,808 | `("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "car t"[Title/Abstract] OR "car t"[Title/Abstract] OR "CART"[Title/Abstract] OR "car t cell"[Title/Abstract] OR "car t cell"[Title/Abstract] OR "chimeric antigen receptor T cell"[Title/Abstract]) AND 1800/01/01:2023/04/24[Date - Publication]` | I の規模。重複の展開を確認 |
| 3 | query-builder | P AND #2 | 473 | #1 と #2 を AND（日付つき） | 1回目の案 |
| 4 | 本体（esearch） | #3 | 473（上限なし 929） | #3 と同じ | 日付の確認 |
| 5 | 本体 | P AND I（`"CAR T"`・`"CAR T-cell"` を削った6語） | 473 | I：`"receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor" OR "CAR-T" OR "CART" OR "CAR-T cell" OR "chimeric antigen receptor T cell"`（各 [Title/Abstract]） | 同じ語に展開される重複を削る（人の指示） |
| 6 | 本体 | P AND I（`"CAR-T cell"`・`"chimeric antigen receptor T cell"` も削った4語、採用） | 473 | 上の式のとおり | 33746596 の試行 #6・#10 で、`"CAR-T"`・`"chimeric antigen receptor"` がこの2語を含むことが分かったため。件数は変わらない |
| 7 | 本体（esearch） | #6 | 473（上限なし 929） | #6 と同じ | 採用の式の確認 |

query-builder は #3 の relevance 順上位のうち5件の抄録（PMID 36927623、36549969、36351654、30871629、36764323）を見て、足りない語は無いと判断した。

## 未決・気になる点
- γδT・CIK など T 細胞由来の CAR に専用の語（"CAR-CIK" など）が要るかは確かめていない
- 上位200件は relevance 順。473件のうち273件は取らない
