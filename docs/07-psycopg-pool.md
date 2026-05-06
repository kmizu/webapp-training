# 第7章 dict_rowとコネクションプール

ここまでの章で「動く」「安全に動く」までは押さえました。
この章では「**実用的に使える**」状態にします。

- 行を辞書で受け取る `dict_row`
- 接続を使い回す `ConnectionPool`
- 接続情報を環境変数化する
- よくあるエラー一覧

## 7.1 行を「辞書」で受け取る

タプルだとカラムの順番を覚えないといけなくて面倒です。
`row_factory` を使うと **辞書（dict）** で受け取れます。

```python
import psycopg
from psycopg.rows import dict_row

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title, done FROM todos ORDER BY id")
    for row in cur.fetchall():
        print(row["id"], row["title"], row["done"])
```

このアプリでは **常に `dict_row` を使う**ことにします。
カラムの並び順に依存したコードはバグの温床なので避けたい。

!!! tip "`class_row` で dataclass に変換する手もある"
    `psycopg.rows.class_row(MyClass)` を使うと、行を直接 dataclass に詰めて返せます。
    研修では「`dict_row` で取って、リポジトリ層で dataclass に詰め直す」方針です。

## 7.2 コネクションプール

Web アプリで毎リクエストごとに `connect` するとレイテンシが大きいので、
**コネクションプール**を使います。psycopg には `psycopg_pool` という別パッケージがあります。

```python
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo="host=localhost port=5432 dbname=tododb user=todo password=todo",
    min_size=1,
    max_size=5,
    kwargs={"row_factory": dict_row},
)

def fetch_todos() -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM todos ORDER BY id")
        return cur.fetchall()
```

`with pool.connection() as conn:` で **プールから接続を借り**、ブロックを抜けると
**プールに返す**動きになります。新しく `connect` するわけではないのでとても速い。

第13章（FastAPI 入門）でこのプールを依存性注入（DI）として渡せるようにします。

## 7.3 接続情報を環境変数にする

DSN にパスワードをハードコードするのは危険です。**環境変数**から読みましょう。

```python
# app/db.py（最終形に近いもの）
import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def build_dsn() -> str:
    return (
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'tododb')} "
        f"user={os.getenv('DB_USER', 'todo')} "
        f"password={os.getenv('DB_PASSWORD', 'todo')}"
    )


_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=build_dsn(),
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
    return _pool
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

設定オブジェクトとしてまとめる方法は第17章で扱います。

## 7.4 よくあるエラーと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `connection refused` | PostgreSQL が起動していない | `docker compose ps` で確認、`up -d` し直す |
| `password authentication failed` | パスワードが違う | `.env` を見直す |
| `relation "todos" does not exist` | テーブルが作られていない | 第9章のマイグレーションを実行する |
| `null value in column ... violates not-null constraint` | 必須カラムを入れ忘れ | INSERT の値とカラム数を確認 |
| `current transaction is aborted` | 直前の SQL がエラーになって、まだ ROLLBACK していない | `with` を抜ける、`conn.rollback()` を呼ぶ |
| `pool exhausted` | プールの最大数を使い切った | `with` を確実に抜けているか、`max_size` の見直し |

## 7.5 実装テンプレート

ここまでの内容をまとめると、**ToDo アプリで実際に使う `db.py`** は次のようになります。
これは第10章以降でそのまま使うコードです。

```python
# app/db.py（ToDoアプリの実装に使う最終形）
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings   # 設定オブジェクト（第17章で扱う）


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
    """`with connection() as conn:` で接続を借りるためのヘルパ。"""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
```

## やってみよう

1. `dict_row` を **使った場合と使わない場合**で、同じ `SELECT` をループで出力して
   コードの見た目を比べる。
2. プールの `max_size=2` にして、`with pool.connection()` を **3 つ並列で取り合う**
   コードを書いてどうなるか観察する（順番待ちになるはず）。
3. `.env` ファイルを作って、`DB_PASSWORD` だけ環境変数経由で読み込むコードを書く。

これで Part 2 はおしまいです。
次は [第 8 章 要件・画面・API設計](08-design-app.md) から、
**実際の ToDo アプリの設計**に入ります。
