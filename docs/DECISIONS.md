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
- 2026-09-27 pico-to-criteria は `.claude/skills/pico-to-criteria/SKILL.md`。人も Claude も起動できる（`disable-model-invocation` は付けない）。PICO に無い基準は「PICO 外」と出典に書いて人に採否を委ねる。基準を起こすときは `included_pmids`（正解）を読まない
- 参照：https://code.claude.com/docs/en/skills（新しい skill は起動中のセッションにも反映されるが、`.claude/skills/` 自体をセッション開始後に作った場合は `/reload-skills` が要る）
- 2026-09-27 適格基準の承認（人が決定）：31190844 は比較群（C）を基準にしない（案の I5 を削除）。元レビューは単群の割合を統合しており、C を基準にすると方法と矛盾するため。included_pmids は見ずに、元レビューの抄録から判断した
- 2026-09-27 適格基準の承認（人が決定）：case report は3本とも除外しない（Recall を優先）。E1〜E3（PICO 外）は採用し、E1 には editorial・comment を含めるが、原著データを含む letter は E1 に当たらない
- 2026-09-27 検索期間の上限（人が決定）：3本とも元レビューの epubdate で確定（33746596：2021/02/18、31190844：2019/05/06、37168849：2023/04/24）。received は参考として criteria.md に残す。絞り込みは E-utilities の `datetype=pdat` と `maxdate`
- 2026-09-27 未決2点（人が決定）：31190844 は CD19 を標的の1つに含む CAR-T（CD19/CD22 などの二重標的）も I2 を満たす（Recall 優先）。37168849 は CAR-NK など T 細胞以外の CAR 細胞は I3 を満たさず、γδT・CIK など T 細胞由来の CAR は満たす（境界は CAR を載せた細胞が T 細胞かどうか）

## 2026-09-27 フェーズ2（完了）：PubMed コネクタの tool を allow に追加

- PubMed プラグインの7つの tool はすべて読み取り系なので、ワイルドカードを使わず名前で1つずつ `permissions.allow` に足した（ツールが増えても勝手に許可されないようにするため）
- コネクタは演算子20個・200件までなので、検索式の試行錯誤は部分式で行い、本検索と取得は `fetch_pubmed.py`（E-utilities）でする。役割の分け方（requirements 決定事項8）は変えない
- 上限の日付で絞るときは、コネクタでも `date_from` を必ず渡す（`date_to` だけだと絞り込みが無視される）
- 参照：https://code.claude.com/docs/en/permissions（MCP tool の permission rule の書き方）
