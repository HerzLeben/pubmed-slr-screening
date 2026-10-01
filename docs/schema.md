# 出力 JSON の形と判定の規則 — 第2作 HTML レポート（2026-09-27 v2）

> v2（2026-09-27 夜）：subagent を使わない試走の結果を受け、引用の照合を変更（Unicode の正規化をする、引用元をタイトルと抄録の両方にする）。E1 の定義を3章に追記。

screener・adjudicator・人の判断・HTML レポートが共有する「形」の正本。
指示7で作る `screening-rules` skill、出力を検査する hook（`.claude/hooks/check_screen_output.py`）、`scripts/build_report.py` はこの文書に合わせる。
リポジトリでは `docs/schema.md` に置く想定。

## 0. 決定事項（2026-09-27、Wataru 承認）

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| 1 | 除外基準の符号 | **全基準で 1＝組み入れ側、-1＝除外側、0＝不明**。E1 なら「二次文献ではない」が 1 | 合計スコアで順位付け（Recall@k）でき、規則が1本で済む。HTML は E の値を「該当せず／該当」と表示して読み違いを防ぐ |
| 2 | overall | **screener は出さない。基準の判定から規則で導く**（下の 5章） | adjudicator・評価・HTML で結論が必ず一致する |
| 3 | 抄録の本文 | **候補ファイル（`fetch_pubmed.py` の出力）が正**。screener の出力は PMID と判定・引用だけ | 出力が短い。抄録の写し間違いが起きない。hook の照合も同じファイルを見る |
| 4 | 人の判断 | **HTML で入力し、JSON をダウンロード**して `results/human/` に置く。置いて再生成すると最終リストに反映 | 静的 HTML のままで保存できる。記録がファイルで残る |
| 5 | UI の言語と見た目 | 日本語／EN の切り替え（Medicare アプリと同じ）。記事の撮影は EN。配色・ヘッダー・サイドバーは Medicare アプリのトークンに揃える | 連載で画面は英語 UI、アプリの見た目を揃える |
| 6 | status の決め方 | `scripts/adjudicate.py` が規則で決める。adjudicator（subagent）は needs_human の summary だけを書く | 規則で決まることはコード、判断が要ることだけエージェント |
| 7 | 引用の照合 | Unicode の正規化（NFKC、ハイフンの異体字、空白）をしてから照合。引用元は**タイトルと抄録**。言い換え・縮約は不可 | 試走で外れた9件中5件は字形の違いだけ。抄録の無い候補が約15%あり、タイトルが唯一の手がかり |

## 1. ファイルの置き場所

```
reviews/<review_pmid>/criteria.md        # 人が承認した基準（人が読む）
reviews/<review_pmid>/criteria.json      # 同じ内容の機械用（screener・hook・レポートが読む）
results/<review_pmid>/search.json        # 検索式・期間・取得日時・件数（既存の設計どおり）
results/<review_pmid>/candidates.json    # 候補と抄録（fetch_pubmed.py の出力）
results/batches/<review_pmid>/<a|b>/batch_<nn>.json  # screener への入力（scripts/make_batches.py。candidates の写しと、読む順に並べた基準）
results/screen/a/<review_pmid>/batch_<nn>.json
results/screen/b/<review_pmid>/batch_<nn>.json
results/adjudication/<review_pmid>.json
results/human/<review_pmid>.json         # HTML からダウンロードして置く
results/report.html                      # build_report.py の出力（1枚）
results/fulltext/<pmid>.txt              # 抽出の入力（fulltext_to_text.py。10章）
results/extraction/jobs/<review_pmid>/<pmid>.json   # extractor への入力（make_extraction_jobs.py。10章）
results/extraction/out/<review_pmid>/<pmid>.json    # extractor の出力（10章）
results/extraction/human/<review_pmid>.json         # 抽出の人の採点（レポートから保存）
```

`<nn>` は 2桁のゼロ埋め（`batch_01.json`）。

## 2. criteria.json

```json
{
  "review_pmid": "33746596",
  "review_title": "RRMM に対する CAR-T 療法の有効性と安全性",
  "criteria": [
    {"id": "I1", "type": "inclusion", "text": "対象が多発性骨髄腫の患者である"},
    {"id": "E1", "type": "exclusion", "text": "二次文献（総説・系統的レビュー・editorial・comment）である。原著データを含む letter は当たらない"}
  ]
}
```

- `id` は `I<n>` / `E<n>`。**数はレビューごとに違ってよい**（レポートは列を固定しない）
- 任意：`review_title_en`、各基準の `text_en`（レポートの EN 表示用。無ければ日本語を出す）
- 任意：各基準の `note`（criteria.md の「判定の補足」表の写し。人が決めた境界の扱い。screener は `text` と同じ重みで従う）
- 作り方：`scripts/criteria_to_json.py reviews/<review_pmid>`（criteria.md の表から機械的に写す）
- `text` は criteria.md の文言そのまま。E の `text` は「除外に当たる条件」を書く（判定値の向きは 3章の規則で決まる）
- criteria.md を承認したら、同じ commit で criteria.json を作る（criteria.md が正、json はその写し）

## 3. 判定値の意味

| 値 | inclusion（I） | exclusion（E） |
|---|---|---|
| 1 | 満たす | 該当しない（除外に当たらない） |
| -1 | 満たさない | 該当する（除外に当たる） |
| 0 | タイトル・抄録からは分からない | タイトル・抄録からは分からない |

- ±1 には**タイトルか抄録からの逐語引用が必須**。0 は `quote: null`（どこにも無い情報は引用できない）
- タイトルにも抄録にも無い情報は 0。推測で ±1 にしない
- **向きに注意**：criteria.md の除外基準は「該当するか」の問いで書かれているが、判定値は上の表のとおり「該当する＝-1」。試走（subagent なし）では逆向き（該当する＝1）で判定していた。screening-rules に明記する
- **E1 の範囲**：その文書自身の患者データを含まず、他の研究を紹介・論評するもの（review、editorial、comment、news、学会報告の紹介）は E1 に当たる（-1）。自分の原著データを含む学会抄録や letter は当たらない（1）

## 4. candidates.json（fetch_pubmed.py の出力）

```json
{
  "review_pmid": "33746596",
  "records": [
    {"pmid": "12345678", "rank": 1, "title": "...", "abstract": "...",
     "journal": "Blood", "year": 2020, "publication_types": ["Clinical Trial, Phase I"]}
  ]
}
```

- 必須：`pmid`（文字列）、`rank`（esearch の relevance 順、1始まり）、`title`、`abstract`（無ければ `""`）
- 任意：`journal`、`year`、`publication_types`
- 構造化抄録の見出し（`BACKGROUND:` など）は本文に含めたまま1本の文字列にする。**hook の照合もレポートのハイライトも、この `title` と `abstract` に対して行う**

## 5. screener の出力（screener-a / screener-b 共通）

```json
{
  "review_pmid": "33746596",
  "screener": "a",
  "batch": 1,
  "records": [
    {"pmid": "12345678",
     "criteria": [
       {"id": "I1", "verdict": 1, "quote": "patients with relapsed or refractory multiple myeloma"},
       {"id": "I2", "verdict": 0, "quote": null, "note": "前治療歴の記載なし"}
     ]}
  ]
}
```

- `records` はバッチの全件。`criteria` は**全基準を ID 順**（I1, I2, …, E1, …）に並べる。screener-b は逆順で読むが、出力は ID 順に揃える
- `quote`：±1 のとき必須。**タイトルか抄録の**連続した1か所をそのまま写す（省略記号・言い換え・縮約・つなぎ合わせ禁止）。どちらから取ったかは書かなくてよい（照合で分かる）。目安 300 字以内
- `note`：任意。1文まで（0 の理由など）
- **overall もスコアも書かない**（規則で導くため）

### 規則（`scripts/rules.py` 相当。build_report・adjudicator・eval で同じ）

- `score` ＝ 全基準の判定値の合計（順位付け用）
- `overall` ＝ -1 が1つでもあれば `exclude`、それ以外は `include`（0 は組み入れ側に倒す）

### 引用の照合（`scripts/quote_match.py`。hook とレポートで共有）

引用・タイトル・抄録の3つを同じ規則で正規化し、引用が**抄録かタイトルの中に**大文字小文字まで一致する連続した部分文字列として存在すれば「実在」。抄録を先に探し、無ければタイトルを探す。

正規化：
1. Unicode NFKC（1文字ずつ。合字 ﬁ → fi、全角 → 半角など）
2. ハイフン・ダッシュの異体字（U+2010〜2015、U+2212、U+FE58、U+FE63、U+FF0D）を `-` に。ソフトハイフン（U+00AD）とゼロ幅文字は消す
3. 空白の連続（NBSP・thin space を含む）を半角スペース1つに畳み、前後を削る

関数：`locate_quote(title, abstract, quote)` → `("abstract" | "title", (start, end))` か `None`。`quote_exists()` はその真偽。位置は正規化前の元の文字列の位置で返す（レポートのハイライト用）。

### hook が検査すること（`.claude/hooks/check_screen_output.py`）

**差し戻しは PreToolUse（matcher `Write`）で行う**（2026-09-27 変更。公式ドキュメント https://code.claude.com/docs/en/hooks の「Exit code 2 behavior per event」で、SubagentStop は "Exit code 2 isn't honored; the subagent has already finished"。PreToolUse は "Blocks the tool call" で、subagent は stderr を受け取って作業を続ける）。screener が `results/screen/<a|b>/<review>/batch_<nn>.json` を Write する直前に、書こうとしている内容を検査する：

1. JSON として読め、上の形である（`screener`・`review_pmid`・`batch` がパスと一致、`records` が `results/batches/<review>/<a|b>/batch_<nn>.json` の PMID とちょうど一致）
2. 各レコードに criteria.json の全基準がちょうど1回ずつ ID 順にあり、`verdict` が -1/0/1 の整数。`overall`・`score` を書いていない
3. ±1 に `quote` があり、`quote_match.quote_exists(title, abstract, quote)` が真（タイトルと抄録は candidates.json から引く）。0 の `quote` は null

不備は exit 2、stderr に「PMID・基準 ID・何が足りないか」を書いて Write を止める（subagent が直して書き直す）。同じ hook で、screener は自分の `results/screen/<a|b>/` 以外に、adjudicator は `results/adjudication/<review>.json` 以外に書けない。adjudicator の Write は、status・reasons・disagree_criteria・レコードの並びが変わっていないこと、needs_human に summary があることを検査する。

SubagentStop（matcher `screener-a|screener-b`）では、最後のメッセージに書かれた出力ファイルを同じ規則で検査し直し、不備があれば `systemMessage` で本体に知らせる（止められないので観察だけ。書かずに終わった screener を見つけるため）。

## 6. adjudication/<review_pmid>.json

```json
{
  "review_pmid": "33746596",
  "records": [
    {"pmid": "12345678",
     "status": "needs_human",
     "reasons": ["overall_disagree", "criterion_disagree"],
     "disagree_criteria": ["I2"],
     "summary": "I2 で A は不明（0）、B は前治療1ライン後のため R/R ではない（-1）と判定。結論が割れた"}
  ]
}
```

**2段で作る（2026-09-27 決定：案2）**

1. `scripts/adjudicate.py` が規則で `status`・`reasons`・`disagree_criteria` を決めて書く（判断の余地が無いのでコードに置く）
2. adjudicator（subagent）は `needs_human` のレコードだけを読み、`summary` を書き足す。**status・reasons は変えない**

`adjudicate.py` を再実行しても、status が変わらないレコードの summary は残す。

`status` の規則（上から最初に当たったもの）：

| 順 | 条件 | status | reasons に入れる |
|---|---|---|---|
| 1 | A か B の片方にしかレコードが無い | `needs_human` | `missing_record` |
| 2 | どちらかの ±1 の引用がタイトルにも抄録にも無い | `needs_human` | `quote_missing` |
| 3 | A と B の overall が違う | `needs_human` | `overall_disagree` |
| 4 | overall が一致 | `agreed_include` / `agreed_exclude` | 基準の判定が違えば `criterion_disagree`（参考、人には回さない） |

- `disagree_criteria`：A と B で判定値が違った基準の ID
- `summary`：needs_human では必須、agreed では任意。`summary_en` は任意（EN 表示用）
- **build_report.py は同じ規則で status を計算し直し**、ファイルの status と違えばレポートに警告を出す（subagent が status を書き換えた場合に見つかる）
- 理由：規則で決まることはコードに、判断が要ること（なぜ割れたかを人に説明する）だけを subagent に任せる

## 7. human/<review_pmid>.json（HTML から保存）

```json
{
  "review_pmid": "33746596",
  "saved_at": "2026-09-28T10:15:00+09:00",
  "records": [
    {"pmid": "12345678", "decision": "include", "note": "1ライン後でも難治例を含む。全文で確認"}
  ]
}
```

- `decision`：`include` / `exclude`。`note` は一言（要件の「理由を一言残す」）
- 対象は needs_human のものだけ。agreed を人が覆す機能は持たない（持たせるなら別に決める）

## 8. 最終の組み入れ候補

`agreed_include` ＋ 人が `include` にした needs_human。人の判断が無い needs_human は「未判断」として別に数え、最終リストには入れない（レポートに件数を出す）。

## 9. レポートが出す警告（レポート上部の「検査の警告」）

- candidates にあって screener の出力に無い PMID、その逆
- 基準の欠け・重複・未知の ID、範囲外の判定値
- ±1 なのに引用が無い／抄録に無い（hook をすり抜けたもの）
- adjudicator の status が規則と違う
- needs_human に `summary` が無い

## 10. 研究特性の抽出（指示書20）

### 入力：job（`scripts/make_extraction_jobs.py`）

```json
{
  "review_pmid": "33746596",
  "pmid": "30572922",
  "fulltext": "results/fulltext/30572922.txt",
  "items": ["<extraction_items.md の項目名、その順>"],
  "output": "results/extraction/out/33746596/30572922.json"
}
```

- 対象は `bench/extraction/<review>.jsonl` の `pmid` の列のうち、`results/fulltext/status.json` が `body` のもの（7組）。jsonl の値は読まない
- `fulltext` は `scripts/fulltext_to_text.py` が PMC の XML から作る：タイトル、抄録、本文の節（見出しは `## `）、すべての表（label、caption、行ごとにタブ区切り、脚注）、図の label と caption。参考文献と補足資料は入れない。長い段落は文の切れ目で 1,000字以下の行に分ける

### 出力（extractor）

```json
{
  "review_pmid": "33746596",
  "pmid": "30572922",
  "items": [
    {"name": "<項目名>", "value": "<値>", "quotes": ["<全文の文字列>"]},
    {"name": "<項目名>", "value": "記載なし", "quotes": []}
  ]
}
```

- `items` は job の `items` と同じ名前・同じ数・同じ順
- `value`：空でない文字列。全文に根拠が無ければ `"記載なし"`
- `quotes`：`"記載なし"` なら `[]`、それ以外は1つ以上。各引用は全文の txt に逐語で存在する（`scripts/quote_match.find_quote`。5章と同じ正規化で、改行・タブも空白1つに畳む）

### hook が検査すること（`.claude/hooks/check_extract_output.py`）

- PreToolUse（matcher `Write`）：`results/extraction/out/<review>/<pmid>.json` への書き込みで、上の形・パスとの一致・項目の過不足と順番・value と quotes の組み合わせ・引用の実在を検査し、不備は exit 2 で差し戻す。extractor が書けるのは job の `output` だけ
- SubagentStop（matcher `extractor`）：最後のメッセージに書かれた出力を同じ規則で検査し直し、不備や書かずに終わったことを `systemMessage` で本体に知らせる（観察だけ）
- `limit_reads.py`（PreToolUse Read）：extractor が読めるのは、最初に読んだ job ファイルとその `fulltext` だけ

### 採点（`scripts/score_extraction.py`、`results/extraction/human/<review>.json`）

- 分母：`results/extraction/jobs/` の全組 × job の項目（102）。答えは `bench/extraction/<review>.jsonl`、値は `results/extraction/out/`
- 規則：前後の空白と大文字・小文字だけそろえて完全一致 → 正解。それ以外は `"記載なし"` も含めて人が採点する（2026-10-01 人が決定）
- 参考値：`REFERENCE_EXCLUDE`（37168849/33495835、答えの不備の疑い）を除いた Accuracy も `score.json` の `reference_without` とレポートに並べる。主な値は 102項目のまま
- 人の採点は eval-3 のレポート（`build_report.py --run eval-3` の「抽出」の節）で付け、そこから保存する。規則で決まった項目は書かない（書いてあれば `score_extraction.py` が止まる）

```json
{
  "review_pmid": "<review>",
  "saved_at": "<ISO 8601>",
  "records": [
    {"pmid": "<pmid>", "item": "<項目名>", "correct": true}
  ]
}
```

- Accuracy＝正解 ÷ 採点済み。95% CI は Wilson（z＝1.96）。全体・レビューごと・組ごと。計算は `score_extraction.metrics()` と `scripts/extraction_metrics.js`（レポートに埋め込む）の2か所にあり、`tests/test_score_extraction.py` が同じ結果になることを node で確かめる
- `score_extraction.py` は結果を `results/extraction/score.json` に書く
