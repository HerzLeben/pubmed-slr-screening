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
5. 検索：query-builder が公式コネクタで Boolean query を試して直す → 検索式と検索期間の上限（元レビューの出版時点）を見せて人の承認まで止まる → `fetch_pubmed.py` で上位200件と抄録を取得、Recall を出す
6. スクリーニング：1バッチ（20件）で試走 → 止まる → 全件を並列で → adjudicator → 要人判断リストを出して止まる
7. hook（引用の検査、PRISMA、subagent 起動の上限）
8. 評価：`/eval` は人だけが起動する

## やらないこと
- 全文の精読の最終判断、バイアスリスク評価、メタ解析の結論（臨床的な解釈を書かない）
- `.env`・API key を読む・表示する・コミットする
- 設計書に無い subagent の追加、同時起動数の上限（6）を超える起動
- 自作の MCP（PubMed は公式コネクタと一括取得スクリプトで足りる）
- 画面のある Web アプリ（成果物は HTML のレポートまで）
- screener に CLAUDE.md や他の研究の判定を渡すこと（独立性を壊す）
- 推測で値を書くこと。判定の根拠は abstract の逐語引用だけ

## 判定の規則（requirements.md の要約。screener には agent 定義と skill で渡す）
- 基準ごとに 1（満たす）/ -1（満たさない）/ 0（不明）。0 は組み入れる側に倒す
- screener-a は基準を正順、screener-b は逆順で読む。互いの判定は見せない
- モデルはすべて Sonnet

## 記録の規則
- 節目で commit し tag を付ける：`snap/02-benchmark`、`snap/03-criteria-draft`（人が直す前）、`snap/04-criteria-approved`、`snap/05-query-approved`、`snap/06-no-subagent`、`snap/07-agents-v1`、`snap/08-first-parallel`、`snap/09-hook`、`snap/10-eval-1`、`snap/11-eval-2`、`snap/12-eval-2-notes`、`snap/13-prisma-eval`
- 想定と違ったこと・詰まった点・人が決めたことは、その場で `docs/HARNESS.md` に日付つき1行
- 設計を変えたら `docs/DECISIONS.md` に1〜3行
- `docs/prompts/log.md`（hook が記録した指示文）は、フェーズごとの commit に含める
- 記事に使う結果（最初の試走、subagent なしの試走、最初の並列実行）は `docs/samples/` にコピーして commit（`results/` は gitignore）
- 公式仕様（hook・subagent・MCP・settings）は記憶でなく公式ドキュメントで確認し、見た URL を DECISIONS に残す

## 用語と表記
- API のパラメータ・技術用語は英語のまま書く（`temperature`、`max_tokens`、subagent、few-shot、prompt caching）。コメント・docs も同じ
- コマンドは1つずつ実行する（`;` や `&&` で繋がない。権限のパターンに当たらなくなる）
