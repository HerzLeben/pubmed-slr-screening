# 検索式 — PMID 31190844（eval-3）

状態：人の承認なし（指示書19。query-builder の最終案をそのまま使う。人は動いたかだけを確かめる）
作成：2026-09-29、query-builder（1回。委任文は DECISIONS「2026-09-29 指示書19」のまま。1回目は PubMed の tool が無く起動前にエラー、これはそのやり直し）
上限：2019/05/06（`datetype=pdat`、`mindate=1800/01/01`）

以下は query-builder の返答を一字も変えずに写したもの。

---

## 検索式の案（PMID 31190844）
上限：2019/05/06（date_from=1800/01/01）
演算子の数：14（20以下。コネクタで試験済み。試行4と同一の式）

("Receptors, Chimeric Antigen"[MeSH] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR CART19[tiab] OR "CAR-modified"[tiab]) AND (CD19[tiab] OR "Antigens, CD19"[MeSH]) AND ("Hematologic Neoplasms"[MeSH] OR leukemia[tiab] OR lymphoma[tiab] OR myeloma[tiab] OR "hematologic malignancies"[tiab] OR "hematological malignancies"[tiab] OR "B-cell malignancies"[tiab])

`*` は使っていません。この式の total_count は 698 です。

### ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| I1 CAR-T | "Receptors, Chimeric Antigen"[MeSH] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR CART19[tiab] OR "CAR-modified"[tiab] | 5 |
| I2 CD19 | CD19[tiab] OR "Antigens, CD19"[MeSH] | 1 |
| P 血液腫瘍 | "Hematologic Neoplasms"[MeSH] OR leukemia[tiab] OR lymphoma[tiab] OR myeloma[tiab] OR "hematologic malignancies"[tiab] OR "hematological malignancies"[tiab] OR "B-cell malignancies"[tiab] | 6 |
| ブロック間 | I1 AND I2 AND P | 2 |

C と O は絞り込みに使っていません。autologous も式に入れていません。

### 試行の記録
すべて date_from=1800/01/01、date_to=2019/05/06 で実行しました。`query_translation` では、"CAR-T" と "CAR T" のどちらも "car t"[Title/Abstract] に展開されていました。

| # | 式（部分式） | total_count | query_translation | 直した理由 |
|---|---|---|---|---|
| 1 | (Receptors, Chimeric Antigen[MeSH] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR CD19[tiab]) AND (Hematologic Neoplasms[MeSH] OR leukemia[tiab] OR lymphoma[tiab] OR myeloma[tiab] OR "hematologic malignancies"[tiab] OR "hematological malignancies"[tiab]) | 4483 | MeSH とすべての [tiab] を展開。範囲は 1800/01/01:2019/05/06[Date - Publication] | 初回の試行。CD19 が I の OR に入っていて、CD19 だけの論文も拾うため件数が多すぎた |
| 2 | 試行1から myeloma[tiab] を除く | 4087 | 同上（myeloma なし） | myeloma の寄与を見るための試行。CD19 を CAR-T と AND にする必要があると判断した |
| 3 | (CAR 語 OR CART19[tiab]) AND (CD19[tiab] OR CD19[MeSH] OR "Antigens, CD19"[MeSH]) AND (P: myeloma なし) | 605 | CD19[MeSH] は展開結果から消えていた（"CD19"[Title/Abstract] OR "antigens, cd19"[MeSH Terms] のみ）。その他は入力どおり | CD19 を CAR とは別のブロックにして AND にした。件数は数百に下がった |
| 4（採用） | 上記の式全体 | 698 | 入力どおり展開（CAR-modified、myeloma、B-cell malignancies も [Title/Abstract]） | CAR-modified、myeloma、"B-cell malignancies" を足した。605 から 698 に増えた |

### 未確認・気になる点
- 試行1〜4の抄録は読んでいません。語は PICO の語句と一般的な同義語から選びました。
- 上位200件に候補が入るかは未確認です。relevance 順の上位を見ていません（試行3・4で返した PMID の先頭は 32117200、31997880 など）。
- 上限が 2019/05/06 なのに、上位に PMID 32117200 や 31997880 のような大きな番号が出ています。pdat が上限以前に付いているためだと思いますが、確認していません。
- "CAR T-cell" や "CD19-targeted" のような表記は "car t"[tiab] や CD19[tiab] の範囲外の書き方がありえます。CD19 を必須にしたので、CD19 と書かれていない論文は落ちます。
- 1回の試行で `query_translation` に出た "CAR-T" と "CAR T" の展開は同一でした。
- 臨床的な判断や組み入れの判断は書いていません。
