# 検索式 — PMID 37168849（eval-3）

状態：人の承認なし（指示書19。query-builder の最終案をそのまま使う。人は動いたかだけを確かめる）
作成：2026-09-29、query-builder（1回。委任文は DECISIONS「2026-09-29 指示書19」のまま。1回目は PubMed の tool が無く起動前にエラー、これはそのやり直し）
上限：2023/04/24（`datetype=pdat`、`mindate=1800/01/01`）

以下は query-builder の返答を一字も変えずに写したもの。

---

## 検索式の案（PMID 37168849）
上限：2023/04/24（date_from=1800/01/01）
演算子の数：12（20以下。コネクタで試験済み。試行4の式そのもの）

("Leukemia, Myeloid, Acute"[MeSH Terms] OR "acute myeloid leukemia"[tiab] OR "acute myeloid leukaemia"[tiab] OR "acute myelogenous leukemia"[tiab] OR AML[tiab]) AND ("Receptors, Chimeric Antigen"[MeSH Terms] OR "chimeric antigen receptor"[tiab] OR "chimeric antigen receptors"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-modified"[tiab] OR CART[tiab] OR "CAR T-cells"[tiab])

`*` は不使用。O・研究デザイン・R/R の語はブロックにしていない（Recall を優先）。

### ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| P（AML） | "Leukemia, Myeloid, Acute"[MeSH Terms] OR "acute myeloid leukemia"[tiab] OR "acute myeloid leukaemia"[tiab] OR "acute myelogenous leukemia"[tiab] OR AML[tiab] | 4 |
| I（CAR-T） | "Receptors, Chimeric Antigen"[MeSH Terms] OR "chimeric antigen receptor"[tiab] OR "chimeric antigen receptors"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-modified"[tiab] OR CART[tiab] OR "CAR T-cells"[tiab] | 7 |
| P AND I | 上記2つを AND で結合 | 1 |

### 試行の記録
全試行で date_from=1800/01/01、date_to=2023/04/24 を指定。

| # | 式（部分式） | total_count | query_translation | 直した理由 |
|---|---|---|---|---|
| 1 | P：MeSH OR "acute myeloid leukemia"[tiab] OR "acute myeloid leukaemia"[tiab] OR AML[tiab]（演算子3） | 88715 | 指定どおり（"leukemia, myeloid, acute"[MeSH Terms] と各 [Title/Abstract]）に日付範囲が AND で付いた | 初回 |
| 2 | I：Receptors, Chimeric Antigen[MeSH] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-T cell"[tiab] OR "CAR T-cell"[tiab]（演算子5） | 11462 | "CAR-T" と "CAR T" はどちらも "car t" に、"CAR-T cell" と "CAR T-cell" は "car t cell" に展開された（重複あり） | 初回 |
| 3 | 試行1 AND 試行2（演算子9） | 461 | 上記の展開を AND で結合 | P と I の結合を確認 |
| 4 | P に "acute myelogenous leukemia"[tiab] を追加。I は MeSH, "chimeric antigen receptor", "CAR-T", "CAR-modified", "chimeric antigen receptors", CART, "CAR T-cells"（"CAR T" なし。演算子11） | 484 | "CAR-T" は展開されず "CAR-T"[Title/Abstract] のまま | 同義語・表記ゆれを追加。重複していた "CAR-T cell" 系を整理 |
| 5（採用案） | 試行4に "CAR T"[tiab] を戻した式（演算子12）。max_results=200 で実行 | 484 | "CAR-T" と "CAR T" は両方とも "car t" に展開された。その他は指定どおり | "CAR T" の表記を落とさないため。件数は試行4と同じ |

### 未確認・気になる点
- 試行5は total_count が 484 で、上位200件に収まらない残り284件は eval-1 では取得されない。relevance 順の上位200件に候補が入るかは未検証。
- 上位200件の PMID に 38xxx や 37xxx が含まれる。date_to=2023/04/24 の絞り込みは [Date - Publication] で効いているが、エポック/オンライン先行日との差かもしれない。理由は未確認。
- 元レビュー自身（37168849）が結果に含まれている。抄録などは読んでおらず、式の調整にも使っていない。
- 上位の抄録は読んでおらず、語は PICO と一般的な同義語だけから選んだ。"CAR-NK"、"chimeric antigen receptor-modified T"（"CAR-modified" が拾うかは未検証）、"relapsed/refractory" の語、"Immunotherapy, Adoptive"[MeSH] は入れていない。
- "CART"[tiab] や "AML"[tiab] は略語で、AML 以外の意味（他の CART など）が混ざる可能性がある。ただし AND で絞っており、件数への影響は試行3と4の差（461と484）に含まれる。個別には未検証。
- 試行5の式は "CAR T-cells"[tiab] を含むが、"CAR T-cell"（単数）は入れていない。試行3の "CAR T"（"car t" 展開）が単数形の一部を拾う可能性はあるが、確認していない。
