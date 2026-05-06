from datetime import date
from typing import Any

import psycopg

from .models import Tag, Todo


# Sentinel: "due_on を渡さない" と "明示的に NULL" を区別するため
_UNSET: Any = object()


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
    if due_on is not _UNSET:
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
