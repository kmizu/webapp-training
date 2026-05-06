from collections.abc import Iterator
from datetime import date as _date
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import repositories as repo
from ..db import connection

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def get_conn() -> Iterator[psycopg.Connection]:
    with connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


PRIORITY_LABEL = {1: "高", 2: "中", 3: "低"}
templates.env.globals["PRIORITY_LABEL"] = PRIORITY_LABEL


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    conn: Conn,
    filter: Literal["all", "open", "done"] = "all",
    q: str | None = None,
):
    todos = repo.list_todos(conn, filter_=filter, q=q)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"todos": todos, "filter": filter, "q": q or ""},
    )


@router.get("/partials/list", response_class=HTMLResponse)
def list_partial(
    request: Request,
    conn: Conn,
    filter: Literal["all", "open", "done"] = "all",
    q: str | None = None,
):
    todos = repo.list_todos(conn, filter_=filter, q=q)
    return templates.TemplateResponse(request, "_list.html", {"todos": todos})


@router.post("/htmx/todos", response_class=HTMLResponse)
def htmx_create(
    request: Request,
    conn: Conn,
    title: Annotated[str, Form()],
    due_on: Annotated[str, Form()] = "",
    priority: Annotated[int, Form()] = 2,
):
    parsed_due = _date.fromisoformat(due_on) if due_on else None
    repo.create_todo(conn, title=title, due_on=parsed_due, priority=priority)
    todos = repo.list_todos(conn, filter_="all")
    return templates.TemplateResponse(request, "_list.html", {"todos": todos})


@router.post("/htmx/todos/{todo_id}/toggle", response_class=HTMLResponse)
def htmx_toggle(request: Request, conn: Conn, todo_id: int):
    repo.toggle_done(conn, todo_id)
    t = repo.get_todo(conn, todo_id)
    return templates.TemplateResponse(request, "_row.html", {"t": t})


@router.delete("/htmx/todos/{todo_id}", response_class=HTMLResponse)
def htmx_delete(conn: Conn, todo_id: int):
    repo.delete_todo(conn, todo_id)
    return HTMLResponse("")
