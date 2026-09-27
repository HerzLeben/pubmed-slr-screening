# 適格基準 — PMID 31190844

状態：承認済み（2026-09-27、人が承認）
Topic：Immunotherapy
元レビュー：Survival outcomes and efficacy of autologous CD19 chimeric antigen receptor-T cell therapy in the patient with diagnosed hematological malignancies: a systematic review and meta-analysis（Ther Clin Risk Manag 2019）

## 元の PICO
- P：Patients with diagnosed hematological malignancies
- I：Autologous CD19 chimeric antigen receptor-T cell therapy
- C：Standard care or alternative treatments
- O：Survival outcomes and efficacy of the therapy

## 検索期間の上限（確定）
| 項目 | 値 |
|---|---|
| 出典 | PubMed esummary（取得日 2026-09-27） |
| pubdate | 2019 |
| epubdate | 2019 May 6 |
| sortpubdate | 2019/05/06 |
| history：received（参考） | 2019/02/05 |
| history：accepted | 2019/03/20 |
| history：entrez | 2019/06/14 |
| 抄録の検索終了日 | 記載なし（検索したデータベース名も抄録には無い） |
| 上限（確定） | 2019/05/06（epubdate。レビューが公開された日で、これより後の論文は元レビューが見られなかった） |
| 絞り込みの日付項目 | E-utilities の `datetype=pdat`、`maxdate=2019/05/06` |

## 包含基準（すべて 1 または 0 なら組み入れ候補）
| ID | 問い | 出典 |
|---|---|---|
| I1 | 対象は hematological malignancies（血液がん）と診断された患者か | P |
| I2 | 対象は CD19 を標的とする chimeric antigen receptor-T cell（CAR-T）therapy を受けたか | I |
| I3 | 使われた CAR-T cell は autologous（自家）か | I |
| I4 | survival outcomes（生存）または efficacy（有効性）の結果を1つ以上報告しているか | O |

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
- 比較群（PICO の C）は基準にしない（案の I5 を削除）。元レビューは単群の割合を統合しており、C を基準にすると方法と矛盾するため（included_pmids は見ずに、元レビューの抄録から判断）
- 案どおり：I3（autologous）は抄録に書かれなければ 0（組み入れる側）
- CD19 を標的の1つに含む CAR-T（CD19/CD22 などの二重標的）は I2 を満たす（1）。Recall を優先するため
