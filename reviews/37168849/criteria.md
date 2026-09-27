# 適格基準 — PMID 37168849

状態：承認済み（2026-09-27、人が承認）
Topic：Immunotherapy
元レビュー：Outcomes with chimeric antigen receptor t-cell therapy in relapsed or refractory acute myeloid leukemia: a systematic review and meta-analysis（Front Immunol 2023）

## 元の PICO
- P：Patients with relapsed/refractory acute myeloid leukemia (RR-AML)
- I：Chimeric antigen receptor T cell (CAR-T) therapy
- C：N/A
- O：Outcomes following CAR-T therapy in RR-AML such as complete and overall response rates, and the incidence of cytokine release syndrome, immune-effector cell associated neurotoxicity syndrome, and graft-versus-host disease

## 検索期間の上限（確定）
| 項目 | 値 |
|---|---|
| 出典 | PubMed esummary（取得日 2026-09-27） |
| pubdate | 2023 |
| epubdate | 2023 Apr 24 |
| sortpubdate | 2023/04/24 |
| history：received（参考） | 2023/01/27 |
| history：accepted | 2023/04/11 |
| history：entrez | 2023/05/11 |
| 抄録の検索終了日 | 記載なし（データベース名のみ：PubMed, Cochrane Library, Clinicaltrials.gov。「After screening 677 manuscripts, 13 studies were included」） |
| 上限（確定） | 2023/04/24（epubdate。レビューが公開された日で、これより後の論文は元レビューが見られなかった） |
| 絞り込みの日付項目 | E-utilities の `datetype=pdat`、`maxdate=2023/04/24` |

## 包含基準（すべて 1 または 0 なら組み入れ候補）
| ID | 問い | 出典 |
|---|---|---|
| I1 | 対象は acute myeloid leukemia（AML、急性骨髄性白血病）の患者か | P |
| I2 | 対象の AML は relapsed/refractory（再発・難治性）か | P |
| I3 | 対象は chimeric antigen receptor T cell（CAR-T）therapy を受けたか | I |
| I4 | O に挙げた評価項目（complete response rate、overall response rate、cytokine release syndrome、immune-effector cell associated neurotoxicity syndrome、graft-versus-host disease）のいずれか1つ以上の結果を報告しているか | O |

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
- 案どおり：RR-AML の結果が抄録で分けて書かれていない混合集団の試験は I1 を 0（組み入れる側）とする
- CAR-NK など T 細胞以外の CAR 細胞は I3 を満たさない（-1）。γδT・CIK など T 細胞由来の CAR は満たす（1）。境界は「CAR を載せた細胞が T 細胞かどうか」
