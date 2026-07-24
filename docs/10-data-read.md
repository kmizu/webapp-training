# 第10章 ドメインモデルとリポジトリ（Read系）

設計が固まったので、いよいよ **Python のコード**を書き始めます。
この章では「**読み取り系**」だけに絞ります。

- ドメインモデル（dataclass）の用意
- 接続ヘルパ
- 取り出し系の関数（一覧・1件取得・タグ）

書き込み系は次章で扱います。

## 10.1 ドメインモデル（models.py）

ToDo と Tag を [**dataclass**](https://docs.python.org/3/library/dataclasses.html) で表します（第1章のおさらいです）。
DB の行を **そのまま Python の値**にする層です。

ここで「DB の行」と「ドメインモデル」をあえて別の型として扱うのには理由があります。
psycopg が `dict_row` で返す行は `row["due_on"]` のような**文字列キーの辞書**なので、キー名を
打ち間違えてもエディタは教えてくれず、実行して初めて `KeyError` で気づく、ということが起こります。
`Todo` を dataclass にしておけば `todo.due_on` という**属性アクセス**になり、型ヒントのぶんだけ
エディタの補完や静的解析が効くようになります。さらに、DB のカラム構成が変わっても、影響をこのあと
書く `_row_to_todo` のような変換関数の中に閉じ込められるので、カラム名の変更がアプリ全体に
波及しにくくなる、という利点もあります。

```python
# app/models.py
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
    priority: int           # 1=高, 2=中, 3=低
    created_at: datetime
    updated_at: datetime
    tags: list[Tag] = field(default_factory=list)
```

!!! tip "なぜ Pydantic ではなく dataclass？"
    dataclass は **依存ゼロ・軽量**で、変換ロジックを自分で書きたいときに素直です。
    [Pydantic](https://docs.pydantic.dev/latest/) は API 入出力（HTTP の世界）で使い、内部のドメイン型は dataclass、と
    使い分けるとレイヤーがはっきりします。Pydantic はバリデーションと JSON との変換を自動でやって
    くれる分、HTTP リクエストの形（JSON のキーや型）に内部の値まで引きずられやすくなります。
    ドメイン用の型を dataclass として別に持っておくと、「外から来た形」と「アプリの中で扱いたい形」
    を切り離せます。

## 10.2 接続ヘルパ（db.py）

第7章の最後で書いたものをそのまま使います。

```python
# app/db.py
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

`get_pool()` は [コネクションプール](https://www.psycopg.org/psycopg3/docs/advanced/pool.html) を
モジュール変数 `_pool` に**1つだけ**保持しておき、2回目以降の呼び出しでは同じプールを使い回します。
プールの中身自体が複数の DB 接続を張った重いオブジェクトなので、呼ばれるたびに作り直してしまうと
プールを使う意味がなくなります。`kwargs={"row_factory": dict_row}` は第7章で見た設定で、この
プールから借りるすべての接続で行を辞書として受け取れるようにしています（詳しくは
[psycopg3 の row factory](https://www.psycopg.org/psycopg3/docs/advanced/rows.html) を参照）。

`connection()` は [`contextlib.contextmanager`](https://docs.python.org/3/library/contextlib.html) を
使って自作した、独自の[コンテキストマネージャ](02-python-context.md)です。関数の中に `yield` を
1つ書くだけで、`yield` より前が `with` に**入るとき**の処理、`with` のブロックを抜けたあとが
`yield` より後の処理として実行されます。ここでは `yield` の前でプールから接続を借り、
`with pool.connection() as conn:` のブロックを抜けたタイミングで接続がプールに返却されます。
こう包んでおくことで、この先のリポジトリ関数は `get_pool()` の存在を意識せず、
`with connection() as conn:` と書くだけで安全に接続を借りられます。

`config.py` は第17章で扱いますが、いまのところは第7章の `build_dsn()` をそのまま
使ってもかまいません。

## 10.3 リポジトリの考え方

「SQL を書く場所」を **`repositories.py` に集める**ルールにします。
他の層から SQL を直接呼ばないことで、後で SQL を一括で見直すときに楽になります。

たとえば `todos` テーブルにカラムを1つ追加したくなったとき、SQL がアプリのあちこち（API のハンドラ、
テンプレートのロジック、バッチ処理…）に散らばっていると、影響範囲を洗い出すだけでも一苦労です。
SQL の置き場所を `repositories.py` に統一しておけば、「`todos` に関わるクエリを全部見る」がそのまま
このファイル1つを読むことと同じになります。API 層やテスト側は `get_todo(conn, 1)` のような
**関数呼び出し**しか知らなくてよくなるので、SQL の書き方（今は生 SQL ですが、将来 ORM に変える、
といった判断）を後から差し替える余地も残せます。

```python
# app/repositories.py
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
```

`dict_row` で取った行（辞書）を、ヘルパー関数で dataclass に詰め直します。`_row_to_tag` と
`_row_to_todo` を専用の関数として切り出しておくことで、このあと出てくる Read 系の関数
（`get_todo`・`list_todos`・`list_all_tags` など）が同じ変換コードを重複して書かずに済みます。
先頭がアンダースコアの関数名は、`repositories.py` の外からは呼ばれない**内部用のヘルパー**である
ことを示す、Python の慣習的な印です。

## 10.4 1 件取得：`get_todo`

```python
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
```

取得した行が `None` なら、その `id` の ToDo は存在しないということです。戻り値の型 `Todo | None`
のとおり、そのまま `None` を返して呼び出し側に判断を委ねます（呼び出し側でどう扱うか——たとえば
404 を返す、といった処理は第14章で API 側に実装します）。

1 件分のタグは `list_tags_for_todo` を呼んで追加のクエリで取ってきて、`Todo.tags` に詰めて返します。
ここでは ToDo が1件だけなので追加クエリは1本で済みますが、次の 10.6 節の `list_todos` で同じやり方
（一覧の ToDo 1件ごとにタグを引く）をしてしまうと、後述する **N+1 問題**を引き起こします。

## 10.5 タグの取得

タグまわりは2つの関数を用意します。**`list_all_tags`** は `tags` テーブルをそのまま返すだけですが、
**`list_tags_for_todo`** は「ある ToDo に紐づくタグ」を取ってくるので、第9章で作った中間テーブル
`todo_tags` を経由した[テーブルの結合（`JOIN`）](https://www.postgresql.org/docs/current/queries-table-expressions.html)
が必要になります。`tags` と `todo_tags` を `tag_id` で結合し、`WHERE tt.todo_id = %s` で対象の ToDo
に絞り込む、という組み立てです。「多対多の関係は中間テーブルで表す」のは第9章で見た設計で、
ここではそれを実際に取り出すコードとして確認しておきましょう。

```python
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

## 10.6 一覧取得：`list_todos`

ここがちょっと長くなります。**フィルタと検索**を扱うため、
WHERE 句を動的に組み立てます。

```python
def list_todos(
    conn: psycopg.Connection,
    *,
    filter_: str = "all",   # "all" | "open" | "done"
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

    # タグを 1 クエリでまとめて引いてくる（N+1 を避ける）
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
```

2つ目のクエリが返す行は `(todo_id, tag_id, tag_name)` の組が、ToDo × タグの数だけ並んだものです。
`for row in cur.fetchall(): for t in todos: ...` の二重ループで、`row["todo_id"]` が一致する
`Todo` オブジェクトを探し出し、その `tags` にタグを追加しています。ToDo の件数が多いとループ回数は
それなりに増えますが、これはあくまで**Python のメモリ上での処理**であり、DB への往復（ネットワーク
のやりとり）が増えるわけではありません。下の warning で説明する N+1 問題で本当に問題になるのは
DB への往復回数なので、この程度のループ自体は気にしなくて大丈夫です。

ポイント:

- **`title ILIKE %s`** は大文字小文字を無視した部分一致です。`LIKE` との違いは大文字小文字を
  区別しない点だけで、`%` を前後に挟むことで部分一致を表現しています。`f"%{q}%"` は
  **プレースホルダに渡す値の中身**を組み立てているだけで、SQL 文字列そのものを組み立てている
  わけではないので、第6章で注意した「文字列連結によるSQLインジェクション」には当たりません。
- **WHERE 句の動的組み立て**は `where` リストに条件を追加して `AND` で結合する素朴な方式です。
  [プレースホルダ](https://www.psycopg.org/psycopg3/docs/basic/params.html) `%s` は**書かれた順番**
  で `params` の値と対応するので、`where.append(...)` と `params.append(...)` は必ずペアで、同じ
  順番に追加するのがポイントです（片方だけ足し忘れると、値がずれて意図しないパラメータが
  渡ってしまいます）。
- **`ORDER BY done ASC, due_on NULLS LAST, priority ASC, id ASC`** は「未完了を先に→期限が近い順
  →優先度順→ID順」に並べる指定です。`due_on` は値なし（`NULL`）を許すカラムなので、
  `NULLS LAST` を付けないと PostgreSQL のデフォルトでは `NULL` が先頭に来てしまいます（期限なしの
  ToDo が一番上に来るのは直感に反しますよね）。この `done, due_on` という並び順は、第9章で作った
  複合[インデックス](https://www.postgresql.org/docs/current/indexes.html) `idx_todos_done_due` の
  カラム順と揃えてあります。揃えておくと、PostgreSQL がこのインデックスをソートにも活用できる
  可能性が上がります。実際に使われているかは
  [`EXPLAIN`](https://www.postgresql.org/docs/current/sql-explain.html) で確認できるので、
  「やってみよう」3番で試してみましょう。

!!! warning "N+1 問題に注意"
    もし `list_todos` の中で `for t in todos: t.tags = list_tags_for_todo(conn, t.id)` のように
    書いてしまうと、一覧を取る 1 回のクエリに加えて、ToDo の件数ぶんだけタグ取得クエリが飛びます。
    ToDo が 100 件あれば、単純計算で 1 + 100 = 101 回のクエリが発生します。これが **N+1 問題**と
    呼ばれる典型的な性能劣化パターンです。1 回の SQL 実行にはネットワーク往復や DB 側の処理コスト
    がかかるので、件数に比例してクエリ回数が増える書き方は、データが増えるほど致命的に遅くなります。
    `ANY(%s)` でまとめて 1 クエリに減らすのが定石です（第6章でも見た書き方です）。

## 10.7 動作確認

`psql` でデータを入れてから、Python から呼んでみます。

```python
# scripts/try_read.py
from app.db import connection
from app import repositories as repo

with connection() as conn:
    for t in repo.list_todos(conn, filter_="open"):
        print(t.id, t.title, [g.name for g in t.tags])
```

```bash
uv run python -m scripts.try_read
```

## やってみよう

1. `list_todos` に **「期限切れ（`done=FALSE` かつ `due_on < CURRENT_DATE`）」**
   というフィルタ値を追加してみる。
2. ` repository.list_open_count(conn) -> int` を追加して、
   `SELECT COUNT(*) FROM todos WHERE done = FALSE` の結果を返す関数を書く。
3. `EXPLAIN` を `psql` で実行して、`list_todos(filter_="open")` が
   `idx_todos_done_due` を使っているか確認する。

次は [第 11 章 リポジトリ（Write系）とタグの多対多](11-data-write.md) で、
**書き込み系の関数**を実装します。
