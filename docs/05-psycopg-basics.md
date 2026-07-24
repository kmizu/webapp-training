# 第5章 psycopg入門 接続と基本のCRUD

ここからが本番です。**Python から PostgreSQL を操作する**方法を確認します。
PostgreSQL はソケット越しに独自のプロトコルでやり取りするサーバーなので、
Python の標準機能だけでは直接話しかけられません。そこで間を取り持つ
**ドライバライブラリ**が必要になります。
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

`psycopg-pool` や `fastapi` / `jinja2` などは後の章（第7章・第13章以降）で使うものです。
今の時点では「そういうものも一緒に入っている」くらいの認識で構いません。
この章で主役になるのは `psycopg` 本体だけです。

!!! note "`psycopg[binary]` の `[binary]` とは"
    PostgreSQL のクライアントライブラリ（libpq）を **Python の wheel に同梱**してくれます。
    これがないと環境に依存して入らないことがあるので、研修では `[binary]` 付きを推奨します。

## 5.2 接続するいちばん簡単なコード

接続情報は `DSN`（Data Source Name、接続文字列）という 1 本の文字列にまとめます。
ホスト名やパスワードを毎回バラバラの引数で渡すのではなく `key=value` を並べて
1 か所にまとめておくことで、設定ファイルや環境変数との受け渡しがしやすくなります
（DSN の書き方は [psycopgの基本的な使い方](https://www.psycopg.org/psycopg3/docs/basic/usage.html) に一覧があります）。

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

`psycopg.connect(DSN)` が作る `conn` は **コネクション**（PostgreSQL サーバーとの通信路そのもの）、
`conn.cursor()` が作る `cur` は **カーソル**（SQL を送って結果を受け取るための手元の窓口）です。
1 本のコネクションの中に複数のカーソルを開くこともできますが、この章ではひとまず
「コネクション 1 つにつきカーソル 1 つ」で進めます。

`with psycopg.connect(...)` を使うと、**ブロックを抜けるときに自動で接続が閉じる**
だけでなく、**例外が起きていなければ COMMIT、起きていれば ROLLBACK** されます。
接続を閉じ忘れると PostgreSQL 側にコネクションが残ったままになり、積み重なると
やがて最大接続数に達して新しい接続ができなくなるので、これは地味に効いてくる保証です。
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

`cur.execute(...)` は SQL を実行するだけで、結果はいったん**カーソルの中に保持**
されます。そこから `fetchone()`（1 行）・`fetchmany(n)`（n 行）・`fetchall()`
（全行）で必要な分だけ取り出す、という二段構えです。
**大量データに `fetchall()` を使わない** ようにだけ注意してください
（メモリに全行載せる）。件数が多いときは `fetchmany(n)` で少しずつ処理するとよいでしょう。

なお `row` の各要素は `SELECT` に書いた**カラムの順番そのまま**のタプルです。
今回の例だと `row[0]` が `id`、`row[1]` が `title` になります。名前でアクセス
したい場合は `dict_row`（第7章で扱います）を使うと読みやすくなります。

## 5.4 INSERT で行を追加する

```python
with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute(
        "INSERT INTO todos (title, priority) VALUES (%s, %s)",
        ("牛乳を買う", 2),
    )
```

**プレースホルダ `%s`** で値を渡すのが超重要なポイントです。文字列連結で SQL を
組み立てる代わりに `%s` へ値を渡すと、psycopg が Python の型（`str` / `int` /
`bool` / `None` など）を見て、適切な形にエスケープ・変換してから SQL に埋め込んで
くれます（[psycopgのパラメータの渡し方](https://www.psycopg.org/psycopg3/docs/basic/params.html)）。
安全性の詳しい話（SQL インジェクション）は次章で扱いますが、
**絶対に文字列連結や f-string で値を埋め込まないでください**。

`INSERT` を実行しただけでは、DB 側で自動採番された `id` が何になったかは
Python 側にはわかりません。`RETURNING id` を付けると、**INSERT と同じ 1 回の
やり取りで**生成された値を受け取れるので、わざわざ別の `SELECT` を投げて
調べ直す必要がなくなります。

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

ループで 1 件ずつ `execute` すると、そのたびに Python と PostgreSQL の間で
通信が発生します。`executemany` はまとめて送るぶん通信回数が減るので、
たくさん入れる場合はその方が速いです。

## やってみよう

1. 上の `check_connection.py` を **エラーになるように DSN を壊して**みる。
   例: `port=9999` にして接続失敗を体験する。エラーメッセージを読み取る練習。
2. `INSERT ... RETURNING id` を使って ToDo を 3 件入れ、生成された `id` を Python 側で出力する。
3. `executemany` で 10 件まとめて入れて、`SELECT COUNT(*)` で件数を確認する。

次は [第 6 章 プレースホルダとトランザクション](06-psycopg-tx.md) で、
**安全に値を渡す**話と、トランザクションの正しい使い方を扱います。
