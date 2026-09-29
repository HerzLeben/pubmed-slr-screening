# 検索式 — PMID 33746596（eval-3）

状態：人の承認なし（指示書19。query-builder の最終案をそのまま使う。人は動いたかだけを確かめる）
作成：2026-09-29、query-builder（1回。委任文は DECISIONS「2026-09-29 指示書19」のまま。1回目は PubMed の tool が無く起動前にエラー、これはそのやり直し）
上限：2021/02/18（`datetype=pdat`、`mindate=1800/01/01`）

以下は query-builder の返答を一字も変えずに写したもの。

---

## 検索式の案（PMID 33746596）
上限：2021/02/18（date_from=1800/01/01）
演算子の数：14（OR 13 個 + AND 1 個。20以下なのでコネクタで試験済み）

```
("Multiple Myeloma"[MeSH Terms] OR "multiple myeloma"[tiab] OR "myeloma"[tiab] OR RRMM[tiab]) AND ("Receptors, Chimeric Antigen"[MeSH Terms] OR "Immunotherapy, Adoptive"[MeSH Terms] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-T cell"[tiab] OR CART[tiab] OR "CAR T-cell"[tiab] OR "CAR-modified"[tiab] OR "BCMA"[tiab] OR "idecabtagene"[tiab] OR "ciltacabtagene"[tiab])
```

### ブロック
| ブロック | 部分式 | 演算子数 |
|---|---|---|
| P（多発性骨髄腫） | "Multiple Myeloma"[MeSH Terms] OR "multiple myeloma"[tiab] OR "myeloma"[tiab] OR RRMM[tiab] | 3 |
| I（CAR-T） | "Receptors, Chimeric Antigen"[MeSH Terms] OR "Immunotherapy, Adoptive"[MeSH Terms] OR "chimeric antigen receptor"[tiab] OR "CAR-T"[tiab] OR "CAR T"[tiab] OR "CAR-T cell"[tiab] OR CART[tiab] OR "CAR T-cell"[tiab] OR "CAR-modified"[tiab] OR "BCMA"[tiab] OR "idecabtagene"[tiab] OR "ciltacabtagene"[tiab] | 10 |
| ブロック間 | P AND I | 1 |

O・研究デザインはブロックにしていない。

### 試行の記録
すべての試行で date_from=1800/01/01、date_to=2021/02/18 を渡した。

| # | 式（部分式） | total_count | query_translation | 直した理由 |
|---|---|---|---|---|
| 1 | P ブロック単独 | 62964 | ("Multiple Myeloma"[MeSH Terms] OR "Multiple Myeloma"[Title/Abstract] OR "myeloma"[Title/Abstract] OR "RRMM"[Title/Abstract]) AND 1800/01/01:2021/02/18[Date - Publication] | 初回の確認。ATM による余計な展開はなかった |
| 2 | I ブロック単独 | 22778 | ("receptors, chimeric antigen"[MeSH Terms] OR "immunotherapy, adoptive"[MeSH Terms] OR "chimeric antigen receptor"[Title/Abstract] OR "car t"[Title/Abstract] OR "car t"[Title/Abstract] OR "car t cell"[Title/Abstract] OR "CART"[Title/Abstract] OR "car t cell"[Title/Abstract] OR "CAR-modified"[Title/Abstract] OR "BCMA"[Title/Abstract] OR "idecabtagene"[Title/Abstract] OR "ciltacabtagene"[Title/Abstract]) AND 1800/01/01:2021/02/18[Date - Publication] | 初回の確認。ハイフンは空白に正規化され、"CAR-T" と "CAR T" が同一語になった |
| 3 | P AND I（案の式全体） | 683 | P と I の各展開を AND で結び、末尾に AND 1800/01/01:2021/02/18[Date - Publication] が付いた | 試行1・2の式をそのまま AND で結んだ。件数は数百で、数千を大きく超える規模ではない |

### 未確認・気になる点
- 予備検索の上位の抄録は読んでいない。語の追加と削除の調整は行っていない（試行は3回のみ）。
- 上位200件に候補が入るかどうかは未確認。件数は683。
- "CAR-T" と "CAR T" は PubMed 側で同じ語に正規化されるため、重複している。演算子の余裕は 6 個ある。
- "Immunotherapy, Adoptive"[MeSH Terms] は CAR-T 以外の養子免疫療法（TIL、NK 細胞など）も拾う。
- BCMA[tiab] は抗体薬物複合体や二重特異性抗体も拾うので、件数が増える可能性がある。
- 語の追加候補は、"chimeric antigen receptor T" や "CAR-T" の別表記、LCAR-B38M、bb2121、"cilta-cel"、"ide-cel" などの製品名・コード名。試していない。
- 期間指定は `[Date - Publication]` で、2021/02/18 以前の電子先行公開の扱いは確認していない。
