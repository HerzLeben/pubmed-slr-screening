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

## 2026-09-27 フェーズ5：query-builder と fetch_pubmed.py

- query-builder の tools はコネクタの `search_articles` と `get_article_metadata` だけ。Read を持たせないので bench/reviews.jsonl（included_pmids）を読めない。PICO・承認済み基準・上限は本体が委任メッセージで渡す。`find_related_articles`・`get_full_text_article` は外す（元レビューの関連論文や参考文献から正解が漏れるため）
- 試行の記録（式・total_count・query_translation）は query-builder が返し、本体が `reviews/<PMID>/query.md` に書く（query-builder に Write を持たせない。設計の「PubMed MCP のみ」を守る）
- fetch_pubmed.py は esummary の pubdate・epubdate を逐語で候補ごとに保存し、上限との前後（within / after / straddles / none）を付ける。pubdate が年だけ（"2021"）など上限をまたぐものは after に数えず straddles とする。`--compare-maxdate` で別の上限での total_hits も search.json に残す
- 参照：https://code.claude.com/docs/en/sub-agents（`tools` の MCP tool 名の書き方、MCP tool の継承、agents ディレクトリの再起動条件）、https://www.ncbi.nlm.nih.gov/books/NBK25499/（esummary）

## 2026-09-27 フェーズ5：検索式の形（人が決定）

- 3本とも検索式は P AND I だけにする。relapsed/refractory・評価項目・研究デザインはブロックにせず、スクリーニングで判定する（1回目の 33746596 は R/R ブロックを入れ、37168849 は入れておらず、そろっていなかった）
- 31190844 の I は「(CAR の語) AND (CD19 の語 OR 製品名)」に分ける。製品名に lisocabtagene・JCAR017 を足す。`*` は使わず語形を並べる。1回目は CD19 と CAR の語が OR で並び、CD19 でない CAR-T（BCMA など）が上位を占めた
- 同じ語に展開される重複した語は削る。"CART"[tiab] は残す。試行の記録は `reviews/<PMID>/query.md`
- 2026-09-27（人が決定）：31190844 の I-CAR に `"CAR-T"[tiab]` を足す（3本の CAR の語をそろえる。692→695）。33746596 の P に単独の `"myeloma"[tiab]` を足す（418→436）。「P は multiple myeloma の語だけ」は人の指示ではなく、本体が委任メッセージに書き足したものだった
- 2026-09-27（人が承認）：3本の検索式と上限を承認（31190844：695件・2019/05/06、33746596：436件・2021/02/18、37168849：473件・2023/04/24。件数は esearch）
- 2026-09-27 fetch_pubmed.py は抄録を取る上位 n 件とは別に、esearch の全ヒットの PMID（relevance 順）を search.json の `all_pmids` に保存する。評価で「全ヒットでの Recall」と「上位200件での Recall」を分けて出すため（人の指示）
- 2026-09-27（人が決定）：上位200件は、この取得時点（2026-09-27 20:07）の relevance 順で固定する。Best Match は呼び出しで揺れ、取り直すと別の200件になるため。固定した search.json（`pmids`＝上位200件と並び、`all_pmids`、`retrieved_at`）は `reviews/<PMID>/search.json` に commit する。candidates.jsonl は抄録の著作権があるので commit しない（`results/` は .gitignore）
- 2026-09-27（人が決定）：fetch_pubmed.py は NCBI Bookshelf のレコード（PubmedBookArticle）も読む。`--from-search <search.json>` で、検索をせずに固定した PMID から candidates.jsonl を作り直す（手元の candidates.jsonl に無い PMID だけ efetch）。31190844 の欠けた4件はこれで足した

## 2026-09-27 指示6（subagent なしの試走）から（人が決定）

- tag の番号をそろえ直した：付いている tag（01〜05）は動かさず、まだ付けていないものを1つずつ後ろにずらす（`snap/06-no-subagent`、`snap/07-agents-v1`、`snap/08-first-parallel`、`snap/09-hook`、`snap/10-eval-1`）。`snap/05-query-approved` と `snap/05-no-subagent` の番号が重なっていたため
- 指示7で反映する：試走では E を「1＝除外に当たる」で判定した。docs/schema.md（指示7で入れる）では E は「1＝除外に当たらない」。criteria.json と screening-rules は schema に合わせる
- 指示7で反映する：引用の照合は Unicode の正規化（ハイフンの異体字・空白）をしてから行う。引用元はタイトルと抄録。言い換え・縮約は不可（試走では 16/101件が逐語でなく、うち4件が言い換え・縮約だった）
- 指示7で反映する：E1 は「その文書自身の患者データを含まず、他の研究を紹介・論評するもの（review・editorial・comment・news・学会報告の紹介）」。原著データを含む学会抄録や letter は当たらない（試走では、総説と明記されない解説を E1=0 とし、news（S041）と commentary（S059）で線引きが揺れた）

## 2026-09-27 指示7：subagent・skill・hook（snap/07-agents-v1、snap/09-hook）

- 「指示7で反映する」3点を反映した：E の向きは docs/schema.md（1＝除外に当たらない）で criteria.json・screening-rules に明記。引用の照合は Unicode 正規化のうえタイトルと抄録の両方（scripts/quote_match.py、Drive の v2 をそのままコピー。build_report.py もタイトルの引用を `src: "title"` で表示する作りだった）。E1 の定義は3本の criteria.md の表を書き換え、決定事項にも1行足した
- **差し戻しの hook を SubagentStop から PreToolUse（matcher `Write`）に移した**：公式ドキュメントの「Exit code 2 behavior per event」で SubagentStop は "Exit code 2 isn't honored; the subagent has already finished"、decision control も "does not support blocking"。design.md 4章・schema 5章の「SubagentStop の exit 2 で差し戻す」（2026-09-26 に確認したと書いていた）は今の仕様では成り立たない。PreToolUse の exit 2 は "Blocks the tool call" で、subagent は stderr を受け取って作業を続けるので、screener が出力を Write する直前に検査すれば差し戻しになる。SubagentStop（matcher `screener-a|screener-b`）には、書かれたファイルを検査し直して systemMessage で知らせる観察だけを残した。design.md・schema.md を直した
- 同時起動の上限は SubagentStart / SubagentStop の hook（`.claude/hooks/agent_gate.py`、セッションごとに動いている subagent を印のファイルで数える）で6までにした。SubagentStart は exit 2 で起動を止められる。Claude Code 自体の上限 `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=6`（settings.json の env、既に設定済み）と二重に掛ける。design.md の `PreToolUse`（`Agent`）案は使わない
- screener への入力は `results/batches/<review>/<a|b>/batch_<nn>.json`（`scripts/make_batches.py`、20件ずつ）。screener-b の基準の逆順はこのファイルの `criteria` の並びで渡す（指示で頼むだけにしない）。hook はこのファイルの PMID でバッチの全件が揃っているかを見る
- criteria.json は criteria.md から `scripts/criteria_to_json.py` で機械的に作る。決定事項にあった境界の扱い（CD19 の二重標的、CAR-NK、混合集団など）を criteria.md の「判定の補足」表に写し、criteria.json の基準ごとの `note` にした（omitClaudeMd の screener には criteria.md の決定事項が届かないため）
- fetch_pubmed.py の出力を candidates.jsonl から schema 4章の candidates.json（`{review_pmid, records}`、year は整数）に変えた。前の jsonl も読める
- adjudicator は Read・Write だけ（Edit なし）。adjudication ファイル全体を書き直すが、status・reasons・disagree_criteria・並びが変わっていないことを PreToolUse の hook が検査する
- 参照：https://code.claude.com/docs/en/hooks（Exit code 2 behavior per event、SubagentStop・SubagentStart の入力）、https://code.claude.com/docs/en/sub-agents（frontmatter の `skills`・`omitClaudeMd`（v2.1.271 以降、手元は v2.1.283）・`hooks`、ツール名 `Agent`、同時起動の上限 `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`）

## 2026-09-27 指示11のあと：adjudicator の読み取りを入力に限る

- adjudicator に `omitClaudeMd: true` を足し、Read を入力4種（`results/adjudication/<review>.json`、`results/screen/<a|b>/<review>/batch_<nn>.json`、`reviews/<review>/criteria.json`、`results/<review>/candidates.json`）に限った。指示8〜9b で 33746596 の adjudicator が docs/HARNESS.md や results/batches/ まで読んだ（ツール呼び出し43回）ため
- subagent の `tools` はツール名だけでパスを指定できない（`disallowedTools` の指定子もツールごと外す）。そこでパスの検査は PreToolUse（matcher `Read`）の hook `.claude/hooks/limit_reads.py` で行う。PreToolUse は subagent の中でも発火し `agent_type` を持つ。exit 2 で Read を止め、stderr が subagent に返る。screener の Read は今回は絞っていない
- 参照：https://code.claude.com/docs/en/sub-agents（frontmatter の表：`tools`・`disallowedTools`・`omitClaudeMd`）、https://code.claude.com/docs/en/hooks（common input fields の `agent_id`・`agent_type`、PreToolUse の exit 2 は "Blocks the tool call"）

## 2026-09-27 指示12：eval-2（全ヒットをスクリーニング、人が決定）

- 検索式は変えず、上位200件の枠だけを外して all_pmids（固定した全ヒット）をスクリーニングする。P のブロックは直さない（検索で落ちた3件は eval-1.md の記録のまま）
- 既に判定した200件（rank 1〜200、batch_01〜10）はそのまま使い、残りを all_pmids の並びで rank 201〜、batch_11〜 にする（`fetch_pubmed.py --from-search ... --all-hits`、`make_batches.py` は既存のバッチを変えない）
- 2026-09-29 eval_screening.py の「落ちた段」は、上位200件ではなく「スクリーニングした候補（candidates.json）に入っているか」で分ける。eval-1 と eval-2 で同じスクリプトを使い、eval-1 は `--results results/archive/eval-1` で再現する

## 2026-09-29 eval-2 の後（人が決定）：答えを見たあとで検索式・基準・規則を動かさない

- 31190844 の P のブロックは見直さない。検索に当たらなかった2件（22160384・24030379）は、検索の段の取りこぼしとして報告する。答えに合わせて検索式を直すと、Recall が答えを見て調整した数字になるため
- 37168849 の基準（CAR-NK は I3 を満たさない、前臨床は E2 で除外）は変えない。元のレビューの Selection criteria と照らすと criteria.md はそのとおりで、答えのほうが元のレビュー自身の基準から外れていた（eval-2.md「元のレビューとの照合」）。取りこぼし3件は分類して報告する
- 最終候補が多いこと（31190844 の145件）には、規則（0 は組み入れ側、I3 の注）を変えずに内訳を出して対処する（`scripts/breakdown_final.py`）。作業量は「スコア順に全文を読んだとき何件で組み入れ研究に届くか」で示す（上位96件）

## 2026-09-29 PRISMA の記録と /eval

- PRISMA の件数は `scripts/prisma_record.py` が数えて、和を確かめてから `results/prisma.json` に書く（Claude が手で写さない）。PostToolUse（matcher `Write|Edit`）の hook `.claude/hooks/check_prisma.py` は、手で直したときに同じ和（`prisma_record.check`）を検査する。PostToolUse の exit 2 は書き込みを止めず、stderr を Claude に見せる
- 除外理由は1件に1つ：`agreed_exclude` は criteria.json の並びで最初に A か B が -1 を付けた基準、人が除外した `needs_human` は `human`。スクリーニングしていない件数（eval-1 の枠の外）は `not_screened` として別に数え、除外に入れない
- skill の `eval` は `disable-model-invocation: true`（人だけが `/eval` で起動）。スクリプトは design の `eval/` ではなく、既にある `scripts/eval_screening.py`・`breakdown_final.py`・`prisma_record.py` を使い、記録は `docs/EVAL.md` ではなく `docs/eval/<名前>.md`（eval-1・eval-2 に合わせる）。commit と tag は人の指示を待つ
- 参照：https://code.claude.com/docs/en/hooks（Exit code 2 behavior per event の PostToolUse）、https://code.claude.com/docs/en/skills（`disable-model-invocation`、`$ARGUMENTS`、スキルのディレクトリの変更検知）
