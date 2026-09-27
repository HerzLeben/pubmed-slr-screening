# 検索式 — PMID 31190844

状態：案（人の承認待ち。承認まで `fetch_pubmed.py` で取得しない）
作成：2026-09-27、query-builder（2回目。人の指示で I を CAR AND CD19 に分けて作り直し）
上限：2019/05/06（`datetype=pdat`、`mindate=1800/01/01`）

## 式（演算子28。20を超えるのでコネクタでは式全体を試していない。全体の件数は esearch で確認）
```
("Hematologic Neoplasms"[Mesh] OR hematologic malignancy[tiab] OR hematologic malignancies[tiab] OR hematological malignancy[tiab] OR hematological malignancies[tiab] OR haematologic malignancy[tiab] OR haematologic malignancies[tiab] OR haematological malignancy[tiab] OR haematological malignancies[tiab] OR leukemia[tiab] OR leukaemia[tiab] OR lymphoma[tiab] OR myeloma[tiab])
AND
("Receptors, Chimeric Antigen"[Mesh] OR chimeric antigen receptor[tiab] OR chimeric antigen receptors[tiab] OR CAR T cells[tiab] OR CAR-T cell[tiab])
AND
("Antigens, CD19"[Mesh] OR CD19[tiab] OR CD19-specific[tiab] OR anti-CD19[tiab] OR tisagenlecleucel[tiab] OR CTL019[tiab] OR axicabtagene ciloleucel[tiab] OR KTE-C19[tiab] OR lisocabtagene maraleucel[tiab] OR lisocabtagene[tiab] OR JCAR017[tiab])
```

| 確認の経路 | 上限あり | 上限なし |
|---|---|---|
| コネクタ | 未試験（演算子28） | — |
| E-utilities esearch（retmax=0、2026-09-27） | 692 | 4,195 |

esearch の query_translation：
`("Hematologic Neoplasms"[MeSH Terms] OR "hematologic malignancy"[Title/Abstract] OR "hematologic malignancies"[Title/Abstract] OR "hematological malignancy"[Title/Abstract] OR "hematological malignancies"[Title/Abstract] OR "haematologic malignancy"[Title/Abstract] OR "haematologic malignancies"[Title/Abstract] OR "haematological malignancy"[Title/Abstract] OR "haematological malignancies"[Title/Abstract] OR "leukemia"[Title/Abstract] OR "leukaemia"[Title/Abstract] OR "lymphoma"[Title/Abstract] OR "myeloma"[Title/Abstract]) AND ("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "chimeric antigen receptors"[Title/Abstract] OR "car t cells"[Title/Abstract] OR "car t cell"[Title/Abstract]) AND ("antigens, cd19"[MeSH Terms] OR "CD19"[Title/Abstract] OR "CD19-specific"[Title/Abstract] OR "anti-CD19"[Title/Abstract] OR "tisagenlecleucel"[Title/Abstract] OR "CTL019"[Title/Abstract] OR "axicabtagene ciloleucel"[Title/Abstract] OR "KTE-C19"[Title/Abstract] OR "lisocabtagene maraleucel"[Title/Abstract] OR "lisocabtagene"[Title/Abstract] OR "JCAR017"[Title/Abstract]) AND 1800/01/01:2019/05/06[Date - Publication]`

## ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| P（血液がん） | 上の1行目（`*` を使わず語形を並べた） | 12 |
| I-CAR | `"Receptors, Chimeric Antigen"[Mesh] OR chimeric antigen receptor[tiab] OR chimeric antigen receptors[tiab] OR CAR T cells[tiab] OR CAR-T cell[tiab]` | 4 |
| I-CD19（CD19 の語 OR 製品名） | 上の3行目 | 10 |

R/R・評価項目・研究デザインはブロックにしない（人が決定）。

## 試行の記録（2回目、すべて date_from=1800/01/01、date_to=2019/05/06）
| # | 誰が | 式 | total_count | query_translation | 理由 |
|---|---|---|---|---|---|
| 1 | query-builder | P（13語） | 433,627 | 各語が個別に [MeSH Terms]・[Title/Abstract] に展開、重複なし（日付つき） | 初回 |
| 2 | query-builder | I-CAR 初版（9語：CAR T cell / CAR T cells / CAR-T cell / CAR-T cells / CAR T-cell / CAR-T-cell を含む） | 3,277 | `("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "chimeric antigen receptors"[Title/Abstract] OR "CAR-T-cell"[Title/Abstract] OR "car t cells"[Title/Abstract] OR "CAR-T-cell"[Title/Abstract] OR "car t cells"[Title/Abstract] OR "CAR-T-cell"[Title/Abstract] OR "CAR-T-cell"[Title/Abstract])` | 表記ゆれが2種類にしか展開されず重複 |
| 3 | query-builder | I-CAR（5語、採用） | 3,277 | `("receptors, chimeric antigen"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "chimeric antigen receptors"[Title/Abstract] OR "car t cells"[Title/Abstract] OR "car t cell"[Title/Abstract]) AND 1800/01/01:2019/05/06[Date - Publication]` | 重複を削った。件数は同じ |
| 4 | query-builder | I-CD19（11語） | 11,024 | `("antigens, cd19"[MeSH Terms] OR "CD19"[Title/Abstract] OR "CD19-specific"[Title/Abstract] OR "anti-CD19"[Title/Abstract] OR "tisagenlecleucel"[Title/Abstract] OR "CTL019"[Title/Abstract] OR "axicabtagene ciloleucel"[Title/Abstract] OR "KTE-C19"[Title/Abstract] OR "lisocabtagene maraleucel"[Title/Abstract] OR "lisocabtagene"[Title/Abstract] OR "JCAR017"[Title/Abstract]) AND 1800/01/01:2019/05/06[Date - Publication]` | 初回 |
| 5 | query-builder | I-CAR AND I-CD19 | 929 | #3 と #4 を AND（日付つき） | 上位の抄録5件（PMID 30810217、29676486、28382423、27322438、27139507）に足りない語は無かった |
| 6 | 本体 | I-CAR に `"CAR-T"[tiab]` を足して AND I-CD19 | 942 | I-CAR に `"CAR-T"[Title/Abstract]` が加わる以外は #5 と同じ | CAR-T だけ（cell なし）の表記の寄与を確認 |
| 7 | 本体（esearch） | 式全体（P AND I-CAR AND I-CD19） | 692（上限なし 4,195） | 上の esearch のとおり | コネクタで試せない全体の件数 |

## 1回目の案（採らなかった。I に CD19 と CAR の語が OR で並んでいた）
| # | 式 | total_count | 備考 |
|---|---|---|---|
| v1-1 | P（`hematologic malignanc*` など `*` を使用、9語） | 433,648 | |
| v1-2 | I（CAR-T・CD19・製品名を OR で10語） | 12,542 | |
| v1-3 | v1-1 AND v1-2 | 4,708（上限なし 16,685。esearch でも同数） | 上位5件はすべて BCMA の CAR-T で CD19 ではなかった |

## 未決・気になる点
- **I-CAR に `"CAR-T"[tiab]` が無い。** 33746596・37168849 の I には入っている。足すと I-CAR AND I-CD19 が 929→942（+13）。式全体での増分は確かめていない。入れると3本の CAR の語がそろう
- P に略語（ALL・CLL・DLBCL・NHL など）は入れていない（"ALL" は英単語と重なるため）
- 上位200件は relevance 順。692件のうち492件は取らない
