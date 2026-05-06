# 第5章 psycopg入門 接続と基本のCRUD

ここからが本番です。**Python から PostgreSQL を操作する**方法を確認します。
本研修では [`psycopg`](https://www.psycopg.org/psycopg3/) のバージョン 3 を使います。

この章では「**接続して、SELECT/INSERT する**」までを扱います。

## 5.1 psycopg を入れる

ToDo アプリ用のディレクトリを使います。すでに `sample/todo-app/` を
用意しているので、そこに移動して依存を入れます。

```bash
cd sample/todo-app
uv sync
```

`pyproject.toml` には次のような `dependencies` が並んでいます。

```toml
[project]
dependencies = [
    "psycopg[binary]>=3.2",
    "psycopg-pool>=3.2",
    "fastapi>=0.115",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "uvicorn[standard]>=0.30",
]
```

!!! note "`psycopg[binary]` の `[binary]` とは"
    PostgreSQL のクライアントライブラリ（libpq）を **Python の wheel に同梱**してくれます。
    これがないと環境に依存して入らないことがあるので、研修では `[binary]` 付きを推奨します。

## 5.2 接続するいちばん簡単なコード

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
これは psycopg v3 の親切設計のひとつです（詳細は次章で）。

## 5.3 SELECT で行を取り出す

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    # まずはテーブルを用意（前章までに作っていなければ）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id          SERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            done        BOOLEAN NOT NULL DEFAULT FALSE,
            due_on      DATE,
            priority    SMALLINT NOT NULL DEFAULT 2,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    cur.execute("SELECT id, title, done FROM todos ORDER BY id")
    for row in cur.fetchall():
        print(row)   # tuple 形式で返る
```

`fetchone()` は 1 行だけ取る、`fetchmany(n)` は n 行取る、`fetchall()` は全部取る。
**大量データに `fetchall()` を使わない** ようにだけ注意してください
（メモリに全行載せる）。

## 5.4 INSERT で行を追加する

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute(
        "INSERT INTO todos (title, priority) VALUES (%s, %s)",
        ("牛乳を買う", 2),
    )
```

**プレースホルダ `%s`** で値を渡すのが超重要なポイント。
詳しくは次章で扱いますが、**絶対に文字列連結や f-string で値を埋め込まないでください**。

`RETURNING` を使えば、自動採番された `id` を取れます。

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute(
        "INSERT INTO todos (title) VALUES (%s) RETURNING id",
        ("テスト",),
    )
    new_id = cur.fetchone()[0]
    print("inserted id =", new_id)
```

!!! tip "値が 1 つでも `(value,)` と書く"
    `("テスト",)` のように **末尾のカンマ**が必要です。`("テスト")` は単なる文字列です。
    psycopg はパラメータを「タプルかリスト」として受け取ります。

## 5.5 ループで複数行を入れる

ベタ書きすると:

```python
titles = ["a", "b", "c"]
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    for t in titles:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", (t,))
```

`executemany` を使うとまとめて投げられます:

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.executemany(
        "INSERT INTO todos (title) VALUES (%s)",
        [(t,) for t in titles],
    )
```

たくさん入れる場合は `executemany` の方が速いです。

## やってみよう

1. 上の `check_connection.py` を **エラーになるように DSN を壊して**みる。
   例: `port=9999` にして接続失敗を体験する。エラーメッセージを読み取る練習。
2. `INSERT ... RETURNING id` を使って ToDo を 3 件入れ、生成された `id` を Python 側で出力する。
3. `executemany` で 10 件まとめて入れて、`SELECT COUNT(*)` で件数を確認する。

次は [第 6 章 プレースホルダとトランザクション](06-psycopg-tx.md) で、
**安全に値を渡す**話と、トランザクションの正しい使い方を扱います。
