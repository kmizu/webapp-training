# 第10章 ドメインモデルとリポジトリ（Read系）

第9章で、DB 側の土台（テーブルと初期データ）ができました。
この章から、いよいよ **ToDo アプリの Python コード**を書き始めます。
第8章で約束したとおり、ここからは写経式で進めます。
読者の皆さんが作るのは `mytodo/` の中のファイルで、
リポジトリの `sample/todo-app/` は**答え合わせ用の完成版**です。

この章ではまず「**読み取り系**」だけに絞ります。
書き込み系（追加・更新・削除）は第11章で、この章が作るファイルに追加していきます。

## 10.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- レイヤー分けとは何か、「DB の行」と「ドメインモデル」の違いを説明できる
- `mytodo/` を uv プロジェクトにして、依存パッケージをインストールできる
- `config.py` / `db.py` / `models.py` / `repositories.py`（Read系）/ `cli.py` を
  写経し、`diff` で完成版と答え合わせできる
- `uv run python -m app.cli init-db` でマイグレーションの管理を cli に切り替えられる
- Read 系のリポジトリ関数で ToDo とタグを読み出せる

**所要時間の目安: 120 分**

この章で作るファイルは 6 つと、動作確認用の小さなスクリプトが 1 つです。
量はありますが、1 つずつ写経しては `diff` で答え合わせする、
という同じリズムの繰り返しです。

## 10.2 前提知識

コードに入る前に、このアプリ全体を貫く 2 つの考え方を押さえておきます。

!!! note "レイヤー分けとは"
    Web アプリのコードは、**役割ごとにファイル（層）を分けて**書くのが定石です。
    この研修の ToDo アプリでは、最終的に次のような分担になります。

    ```text
    app/
    ├── routers/        HTTP の入口（第13〜14章）
    ├── services.py     業務ロジック（第14章）
    ├── repositories.py SQL を実行する層（この章と第11章）
    ├── models.py       アプリ内で使う「もの」の型（この章）
    └── db.py           DB との接続の世話（この章）
    ```

    なぜ分けるのでしょうか。たとえば「`todos` テーブルにカラムを 1 つ足したい」
    となったとき、SQL が画面のコードや API のコードに散らばっていると、
    影響範囲を洗い出すだけで一苦労です。「SQL は `repositories.py` にだけ書く」
    と決めておけば、見直す場所は 1 ファイルに限定できます。
    **変更が起きたときに、直す場所がどこか即座にわかる**ようにするのが
    レイヤー分けの目的です。

!!! note "DB の行とドメインモデルは別もの"
    psycopg が `dict_row`（第7章）で返す DB の行は、
    `row["due_on"]` のような**文字列キーの辞書**です。
    キー名を打ち間違えてもエディタは教えてくれず、
    実行して初めて `KeyError` で気づくことになります。

    そこで、DB から取り出した行はすぐ **ドメインモデル**
    （このアプリで扱う「もの」を表す dataclass。第1章のおさらいです）に
    詰め替えてから使います。`Todo` を dataclass にしておけば
    `todo.due_on` という**属性アクセス**になり、型ヒントのぶんだけ
    エディタの補完や静的解析が効きます。さらに、DB のカラム構成が変わっても、
    影響を「辞書から dataclass への変換関数」の中に閉じ込められるので、
    カラム名の変更がアプリ全体に波及しにくくなります。

    !!! tip "なぜ Pydantic ではなく dataclass？"
        dataclass は**依存ゼロ・軽量**で、変換ロジックを自分で書きたいときに素直です。
        [Pydantic](https://docs.pydantic.dev/latest/) は API 入出力（HTTP の世界）で使い、
        内部のドメイン型は dataclass、と使い分けるとレイヤーがはっきりします。
        Pydantic は第13章で登場します。

## 10.3 ここまでのファイル構成

まず現在地を確認します。第9章までに作ったのは `mytodo/migrations/` だけです。

```text
mytodo/                     第8章で作成
└── migrations/             第9章で作成・tododb に適用済み
    ├── 001_init.sql
    └── 002_seed.sql
```

（第9章の「やってみよう」に取り組んだ人は、ここに `003_add_memo.sql`
もあるはずです。そのままで大丈夫です。）

この章が終わると、こうなります。

```text
mytodo/
├── pyproject.toml          この章で作成
├── uv.lock                 uv sync が自動生成
├── .venv/                  uv sync が自動生成
├── app/
│   ├── __init__.py         この章で作成（空ファイル）
│   ├── config.py           この章で作成
│   ├── db.py               この章で作成
│   ├── cli.py              この章で作成
│   ├── models.py           この章で作成
│   └── repositories.py     この章で作成（Read系のみ。Write系は第11章で追加）
├── migrations/
│   ├── 001_init.sql
│   └── 002_seed.sql
└── try_read.py             この章で作成（動作確認用の使い捨て）
```

写経するコードはすべて、完成版 `sample/todo-app/` の実ファイルと同じ内容です。
各ファイルを書き終えるたびに `diff` で答え合わせをし、
**差分なし**をゴールに進んでいきます。

## 10.4 pyproject.toml を作って uv sync する

最初に、`mytodo/` を独立した uv プロジェクトにします。
リポジトリのルートにある `pyproject.toml` は研修テキストのサイト用で、
これから作る `mytodo/pyproject.toml` は ToDo アプリ用の**別物**です。

`mytodo/pyproject.toml` を作成して、次の内容を書き写してください。

```toml
[project]
name = "todo-app"
version = "0.1.0"
description = "研修用 ToDo アプリ"
requires-python = ">=3.12"
dependencies = [
    "psycopg[binary]>=3.2",
    "psycopg-pool>=3.2",
    "fastapi>=0.115",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"

[tool.uv]
package = false
```

各セクションの意味:

- `[project]` …… プロジェクト名と依存パッケージの一覧。
  `psycopg` と `psycopg-pool` はこの章で使います。
  `fastapi` や `jinja2` などは第13章以降で使いますが、
  あとから追記する手間を省くため、完成版と同じく最初から全部書いておきます。
- `[dependency-groups]` の `dev` …… 開発中だけ使うパッケージ
  （第12章のテストで使う `pytest` など）。
- `[tool.pytest.ini_options]` …… pytest の設定（第12章で効いてきます）。
- `[tool.uv]` の `package = false` …… このプロジェクト自体を
  パッケージとしてインストールしない、という指定です。
  「アプリケーション（配布しない）」の定番の設定です。

書き終わったら、完成版と差分がないことを確認します
（`diff` コマンドは**リポジトリのルート**で実行してください）。

```bash
diff -u mytodo/pyproject.toml sample/todo-app/pyproject.toml
```

何も表示されなければ完成版と一致しています（差分なしがゴールです）。

続けて、依存パッケージをインストールします。
ここから `uv` や `python` を動かすコマンドは、**`mytodo/` の中**で実行します
（第9章までのリポジトリルートとは場所が変わるので注意してください）。

```bash
cd mytodo
uv sync
```

期待される出力（バージョンや件数はタイミングによって変わります）:

```text
Using CPython 3.13.x
Creating virtual environment at: .venv
Resolved 36 packages in ...
Installed 33 packages in ...
 + annotated-doc==...
 + ...
```

`uv sync` は `pyproject.toml` を読んで、必要なパッケージを `mytodo/.venv/`
にインストールします。同時に、依存関係の解決結果を `uv.lock` に記録します。
第0章でルートのプロジェクトに対してやったのと同じ操作を、
今度は `mytodo/` に対して行った形です。

## 10.5 設定と接続: `__init__.py` / `config.py` / `db.py`

`app/` ディレクトリを作り、土台になる 3 ファイルを写経します。

```bash
mkdir app
```

### `app/__init__.py`（空ファイル）

`mytodo/app/__init__.py` を**中身は空のまま**作成してください。
このファイルは「`app/` は Python のパッケージである」という目印です
（第2章で見たとおりです）。空でないと `from app.db import ...` のような
import ができません。

### `app/config.py`

`mytodo/app/config.py` を作成して、次の内容を書き写してください。

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "tododb")
    db_user: str = os.getenv("DB_USER", "todo")
    db_password: str = os.getenv("DB_PASSWORD", "todo")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password}"
        )


settings = Settings()
```

DB の接続先などの設定を、**環境変数**から読むクラスです。
`os.getenv("DB_HOST", "localhost")` は「環境変数 `DB_HOST` があればその値、
なければ `localhost`」という意味です。デフォルト値は、
第0章で立てた Docker の PostgreSQL（`localhost:5432`、ユーザー `todo` /
パスワード `todo` / DB `tododb`）と一致しているので、
研修の環境では環境変数を何も設定しなくても動きます。

`dsn` は第7章で自分で書いた `build_dsn()` と同じものを、
`@property` として持たせた形です。`settings.dsn` と書くだけで
接続文字列が得られます。`frozen=True` は「作成後に書き換えられない
dataclass」という指定で、設定がうっかり書き換わるのを防ぎます。

設定まわりの本格的な話（ログレベルや `.env` ファイル）は第17章で扱います。
いまは「**接続先を環境変数で差し替えられる入れ物**」と理解しておけば十分です。

### `app/db.py`

`mytodo/app/db.py` を作成して、次の内容を書き写してください。

```python
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings


_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.dsn,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
    return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
```

第7章の最後で `practice/` に書いた `get_pool()` / `connection()` と
ほぼ同じものです。違いは接続文字列を `settings.dsn` から取る点だけです。
おさらいすると:

- `get_pool()` …… コネクションプールを**最初に呼ばれたときだけ**作り、
  モジュール変数 `_pool` に保持します。2 回目以降は同じプールを使い回します。
- `connection()` …… `@contextmanager` で作った自作のコンテキストマネージャ
  （第2章・第7章）で、呼び出し側は `with connection() as conn:` と書くだけで
  プールから接続を借り、ブロックを抜けると自動で返却できます。
- `kwargs={"row_factory": dict_row}` …… このプールから借りるすべての接続で、
  行を辞書として受け取る設定です。

2 つのファイルを写経し終えたら、まとめて答え合わせします
（リポジトリのルートで実行してください）。

```bash
diff -u mytodo/app/__init__.py sample/todo-app/app/__init__.py
diff -u mytodo/app/config.py sample/todo-app/app/config.py
diff -u mytodo/app/db.py sample/todo-app/app/db.py
```

3 つとも何も表示されなければ一致です。

## 10.6 cli.py: マイグレーション管理の切り替え

第9章ではマイグレーションを `psql -f` で手で流し込みました。
そして「`cli.py` の写経は第10章で `db.py` を作ってから」と予告していました。
`db.py` ができたので、ここで `cli.py` を写経し、
**マイグレーションの管理を cli に引き継ぎます**。

`mytodo/app/cli.py` を作成して、次の内容を書き写してください。

```python
import argparse
from pathlib import Path

from .db import connection

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def init_db() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_versions (
                    version    TEXT        PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT version FROM schema_versions")
            applied = {row["version"] for row in cur.fetchall()}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in applied:
                print(f"  skip  {version} (already applied)")
                continue
            print(f"apply  {version}")
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_versions (version) VALUES (%s)",
                    (version,),
                )


def reset_db() -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DROP TABLE IF EXISTS todo_tags;
            DROP TABLE IF EXISTS tags;
            DROP TABLE IF EXISTS todos;
            DROP TABLE IF EXISTS schema_versions;
            """
        )
    print("reset done")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="マイグレーションを適用する")
    sub.add_parser("reset-db", help="ぜんぶ消す（怖い）")
    args = parser.parse_args()
    if args.cmd == "init-db":
        init_db()
    elif args.cmd == "reset-db":
        reset_db()


if __name__ == "__main__":
    main()
```

仕組みのポイント:

- **`schema_versions` テーブル** …… 「どのマイグレーションファイルを
  適用済みか」を DB 自身に記録するテーブルです。`init_db()` はまず
  これを作り（なければ）、適用済みの一覧を読みます。
- **`MIGRATIONS_DIR.glob("*.sql")`** …… `migrations/` の SQL ファイルを
  ファイル名順に 1 つずつ見ていき、適用済みなら `skip`、
  未適用なら実行して `schema_versions` に記録します。
  第9章の「`psql -f` で 2 回流すと `todos` が重複して入る」問題が、
  この仕組みで構造的に防げます。
- **`argparse` のサブコマンド** …… `python -m app.cli init-db` のように、
  ハイフン付きの名前で 2 つのコマンドを使い分けます。

### 実行する前に: 一度リセットが必要です

ここで 1 つ注意があります。あなたの `tododb` には、
第9章で `psql -f` で適用したテーブルが**すでに入っています**。
この状態でいきなり `init-db` を実行すると、`schema_versions` には
何も記録されていないため、`001_init.sql` をもう一度適用しようとして
「テーブルはもうある」というエラー（`DuplicateTable`）で止まります。

そこで、今回に限り **`reset-db` で一度まっさらにしてから `init-db` で作り直す**
ことで、管理を cli に切り替えます。中身は同じマイグレーションファイルから
作られるので、結果的に同じテーブルと同じ初期データに戻ります。

`mytodo/` の中で次を実行してください。

```bash
uv run python -m app.cli reset-db
```

期待される出力:

```text
reset done
```

続けて:

```bash
uv run python -m app.cli init-db
```

期待される出力:

```text
apply  001_init
apply  002_seed
```

（第9章の「やってみよう」で `003_add_memo.sql` を作った人は、
`apply  003_add_memo` の行も表示されます。）

もう一度同じコマンドを実行してみます。

```bash
uv run python -m app.cli init-db
```

期待される出力:

```text
  skip  001_init (already applied)
  skip  002_seed (already applied)
```

適用済みのファイルはスキップされました。これが
「どこまで適用したかを DB に記録する」方式の効果です。

!!! note "実行のたびに `couldn't stop thread ...` と出る場合"
    `uv run python -m app.cli ...` のあとに、
    `couldn't stop thread 'pool-1-worker-0' within 5.0 seconds`
    のような行が何行か表示されることがあります。
    これは「スクリプトの終了時に、コネクションプールの後片付けが
    間に合わなかった」という**警告**で、データ処理自体は成功しています。
    第13章以降の Web アプリとして動かす形では出てきません。
    詳しくは 10.11 のつまずきポイントを参照してください。

最後に、psql で状態を確認しておきます
（接続の手順は第3章と同じです）。

```text
\dt
```

期待される出力:

```text
            List of relations
 Schema |      Name       | Type  | Owner 
--------+-----------------+-------+-------
 public | schema_versions | table | todo
 public | tags            | table | todo
 public | todo_tags       | table | todo
 public | todos           | table | todo
(4 rows)
```

`schema_versions` が増えていれば、管理の切り替えは完了です。

`app/cli.py` の答え合わせもしておきます（リポジトリのルートで）。

```bash
diff -u mytodo/app/cli.py sample/todo-app/app/cli.py
```

何も表示されなければ一致です。

## 10.7 ドメインモデル: models.py

いよいよアプリの中身です。まず、10.2 で説明した**ドメインモデル**を
定義する `models.py` を写経します。

`mytodo/app/models.py` を作成して、次の内容を書き写してください。

```python
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Tag:
    id: int
    name: str


@dataclass
class Todo:
    id: int
    title: str
    done: bool
    due_on: date | None
    priority: int
    created_at: datetime
    updated_at: datetime
    tags: list[Tag] = field(default_factory=list)
```

フィールドは第9章で作った `todos` テーブルのカラムと 1 対 1 で対応し、
最後に「その ToDo に付いたタグの一覧」を入れる `tags` だけを足した形です。
`field(default_factory=list)` は「`tags` を省略したら空リストにする」
という指定で、第1章で見たとおり、可変なデフォルト値を安全に書くための
決まり文句です。`due_on: date | None` は「`date` 型か `None`」
（期限なしを許す）という意味で、テーブル定義で `NOT NULL` を
付けなかったことに対応しています。

答え合わせ（リポジトリのルートで）:

```bash
diff -u mytodo/app/models.py sample/todo-app/app/models.py
```

## 10.8 リポジトリ（Read系）: repositories.py

この章の主役です。10.2 のレイヤー分けの考え方に沿って、
「SQL を書く場所」を **`repositories.py` に集める**ルールにします。
API 層やテスト側は `get_todo(conn, 1)` のような**関数呼び出し**だけを知り、
SQL の中身はこのファイルに閉じ込めます。

!!! warning "この章では Read 系だけ写経します"
    完成版の `repositories.py` には、Read 系（取得）と Write 系
    （作成・更新・削除）の関数が両方入っていますが、
    **この章で写経するのは Read 系だけ**です。
    Write 系は第11章で、このファイルに**追記**します。
    そのため、この時点で完成版と `diff` を取ると
    「Write 系のぶんだけ完成版のほうが長い」という差分が出ます。
    それが正しい状態です（差分の見方は 10.9 で説明します）。

`mytodo/app/repositories.py` を作成して、次の内容を書き写してください。

```python
import psycopg

from .models import Tag, Todo


def _row_to_tag(row: dict) -> Tag:
    return Tag(id=row["id"], name=row["name"])


def _row_to_todo(row: dict, tags: list[Tag] | None = None) -> Todo:
    return Todo(
        id=row["id"],
        title=row["title"],
        done=row["done"],
        due_on=row["due_on"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags or [],
    )


# ---------- Todo ----------


def list_todos(
    conn: psycopg.Connection,
    *,
    filter_: str = "all",
    q: str | None = None,
) -> list[Todo]:
    where: list[str] = []
    params: list = []
    if filter_ == "open":
        where.append("done = FALSE")
    elif filter_ == "done":
        where.append("done = TRUE")
    if q:
        where.append("title ILIKE %s")
        params.append(f"%{q}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT id, title, done, due_on, priority, created_at, updated_at
          FROM todos
          {where_sql}
         ORDER BY done ASC,
                  due_on NULLS LAST,
                  priority ASC,
                  id ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    todos = [_row_to_todo(r) for r in rows]
    if not todos:
        return todos

    ids = [t.id for t in todos]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tt.todo_id, g.id, g.name
              FROM todo_tags tt
              JOIN tags g ON g.id = tt.tag_id
             WHERE tt.todo_id = ANY(%s)
             ORDER BY g.name
            """,
            (ids,),
        )
        for row in cur.fetchall():
            for t in todos:
                if t.id == row["todo_id"]:
                    t.tags.append(Tag(id=row["id"], name=row["name"]))
                    break
    return todos


def get_todo(conn: psycopg.Connection, todo_id: int) -> Todo | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, done, due_on, priority, created_at, updated_at "
            "FROM todos WHERE id = %s",
            (todo_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    todo = _row_to_todo(row)
    todo.tags = list_tags_for_todo(conn, todo.id)
    return todo


# ---------- Tag ----------


def list_all_tags(conn: psycopg.Connection) -> list[Tag]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM tags ORDER BY name")
        return [_row_to_tag(r) for r in cur.fetchall()]


def list_tags_for_todo(conn: psycopg.Connection, todo_id: int) -> list[Tag]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT g.id, g.name
              FROM tags g
              JOIN todo_tags tt ON tt.tag_id = g.id
             WHERE tt.todo_id = %s
             ORDER BY g.name
            """,
            (todo_id,),
        )
        return [_row_to_tag(r) for r in cur.fetchall()]
```

長いので、上から順に見ていきます。

### `_row_to_tag` / `_row_to_todo`（変換ヘルパー）

`dict_row` で取った行（辞書）を dataclass に詰め直す、
10.2 で言うところの「変換関数」です。専用の関数に切り出してあるので、
あとに出てくる取得系の関数が同じ変換コードを重複して書かずに済みます。
先頭がアンダースコアの名前は、「`repositories.py` の外からは呼ばない
**内部用ヘルパー**」であることを示す Python の慣習です。

### `get_todo`（1 件取得）

`fetchone()` が `None` なら、その `id` の ToDo は存在しないということなので、
戻り値の型 `Todo | None` のとおり `None` を返して呼び出し側に判断を委ねます
（存在しないときに 404 を返す、といった処理は第14章で API 側に実装します）。
ToDo が見つかった場合は、`list_tags_for_todo` でタグを追加のクエリで取ってきて
`Todo.tags` に詰めて返します。1 件だけなので、これでクエリは合計 2 本です。

### `list_all_tags` / `list_tags_for_todo`（タグの取得）

`list_all_tags` は `tags` テーブルをそのまま返すだけですが、
`list_tags_for_todo` は「ある ToDo に紐づくタグ」を取るため、
第9章で作った中間テーブル `todo_tags` を経由した `JOIN` が必要です。
「多対多の関係は中間テーブルで表す」という設計を、
実際に取り出すコードとして確認しておきましょう（第4章の JOIN の復習でもあります）。

### `list_todos`（一覧取得）

いちばん長い関数です。フィルタと検索を扱うため、
**WHERE 句を動的に組み立て**ています。ポイントは 3 つです。

- **`title ILIKE %s`** は大文字小文字を区別しない部分一致です。
  `f"%{q}%"` は**プレースホルダに渡す値の中身**を組み立てているだけで、
  SQL 文字列そのものを組み立てているわけではないので、
  第6章で注意した「文字列連結による SQL インジェクション」には当たりません。
- **WHERE 句の動的組み立て**では、プレースホルダ `%s` は**書かれた順番**で
  `params` の値と対応します。`where.append(...)` と `params.append(...)` は
  必ずペアで、同じ順番に追加するのがポイントです。
  片方だけ足し忘れると、値がずれて意図しないパラメータが渡ってしまいます。
- **`ORDER BY done ASC, due_on NULLS LAST, priority ASC, id ASC`** は
  「未完了を先に → 期限が近い順 → 優先度順 → ID 順」という、
  第8章の画面設計そのものの並びです。`NULLS LAST` を付けないと
  PostgreSQL のデフォルトでは期限なし（`NULL`）が先頭に来てしまいます。
  先頭の `done, due_on` は、第9章で作った複合インデックス
  `idx_todos_done_due` のカラム順と揃えてあります
  （実際にインデックスが使われるかは「やってみよう」問3で確かめます）。

!!! warning "N+1 問題に注意"
    `list_todos` の後半で、タグを `ANY(%s)` を使った **1 本のクエリ**で
    まとめて取っているのには理由があります。もし
    `for t in todos: t.tags = list_tags_for_todo(conn, t.id)` のように
    書いてしまうと、一覧を取る 1 回のクエリに加えて、
    ToDo の件数ぶんだけタグ取得クエリが飛びます。
    ToDo が 100 件あれば 1 + 100 = 101 回のクエリです。
    これが **N+1 問題**と呼ばれる典型的な性能劣化パターンで、
    データが増えるほど致命的に遅くなります。
    `ANY(%s)` には Python のリストをそのまま渡せます（第6章で見た書き方です）。

    まとめ取りしたあとの二重ループ（`for row in ...: for t in todos: ...`）は
    一見非効率に見えますが、これは **Python のメモリ上での処理**であり、
    DB への往復は増えません。N+1 問題で本当に問題になるのは
    DB への往復回数なので、この程度のループは気にしなくて大丈夫です。

## 10.9 動作確認

写経した Read 系の関数を、実際に動かしてみます。
`mytodo/try_read.py` を作成して、次の内容を書き写してください
（これは完成版にはない、**動作確認用の使い捨てスクリプト**です。
第7章の `practice/` のスクリプトと同じ位置づけです）。

```python
from app.db import connection
from app import repositories as repo

with connection() as conn:
    print("--- list_todos(open) ---")
    for t in repo.list_todos(conn, filter_="open"):
        print(t.id, t.title, [g.name for g in t.tags])

    print("--- get_todo ---")
    todo = repo.get_todo(conn, 1)
    print(todo.title, todo.due_on, todo.priority, [g.name for g in todo.tags])
    print(repo.get_todo(conn, 999))

    print("--- list_all_tags ---")
    for g in repo.list_all_tags(conn):
        print(g.id, g.name)

    print("--- list_todos(q='買') ---")
    for t in repo.list_todos(conn, q="買"):
        print(t.id, t.title)
```

`mytodo/` の中で実行します。

```bash
uv run python try_read.py
```

期待される出力（`due_on` の日付は、シードデータを適用した日によって変わります）:

```text
--- list_todos(open) ---
1 牛乳を買う ['家事']
2 健康診断の予約 ['健康']
4 家賃を振り込む []
3 過去の領収書を整理 []
--- get_todo ---
牛乳を買う 2026-08-15 2 ['家事']
None
--- list_all_tags ---
2 仕事
3 健康
1 家事
--- list_todos(q='買') ---
1 牛乳を買う
```

読み取りのポイント:

- `list_todos(open)` は 4 件すべてが未完了なので全件出ますが、
  並びが `id` 順ではありません。期限が近い順（1 日後、2 日後、18 日後）のあとに、
  期限なし（`NULLS LAST`）の「過去の領収書を整理」が来ています。
  `ORDER BY` が意図どおり効いている証拠です。
- `get_todo(conn, 999)` は存在しない `id` なので `None` が返りました。
- `list_all_tags` は `ORDER BY name` で並んでいますが、
  **日本語は五十音順にはなりません**。この研修で使う PostgreSQL
  （`postgres:16` イメージ、デフォルトの照合順序）では、
  文字列は文字のコードポイント順に並びます。`仕`（U+4ED5）→ `健`（U+5065）
  → `家`（U+5BB6）の順なので、「仕事 → 健康 → 家事」という
  一見バラバラに見える並びになります。五十音順に並べたい場合は
  照合順序（collation）やよみがな列の工夫が必要ですが、この研修では扱いません。
- `q="買"` で「買」を含むタイトルだけに絞れています。

最後に、この章で作ったファイルの答え合わせをまとめて行います
（リポジトリのルートで実行してください）。

```bash
diff -u mytodo/app/models.py sample/todo-app/app/models.py
diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py
```

`models.py` は何も表示されなければ一致です。
`repositories.py` は、10.8 で説明したとおり**差分が出るのが正しい状態**です。
次の 2 点を確認してください。

- **`-`（マイナス）で始まる行が 1 行もないこと**。
  `-` は「あなたのファイルにだけある行」なので、出ていたら写経ミスです。
- **`+`（プラス）で始まる行が、Write 系の関数
  （`create_todo` / `update_todo` / `toggle_done` / `delete_todo` /
  `attach_tags` / `replace_tags`）と、その部品
  （先頭の import 2 行 `from datetime import date` / `from typing import Any` と、
  `_UNSET` の定義まわり）だけであること**。
  `+` は「完成版にだけある行」で、これらは第11章で写経します。

## 10.10 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] レイヤー分けとは何か、「SQL は `repositories.py` に集める」理由とともに説明できる
- [ ] DB の行（辞書）とドメインモデル（dataclass）の違いと、分ける利点を説明できる
- [ ] `mytodo/pyproject.toml` を作成し、`mytodo/` の中で `uv sync` できた
- [ ] `__init__.py` / `config.py` / `db.py` / `cli.py` / `models.py` を写経し、
      `diff` で完成版との一致を確認した
- [ ] `reset-db` → `init-db` でマイグレーション管理を cli に切り替え、
      2 回目の `init-db` が `skip` になることを確認した
- [ ] `repositories.py` の `diff` で `-` の行がないことを確認した
      （`+` は Write 系だけ。第11章で写経する）
- [ ] `try_read.py` で 4 件の ToDo とタグを読み出せた
- [ ] N+1 問題とは何か、`ANY(%s)` でどう回避しているかを説明できる

## 10.11 つまずきポイント

### `couldn't stop thread 'pool-1-worker-0' within 5.0 seconds` と出る

`uv run python -m app.cli ...` や `uv run python try_read.py` の実行後に、
次のような行が標準エラー出力に出ることがあります。

```text
couldn't stop thread 'pool-1-worker-0' within 5.0 seconds
hint: you can try to call 'close()' explicitly or to use the pool as context manager
```

これはエラーではなく**警告**です。`db.py` のプールはアプリが動き続ける
前提で「閉じない」作りになっているため、一発で終わるスクリプトだと
プロセス終了時にプールの後片付けが間に合わず、このメッセージが出ます。
データ処理自体は成功しているので、そのまま進めて大丈夫です
（第13章以降の Web アプリとして動かす形では、プロセスが生き続けるため出ません）。

### `connection refused` が何度も繰り返し表示される

```text
error connecting in 'pool-1': connection failed: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

PostgreSQL が起動していません。プールが接続をリトライするため
同じ行が何度も表示され、最後に Traceback で止まります。
リポジトリのルートで `docker compose up -d` を実行してから、やり直してください
（第0章の手順どおりです）。

### `psycopg.errors.DuplicateTable: relation "todos" already exists`

`reset-db` を実行せずに `init-db` したときのエラーです。
第9章で `psql -f` により適用済みのテーブルが残っているのに、
`schema_versions` には記録がないため、`001_init.sql` の再適用に
踏み込んでしまっています。10.6 の手順どおり、
`reset-db` → `init-db` の順に実行してください。

### `ModuleNotFoundError: No module named 'app'` / `No module named 'psycopg'`

`uv run python -m app.cli ...` や `uv run python try_read.py` を
**`mytodo/` の外**（リポジトリのルートなど）で実行したときのエラーです。
`cd mytodo` で移動してから実行してください。
`mytodo/` の中で実行しているのに `No module named 'psycopg'` と出る場合は、
`uv sync`（10.4）をまだ実行していません。

## 10.12 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 「期限切れ」フィルタを追加する

`list_todos` の `filter_` に、**「期限切れ」（`done=FALSE` かつ
`due_on < CURRENT_DATE`）** を表す値 `"overdue"` を追加してください。
試すときは、過去の期限の ToDo を `psql` から 1 件入れると確認しやすいです。

??? example "解答例"

    `list_todos` の条件分岐に 1 つ追加します。

    ```python
        if filter_ == "open":
            where.append("done = FALSE")
        elif filter_ == "done":
            where.append("done = TRUE")
        elif filter_ == "overdue":
            where.append("done = FALSE AND due_on < CURRENT_DATE")
    ```

    確認用のデータ投入（psql で）:

    ```sql
    INSERT INTO todos (title, due_on, priority)
    VALUES ('期限切れテスト', CURRENT_DATE - 1, 1);
    ```

    期待される出力:

    ```text
    INSERT 0 1
    ```

    `try_read.py` などで `repo.list_todos(conn, filter_="overdue")` を呼ぶと、
    いま入れた 1 件だけが返ります。
    条件は SQL の文字列として `where` に足すだけで、
    パラメータを使わないので `params` への追加は不要です。

### 問2 未完了の件数を返す関数を書く

`repositories.py` に `list_open_count(conn) -> int` を追加して、
`SELECT COUNT(*) FROM todos WHERE done = FALSE` の結果を返してください。

??? example "解答例"

    ```python
    def list_open_count(conn: psycopg.Connection) -> int:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM todos WHERE done = FALSE")
            return cur.fetchone()["count"]
    ```

    `dict_row` で取った行では、`COUNT(*)` の結果は `"count"` というキーに
    入ります。`COUNT(*)` は 0 件のときでも必ず 1 行（値 `0`）を返すので、
    `get_todo` のような `None` チェックは不要です。

    `list_open_count(conn)` を呼ぶと `4` が返ります
    （問1のデータを入れた人は `5`）。

### 問3 インデックスが使われているか EXPLAIN で確かめる

`list_todos(filter_="open")` が投げるのと同じ SQL を `psql` で
`EXPLAIN` にかけて、第9章で作った `idx_todos_done_due` が
使われているか確認してください。使われていない場合、
その理由も考えてみてください。

??? example "解答例"

    ```sql
    EXPLAIN
    SELECT id, title, done, due_on, priority, created_at, updated_at
      FROM todos
     WHERE done = FALSE
     ORDER BY done ASC, due_on NULLS LAST, priority ASC, id ASC;
    ```

    期待される出力（行数の少ない現在の状態）:

    ```text
                              QUERY PLAN                           
    ---------------------------------------------------------------
     Sort  (cost=39.90..41.06 rows=465 width=59)
       Sort Key: done, due_on, priority, id
       ->  Seq Scan on todos  (cost=0.00..19.30 rows=465 width=59)
             Filter: (NOT done)
    (4 rows)
    ```

    **`Seq Scan`（全件走査）になり、インデックスは使われません**。
    いま `todos` には 4 行しかなく、インデックスを調べるより
    全部読むほうが速い、と PostgreSQL が正しく判断しているためです。
    インデックスは「行数が増えたときの保険」であって、
    常に使われるものではありません。

    参考として、強制的にインデックスを使わせるとこうなります。

    ```sql
    SET enable_seqscan = off;
    ```

    同じ `EXPLAIN` をもう一度実行すると:

    ```text
                                            QUERY PLAN                                        
    -----------------------------------------------------------------------------------------
     Sort  (cost=43.01..44.17 rows=465 width=59)
       Sort Key: done, due_on, priority, id
       ->  Bitmap Heap Scan on todos  (cost=7.75..22.40 rows=465 width=59)
             Recheck Cond: (NOT done)
             ->  Bitmap Index Scan on idx_todos_done_due  (cost=0.00..7.64 rows=465 width=0)
                   Index Cond: (done = false)
    (6 rows)
    ```

    `Bitmap Index Scan on idx_todos_done_due` と、
    インデックスを使う計画に切り替わりました。
    確認が終わったら `RESET enable_seqscan;` で元に戻しておきましょう
    （`SET` はその接続の中だけで有効な設定なので、
    psql を終了しても自動的に元に戻ります）。

## まとめ

- Web アプリのコードは**レイヤー分け**する。SQL は `repositories.py` に集め、
  他の層は関数呼び出しだけを知る
- DB の行（辞書）はすぐ**ドメインモデル**（dataclass）に詰め替えて使う。
  補完と静的解析が効き、カラム変更の影響を変換関数に閉じ込められる
- `mytodo/` は独立した uv プロジェクト。`pyproject.toml` を書いて
  `uv sync` すると、依存が `.venv/` に入る
- `app/cli.py` の `init-db` は `schema_versions` テーブルで適用済みを記録し、
  未適用のマイグレーションだけを当てる。今後は `psql -f` ではなく
  こちらで管理する
- `list_todos` は WHERE 句の動的組み立てと、タグの `ANY(%s)` による
  まとめ取り（**N+1 問題**の回避）がポイント

次は [第11章 リポジトリ（Write系）とタグの多対多](11-data-write.md) で、
この章で作った `repositories.py` に**書き込み系の関数を追加**します。
