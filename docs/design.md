# アプリ設計書 — 第2作：系統的文献レビュー × スクリーニング（TrialMind の再実装）（2026-09-27 v0.2）

> **v0.2（2026-09-27）**：要件を確定（`slr-kit/requirements.md`。リポジトリでは `docs/requirements.md`）。主な変更：PubMed は**自作 MCP をやめ、Anthropic 公式の PubMed コネクタ＋一括取得スクリプト**／対象は血液がん3本（33746596・31190844・37168849）／screener-b は基準の逆順／モデルは全て Sonnet／成果物は HTML レポート／抽出はしない。**本書と requirements が食い違う箇所は requirements が正**

> **上位方針**：`00_連載の土台_agentic-coding.md` を先に読むこと。この連載の目的は agentic coding の解説で、アプリはそのための題材である。食い違いがあれば土台の文書を優先する。
> 題材の決定経緯と論拠は `00_アプリラインナップ_20260921.md` 末尾の追補。
> 用語は英語のまま書く（`temperature`、subagent、few-shot、prompt caching など）。コードコメント・docs も同じ。

---

## 0. 位置づけ

- **第1作との違い**：第1作は「エージェントにアプリを作らせた」。第2作は「**エージェントに業務（文献スクリーニング）を任せ、ハーネスで品質を担保する**」。成果物は Web アプリではなく、Claude Code が回すワークフローとそのレポート
- **連載上の焦点**：**subagent の詳細な解説**（主役）。CLAUDE.md（土台5章の新ルールで詳しく扱う）、MCP（PubMed API の接続）、skill、hook、権限、評価も毎回組み込む
- **型**：A（論文の再実装）。Part0 で原著の紹介と限界を先に書く
- **原著**：Wang Z, Cao L, Danek B, Jin Q, Lu Z, Sun J. "Accelerating clinical evidence synthesis with large language models", *npj Digital Medicine* 2025（arXiv:2406.17755）。コード `RyanWangZf/TrialMind-SLR`（MIT）、ベンチマーク `zifeng-ai/TrialReviewBench`（Apache-2.0）
- **関連研究**：otto-SR（medRxiv 2025 / ISPOR 2026 ポスター）。比較の参考値のみ。詳しい位置づけは解説ページ2へ

### 原著の手法（再実装の対象）

| 段 | 原著の処理 | 原著の評価 |
|---|---|---|
| 検索 | PICO から in-context learning で Boolean query を生成 → 予備検索の abstract を足して（RAG）→ chain-of-thought で「語の抽出 → 不要語の除去 → 同義語・略語の追加」→ PubMed API | Recall（組み入れ研究をどれだけ拾えたか）。0.711–0.834（人の query 0.138–0.232） |
| スクリーニング | PICO から適格基準を生成（人が編集可）→ 研究ごとに**基準1つずつ** {-1, 0, 1}（不適格／不明／適格）を予測 → 合計してスコア化 → 順位付け | Recall@20 / Recall@50。埋め込み法（MPNet、MedCPT）を 30–160% 上回る |
| 研究特性の抽出 | 全文から研究デザイン・対象・アウトカムなどを抽出。出典箇所へのリンク付き | Accuracy |
| 結果の抽出 | 該当箇所の特定 → 数値抽出 → メタ解析用に Python コードで標準化 | Accuracy |

TrialReviewBench：がん治療の SR 100本（免疫療法／放射線・化学療法／ホルモン療法／温熱療法）、2,220研究、研究特性の注釈 1,334、結果の注釈 1,049。ファイルは `TrialReviewBench-reviews.csv`（128 kB）、`TrialReviewBench-study-search-screening.jsonl`（1.42 MB）、`TrialReviewBench-data-extraction/`。**CSV 間で列構成が揃っておらず HF のビューアが壊れている**（整形が最初の工程になる）。

### 自分の貢献（原著との差分）

1. GPT のノートブックを、**Claude Code の subagent・skill・hook・MCP** で組み直す
2. スクリーニングを**独立した2体の screener ＋ 裁定役**にする。**原著の設計ではなく**、コクランの二重スクリーニングに倣った追加。1体（原著相当）と2体の差を評価で示す
3. 判定の各基準に **abstract からの逐語引用**を必須にし、hook で検査する（原著は出典リンクを抽出段で付けるのみ）
4. 評価に原著の Recall@k に加えて、業務の指標（感度、WSS@95%、2体の一致度、人に回った件数）を足す

---

## 1. この題材で見せるハーネス

| 要素 | どの工程で自然に必要になるか | 扱い |
|---|---|---|
| **subagent（主役）** | 候補が数百〜数千件あり、1つの context に入らない。二重スクリーニングは**独立性**が要件で、同じ context で2回判定させると独立にならない。段ごとに必要な道具と情報が違う | Part2・3 の2回分 |
| **CLAUDE.md** | orchestrator（本体）と subagent に渡る文書の書き分けが必要になる。subagent は既定で CLAUDE.md を読む（`omitClaudeMd: true` で外せる）ため、「何を CLAUDE.md に書き、何を agent 定義に書くか」が設計判断になる | Part2 で全文を節ごとに解説 |
| MCP | **既製の MCP の接続**：Anthropic 公式の PubMed コネクタで検索式を試行錯誤する。決まった検索式の一括取得はスクリプト（「MCP は探索、定型の大量処理はスクリプト」の線引き） | Part1 |
| skill | PICO → 適格基準の起こし方、screener が毎回従う判定手順（agent 定義の `skills` で preload）、PRISMA の記録、評価（第1作の `/eval` の型を再利用） | Part1・2・4 |
| hook | screener の出力検査（全基準に逐語引用があり、引用が abstract に実在するか）、PRISMA 件数の整合、subagent 起動の課金ゲート | Part4 |
| 権限と停止条件 | screener は読むだけ・書く場所を限定、外部への送信なし、並列数の上限、評価の全件実行は人が起動 | Part1・3 |
| 評価 | 原著と同じ指標＋業務の指標。1体と2体の比較 | Part5 |
| （拡張）非対話実行 | 評価バッチを `claude -p` で回す。リビングレビューの定期更新は発展として触れる | Part5 |

---

## 2. 人が決めること／エージェントに任せること

| 人が決める（壊れ方に関わる判断） | エージェントに任せる |
|---|---|
| 対象にする SR（ベンチマークのどれを使うか）と PICO の確認 | ベンチマークの整形、PICO からの query 生成と改良 |
| 適格基準の**承認**（生成案を人が編集） | 基準ごとの判定と逐語引用 |
| 判定が割れた研究の最終判断（裁定役が「要人判断」に回したもの） | 2体の判定の突き合わせ、一致したものの確定 |
| 「不明（0）」の扱い（感度優先なら組み入れ側に倒す、という方針） | 方針に従った集約とスコア化 |
| 評価の全件実行（課金） | 部分実行、失敗の分類、直す場所の提案 |
| 並列数・モデル選択の上限 | 上限内でのバッチ分割 |

**任せないこと**：全文の取得と精読の最終判断、バイアスリスク評価、メタ解析の解釈（臨床的な結論は書かない）。

---

## 3. 権限と停止条件

- `.claude/settings.json`
  - allow：`pytest`、`ruff`、`git status/diff/log`、MCP の読み取り系（`mcp__pubmed__search`、`mcp__pubmed__fetch`）
  - ask：評価の全件実行（`claude -p` を含むスクリプト）、`git push`、ベンチマークの再ダウンロード
  - deny：`.env`・鍵の読み取り、`results/` の外への screener の書き込み（agent 定義の `tools` と permission rule の両方で）
- **フェーズの区切り（承認点）**
  1. ベンチマーク整形 → 行数・列の突き合わせを見せて止まる
  2. 適格基準の生成 → **人が承認するまで screener を起動しない**
  3. 1 バッチ（20件）だけで screener を試走 → 出力を見せて止まる
  4. 全件スクリーニング → 裁定 → 要人判断リストを出して止まる
  5. 評価の全件実行は人が `/eval` で起動
- **subagent の上限**：同時実行は `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`（既定 20）より小さく明示（例：6）。入れ子は不要なので `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`（screener が subagent を増やさない）

---

## 4. subagent・skill・hook・MCP の一覧

### subagent（`.claude/agents/*.md`）

公式仕様（`https://code.claude.com/docs/en/sub-agents`、2026-09-25 確認）：各 subagent は**独立した context window**・独自の system prompt・道具・権限を持つ。起動時に読むのは自分の system prompt、委任メッセージ、**CLAUDE.md（`omitClaudeMd: true` で除外可）**、git status、`skills` で preload した skill。**会話履歴は読まない**。frontmatter：`name`・`description`（必須）、`tools`・`disallowedTools`・`model`・`permissionMode`・`skills`・`mcpServers`・`hooks`・`maxTurns`・`effort`・`omitClaudeMd` など。結果は本体に subagent 出力として返る。`SubagentStart` / `SubagentStop` hook あり。

| 名前 | 役割 | tools | model | CLAUDE.md | 渡す情報 |
|---|---|---|---|---|---|
| `query-builder` | PICO → Boolean query、予備検索で改良（原著の検索段） | PubMed MCP のみ | sonnet | 読む | PICO、予備検索の結果 |
| `screener-a` | 1バッチ（20件）を基準ごとに {-1,0,1}＋逐語引用で判定 | Read、Write（`results/screen/a/` のみ） | sonnet | **読まない**（`omitClaudeMd: true`） | 承認済み基準、abstract のバッチだけ |
| `screener-b` | 同上、独立に判定 | 同上（`results/screen/b/`） | **別条件**（下記） | 読まない | 同上 |
| `adjudicator` | A と B を突き合わせ、一致は確定、不一致・引用不備は「要人判断」へ | Read、Write（`results/adjudication/`） | sonnet | 読む | A・B の出力だけ（abstract は必要時のみ） |
| （任意）`extractor` | 研究特性の抽出（PMC OA の全文がある研究のみ） | Read、Write | sonnet | 読む | 全文と抽出項目 |

**screener を独立にする工夫（記事の中心）**
- 会話履歴を持たない＝互いの判定を見ない（subagent の仕様そのものが独立性を担保）
- `omitClaudeMd: true`：orchestrator 向けのルール（フェーズ、評価の手順）を screener に混ぜない。判定規則は agent 定義と preload skill だけに置く
- **同じモデル・同じ指示の2体は誤りが相関する**。B の条件を変える候補を実験で比べる：(a) 別モデル、(b) 基準の提示順を逆にする、(c) 同条件（ばらつきだけ）。一致度（Cohen's kappa）と感度で選ぶ
- 渡すのは abstract と基準だけ。スコアや他の研究の判定は渡さない

### skill（`.claude/skills/<name>/SKILL.md`）

| 名前 | 起動 | 内容 |
|---|---|---|
| `pico-to-criteria` | 人と Claude | PICO から適格基準を起こす。基準は「1つの判定で答えられる粒度」、除外基準は明示、**人の承認で止まる** |
| `screening-rules` | screener に preload（`skills` 欄） | 判定手順：基準ごとに {-1,0,1}、必ず逐語引用、abstract に無い情報は 0（推測で ±1 にしない）、出力 JSON の形 |
| `prisma-record` | 人と Claude | 検索件数 → 重複除去 → スクリーニング除外（理由別）→ 組み入れ、を `results/prisma.json` に記録 |
| `eval` | 人だけ（`disable-model-invocation: true`） | 第1作の型を再利用：何を測るか先に書く → 実行 → 前回と比較 → 失敗の分類 → 記録 |
| `benchmark-prep` | 人と Claude | TrialReviewBench の整形（列の統一、PMID の正規化、行数の突き合わせ） |

### hook

| イベント | 対象 | 検査 |
|---|---|---|
| `SubagentStop`（matcher：`screener-*`） | screener の出力 | 全基準に判定と引用があるか／**引用文字列が abstract に逐語で存在するか**（スクリプトで照合）／JSON の形。不備は exit 2 で差し戻し（公式ドキュメント 2026-09-26 確認：exit 2 は subagent の停止を止め、stderr が伝わる。最終出力は `last_assistant_message` で読める） |
| `PostToolUse`（Write、`results/prisma.json`） | PRISMA | 各段の件数の和が合うか（除外理由の合計＝除外件数） |
| `PreToolUse`（`Agent`） | subagent 起動 | 同時起動数・1回の起動件数の上限（課金ゲート）。`Agent` に matcher が掛かるかは要確認 |
| `PostToolUse`（Edit/Write、`*.py`） | コード | `ruff`、`pytest`（第1作の構成を流用） |
| `UserPromptSubmit` | 人が送った指示 | `docs/prompts/log.md` に時刻つきで自動追記（記録用。stdout は出さず exit 0。stdout を出すと Claude の context に入る）。第1作で指示文が残らなかった反省から |

### MCP

- **Anthropic 公式の PubMed コネクタ**（`https://pubmed.mcp.claude.com/mcp`、Claude Code では `/plugin marketplace add anthropics/life-sciences` → `/plugin install pubmed@life-sciences`）。検索、書誌・抄録、PMC 全文、関連論文、引用からの PMID 特定、ID 変換。無料、NCBI の制限はサーバー側で順守
- 使うのは query-builder だけ（screener には渡さない）
- 1回の検索で返る件数・長い検索式の扱いなどの制限は、接続確認で試して HARNESS に記録（第三者の記事に「上位15件程度」「長い式で失敗」の報告あり、未確認）
- 候補200件と抄録の一括取得は `scripts/fetch_pubmed.py`（E-utilities の esearch / efetch を直接呼ぶ。API key は環境変数）。再現性のため、検索式・検索期間・取得日時・件数を `results/<PMID>/search.json` に残す
- 自作しない理由：保守・アクセス制限を公式に任せられる、読者はプラグイン1つで再現できる、自作は第3作の主役

---

## 5. 評価設計

- **データ**：TrialReviewBench。全100本は課金が重いので、**1トピック（免疫療法）から 5〜10 本**に絞る（どれを使うかは人が決める）。補助に SYNERGY（CC0）の医学系レビュー1〜2本
- **指標**

| 段 | 原著と同じ指標 | 追加する業務の指標 |
|---|---|---|
| 検索 | Recall | query の件数（人が読む量） |
| スクリーニング | Recall@20、Recall@50 | 感度・特異度（「不明」を組み入れ側に倒した場合）、WSS@95%、2体の一致度（kappa）、要人判断に回った件数 |
| 抽出（任意） | Accuracy | 引用の実在率 |

- **比較**：(1) 1体（原著相当）vs 2体＋裁定、(2) screener-b の条件 (a)(b)(c)、(3) 原著の数値との並記（「追試」とは書かない。データの取得時期・モデルが違う）
- **失敗の分類**：基準の粒度不足／abstract に情報が無い／引用の捏造（hook が捕まえた数）／2体とも誤り（相関）／ベンチマークの正解側の問題
- **記録**：`docs/EVAL.md`（第1作と同じ書式）。所要時間・トークンは比率で記事に、金額は書かない

---

## 6. 記事での見せ場

- subagent を**使わなかった場合**（本体1つで全件判定）に何が起きるか：context の圧迫、先に見た研究の判定に引きずられる、途中で方針がぶれる → 実際に試走して見せる
- 並列で screener が走っている画面（Claude Code の実画面）
- **2体の判定が割れた実例**と、裁定役が人に回した理由
- hook が**abstract に無い引用**を差し戻した実例
- `omitClaudeMd` の有無で screener の出力が変わるか（orchestrator 向けルールの混入）
- 1体と2体の感度の差、人が読む件数の減り方
- 人が決めたこと（基準の承認、「不明」の扱い、割れた研究の判断）と、実行が見つけたこと

---

## 7. リポジトリ構成（案）

```
trialmind-slr-claude-code/
├── CLAUDE.md                     # orchestrator 向け：フェーズ、承認点、やらないこと、用語
├── .claude/
│   ├── settings.json             # 権限、hooks、subagent の上限（env）
│   ├── agents/                   # query-builder / screener-a / screener-b / adjudicator
│   ├── skills/                   # pico-to-criteria / screening-rules / prisma-record / eval / benchmark-prep
│   └── hooks/                    # check_screen_output.py / check_prisma.py / agent_gate.py
├── .mcp.json                     # pubmed MCP
├── mcp/pubmed/                   # 自作 MCP（esearch / efetch）
├── bench/                        # 整形スクリプト（データ本体は gitignore、取得手順は README）
├── reviews/<review_id>/          # pico.md、criteria.md（承認済み）
├── results/                      # screen/a、screen/b、adjudication、prisma.json（gitignore、サンプルのみ同梱）
├── eval/                         # 評価スクリプト、指標
├── docs/                         # design.md、DECISIONS.md、EVAL.md、HARNESS.md
├── NOTICE                        # TrialMind（MIT）、TrialReviewBench（Apache-2.0）の帰属表示
└── README.md
```

名前はデータ名×手法名の原則に合わせて最終決定（例：`pubmed-slr-screening`）。

---

## 8. Part 構成（案）

| Part | サブタイトル案 | ハーネス | 題材 |
|---|---|---|---|
| 0 | 全体像とハーネス設計 | 全体図（subagent 中心） | SR という業務、原著と限界、otto-SR との位置関係、任せる範囲 |
| 1 | PubMed API と MCP | MCP、権限 | ベンチマークの整形、query の生成と改良 |
| 2 | CLAUDE.md と subagent の設計 | **CLAUDE.md（全文解説）**、agent 定義、`omitClaudeMd`、`skills` の preload | 分担の決め方、渡す情報の絞り方 |
| 3 | 並列判定と裁定 | subagent の並列実行、上限、受け渡し | 二重スクリーニング、割れた実例、人に回す線 |
| 4 | 引用の検査と hook | hook（SubagentStop ほか）、skill | 捏造引用の差し戻し、PRISMA の整合 |
| 5 | 原著との比較評価 | 評価、非対話実行 | 原著の指標と業務の指標、1体 vs 2体 |

解説ページ：【業務説明】系統的文献レビュー／【技術説明】スクリーニング自動化の系譜と評価指標（`00_アプリラインナップ` 追補を参照）。

---

## 9. 作業と記録の指示（**時系列で記事を書くための撮影・記録**）

第1作は後から撮り直した画面が多く、「実際に貼った指示文」が手元に残っていなかった（Part3 で指示文を引用できなかった）。第2作は**作りながら残す**。

**2026-09-26 改訂：録画を回しっぱなしにする方式に変更。** 詳細は `12_撮影と記録_第2作_20260925.md`。

- 人：作業中は VS Code のウィンドウを録画しっぱなし（保存先はローカルの `~/Movies/slr-rec/`、Drive に置かない）
- hook：`UserPromptSubmit` で指示文を `docs/prompts/log.md` に自動記録
- エージェント：CLAUDE.md の規則で節目の commit と `snap/*` tag、`docs/HARNESS.md` への記録、`docs/samples/` への結果の保存
- Cowork：会話ログと git の時刻で動画の該当箇所を特定し、ffmpeg で切り出す。ファイルの中身は tag から撮り直す

## 10. 未決事項

1. ~~範囲~~ → 検索＋スクリーニングまで（2026-09-27）
2. TrialReviewBench のどのレビュー（5〜10本）を使うか。`study-search-screening.jsonl` に候補集合（非組み入れ研究）が含まれるかを確認してから決める
3. ~~screener-b の条件~~ → 基準の逆順（2026-09-27）
4. ~~自作 MCP か既製か~~ → 公式コネクタ＋スクリプトに決定（2026-09-27）
5. `PreToolUse` の matcher に subagent 起動のツール名（`Agent`）をどう書くか（実機で確認。`SubagentStop` の exit 2 は確認済み）
6. 原著著者への連絡タイミング
7. リポジトリ名

## 参考文献

- Wang Z et al. Accelerating clinical evidence synthesis with large language models. *npj Digit Med* 2025. https://www.nature.com/articles/s41746-025-01840-7 / arXiv:2406.17755
- TrialMind-SLR（MIT）https://github.com/RyanWangZf/TrialMind-SLR
- TrialReviewBench（Apache-2.0）https://huggingface.co/datasets/zifeng-ai/TrialReviewBench
- Cao C et al. Automation of Systematic Reviews with Large Language Models. medRxiv 2025. doi:10.1101/2025.06.13.25329541
- SYNERGY dataset（CC0）https://github.com/asreview/synergy-dataset
- Claude Code subagents https://code.claude.com/docs/en/sub-agents
- NCBI E-utilities https://www.ncbi.nlm.nih.gov/books/NBK25497/
