# 第11章 リポジトリ（Write系）とタグの多対多

前章で読み取りができました。今度は **書き込み系**を実装します。

- 作成（INSERT）
- 部分更新（UPDATE）
- 削除（DELETE）
- 完了/未完了の切替（toggle）
- タグの付け替え（多対多の扱い）

## 11.1 ToDo を作る：`create_todo`

```python
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
```

`RETURNING` で **作ったばかりの行を 1 回で取得**します。
タグが指定されていれば、別関数 `attach_tags` で関連付けます（後述）。

## 11.2 完了/未完了を切り替える：`toggle_done`

```python
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
```

`SET done = NOT done` のように **DB 側の値を反転**させると、
読み取って書き戻す競合（取得と更新の間に別の人が変えるリスク）を避けられます。

## 11.3 削除する：`delete_todo`

```python
def delete_todo(conn: psycopg.Connection, todo_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        return cur.rowcount > 0
```

`todo_tags` の関連は **第9章で `ON DELETE CASCADE` を入れたので自動で消えます**。

## 11.4 部分更新：`update_todo`（重要）

ここがいちばん工夫が要るところです。
**「指定なし」と「明示的に NULL（期限を消したい）」を区別**したい。

普通に `due_on: date | None = None` にしてしまうと、`update_todo(t.id)` と
`update_todo(t.id, due_on=None)` の区別がつきません。

そこで **sentinel** を使います。

```python
from typing import Any

_UNSET: Any = object()


def update_todo(
    conn: psycopg.Connection,
    todo_id: int,
    *,
    title: str | None = None,
    due_on: date | None | Any = _UNSET,
    priority: int | None = None,
    done: bool | None = None,
    tag_names: list[str] | None = None,
) -> Todo | None:
    sets: list[str] = []
    params: list = []
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if due_on is not _UNSET:           # ← ここがポイント
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
```

呼び方:

```python
# title だけ変える（他はそのまま）
repo.update_todo(conn, t.id, title="変更後")

# 期限を消したい（明示的に NULL）
repo.update_todo(conn, t.id, due_on=None)

# 期限を入れたい
repo.update_todo(conn, t.id, due_on=date(2026, 6, 1))
```

!!! tip "API 側ではどう使う？"
    第14章の FastAPI ルーターでは、Pydantic の `model_dump(exclude_unset=True)`
    を使って、**リクエストに含まれていたキーだけ**を repository に渡します。
    `_UNSET` を使うのはリポジトリ層、JSON で来たかどうかを見るのは API 層、と
    役割を分けるとすっきりします。

## 11.5 タグの多対多：`attach_tags` / `replace_tags`

タグは「無ければ作って、関連付ける」処理が要ります。

```python
def attach_tags(conn: psycopg.Connection, todo_id: int, names: list[str]) -> None:
    if not names:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
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

- **`ON CONFLICT DO NOTHING`** で「既にあれば無視」。
  `tags.name` の UNIQUE 制約のおかげで、同じ名前を 2 回入れてもエラーにならない。
- 名前から `id` を引くために `WHERE name = ANY(%s)` を使っています。
- `replace_tags` は **「現在のタグを全消し → 新しいセットを付ける」** という素直な実装。
  量が少ないので差分計算をせずシンプルにしています。

## 11.6 動作確認

```python
# scripts/try_write.py
from datetime import date
from app.db import connection
from app import repositories as repo

with connection() as conn:
    t = repo.create_todo(
        conn, title="ジムに行く",
        due_on=date(2026, 5, 30),
        priority=1,
        tag_names=["健康", "週次"],
    )
    print("created:", t.id, [g.name for g in t.tags])

    repo.toggle_done(conn, t.id)
    print("toggled")

    repo.replace_tags(conn, t.id, ["健康"])
    print("tags replaced")

    print("delete:", repo.delete_todo(conn, t.id))
```

## やってみよう

1. `update_todo` を呼ぶときに、**`title` だけ更新したのに `priority` も上書きされていないか**を
   `psql` で確認する（updated_at だけが変わるはず）。
2. **同じ ToDo に同じタグを 2 回 attach** してみて、`todo_tags` に重複が入らないことを確認する。
3. **存在しない `id` で `update_todo` / `toggle_done` / `delete_todo`** を呼んだとき、
   それぞれが `None` / `False` を返すことを確認する。

次は [第 12 章 データアクセス層のテスト](12-data-tests.md) で、
**ここまで書いた関数に pytest でテストを書きます**。
