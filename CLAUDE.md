# CLAUDE.md — PubMed SLR screening（TrialMind の再実装）

このリポジトリは、系統的文献レビュー（SLR）の検索とスクリーニングを Claude Code の subagent で行うワークフロー。
原著：TrialMind（Wang et al., npj Digital Medicine 2025、コード MIT、ベンチマーク TrialReviewBench は Apache-2.0）。設計の正本は `docs/design.md`。

## 読む順序
1. この CLAUDE.md
2. `docs/requirements.md`（人が決めた要件と理由。迷ったらここが正）
3. `docs/design.md`（どう作るか。3章 権限と停止条件、4章 subagent・skill・hook・MCP）
4. `docs/DECISIONS.md`（途中で決めたことと理由）
requirements と design が食い違ったら requirements を優先する。どちらとも実装が食い違ったら、勝手に直さず止まって人に確認する。

## 作業フェーズと承認点（各フェーズの終わりで止まり、結果を見せる）
1. ハーネスの土台：`.claude/settings.json`（権限）、指示文を記録する hook
2. PubMed：人が公式コネクタ（`pubmed@life-sciences` プラグイン）を入れて再起動 → `/mcp` で確認。1回の検索で返る件数などの制限を試して HARNESS に記録。一括取得用の `scripts/fetch_pubmed.py`（E-utilities を直接呼ぶ。API key は環境変数、表示しない）を作る
3. ベンチマーク整形：TrialReviewBench の取得、行数と列の突き合わせ → 止まる
4. 適格基準：`/pico-to-criteria` で案を出す → 人が承認するまで screener を起動しない
5. 検索：query-builder が公式コネクタで Boolean query を試して直す → 検索式と検索期間の上限（元レビューの出版時点）を見せて人の承認まで止まる → `fetch_pubmed.py` で全ヒット（eval-1 は上位200件）と抄録を取得、Recall を出す
6. スクリーニング：1バッチ（20件）で試走 → 止まる → 全件を並列で → adjudicator → 要人判断リストを出して止まる
7. hook（引用の検査、PRISMA、subagent 起動の上限）
8. 評価：`/eval` は人だけが起動する

## やらないこと
- 全文の精読の最終判断、バイアスリスク評価、メタ解析の結論（臨床的な解釈を書かない）
- `.env`・API key を読む・表示する・コミットする
- 設計書に無い subagent の追加、同時起動数の上限（6）を超える起動
- 自作の MCP（PubMed は公式コネクタと一括取得スクリプトで足りる）
- PubMed 以外のデータベースの検索
- 画面のある Web アプリ（成果物は HTML のレポートまで）
- screener に CLAUDE.md や他の研究の判定を渡すこと（独立性を壊す）
- 推測で値を書くこと。判定の根拠は abstract の逐語引用だけ

## 判定の規則（requirements.md の要約。screener には agent 定義と skill で渡す）
- 基準ごとに 1（満たす）/ -1（満たさない）/ 0（不明）。0 は組み入れる側に倒す
- screener-a は基準を正順、screener-b は逆順で読む。互いの判定は見せない
- モデルはすべて Sonnet

## 記録の規則
- 節目で commit し tag を付ける：`snap/02-benchmark`、`snap/03-criteria-draft`（人が直す前）、`snap/04-criteria-approved`、`snap/05-query-approved`、`snap/06-no-subagent`、`snap/07-agents-v1`、`snap/08-first-parallel`、`snap/09-hook`、`snap/10-eval-1`、`snap/11-eval-2`、`snap/12-eval-2-notes`、`snap/13-prisma-eval`、`snap/14-positioning`、`snap/15-extraction-items`、`snap/16-eval-3-screened`、`snap/17-eval-3`、`snap/18-extraction`、`snap/19-extraction-eval`、`snap/20-public`
- 想定と違ったこと・詰まった点・人が決めたことは、その場で `docs/HARNESS.md` に日付つき1行
- 設計を変えたら `docs/DECISIONS.md` に1〜3行
- `docs/prompts/log.md`（hook が記録した指示文）は、フェーズごとの commit に含める
- 記事に使う結果（最初の試走、subagent なしの試走、最初の並列実行）は `docs/samples/` にコピーして commit（`results/` は gitignore）
- 公式仕様（hook・subagent・MCP・settings）は記憶でなく公式ドキュメントで確認し、見た URL を DECISIONS に残す

## コマンド
- 環境：`.venv`（`requirements.txt` は python-dotenv だけ、`requirements-dev.txt` は ruff・pytest）。設定ファイル（pyproject 等）は無い
- テスト：`python3 -m pytest -q`（ネットワーク不要）。1つだけ：`python3 -m pytest tests/test_rules.py -q`、`-k <名前>` で絞る
- lint：`ruff check .`
- テストは `sys.path` に `scripts/` を足して import する（パッケージ化していない）。hook のテストは `tests/test_hooks.py`

## データの流れ（どのスクリプトが何を読み書きするか。ファイルの形の正本は `docs/schema.md`）
レビューは PMID で呼ぶ（31190844、33746596、37168849）。`reviews/<rid>/` は commit する、`results/` は gitignore。
1. `scripts/build_bench.py` → `bench/reviews.jsonl`（答えの `included_pmids`。screener・PRISMA は読まない）
2. `/pico-to-criteria` → `reviews/<rid>/criteria.md`（人が承認）→ `scripts/criteria_to_json.py` → `criteria.json`
3. `scripts/fetch_pubmed.py` → `results/<rid>/{search,candidates}.json`。PubMed の relevance 順は再現しないので、上位リストは `reviews/<rid>/search.json` に固定し、`--from-search` で candidates を作り直す。`--all-hits` で全ヒットに広げる
4. `scripts/make_batches.py` → `results/batches/<rid>/{a,b}/batch_<nn>.json`（a は基準の正順、b は逆順）。既に判定済みのバッチと中身が変わるなら書かずに止まる
5. screener-a / screener-b（subagent）→ `results/screen/{a,b}/<rid>/batch_<nn>.json`
6. `scripts/adjudicate.py` が status を規則で決める → adjudicator（subagent）は needs_human の `summary` を書くだけ
7. 人の判断：HTML レポートから `results/human/<rid>.json` を保存
8. `scripts/prisma_record.py` → `results/prisma.json`、`scripts/build_report.py` → `results/report.html`、`scripts/eval_screening.py`（評価。`/eval` は人だけが起動）
9. 抽出（⑦、`docs/schema.md` 10章）：`scripts/fulltext_to_text.py`（`results/fulltext/<pmid>.xml` → `.txt`）→ `scripts/make_extraction_jobs.py` → `results/extraction/jobs/<rid>/<pmid>.json` → extractor（subagent）→ `results/extraction/out/<rid>/<pmid>.json` → 人が eval-3 のレポートで採点 → `results/extraction/human/<rid>.json` → `scripts/score_extraction.py` → `results/extraction/score.json`。Accuracy の計算は `score_extraction.metrics()` と `scripts/extraction_metrics.js`（レポートに埋め込む）で同じにする
- 判定の集計（`score`・`overall`）は `scripts/rules.py`、引用の照合は `scripts/quote_match.py` に1つだけ定義し、hook・adjudicate・report・eval が共有する。規則を変えるならここと `docs/schema.md` を一緒に直す
- eval-3 は別の系：`--run eval-3` で `reviews/<rid>/eval-3/`（未承認の `criteria_draft.md` から `draft_criteria_to_json.py`）と `results/eval-3/` を使い、screener-a だけ・adjudication と人の判断なし（`docs/eval/eval-3.md`）

## hook（`.claude/settings.json`、`.claude/hooks/`）
- `log_prompt.py`（UserPromptSubmit）：指示文を `docs/prompts/log.md` に追記。何も出力せず止めない
- `check_screen_output.py`（PreToolUse Write と SubagentStop）：screener・adjudicator の出力の形と逐語引用を検査し、exit 2 で差し戻す
- `limit_reads.py`（PreToolUse Read）：adjudicator が読めるのは自分の入力ファイルだけ（extractor は下の行）
- `agent_gate.py`（SubagentStart/Stop）：同時起動を6に制限（`.claude/state/running/` の marker）
- `check_extract_output.py`（PreToolUse Write と SubagentStop `extractor`）：extractor の出力の形・項目の順・逐語引用を検査し、exit 2 で差し戻す（SubagentStop は観察だけ）。`limit_reads.py` は extractor にも効き、自分の job とその全文の txt だけ読める
- `check_prisma.py`（PostToolUse Write|Edit）：`results/prisma.json` の件数の足し算を検査

## 用語と表記
- API のパラメータ・技術用語は英語のまま書く（`temperature`、`max_tokens`、subagent、few-shot、prompt caching）。コメント・docs も同じ
- コマンドは1つずつ実行する（`;` や `&&` で繋がない。権限のパターンに当たらなくなる）
