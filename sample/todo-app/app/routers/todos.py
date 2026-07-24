from collections.abc import Iterator
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from .. import repositories as repo
from ..db import connection
from ..repositories import _UNSET
from ..schemas import TodoCreate, TodoListQuery, TodoOut, TodoPatch

router = APIRouter(tags=["todos"])


def get_conn() -> Iterator[psycopg.Connection]:
    with connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


@router.get("/todos", response_model=list[TodoOut])
def list_todos(
    conn: Conn,
    query: Annotated[TodoListQuery, Depends()],
):
    todos = repo.list_todos(conn, filter_=query.filter, q=query.q)
    return [TodoOut.model_validate(t) for t in todos]


@router.post(
    "/todos",
    response_model=TodoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_todo(payload: TodoCreate, conn: Conn):
    todo = repo.create_todo(
        conn,
        title=payload.title,
        due_on=payload.due_on,
        priority=payload.priority,
        tag_names=payload.tags,
    )
    return TodoOut.model_validate(todo)


@router.get("/todos/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int, conn: Conn):
    todo = repo.get_todo(conn, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return TodoOut.model_validate(todo)


@router.patch("/todos/{todo_id}", response_model=TodoOut)
def patch_todo(todo_id: int, payload: TodoPatch, conn: Conn):
    fields = payload.model_dump(exclude_unset=True)
    due_on_arg: Any = fields["due_on"] if "due_on" in fields else _UNSET

    updated = repo.update_todo(
        conn,
        todo_id,
        title=fields.get("title"),
        due_on=due_on_arg,
        priority=fields.get("priority"),
        done=fields.get("done"),
        tag_names=fields.get("tags"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return TodoOut.model_validate(updated)


@router.post("/todos/{todo_id}/toggle", response_model=TodoOut)
def toggle_todo(todo_id: int, conn: Conn):
    updated = repo.toggle_done(conn, todo_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return TodoOut.model_validate(updated)


@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, conn: Conn):
    if not repo.delete_todo(conn, todo_id):
        raise HTTPException(status_code=404, detail="todo not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags")
def list_tags(conn: Conn):
    return [{"id": g.id, "name": g.name} for g in repo.list_all_tags(conn)]
