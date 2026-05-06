# 第5章 データアクセス層を作る

設計が固まったので、まずは **DB 周りのコード**を書きます。
ここを先にしっかり作っておくと、第6章の API がぐっと楽になります。

## 5.1 ドメインモデル（models.py）

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

## 5.2 接続管理（db.py）

第3章で書いた `db.py` をプール対応にします。

```python
# app/db.py
import os
from collections.abc import Iterator
from contextlib import contextmanager

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
    """プロセスで 1 つだけ持つコネクションプール。"""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=build_dsn(),
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

!!! warning "テスト時はプールを使い回さない"
    pytest を並列で動かしているとプールの再利用で問題が出ることがあります。
    `tests/conftest.py` でテストごとに独立した接続を作る方法を後で示します。

## 5.3 リポジトリ（repositories.py）

**「SQL を書く場所」** をここに集約します。
他の層から SQL を直接呼ばないルールにすると、後で **DB 種別を変える**ときや
**SQL を一括で見直す**ときに楽になります。

```python
# app/repositories.py
from datetime import date

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


def create_todo(
    conn: psycopg.Connection,
    *,
    title: str,
    due_on: date | None = None,
    priority: int = 2,
    tag_names: list[str] | None = None,
) -> Todo:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO todos (title, due_on, priority)
            VALUES (%s, %s, %s)
            RETURNING id, title, done, due_on, priority, created_at, updated_at
            """,
            (title, due_on, priority),
        )
        todo = _row_to_todo(cur.fetchone())

    if tag_names:
        attach_tags(conn, todo.id, tag_names)
        todo.tags = list_tags_for_todo(conn, todo.id)

    return todo


def list_todos(
    conn: psycopg.Connection,
    *,
    filter_: str = "all",   # "all" | "open" | "done"
    q: str | None = None,
) -> list[Todo]:
    where = []
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


def update_todo(
    conn: psycopg.Connection,
    todo_id: int,
    *,
    title: str | None = None,
    due_on: date | None = ...,   # 「指定なし」と「明示的に NULL」を区別する
    priority: int | None = None,
    done: bool | None = None,
    tag_names: list[str] | None = None,
) -> Todo | None:
    sets: list[str] = []
    params: list = []
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if due_on is not ...:        # ← ここがポイント
        sets.append("due_on = %s")
        params.append(due_on)
    if priority is not None:
        sets.append("priority = %s")
        params.append(priority)
    if done is not None:
        sets.append("done = %s")
        params.append(done)

    if sets:
        sets.append("updated_at = now()")
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE todos SET {', '.join(sets)} WHERE id = %s",
                (*params, todo_id),
            )
            if cur.rowcount == 0:
                return None

    if tag_names is not None:
        replace_tags(conn, todo_id, tag_names)

    return get_todo(conn, todo_id)


def toggle_done(conn: psycopg.Connection, todo_id: int) -> Todo | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE todos
               SET done = NOT done,
                   updated_at = now()
             WHERE id = %s
            """,
            (todo_id,),
        )
        if cur.rowcount == 0:
            return None
    return get_todo(conn, todo_id)


def delete_todo(conn: psycopg.Connection, todo_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        return cur.rowcount > 0


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


def attach_tags(conn: psycopg.Connection, todo_id: int, names: list[str]) -> None:
    if not names:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO tags (name) VALUES (%s)
            ON CONFLICT (name) DO NOTHING
            """,
            [(n,) for n in names],
        )
        cur.execute(
            "SELECT id, name FROM tags WHERE name = ANY(%s)",
            (names,),
        )
        tag_ids = [row["id"] for row in cur.fetchall()]
        cur.executemany(
            """
            INSERT INTO todo_tags (todo_id, tag_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            [(todo_id, tid) for tid in tag_ids],
        )


def replace_tags(conn: psycopg.Connection, todo_id: int, names: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todo_tags WHERE todo_id = %s", (todo_id,))
    attach_tags(conn, todo_id, names)
```

ポイント:

- **`row_factory=dict_row`** で「カラム名アクセス」できるようにしているので、
  `row["title"]` のように書ける。
- **`update_todo` の `due_on=...`** に注目。引数のデフォルト値に `...`（Ellipsis）を使うと、
  「指定なし」と「明示的に `None`（期限を消したい）」を **区別**できます。
  `None` をデフォルトにすると、この区別ができません。
- **`title ILIKE %s`** は大文字小文字を無視した部分一致。日本語にはあまり関係ないですが、
  英語タイトルを混ぜたときに役に立ちます。
- **N+1 問題**を避けるため、ToDo 一覧のタグはひとまとめに `ANY(%s)` で取ってきます。
  これを各 ToDo ごとに発行すると、ToDo が多いほど DB 往復が増えてしまいます。

## 5.4 マイグレーションの実行スクリプト（cli.py）

`uv run python -m app.cli init-db` で、初期スキーマと種データを入れられるようにします。

```python
# app/cli.py
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

## 5.5 マイグレーションファイル

`migrations/001_init.sql`:

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

`migrations/002_seed.sql`（動作確認用のサンプルデータ）:

```sql
INSERT INTO todos (title, due_on, priority) VALUES
    ('牛乳を買う',          CURRENT_DATE + 1, 2),
    ('健康診断の予約',      CURRENT_DATE + 2, 1),
    ('過去の領収書を整理',  NULL,             3),
    ('家賃を振り込む',      CURRENT_DATE + 18, 1);

INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康') ON CONFLICT DO NOTHING;

INSERT INTO todo_tags (todo_id, tag_id)
SELECT t.id, g.id
  FROM todos t
  JOIN tags  g ON g.name = '家事'
 WHERE t.title = '牛乳を買う'
ON CONFLICT DO NOTHING;
```

## 5.6 リポジトリのテスト

DB を実際に立てて、**本物の PostgreSQL に対してテストを書きます**。
モックではなく実物を使うほうが、SQL のミスをちゃんと拾えます。

`tests/conftest.py`:

```python
import os
import psycopg
import pytest
from psycopg.rows import dict_row

DSN = (
    f"host={os.getenv('DB_HOST', 'localhost')} "
    f"port={os.getenv('DB_PORT', '5432')} "
    f"dbname={os.getenv('DB_NAME', 'tododb')} "
    f"user={os.getenv('DB_USER', 'todo')} "
    f"password={os.getenv('DB_PASSWORD', 'todo')}"
)


@pytest.fixture
def conn():
    """各テスト関数ごとに、ロールバック前提の接続を渡す。"""
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=False) as c:
        try:
            yield c
        finally:
            c.rollback()
```

`tests/test_repositories.py`:

```python
from datetime import date
from app import repositories as repo


def test_create_and_get(conn):
    todo = repo.create_todo(conn, title="テスト用", priority=1)
    assert todo.id > 0
    fetched = repo.get_todo(conn, todo.id)
    assert fetched is not None
    assert fetched.title == "テスト用"
    assert fetched.priority == 1


def test_filter_open_done(conn):
    a = repo.create_todo(conn, title="やること")
    b = repo.create_todo(conn, title="完了済")
    repo.toggle_done(conn, b.id)

    open_ids = {t.id for t in repo.list_todos(conn, filter_="open")}
    done_ids = {t.id for t in repo.list_todos(conn, filter_="done")}

    assert a.id in open_ids
    assert b.id in done_ids
    assert a.id not in done_ids


def test_search_with_q(conn):
    repo.create_todo(conn, title="ミーティングの議事録")
    repo.create_todo(conn, title="家賃を振り込む")
    found = repo.list_todos(conn, q="議事")
    assert any(t.title == "ミーティングの議事録" for t in found)


def test_update_clears_due_on(conn):
    t = repo.create_todo(conn, title="期限あり", due_on=date(2026, 5, 30))
    updated = repo.update_todo(conn, t.id, due_on=None)  # 「明示的に NULL」
    assert updated is not None
    assert updated.due_on is None


def test_tags_attach_and_list(conn):
    t = repo.create_todo(conn, title="ジム", tag_names=["健康", "週次"])
    fetched = repo.get_todo(conn, t.id)
    assert fetched is not None
    names = sorted(g.name for g in fetched.tags)
    assert names == ["健康", "週次"]


def test_delete_cascades_tags(conn):
    t = repo.create_todo(conn, title="削除予定", tag_names=["仕事"])
    assert repo.delete_todo(conn, t.id) is True
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM todo_tags WHERE todo_id = %s", (t.id,))
        assert cur.fetchone()["n"] == 0
```

実行:

```bash
uv run pytest -v
```

!!! tip "テスト用 DB を分けるとさらに安心"
    本研修では `tododb` をそのまま使いますが、実務ではテスト用に
    `tododb_test` のような別 DB を用意して、CI で破棄/再生成するのが定石です。

## やってみよう

1. `repositories.list_todos` に **「期限切れ（`done=FALSE` かつ `due_on < CURRENT_DATE`）」**
   というフィルタを追加してみる（仕様変更）。
2. その変更に対応するテストを 1 件追加する。
3. `executemany` を `cur.execute("... VALUES %s", ...)` に置き換える方法を psycopg のドキュメントで調べてみる（性能の話に触れる）。

次は [第 6 章 Web APIを作る](06-web-api.md) で、
**この層の上に FastAPI を載せます**。
