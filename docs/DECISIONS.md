# DECISIONS — 途中で決めたことと理由

## 2026-09-27 フェーズ1：settings と prompt log hook

- `UserPromptSubmit` hook は `.claude/hooks/log_prompt.py`（python3）。JSON を解析するのに jq に頼らないため。例外が出ても黙って exit 0（stdout は context に入り、exit 2 は指示文を拒否するため）
- subagent の上限は settings の `env` で `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=6`、`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`（既定はそれぞれ 20 と 3。どちらも project settings から設定できる変数）
- `.env`・鍵は `Read` / `Edit` の deny で止める（Write の path rule は参照されないため Edit で書く）。Bash の deny は補助で、境界にはならない（公式に明記）
- 参照した公式ドキュメント（2026-09-27）：
  - https://code.claude.com/docs/en/hooks
  - https://code.claude.com/docs/en/permissions
  - https://code.claude.com/docs/en/settings
  - https://code.claude.com/docs/en/settings-reference
  - https://code.claude.com/docs/en/env-vars
  - https://code.claude.com/docs/en/mcp

## 2026-09-27 フェーズ2：fetch_pubmed.py

- E-utilities へのリクエストはすべて POST にする。API key が URL に載らず、エラーメッセージにも出ないため。取得間隔はキーありで 0.11 秒、なしで 0.34 秒（NCBI の上限 10件/秒・3件/秒）
- 出版日の上限は `datetype=pdat`、`maxdate` で指定する。E-utilities は `mindate` と `maxdate` の両方を求めるので、下限の既定は 1800/01/01。実際の検索式は `query_translation` として search.json に残す
- 参照：https://www.ncbi.nlm.nih.gov/books/NBK25499/
- 2026-09-27 API key は `fetch_pubmed.py` が python-dotenv でリポジトリの `.env` から読み込む（シェルの環境変数が優先、値は表示・保存しない）。Claude 自身が `.env` を開く・表示するのは引き続き禁止（人が決定）
