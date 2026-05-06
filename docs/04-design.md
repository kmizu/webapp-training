# 第4章 ToDoアプリの設計

コードを書く前に、**何を作るか**と**どう分けるか**を決めます。
設計を端折ると、あとで「やっぱりこのカラムが要る」「画面の作り直し」が起きます。
時間をかけてやる必要はないですが、**通しで一回考えておく**ことが大切です。

## 4.1 要件（最低限の仕様）

このアプリは **個人で使う ToDo リスト** とします。
複数人で共有することは考えません（ユーザー認証は範囲外）。

機能要件:

- ToDo の **追加・編集・削除・完了切替** ができる
- 一覧で「未完了」「完了」「全部」を **絞り込みできる**
- 各 ToDo は **タイトル・期限・優先度・完了フラグ** を持つ
- ToDo に **タグ** を 0 個以上付けられる（多対多）
- 一覧は **期限が近いもの・優先度が高いもの**を上に並べる
- 検索（タイトルの部分一致）ができる

非機能要件（軽く）:

- 初回画面表示が 1 秒以内
- ToDo は最大 1 万件くらいまで普通に動く
- 個人 PC で動かす前提（外には公開しなくてよい）

機能の **「やらないこと」** も決めておきます。

- ユーザー登録・ログイン
- リマインダー通知
- スマホアプリ
- データのエクスポート

!!! tip "やらないことを書く"
    やる機能だけを書いていると、つい「あ、これも要るかも」が増えていきます。
    **「これはやらない」と紙に書く**だけで、ぐっと迷いが減ります。

## 4.2 ユースケース図（言葉で）

ユーザーは 1 人なので、シンプルに:

```text
ユーザー ──┬── ToDo を追加
          ├── ToDo の一覧を見る（絞り込み・検索付き）
          ├── ToDo を完了にする / 戻す
          ├── ToDo を編集する
          ├── ToDo を削除する
          └── タグを付ける / 外す
```

## 4.3 画面設計（軽く）

ページは **1 枚** にします。
ヘッダ・フィルタ・リスト・追加フォームの 4 ブロック。

```text
┌──────────────────────────────────────────┐
│  ToDo                            [追加]   │  ← ヘッダ
├──────────────────────────────────────────┤
│  [全て] [未完了] [完了]   [ 検索…       ] │  ← フィルタ
├──────────────────────────────────────────┤
│  ☐ 牛乳を買う      5/8 高 [家事]         │
│  ☐ 健康診断の予約  5/9 高 [健康]         │
│  ☑ 領収書の整理    --  中  [仕事]         │  ← リスト
│  ☐ 車検の見積もり  6/1 中                │
├──────────────────────────────────────────┤
│  [ タイトルを入力…   期限   優先  追加 ]  │  ← フォーム
└──────────────────────────────────────────┘
```

UI は htmx でゆるく動かすので、**ボタンを押したら部分的に書き換える**動きにします。

## 4.4 データ設計

ER 図はテキストで:

```text
[todos]              [todo_tags]            [tags]
 id   PK   ─────┐    todo_id  PK,FK ──┐     id    PK
 title          ├──→                   │     name  UNIQUE
 done           │    tag_id   PK,FK ──┘
 due_on         │
 priority       │
 created_at     │
 updated_at     │
                ↑（多対多）
```

具体的なテーブル定義:

```sql
CREATE TABLE todos (
    id          SERIAL      PRIMARY KEY,
    title       TEXT        NOT NULL CHECK (length(title) > 0),
    done        BOOLEAN     NOT NULL DEFAULT FALSE,
    due_on      DATE,
    priority    SMALLINT    NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_todos_done_due ON todos (done, due_on);

CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT   UNIQUE NOT NULL CHECK (length(name) > 0)
);

CREATE TABLE todo_tags (
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
);
```

設計のポイント:

- **`CHECK` 制約** で「タイトルは空NG」「優先度は1-3」を DB レベルで担保。アプリのバグで変な値を入れても DB が止めてくれます。
- **`ON DELETE CASCADE`** で「ToDo を消したら関連する `todo_tags` も消える」ようにします。これがないと孤児レコードが残ります。
- **`idx_todos_done_due`** は「未完了で期限順に並べる」検索が頻繁なので、その複合インデックスを張っています。

!!! note "なぜ priority は SMALLINT？"
    優先度は 1〜3 の小さな整数なので、4 バイトの `INTEGER` ではなく 2 バイトの `SMALLINT` で十分です。何万件もある場合のサイズ差はばかになりません。

## 4.5 API 設計

「画面 → サーバー」のやりとりを **小さな表** にしておきます。
URL の付け方は「**リソース指向**」を意識します（複数形 + 動詞は HTTP メソッド）。

| メソッド | パス | 役割 | リクエスト | レスポンス |
|---|---|---|---|---|
| `GET`    | `/`                   | 画面表示（HTML）          | クエリ: `filter`, `q`              | HTML                 |
| `GET`    | `/api/todos`          | ToDo 一覧（JSON）         | クエリ: `filter`, `q`              | `Todo[]`             |
| `POST`   | `/api/todos`          | ToDo 作成                 | JSON: `{title, due_on?, priority?, tags?}` | `Todo`        |
| `PATCH`  | `/api/todos/{id}`     | ToDo 部分更新             | JSON: 任意フィールド               | `Todo`               |
| `POST`   | `/api/todos/{id}/toggle` | 完了/未完了の切替      | （なし）                           | `Todo`               |
| `DELETE` | `/api/todos/{id}`     | ToDo 削除                 | （なし）                           | `204 No Content`     |
| `GET`    | `/api/tags`           | タグ一覧                  | （なし）                           | `Tag[]`              |

Todo / Tag のスキーマ（Pydantic で表現する想定）:

```text
Todo {
  id: int
  title: string
  done: bool
  due_on: date | null
  priority: 1 | 2 | 3
  tags: string[]
  created_at: datetime
  updated_at: datetime
}

Tag {
  id: int
  name: string
}
```

!!! tip "PATCH と PUT の使い分け"
    - **`PUT`** はリソースを「丸ごと差し替える」
    - **`PATCH`** はリソースを「部分的に書き換える」

    今回は「タイトルだけ変えたい」「優先度だけ変えたい」が普通なので `PATCH` を採用します。

## 4.6 ディレクトリ構成

研修で実際に使う構成です。

```text
sample/todo-app/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI アプリ起動点
│   ├── db.py                # 接続管理（プール）
│   ├── models.py            # ドメインモデル（dataclass）
│   ├── schemas.py           # Pydantic スキーマ（API用）
│   ├── repositories.py      # SQL を投げる層
│   ├── services.py          # 業務ロジック層（軽く）
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── pages.py         # GET / の HTML 返却
│   │   └── todos.py         # /api/todos の CRUD
│   ├── templates/           # Jinja2
│   │   ├── base.html
│   │   └── _list.html       # 部分テンプレート（htmx で差し替え）
│   ├── static/
│   │   └── style.css
│   └── cli.py               # init-db などの管理コマンド
├── migrations/
│   ├── 001_init.sql
│   └── 002_seed.sql
├── tests/
│   ├── conftest.py
│   ├── test_repositories.py
│   └── test_api.py
├── pyproject.toml
└── .env.example
```

レイヤーの考え方:

```text
HTTP（FastAPI ルーター）
   ↓ Pydantic で入力チェック
Service（業務ロジック）
   ↓ ドメインモデル（dataclass）
Repository（SQL 発行）
   ↓
PostgreSQL
```

各層の責務:

- **routers**: HTTP の世界（リクエスト/レスポンス、ステータスコード）
- **schemas**: 入力と出力の型を定義（Pydantic）
- **services**: ビジネスルール（「未完了が 100 件超えたら警告」のような）
- **repositories**: SQL を書く場所
- **models**: アプリ全体で使うドメイン型（dataclass）

研修では **services は薄く** して、ほぼ routers ↔ repositories で完結します。

## 4.7 マイグレーション戦略

スキーマ変更を **連番付きの SQL ファイル**で管理します。
今回は Alembic などのツールを使わず、手書きの最小実装でやります。

```text
migrations/
├── 001_init.sql
├── 002_seed.sql
└── ...
```

`app.cli init-db` を実行すると、`migrations/` 以下の SQL を **連番順に**実行する仕組みにします。**いつどのファイルまで適用したか**を記録するテーブル `schema_versions` を別に持ちます。

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

!!! tip "実務では Alembic / Flyway を使う"
    本研修では学習目的でシンプルなスクリプトを書きますが、
    実務では **Alembic（Python）** や **Flyway（言語非依存）** など
    実績のあるマイグレーションツールを使ってください。

## やってみよう

1. 上のテーブル定義を `psql` で実際に作って、`\d todos` で構造を見る。
2. 自分なら、ToDo に **どんなカラムを追加したいか** 3 つ挙げる
   （例: 説明文 `description`、繰り返し設定 `repeat_kind`、リマインド時刻 `remind_at`）。
3. その追加カラムを **DB に追加する `ALTER TABLE` 文**を書いてみる。

次は [第 5 章 データアクセス層を作る](05-data-layer.md) で、
**この設計を実際に Python のコードに落とし込み**ます。
