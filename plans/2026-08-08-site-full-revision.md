# サイト全面改定 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/` 配下の全 21 ファイルを、新対象読者（Python文法は理解済み・実用プログラム未経験・SQLは忘れ気味）向けにフルリライトする。

**Architecture:** 章立て・ファイル名・`mkdocs.yml`・技術スタックは不変。本文は統一章フォーマットで書き直す。実装パート（第10〜16章）は写経式に転換し、コード片は `sample/todo-app/` の完成版と一致させる。スペック: `specs/2026-08-08-site-full-revision-design.md`

**Tech Stack:** MkDocs Material（admonition / tabbed / details / tasklist / superfences 使用可）、`uv run mkdocs build --strict` が CI 相当の検証。

---

## 全タスク共通のルール

### 統一章フォーマット（全章この構成・この順序）

```markdown
# 第N章 タイトル（既存の章タイトルを維持）

（導入段落: この章の位置づけを2〜4文で）

## N.1 この章でやること
- ゴールの箇条書きと所要時間の目安

## N.2 前提知識
（その章で使う概念を初学者向けに解説。`!!! note` 等のadmonitionを活用）

## N.3 以降: 手順・解説
- コマンドには必ず「期待される出力」のコードブロックを直後に置く
- SQLには必ず実行結果の表示例を置く

## チェックポイント
（tasklist記法 `- [ ]` で「ここまでできたか」の確認項目）

## つまずきポイント
（よくあるエラー2〜4件と対処法）

## やってみよう
（段階的な練習問題2〜4問。解答例は `??? example "解答例"` の折りたたみで）

## まとめ
- 学んだことの箇条書きと次章への一言
```

- セクション番号（N.1 等）は章の内容に合わせて増減してよいが、上記7要素の順序と有無は守る
- 文体: 現在と同じ「です・ます」調、砕けすぎない
- 対象読者が「文法は知っている」ので Python 文法自体の解説は書かない
- 既存ファイル名・既存章タイトルは変更しない（`mkdocs.yml` の nav と一致させるため）

### 写経式パート（Task 12〜18）の追加ルール

- 読者の作業ディレクトリは `mytodo/` とする（`sample/todo-app` とは別）
- コード片は**全文掲載**。`...` や「以下略」による省略は禁止
- 各章冒頭に「ここまでのファイル構成」ツリーを ```text ブロックで示す
- 各コード片の直前に「`mytodo/<パス>` を作成して次の内容を書き写す」形式の指示を置く
- 章末の動作確認で `diff -u mytodo/<パス> sample/todo-app/<対応パス>`（差分なしがゴール）を案内
- `sample/todo-app` は「答え合わせ用の完成版」と明記
- 写経用コードは必ず対応する `sample/todo-app` の実ファイルを Read して転記する。記憶や推測で書かない

### 各タスクの検証・コミット

- 検証: リポジトリルートで `uv run mkdocs build --strict` → 終了コード 0
- コミット: `git add docs/<対象ファイル> && git commit -m "docs: rewrite <対象ファイル名> for new target audience"`

---

### Task 1: index.md（はじめに）

**Files:**
- Modify: `docs/index.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/index.md`
- [ ] **Step 2: 書き直す**。要件:
  - 想定読者を「Python文法は理解・実用プログラム未経験・SQLは忘れ気味」に明確化
  - 「読む前にわかっていること / わからなくてよいこと（このテキストで説明するもの）」の2リストを新設
  - 作るもの・進め方・道具の表・スケジュール表は維持（内容は新読者ペースに調整）
  - 統一フォーマットのうち「この章でやること」「まとめ」は index では省略可
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/index.md && git commit -m "docs: rewrite index.md for new target audience"`

### Task 2: 第0章 環境構築

**Files:**
- Modify: `docs/00-setup.md`

- [ ] **Step 1: 現行ファイルと参照先を読む** `docs/00-setup.md`、`docker-compose.yml`、ルート `pyproject.toml`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: Docker（コンテナとは）、uv（pip との違い）、仮想環境、ポート — すべて未経験者向けに
  - 全コマンドに期待出力を記載（`docker compose up -d`、`uv sync` 等）
  - つまずきポイント: Docker 未起動、ポート5432競合、`uv: command not found`、権限エラー
  - 環境構築の完了を自分で判定できるチェックポイントを置く
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/00-setup.md && git commit -m "docs: rewrite 00-setup.md for new target audience"`

### Task 3: 第1章 型ヒントとdataclass

**Files:**
- Modify: `docs/01-python-types.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/01-python-types.md`
- [ ] **Step 2: 書き直す**。要件:
  - 文法の復習はしない。型ヒント・dataclass を「書いたことがない」前提で「なぜ使うか」から
  - 全コード例に実行例と期待出力
  - 前提知識: 「実用コードではなぜ型を書くのか」
  - 練習問題3問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/01-python-types.md && git commit -m "docs: rewrite 01-python-types.md for new target audience"`

### Task 4: 第2章 with・モジュール・pytest

**Files:**
- Modify: `docs/02-python-context.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/02-python-context.md`
- [ ] **Step 2: 書き直す**。要件:
  - with 文・モジュール分割（複数ファイル構成）・pytest を未経験前提で
  - 前提知識: リソースの後始末（ファイルを閉じる等）の概念、テストを自動化する意味
  - pytest の実行例と期待出力（`1 passed` 等）を記載
  - 練習問題3問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/02-python-context.md && git commit -m "docs: rewrite 02-python-context.md for new target audience"`

### Task 5: 第3章 PostgreSQL① DDL/DML/SELECT

**Files:**
- Modify: `docs/03-postgres-ddl-dml.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/03-postgres-ddl-dml.md`
- [ ] **Step 2: 書き直す**。要件:
  - 「思い出す」前提をやめ「ほぼ初めて」前提に
  - psql の起動・終了・`\dt` `\d` 等の基本メタコマンドから記載
  - 前提知識: リレーショナルDBとは、テーブル・行・列、SQLとpsqlの関係
  - 全 SQL に実行結果の表示例、表の before/after 図解
  - 練習問題4問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/03-postgres-ddl-dml.md && git commit -m "docs: rewrite 03-postgres-ddl-dml.md for new target audience"`

### Task 6: 第4章 PostgreSQL② JOIN・集約・トランザクション

**Files:**
- Modify: `docs/04-postgres-join-tx.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/04-postgres-join-tx.md`
- [ ] **Step 2: 書き直す**。要件:
  - 第3章同様「ほぼ初めて」前提。JOIN は表の図解で視覚的に
  - 前提知識: 主キー・外部キー、トランザクションとは（ACIDは軽く）
  - 全 SQL に実行結果の表示例
  - 練習問題4問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/04-postgres-join-tx.md && git commit -m "docs: rewrite 04-postgres-join-tx.md for new target audience"`

### Task 7: 第5章 psycopg入門

**Files:**
- Modify: `docs/05-psycopg-basics.md`

- [ ] **Step 1: 現行ファイルと参照先を読む** `docs/05-psycopg-basics.md`、`sample/todo-app/pyproject.toml`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: クライアント/サーバーモデル、ドライバとは、コネクションとカーソル、DSN
  - 接続確認スクリプトは読者が自分で書く形式にし、全文掲載＋期待出力
  - つまずきポイント: 接続拒否（Docker未起動）、認証エラー、DB名違い
  - 練習問題2〜3問（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/05-psycopg-basics.md && git commit -m "docs: rewrite 05-psycopg-basics.md for new target audience"`

### Task 8: 第6章 プレースホルダとトランザクション

**Files:**
- Modify: `docs/06-psycopg-tx.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/06-psycopg-tx.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: SQLインジェクション（平易に、具体例で）、コミット/ロールバック
  - プレースホルダの `%s` が「Python の % 書式ではない」点を強調
  - 全コード例に期待出力
  - 練習問題2〜3問（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/06-psycopg-tx.md && git commit -m "docs: rewrite 06-psycopg-tx.md for new target audience"`

### Task 9: 第7章 dict_rowとコネクションプール

**Files:**
- Modify: `docs/07-psycopg-pool.md`

- [ ] **Step 1: 現行ファイルと参照先を読む** `docs/07-psycopg-pool.md`、`sample/todo-app/app/db.py`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 接続確立のコスト、プールの仕組み（貸し出し・返却のたとえ）
  - コード例は `app/db.py` と矛盾しない内容に
  - 全コード例に期待出力
  - 練習問題2〜3問（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/07-psycopg-pool.md && git commit -m "docs: rewrite 07-psycopg-pool.md for new target audience"`

### Task 10: 第8章 要件・画面・API設計

**Files:**
- Modify: `docs/08-design-app.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/08-design-app.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 「なぜ設計してから書くのか」、HTTPリクエスト/レスポンスの基礎、REST APIとは
  - 要件→画面→API の流れは維持
  - この章で写経の進め方を宣言: 読者は `mytodo/` を作成し、第10章以降で写経する。`sample/todo-app` は答え合わせ用
  - 練習問題2問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/08-design-app.md && git commit -m "docs: rewrite 08-design-app.md for new target audience"`

### Task 11: 第9章 テーブル設計とマイグレーション

**Files:**
- Modify: `docs/09-design-db.md`

- [ ] **Step 1: 現行ファイルと参照先を読む** `docs/09-design-db.md`、`sample/todo-app/migrations/001_init.sql`、`sample/todo-app/migrations/002_seed.sql`、`sample/todo-app/app/cli.py`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 正規化の初歩、マイグレーションとは（なぜSQLをファイルで管理するか）
  - マイグレーションSQLの内容は `migrations/` の実ファイルと一致させる
  - 全 SQL に実行結果の表示例
  - 練習問題2問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/09-design-db.md && git commit -m "docs: rewrite 09-design-db.md for new target audience"`

### Task 12: 第10章 ドメインモデルとリポジトリ（Read系）— 写経式

**Files:**
- Modify: `docs/10-data-read.md`
- Source: `sample/todo-app/app/models.py`、`sample/todo-app/app/repositories.py`、`sample/todo-app/app/config.py`、`sample/todo-app/app/db.py`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記4ファイル＋`docs/10-data-read.md`
- [ ] **Step 2: 書き直す**。写経式ルール（上部「写経式パートの追加ルール」）に従う。要件:
  - 前提知識: レイヤー分けとは、ドメインモデルとDBの行の違い
  - 写経対象: `models.py` 全文、`repositories.py` のRead系関数、`config.py`/`db.py`（この章で必要な分）
  - 冒頭に「ここまでのファイル構成」ツリー
- [ ] **Step 3: コード一致確認** 章の写経コード片と `sample/todo-app` の対応ファイルを目視で照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/10-data-read.md && git commit -m "docs: rewrite 10-data-read.md for new target audience"`

### Task 13: 第11章 リポジトリ（Write系）とタグの多対多 — 写経式

**Files:**
- Modify: `docs/11-data-write.md`
- Source: `sample/todo-app/app/repositories.py`

- [ ] **Step 1: 現行ファイルとソースを読む** `docs/11-data-write.md`、`sample/todo-app/app/repositories.py`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 多対多とは、JOINテーブル、UPSERT（`ON CONFLICT`）
  - 写経対象: `repositories.py` のWrite系関数（全文掲載、Read系は「前章で書いた」と参照）
  - 多対多は表の図解つき
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/11-data-write.md && git commit -m "docs: rewrite 11-data-write.md for new target audience"`

### Task 14: 第12章 データアクセス層のテスト — 写経式

**Files:**
- Modify: `docs/12-data-tests.md`
- Source: `sample/todo-app/tests/conftest.py`、`sample/todo-app/tests/test_repositories.py`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記2ファイル＋`docs/12-data-tests.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: フィクスチャとは、テストの独立性、ロールバックによる後始末
  - 写経対象: `conftest.py`・`test_repositories.py` 全文
  - `uv run pytest -v` の期待出力を記載
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/12-data-tests.md && git commit -m "docs: rewrite 12-data-tests.md for new target audience"`

### Task 15: 第13章 FastAPI入門 起動とDI — 写経式

**Files:**
- Modify: `docs/13-api-fastapi.md`
- Source: `sample/todo-app/app/main.py`、`sample/todo-app/app/db.py`、`sample/todo-app/app/routers/todos.py`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記3ファイル＋`docs/13-api-fastapi.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: Webサーバーとは、ASGI/uvicorn、依存性注入（DI）を平易に、`/docs` の自動生成
  - 写経対象: `main.py` 全文、`routers/todos.py` の骨格
  - 起動コマンドとブラウザ/curlでの期待結果を記載
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/13-api-fastapi.md && git commit -m "docs: rewrite 13-api-fastapi.md for new target audience"`

### Task 16: 第14章 CRUD API実装とテスト — 写経式

**Files:**
- Modify: `docs/14-api-crud.md`
- Source: `sample/todo-app/app/routers/todos.py`、`sample/todo-app/app/schemas.py`、`sample/todo-app/app/services.py`、`sample/todo-app/tests/test_api.py`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記4ファイル＋`docs/14-api-crud.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: HTTPメソッドとステータスコード、Pydanticによるバリデーション
  - 写経対象: `schemas.py`・`services.py` 全文、`routers/todos.py` の全エンドポイント、`test_api.py`
  - curl の実行例と期待レスポンス、pytest の期待出力を記載
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/14-api-crud.md && git commit -m "docs: rewrite 14-api-crud.md for new target audience"`

### Task 17: 第15章 Jinja2でHTML — 写経式

**Files:**
- Modify: `docs/15-ui-jinja2.md`
- Source: `sample/todo-app/app/routers/pages.py`、`sample/todo-app/app/templates/base.html`、`sample/todo-app/app/templates/index.html`、`sample/todo-app/app/static/style.css`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記4ファイル＋`docs/15-ui-jinja2.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: サーバーサイドレンダリングとは、テンプレートエンジンの役割
  - 写経対象: `pages.py`・`base.html`・`index.html`・`style.css` 全文
  - ブラウザ表示の確認手順を記載
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/15-ui-jinja2.md && git commit -m "docs: rewrite 15-ui-jinja2.md for new target audience"`

### Task 18: 第16章 htmxで動的UI — 写経式

**Files:**
- Modify: `docs/16-ui-htmx.md`
- Source: `sample/todo-app/app/routers/pages.py`、`sample/todo-app/app/templates/_list.html`、`sample/todo-app/app/templates/_row.html`、`sample/todo-app/app/templates/index.html`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記4ファイル＋`docs/16-ui-htmx.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 部分更新とは、htmxの属性（`hx-get` 等）の仕組み、HTMLフラグメント
  - 写経対象: `_list.html`・`_row.html` 全文、`pages.py` のhtmxエンドポイント、`index.html` の変更差分
  - 動作確認手順（ブラウザで追加・完了切替）を記載
- [ ] **Step 3: コード一致確認** 章の写経コード片と実ファイルを照合
- [ ] **Step 4: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 5: コミット** `git add docs/16-ui-htmx.md && git commit -m "docs: rewrite 16-ui-htmx.md for new target audience"`

### Task 19: 第17章 設定・ログ・例外ハンドリング

**Files:**
- Modify: `docs/17-finishing.md`
- Source: `sample/todo-app/app/config.py`、`sample/todo-app/.env.example`

- [ ] **Step 1: 現行ファイルとソースを読む** 上記2ファイル＋`docs/17-finishing.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: 環境変数とは、なぜ設定をコードに埋め込まないか、ログとは、例外ハンドリングの方針
  - コード例は `config.py`・`.env.example` と一致させる
  - 練習問題2問以上（解答例つき）
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/17-finishing.md && git commit -m "docs: rewrite 17-finishing.md for new target audience"`

### Task 20: 第18章 公開先と最終課題

**Files:**
- Modify: `docs/18-deploy.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/18-deploy.md`
- [ ] **Step 2: 書き直す**。要件:
  - 前提知識: デプロイとは、PaaS/VM/コンテナの選択肢の概観
  - 手順の再現性を強化（コマンド＋期待出力）
  - 最終課題は段階的な仕様＋ヒント構成に
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/18-deploy.md && git commit -m "docs: rewrite 18-deploy.md for new target audience"`

### Task 21: 付録A SQLチートシート

**Files:**
- Modify: `docs/appendix-sql.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/appendix-sql.md`
- [ ] **Step 2: 書き直す**。要件:
  - 忘れた人が引き直せるよう、全項目に「構文＋実行例＋結果例」を揃える
  - 第3〜4章と用語・例の一貫性を保つ
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/appendix-sql.md && git commit -m "docs: rewrite appendix-sql.md for new target audience"`

### Task 22: 付録B 用語集

**Files:**
- Modify: `docs/appendix-glossary.md`

- [ ] **Step 1: 現行ファイルを読む** `docs/appendix-glossary.md`
- [ ] **Step 2: 書き直す**。要件:
  - 既存語彙に加え、実践未経験者向けに追加: HTTP、ポート、プロセス、クライアント/サーバー、仮想環境、コンテナ、ORM、DSN、ASGI、依存性注入、マイグレーション、フィクスチャ
  - 各用語は1〜3文で平易に、本文のどの章で出てくるかを併記
  - 全章で使った「前提知識」の用語と漏れなく対応させる
- [ ] **Step 3: 検証** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 4: コミット** `git add docs/appendix-glossary.md && git commit -m "docs: rewrite appendix-glossary.md for new target audience"`

### Task 23: 最終検証とPR作成

**Files:**
- 全 `docs/*.md`（確認のみ）

- [ ] **Step 1: ビルド最終確認** `uv run mkdocs build --strict` → 終了コード 0
- [ ] **Step 2: 統一フォーマット監査** 全章に「この章でやること / 前提知識 / チェックポイント / つまずきポイント / やってみよう / まとめ」があるか `grep` で確認:

```bash
for f in docs/[01]*.md; do echo "== $f"; grep -c -E "^## .*(この章でやること|前提知識|チェックポイント|つまずきポイント|やってみよう|まとめ)" "$f"; done
```

- [ ] **Step 3: 写経コード片の照合** Task 12〜18 の各章について、掲載コードと `sample/todo-app` の対応ファイルに差分がないことを確認
- [ ] **Step 4: プッシュ** `git push -u origin docs/full-revision`
- [ ] **Step 5: PR作成**

```bash
gh pr create --title "docs: サイト全面改定（実践未経験者向けに全章書き直し）" --body "$(cat <<'EOF'
## 概要

対象読者を「Pythonの文法は理解しているが実用プログラムを書いたことがない、SQLは学習済みだが忘れ気味」の層に合わせ、全21ファイルを書き直しました。章立て・ファイル名・技術スタックは不変です。

デザイン文書: `specs/2026-08-08-site-full-revision-design.md`

## 主な変更

- 全章を統一フォーマット化（やること明示 / 前提知識 / 手順+期待出力 / チェックポイント / つまずきポイント / 練習問題+解答例 / まとめ）
- 第3〜4章: SQLを「ほぼ初めて」前提で書き直し（psqlの基本操作から、実行例完備）
- 第10〜16章: 写経式に転換。読者は `mytodo/` に自分でファイルを作成（コード全文掲載）。`sample/todo-app` は答え合わせ用の完成版
- 各章に実践未経験者向けの前提知識解説（HTTP、ポート、コンテナ、仮想環境等）を追加
- 付録A/B を拡充（SQL実行例、用語追加）

## 検証

- [x] `uv run mkdocs build --strict` 成功
- [x] 写経コード片と `sample/todo-app` の一致を確認

🤖 Generated with Kimi Code
EOF
)"
```

- [ ] **Step 6: PR URLをユーザーに報告**
