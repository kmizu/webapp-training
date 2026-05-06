# 第10章 ドメインモデルとリポジトリ（Read系）

設計が固まったので、いよいよ **Python のコード**を書き始めます。
この章では「**読み取り系**」だけに絞ります。

- ドメインモデル（dataclass）の用意
- 接続ヘルパ
- 取り出し系の関数（一覧・1件取得・タグ）

書き込み系は次章で扱います。

## 10.1 ドメインモデル（models.py）

ToDo と Tag を **dataclass** で表します。
DB の行を **そのまま Python の値**にする層です。

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
    Pydantic は API 入出力（HTTP の世界）で使い、内部のドメイン型は dataclass、と
    使い分けるとレイヤーがはっきりします。

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

`config.py` は第17章で扱いますが、いまのところは第7章の `build_dsn()` をそのまま
使ってもかまいません。

## 10.3 リポジトリの考え方

「SQL を書く場所」を **`repositories.py` に集める**ルールにします。
他の層から SQL を直接呼ばないことで、後で SQL を一括で見直すときに楽になります。

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

`dict_row` で取った行を、ヘルパ関数で dataclass に詰め直します。

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

1 件分のタグも取ってきて、`Todo.tags` に詰めて返します。

## 10.5 タグの取得

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

ポイント:

- **`title ILIKE %s`** は大文字小文字を無視した部分一致。
- **WHERE 句の動的組み立て**は `where` リストに条件を追加して `AND` で結合する素朴な方式。
  プレースホルダ `%s` は順番に対応します。

!!! warning "N+1 問題に注意"
    各 ToDo ごとに「この ToDo のタグを取る」クエリを発行すると、
    ToDo が多いほど DB 往復が増えてしまいます（N+1 問題）。
    `ANY(%s)` でまとめて 1 クエリに減らすのが定石です。

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
