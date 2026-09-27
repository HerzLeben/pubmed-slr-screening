# 適格基準 — PMID 33746596

状態：承認済み（2026-09-27、人が承認）
Topic：Immunotherapy
元レビュー：Efficacy and Safety of CAR-T Therapy for Relapse or Refractory Multiple Myeloma: A systematic review and meta-analysis（Int J Med Sci 2021）

## 元の PICO
- P：Patients with relapsed/refractory multiple myeloma (RRMM)
- I：CAR-T therapy
- C：N/A
- O：Efficacy outcomes such as overall response rate, complete response rate, minimal residual disease (MRD) negativity rate, relapse rate, and median progression-free survival; Safety outcomes such as rates of grade 3-4 cytokine release syndrome (CRS) and neurologic toxicities (NT)

## 検索期間の上限（確定）
| 項目 | 値 |
|---|---|
| 出典 | PubMed esummary（取得日 2026-09-27） |
| pubdate | 2021 |
| epubdate | 2021 Feb 18 |
| sortpubdate | 2021/02/18 |
| history：received（参考） | 2020/04/08 |
| history：accepted | 2021/01/23 |
| history：entrez | 2021/03/22 |
| 抄録の検索終了日 | 記載なし（データベース名のみ：PubMed, EMBASE, Cochrane Central Register of Controlled Trials、ASH・EHA・ASCO の学会抄録、clinicaltrials.gov） |
| 上限（確定） | 2021/02/18（epubdate。レビューが公開された日で、これより後の論文は元レビューが見られなかった） |
| 絞り込みの日付項目 | E-utilities の `datetype=pdat`、`maxdate=2021/02/18` |

## 包含基準（すべて 1 または 0 なら組み入れ候補）
| ID | 問い | 出典 |
|---|---|---|
| I1 | 対象は multiple myeloma（多発性骨髄腫）の患者か | P |
| I2 | 対象の multiple myeloma は relapsed/refractory（再発・難治性）か | P |
| I3 | 対象は CAR-T therapy を受けたか | I |
| I4 | O に挙げた評価項目（overall response rate、complete response rate、MRD negativity rate、relapse rate、progression-free survival、grade 3-4 CRS、neurologic toxicities）のいずれか1つ以上の結果を報告しているか | O |

## 除外基準（どれか 1 なら除外）
| ID | 問い | 出典 |
|---|---|---|
| E1 | review・systematic review・meta-analysis・editorial・comment など、患者データを新たに報告しない出版の種類か（原著データを含む letter は E1 に当たらない） | PICO 外 |
| E2 | in vitro や動物モデルだけの前臨床研究で、患者のデータが無いか | PICO 外 |
| E3 | 結果を含まない試験計画（protocol・study design の紹介）だけか | PICO 外 |

## 決定事項（2026-09-27 人が承認）
- E1〜E3（PICO 外）は採用する。E1 には editorial・comment を含める。原著データを含む letter は E1 に当たらない
- case report は除外しない（Recall を優先するため）
- 検索の上限は epubdate で確定。received は参考として残す。絞り込みは E-utilities の `datetype=pdat`、`maxdate` に上の日付（`scripts/fetch_pubmed.py` の既定。実際の値は `results/<PMID>/search.json` に残る）
- 案どおり：RRMM の結果が抄録で分けて書かれていない混合集団の試験は I1 を 0（組み入れる側）とする。PubMed に載る学会抄録は除外しない
