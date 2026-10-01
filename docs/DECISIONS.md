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

## 2026-09-29 指示書17：位置づけ（人が決定）

- requirements.md を改訂した：1章を「一次スクリーニングを Claude Code でどこまで肩代わりできるかを公開ベンチマークで確かめる。教育と手法（論文）の検証用で、業務の一次スクリーニングの代わりにはしない」にし、利用者像を「SLR の手法を学ぶ人と、LLM スクリーニングの論文を自分で確かめたい人」に、#7 を「eval-1 は上位200件、eval-2 で全ヒット」に更新、「やらないこと」に PubMed 以外のデータベースの検索と業務の代わりとしての利用を足した。実際の SLR は PubMed 以外も検索する必要があるため
- 検索の網羅性は2種類に分けて書く：(a) 検索式の限界（PubMed にあるのに式に当たらない。検索 Recall に表れる）と、(b) データベースの限界（PubMed に無い論文）。(b) はベンチマークの答えが PMID の一覧なので、この評価では測れない（eval-2.md「検索の網羅性」）

## 2026-09-29 指示書18：抽出の準備（人が決定）

- 原著の3つの作業（検索・スクリーニング・抽出）をなぞり、研究特性の抽出を足す（requirements 2章 #1・#11）。対象は答えのある 33746596・37168849 の2本、全文は PMC の efetch で本文が取れる研究だけ（原著の限界 "restricted to publicly available sources from PubMed Central"）。結果の統合はしない
- 答えの食い違い：33746596 の抽出の答えは 30830874（29669947 の Published Erratum）で、included_pmids は 29669947。抽出の評価は抽出の答えの PMID で行う。29669947 の全文も確かめて status.json に書いた（どちらも PMC あり・本文なし）
- 項目は答えの列名をそのまま使い、説明は付けない（原著 Methods "Each table's column names served as input field descriptions for TrialMind."）
- 原著の Accuracy は人の採点（"we enlisted three annotators who manually compared them against the data reported in the original tables"）。完全一致（前後の空白と大文字・小文字だけそろえる）は規則で正解、それ以外は人が1件ずつ採点する（`results/extraction/human/`）。分母は本文が取れた7組の全項目、「記載なし」は答えに値があれば不正解。この採点は原著の採点をなぞるためのもので、抽出の流れ（extractor）には人の判断を入れない。原著との違い（採点者 3人→1人、全文を手で集めた→PMC の本文だけ）は eval とレポートに書く
- 参照：https://arxiv.org/html/2406.17755（Methods の "Data extraction and result extraction"、Discussion の限界の4つ目）

## 2026-09-29 指示書19：人の介入を外した検索式（eval-3、人が決定）

- 1章で検索式に人の手（語の追加、ブロックの形の指示）が入っていたので、3本とも query-builder に人の手なしで作り直させる（案2）。PICO は `bench/reviews.jsonl` が raw と完全一致し、人の指示は検索式の形と語だけで PICO には触れていなかった（HARNESS）
- query-builder に渡すのは PICO（ベンチマークの値をそのまま）、検索期間の上限、書き方の制約（`*` を使わない、演算子20以下）だけ。適格基準は渡さない。レビューの PMID は agent 定義の「元レビュー自身を検索式の調整に使わない」のために渡す（条件ではなく識別子）。本体は条件を書き足さない。agent 定義は変えない
- 1本につき1回だけ走らせ、最終案を中身にかかわらずそのまま使う。エラーで止まったときだけやり直す（HARNESS に書く）。人は検索式を承認しない（動いたかの確認だけ）。より良い案を選ぶための作り直しはしない。本体は委任文に条件を書き足さない
- 置き場所：eval-1・eval-2 の `reviews/<PMID>/query.md`・`search.json` は上書きしない。eval-3 は `reviews/<PMID>/eval-3/`（query.md・search.json）、候補と抄録は `results/eval-3/<PMID>/`（`fetch_pubmed.py --out-dir results/eval-3`）
- 委任文（3本とも同じ形。<...> だけ差し替える）：

```
レビュー PMID <PMID> の PubMed 検索式の案を1本作ってください。

PICO：
P: <PICO.P>
I: <PICO.I>
C: <PICO.C>
O: <PICO.O>

検索期間の上限：<YYYY/MM/DD>（date_from=1800/01/01）

書き方の制約：
- `*`（前方一致）を使わない
- 式全体の演算子（AND・OR・NOT）は合わせて20個以下
```

  上限は 33746596：2021/02/18、31190844：2019/05/06、37168849：2023/04/24（元のレビューの出版日。eval-2 と同じ）

## 2026-09-29 指示書19 2章：基準は案のまま（人が決定）

- `reviews/<PMID>/criteria_draft.md` は `snap/03-criteria-draft` の criteria.md そのまま。screener に渡す形は `scripts/draft_criteria_to_json.py` が `reviews/<PMID>/eval-3/criteria.json` に出す。包含・除外の表の「問い」を一字も変えずに写す（eval-2 と同じく、出典の列は screener に渡さない）
- 31190844 の I5（比較群）は表のまま使う（出典の欄の「採否は人が決める。下記参照」も criteria_draft.md では変えない）。単群試験は I5 で -1 になり除外される見込み。eval-3 で原著と並べるのは I5 を含む値だけ。参考として、同じ判定から I5 を外して合計を取り直した Recall@20・@50 を eval-3.md に1行だけ載せる（スクリーニングはやり直さない。「参考。原著との比較には使わない」と明記）
- 「人に決めてほしい点」の節は screener に渡さない。案の中で既に決めてある扱いだけを、その基準の note として残す（文言は案に近いまま）：

| レビュー | 残した（note） | 外した（人への問い） |
|---|---|---|
| 33746596 | I1：混合集団で RRMM の結果が分かれていなければ I1 を 0。E1：PubMed に載る学会抄録は除外しない、case report は除外しない | E1〜E3 を採るか、上限を epubdate か received か |
| 31190844 | E1：case report は除外しない | I5 を採るか（案は「承認で外すかを決める」で、決めていない）、I3 は 0 が多くなる見込み（見込みで扱いではない）、CD19/CD22 などを I2 で 1 とするか、E1〜E3 を採るか、上限 |
| 37168849 | I1：AML と他の疾患をまとめた試験で RR-AML の結果が分かれていなければ I1 を 0。E1：case report は除外しない | E1〜E3 を採るか、CAR-NK などを I3 で -1 とするか、上限 |

## 2026-09-29 指示書19 3〜4章：候補とスクリーニングの置き場所

- 検索は query-builder の最終案（3本とも1回）を `fetch_pubmed.py --out-dir results/eval-3` で実行し、all_pmids を `reviews/<PMID>/eval-3/search.json` に固定した（683／698／484件）
- 母集団は2通り。「全ヒット」は all_pmids。「原著と同じ作り方」は、全ヒットに、新しい検索で拾えなかった答えの PMID を足したもの。数え直した結果は 37168849 の 28864289 の1件だけ（指示書の決め打ちの3件のうち、31190844 の 22160384・24030379 は新しい検索で拾えた）。足した PMID は `fetch_pubmed.py --add-pmid` で候補の最後（最後のバッチ）に入れ、search.json の `added_pmids` に記録する。screener のバッチには足したかどうかを書かない
- 原著の引用（arXiv HTML 版、Results の "TrialMind enhances literature screening and ranking"）："A candidate set of 2,000 citations is created by combining the actual studies included in the review with additional citations retrieved during the search but not included in the review." 参照：https://arxiv.org/html/2406.17755
- スクリーニングの置き場所は `results/eval-3/`（batches・screen・`<PMID>/candidates.json`）。hook（check_screen_output.py）と make_batches.py がパスで入力を選ぶため、パスの `results/eval-3/` で run を見分け、eval-3 は `reviews/<PMID>/eval-3/criteria.json` で検査する。検査の中身は eval-2 と同じ。eval-3 は screener-a だけなので、バッチも a の分だけ作る（`make_batches.py --run eval-3`）
- 2026-09-30 人の決定：31190844 の I5 は直さずに全件へ進む。試走で、単群と推測できるが明記の無い抄録（27111235）の I5 は 0 だった。-1 には逐語引用が要り、0 は組み入れる側に倒すため、I5 で除外されるのは単群を明記した抄録だけになる。これを eval-3 の結果として記録する（基準は事前に決めて変えない）

## 2026-09-30 eval-3 の評価と範囲（人が決定）

- 抽出（requirements 2章 #1 の ⑦）は今回の範囲から外した。完成は ①〜⑥。extractor・採点・承認点6と7は行わない。準備（`bench/extraction/`、`fetch_pmc.py`、extraction_items.md）は残す
- 原著の値は arXiv 2406.17755（HTML 版）のまま使い、npj Digital Medicine 掲載版とは照合しない。eval-3.md とレポートに「arXiv 版の値」と明記する
- eval-3 の評価は `eval_screening.py --run eval-3`、レポートは `build_report.py --run eval-3`（`results/eval-3/report.html`。`report_template.html` の head と CSS に、`report_eval3_body.html` の本文をつなぐ。eval-1・eval-2 の report.html は触らない）。「原著と同じ作り方」の足した PMID は、候補のうち all_pmids に無いものとして数え、`results/eval-3/<PMID>/search.json` の `added_pmids` と一致することを検査する
- Recall@k の主な値は分母を「母集団に入った組み入れ研究」とし、3本の平均と合算を並べる（原著の値が topic 内の平均か合算かは本文から読み取れないため、両方を出す）
- tag：eval-3 の評価と docs の commit に `snap/17-eval-3`

## 2026-10-01 指示書20：研究特性の抽出（人が決定）

- 2026-09-30 の「⑦ は今回の範囲外」を取り消し、⑦ を行う。範囲・対象（33746596・37168849）・全文は PMC だけ・採点のしかた（完全一致は規則、残りは人）は「2026-09-29 指示書18」のまま
- 機能の追加は抽出で最後にする。抽出のあとで直したい所が出ても実装せず、HARNESS に「やらなかったこと」として1行書く
- 抽出の流れには人の判断を入れない。人がするのは試走の動作確認（承認点6）と、完全一致しなかった値の採点（承認点7）だけ。項目・答え・出力を人が直さない
- 分母は本文が取れた7組の全項目で 102（33746596 は 3組×14項目、37168849 は 4組×15項目）
- 比べる原著の値（arXiv HTML 版、Results の study characteristics extraction。2026-10-01 に原文の HTML で逐語を確かめた）：
  - "it achieved an accuracy of ACC=0.78 (95% confidence interval (CI) = 0.75–0.81) in the Immunotherapy topic"。ほかのトピックは 0.77・0.72・0.83（全体で 0.72–0.83）
  - "Our dataset comprises 1,334 target data points, including 696 on study design, 353 on population features, and 285 on results." → **原著の 0.78 は研究デザイン・患者背景・結果の3種を合わせた値**。Immunotherapy の種類別は study design 0.95（0.92–0.96）、population 0.74（0.67–0.80）、results 0.42（0.36–0.49）。こちらの項目は Table 1 の列（デザインと患者背景）だけなので、eval-3.md では全体の 0.78 と並べ、種類別の値も注記する
  - 入力："use the full content of the study documents in PDF or XML formats as inputs"。出典："each output is linked to the sources for manual inspection"（Results 冒頭の概要）、"each output can be cross-checked by the linked original sources"（抽出の節）
  - 採点者："we enlisted three annotators who manually compared them against the data reported in the original tables"（Methods）
  - 95% CI の出し方は本文に書かれていない（Methods・Results・図の説明を確かめた）→ こちらは Wilson の区間を使う
  - 原著の限界の例：付録にしか無い値は取れない（"it failed to extract data outside the study's main content, such as in appendices, which were not included in the inputs"）
  - 参照：https://arxiv.org/html/2406.17755
- 全文のテキスト化（`scripts/fulltext_to_text.py`）：タイトル、抄録、`<body>` の節（見出しは `## `）、**すべての `<table-wrap>`（`<body>` の外の `<floats-group>` なども）**、`<fig>` の label と caption を入れる。参考文献と補足資料は入れない（補足資料は取りに行かず件数だけ記録）。理由：原著は全文の PDF か XML をそのまま入力にしている。PMC の XML では表の多くが `<body>` の外にあり（6本の表10枚のうち `<body>` の中は4枚）、`<body>` だけでは患者背景の表が落ちる
- extraction-rules skill は `user-invocable: false` だけを付ける。`disable-model-invocation: true` は subagent への preload も止めるため付けられない（公式："Also prevents the skill from being preloaded into subagents"）。つまりモデルが呼ぶことは止められないが、skill に答えは書いていないので漏れは無い。参照：https://code.claude.com/docs/en/skills（frontmatter reference）
- テキスト化の細部：数字の直後の上付きの数字は `^` を付ける（`50×10<sup>6</sup>` → `50×10^6`。付けないと用量が「106」に読める）。語の直後の上付き（引用番号）や記号の上付き（脚注の †）はそのまま。補足資料しかない節は見出しも出さない。表と図は本文のあとに文書の順でまとめて書く（`<body>` の中の表を二重に書かない）。件数は `results/fulltext/text_summary.json`
- 長い段落は文の切れ目で 1,000字以下の行に分ける（2,000字を超える段落が5本にあった。Read tool で長い行が切れると、その先が extractor に届かない）。図の説明も同じ。引用の照合は改行を空白1つに畳むので、行をまたぐ引用も通る
- extractor（`.claude/agents/extractor.md`）は screener-a と同じ書き方（`tools: Read, Write`、`model: sonnet`、`omitClaudeMd: true`、`skills: [extraction-rules]`）。job は `scripts/make_extraction_jobs.py` が作り、jsonl からは `pmid` の列だけを読む（7組・102項目）。skill・agent 定義・委任文に答えの値や答えの書き方の例は書かない（出力の例は `<値>` などの記号だけ）
- hook：出力の検査は `check_extract_output.py`（`check_screen_output.py` とは別のファイル。PreToolUse Write で差し戻し、SubagentStop matcher `extractor` は観察だけ）。読める範囲は `limit_reads.py`。hook からは「どの job を渡された extractor か」が見えないので、**最初に読んだ job を agent_id に結び付け**（`.claude/state/extract_reads/`）、ほかの job と、その job の fulltext 以外の txt を止める
- 委任文（7組とも同じ形。<...> だけ差し替える。本体は条件を書き足さない）：

```
抽出の job を1つ処理してください。

job：results/extraction/jobs/<review>/<pmid>.json
```
- 採点の基準（2026-10-01 人が決定。採点の途中で変えない。レポートの画面の上にも表示する）：①意味が同じなら正解（表記、単位の書き方、語順の違いは問わない）②答えより詳しいだけなら正解。答えの一部が欠けていれば不正解 ③答えが分類（地域など）で、抽出が元の値の場合、その値から分類が一意に決まれば正解 ④「記載なし」は、答えに値があれば不正解（規則で決まる）
- 規則での採点（`scripts/score_extraction.py`）：前後の空白と大文字・小文字だけそろえた完全一致 → 正解、「記載なし」で答えに値がある → 不正解、残りは人。102項目のうち規則で正解6、記載なしで不正解17、人の採点79
- 人の採点の画面は eval-3 のレポートの「抽出」の節に置く（人が決定）。Accuracy は採点のたびに画面で数え直す。計算は `extraction_metrics.js` 1つをレポートに埋め込み、Python 側（`score_extraction.metrics`）と同じ結果になることを node のテストで確かめる。引用は全文の前後160字と一緒に出す（原著の "linked to the sources for manual inspection"）
- 保存は Chrome の File System Access API（`showDirectoryPicker`）で `results/extraction/human/<review>.json` に直接書く。選んだフォルダの handle は IndexedDB に残し、2回目からは選ばない。使えないブラウザでは eval-2 と同じダウンロードに落とす。下書きは localStorage（`slr-extract-human-<review>`）。file:// で `isSecureContext` が true、`showDirectoryPicker` が関数であることは headless Chrome 154 で確かめた（フォルダを選ぶ操作は人のクリックが要るので、最初の保存で人が確かめる）。参照：https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker
- **2026-10-01 人が決定（採点の前）：規則で決めるのは完全一致の正解だけにする。**「記載なし」は答えに値があっても規則で不正解にせず、すべて人の採点に回す（17件）。理由：答えが "not reported" / "Not available" のもの（33746596×30396908 の BCMA positivity、37168849 の 33495835 の Prior Therapies、34034795 の Manufacturing time と Transduction Mechanism）は基準①で正解になる。表記の一覧で拾う規則は作らない（答えを見たあとで規則を作ることになるため）。採点の基準④を「記載なしは、答えも記載が無いことを表していれば正解、値があれば不正解」に直した。これで規則で正解6、人の採点96（上の「記載なしで不正解17、人の採点79」は取り消し）
- **2026-10-01 人が決定：37168849 × 33495835 の答えは直さず、そのまま採点する。** この論文は in vitro で患者がいないのに、答えには年齢・性別があり、Study Design が Clinical Trial、Costimulatory Domain が薬剤名（Cytarabine & Decitabine…）になっている。eval-3.md に「答えの不備の疑い」として書き、この組を除いた Accuracy を参考値として並べる（主な値は102項目のまま。`score_extraction.REFERENCE_EXCLUDE`）
- 抽出の評価（6.3）：保存された `results/extraction/human/*.json`（96件）を `score_extraction.py` で読み、レポートに埋め込んだ JS（`extraction_metrics.js`）の値と全項目が一致することを確かめた。Accuracy は全体 0.735（95% CI 0.642–0.811、75/102）、33746596 0.786、37168849 0.700。33495835 を除く参考 0.759。CI は Wilson（原著は出し方を書いていない。上の行）

## 2026-10-01 指示書21（公開の準備）

- 人が決定（Wataru）：GitHub で公開する（連載の読者が辿るため。業務の道具の配布ではない）。位置づけは「教育と手法の検証用」のまま。コードは MIT（著作権者 HerzLeben Inc.、2026）、`bench/` の整形済みファイルは TrialReviewBench（Apache-2.0）から作ったので NOTICE に出典。`snap/*` の tag は残す。`docs/prompts/log.md` は個人の情報とローカルの情報を消して公開する（2026-10-01、AskUserQuestion で確認）
- 履歴の書き換え（理由：log.md の過去の版に、メールアドレス入りの Google Drive のパス、ホームのパス、作業ファイルのパス、IDE で `.env` を開いた記録が残っていた）：`git filter-repo --file-info-callback` で **全履歴の `docs/prompts/log.md` だけ** に `scripts/redact_log.py` の置き換えを掛けた。ほかのファイルは対象外（規則を書いた redact_log.py 自身とテストの作り物の文字列を壊さないため。ほかのファイルの履歴に個人の情報が無いことは確かめた）
- 人が決定：commit の author・committer のアドレス（43 commit すべて会社のアドレス）も、同じ書き換えで mailmap により `254887246+HerzLeben@users.noreply.github.com` に差し替えた。これからの commit も同じ（`git config user.email`）
- 書き換えは auto mode の安全チェックで止められたので、人がターミナルで打った。前に `~/dev/pubmed-slr-screening.backup-20261001` に `git clone --mirror` で残した
- 2026-10-01 4章の確認と README の手順：取得の URL は Hugging Face の resolve/main（記録した revision は 6dfc322）。清潔な clone で bench/ が再現できることを確かめた

## 2026-10-01 見本の画面の公開（人が決定、Wataru）

- 「機能の追加は抽出で最後」（指示書20 0章）を、この1件だけ取り消す。理由：読者が clone して流れを回すのはハードルが高すぎる。画面は最初から見せておく必要がある
- eval-2（`results/report.html`、人が入る流れ）と eval-3（`results/eval-3/report.html`、原著との比較）の2つを、抄録の本文とすべての逐語引用（スクリーニングの引用、抽出の引用と前後の文）を伏せて GitHub Pages で公開する。タイトル・雑誌・年・PMID（PubMed へのリンク）、基準ごとの判定、スコア、抽出した短い値と答え、人の判断と採点は残す
- 作り方：`build_report.py --public` で、データを作ったあとに伏せる（判定・検査は伏せる前の抄録で行う）。出力は `docs/demo/`。見本の画面は読むだけ（人の判断・採点の操作と保存は出さない）
- 2026-10-01 人が決定（続き）：Pages の見本は eval-3 だけにする（`docs/demo/eval-2.html` は消し、`docs/index.html` は eval-3 へ移動するだけ）。eval-3 の画面の上に、eval-2 と同じロボットのアニメーションで eval-3 の流れ（PICO → query-builder → screener-a → スコアで順位 → extractor → 人が採点）を足す。見本では、ヘッダーの下の「教育と手法の検証用…」の1行を出さない（位置づけは README にある）

## 2026-10-01 コードとファイルの整理（人の指示）

- `results/` の読み込みを `scripts/common.py` に、最終候補・順位・基準の ID 順を `scripts/rules.py` にまとめた。hook の共通部分は `.claude/hooks/hooklib.py`。出力は変えていない（手元の results/ で前後を突き合わせた）
- `docs/prompts/log.md` には人の指示だけを残す。Claude Code が送る task-notification と subagent の報告は `log_prompt.py` が書かず、既存のログからも `redact_log.py` で外した
- 消したもの：`docs/HANDOFF-cowork.md`（Cowork への引き継ぎ。最新の tag と残りの作業が古く、中身は eval-3.md などの正本の要約だけ）、`fetch_pubmed.py` の旧形式 `candidates.jsonl` の読み込み（すべての results に candidates.json がある）。`make_no_subagent_set.py` は commit 済みの見本 `docs/samples/no-subagent-31190844.jsonl` の作り方なので残す
- 2026-10-01 人の指示：`/eval` skill を eval-3（`--run eval-3`：screener-a だけ、基準の案のまま、人の判断なし、抽出の Accuracy）にも使えるようにした。前提の確認・実行するスクリプト・失敗の分け方を流れごとに書き分けた。`docs/eval/eval-3.md` は既にあるので、次の評価は別の名前にする
