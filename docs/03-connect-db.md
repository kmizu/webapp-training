# 第3章 PythonとDBをつなぐ

ここからが本番です。**Python から PostgreSQL を操作する**方法を確認します。
本研修では [`psycopg`](https://www.psycopg.org/psycopg3/) のバージョン 3 を使います。

## 3.1 psycopg を入れる

ToDo アプリ用のディレクトリを使います。すでに `sample/todo-app/` を
用意しているので、そこに移動して依存を入れます。

```bash
cd sample/todo-app
uv sync
```

`pyproject.toml` には次のような `dependencies` が並んでいます。

```toml
[project]
name = "todo-app"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "psycopg[binary]>=3.2",
    "fastapi>=0.115",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "uvicorn[standard]>=0.30",
]
```

!!! note "`psycopg[binary]` の `[binary]` とは"
    PostgreSQL のクライアントライブラリ（libpq）を **Python の wheel に同梱**してくれます。
    これがないと環境に依存して入らないことがあるので、研修では `[binary]` 付きを推奨します。

## 3.2 接続するいちばん簡単なコード

接続情報は `DSN` という文字列にまとめます。

```python
# scripts/check_connection.py
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        row = cur.fetchone()
        print(row)
```

実行:

```bash
uv run python scripts/check_connection.py
```

`with psycopg.connect(...)` を使うと、**ブロックを抜けるときに自動で接続が閉じる**
だけでなく、**例外が起きていなければ COMMIT、起きていれば ROLLBACK** されます。
これは psycopg v3 の親切設計のひとつです。

## 3.3 SQL を投げる：execute と fetch

行を入れる:

```python
with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (title) VALUES (%s) RETURNING id",
            ("牛乳を買う",),
        )
        new_id = cur.fetchone()[0]
        print("inserted id =", new_id)
```

行を取り出す:

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title, done FROM todos ORDER BY id")
    for row in cur.fetchall():
        print(row)   # tuple 形式で返る
```

!!! warning "プレースホルダは必ず `%s`"
    SQL の値を埋め込むときは、**絶対に文字列連結や f-string を使わない**でください。
    SQL インジェクションの原因になります。

    ```python
    # NG（やってはいけない）
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")

    # OK
    cur.execute("SELECT * FROM users WHERE name = %s", (name,))
    ```

    `%s` は psycopg 専用の書き方で、Python の文字列フォーマット（`%`）と
    **似ているけど別物**です。データ型は psycopg が自動で適切にエスケープしてくれます。

## 3.4 行を「辞書」で受け取る

タプルだとカラムの順番を覚えないといけなくて面倒です。
`row_factory` を使うと **辞書（dict）** で受け取れます。

```python
import psycopg
from psycopg.rows import dict_row

with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title, done FROM todos ORDER BY id")
    for row in cur.fetchall():
        print(row["id"], row["title"], row["done"])
```

第5章では **データクラスに変換する `class_row`** も使います。

## 3.5 トランザクションをきちんと意識する

psycopg v3 は **明示的にコミットしない限り変更が保存されません**。
`with` ブロックを正常に抜けると自動で COMMIT、例外を投げると ROLLBACK です。

```python
def add_todo(title: str) -> int:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (title) VALUES (%s) RETURNING id",
            (title,),
        )
        return cur.fetchone()[0]
    # ↑ ここを抜けるときに COMMIT
```

途中で例外が起きるとどうなるか、試してみましょう。

```python
def buggy() -> None:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", ("成功する",))
        cur.execute("INSERT INTO todos (title) VALUES (%s)", (None,))  # ← NOT NULL 違反
```

`title` は `NOT NULL` なので 2 つめの INSERT で例外が出ます。
**最初の INSERT も巻き戻される（保存されない）** ことを `psql` で確認してください。

## 3.6 接続情報を環境変数にする

DSN にパスワードをハードコードするのは危険です。**環境変数**から読みましょう。

```python
# app/db.py（最終版に近い形）
import os
import psycopg
from psycopg.rows import dict_row

def build_dsn() -> str:
    return (
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'tododb')} "
        f"user={os.getenv('DB_USER', 'todo')} "
        f"password={os.getenv('DB_PASSWORD', 'todo')}"
    )

def get_connection() -> psycopg.Connection:
    return psycopg.connect(build_dsn(), row_factory=dict_row)
```

`.env.example` ファイルを作って、必要な環境変数の **名前だけ** Git 管理し、
実際の値は `.env`（Git 管理外）に置くのが定石です。

```env
# .env.example
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tododb
DB_USER=todo
DB_PASSWORD=change-me
```

## 3.7 コネクションプール（軽く触れるだけ）

Web アプリで毎リクエストごとに `connect` するとレイテンシが大きいので、
本来は **コネクションプール** を使います。psycopg には `psycopg_pool` という
別パッケージがあります。

```python
from psycopg_pool import ConnectionPool

pool = ConnectionPool(conninfo=build_dsn(), min_size=1, max_size=5)

def fetch_todos() -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM todos ORDER BY id")
        return cur.fetchall()
```

第6章で FastAPI と組み合わせたときに本格的に使います。

## 3.8 よくあるエラーと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `connection refused` | PostgreSQL が起動していない | `docker compose ps` で確認、`up -d` し直す |
| `password authentication failed` | パスワードが違う | `.env` を見直す |
| `relation "todos" does not exist` | テーブルが作られていない | 第5章のマイグレーションを実行する |
| `null value in column ... violates not-null constraint` | 必須カラムを入れ忘れ | INSERT の値とカラム数を確認 |
| `current transaction is aborted` | 直前の SQL がエラーになって、まだ ROLLBACK していない | `with` を抜ける、`conn.rollback()` を呼ぶ |

## やってみよう

1. 上の `check_connection.py` を **エラーになるように DSN を壊して**みる。
   例: `port=9999` にして接続失敗を体験する。エラーメッセージを読み取る練習。
2. `INSERT ... RETURNING id` を使って ToDo を 3 件入れ、生成された `id` を Python 側で出力する。
3. **わざと例外を投げる**コードを書いて、ロールバックの挙動を `psql` で確認する。

次は [第 4 章 ToDoアプリの設計](04-design.md) で、
**何を作るのか / どう作るのか** をコードに入る前に決めます。
