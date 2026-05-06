# 第14章 CRUD API実装とテスト

前章で FastAPI の基本と DI が動きました。
この章では **ToDo の CRUD すべて**を実装し、Pydantic でバリデーションを入れ、
最後に TestClient で **API のテスト**まで書きます。

## 14.1 入出力スキーマ（schemas.py）

API の **入力**と**出力**を Pydantic で定義します。
ドメインモデル（dataclass）と分けることで、API の都合と DB の都合を切り分けます。

```python
# app/schemas.py
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Annotated[int, Field(ge=1, le=3)]


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    done: bool
    due_on: date | None
    priority: Priority
    tags: list[TagOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_on: date | None = None
    priority: Priority = 2
    tags: list[str] = Field(default_factory=list)


class TodoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_on: date | None = None
    priority: Priority | None = None
    done: bool | None = None
    tags: list[str] | None = None


class TodoListQuery(BaseModel):
    filter: Literal["all", "open", "done"] = "all"
    q: str | None = None
```

!!! note "`from_attributes=True` の意味"
    Pydantic v2 で `from_attributes=True` を付けると、
    **dataclass や ORM オブジェクトから直接変換**できます。
    つまり `TodoOut.model_validate(my_todo_dataclass)` のように書けます。

## 14.2 ルーター本体（routers/todos.py）

`Conn` の依存（前章）はそのまま使います。

```python
# app/routers/todos.py
from collections.abc import Iterator
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from .. import repositories as repo
from ..db import connection
from ..schemas import TodoCreate, TodoListQuery, TodoOut, TodoPatch

router = APIRouter(tags=["todos"])


def get_conn() -> Iterator[psycopg.Connection]:
    with connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


_UNSET: Any = object()


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
```

ポイント:

- **`exclude_unset=True`** で「リクエストに含まれていたキーだけ」を取り出し、
  そのうえで `due_on` が含まれていたかどうかを `_UNSET` 判定で repository に渡す。
- ステータスコードは作成 201、削除 204。これは REST の慣習。

## 14.3 動作確認

サーバーを立ち上げて、`curl` で叩いてみます。

```bash
uv run uvicorn app.main:app --reload
```

別のターミナルから:

```bash
# 一覧
curl -s http://127.0.0.1:8000/api/todos | jq .

# 作成
curl -s -X POST http://127.0.0.1:8000/api/todos \
  -H 'content-type: application/json' \
  -d '{"title":"パスポート更新", "priority":1, "tags":["役所"]}' | jq .

# 完了切替
curl -s -X POST http://127.0.0.1:8000/api/todos/1/toggle | jq .

# 部分更新（期限を消す）
curl -s -X PATCH http://127.0.0.1:8000/api/todos/1 \
  -H 'content-type: application/json' \
  -d '{"due_on": null}' | jq .

# 削除
curl -s -X DELETE http://127.0.0.1:8000/api/todos/1 -i
```

ブラウザで `http://127.0.0.1:8000/docs` を開くと、
**Swagger UI** で同じ API を画面から試せます。

## 14.4 API のテスト

`tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_create_then_list(client):
    r = client.post("/api/todos", json={"title": "API経由で追加"})
    assert r.status_code == 201
    new_id = r.json()["id"]

    r = client.get("/api/todos", params={"filter": "open"})
    assert r.status_code == 200
    assert any(t["id"] == new_id for t in r.json())


def test_toggle_changes_done(client):
    new = client.post("/api/todos", json={"title": "切替テスト"}).json()
    assert new["done"] is False
    r = client.post(f"/api/todos/{new['id']}/toggle")
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_patch_clears_due_on(client):
    new = client.post(
        "/api/todos",
        json={"title": "PATCHで期限消す", "due_on": "2026-06-15"},
    ).json()
    assert new["due_on"] == "2026-06-15"

    r = client.patch(f"/api/todos/{new['id']}", json={"due_on": None})
    assert r.status_code == 200
    assert r.json()["due_on"] is None


def test_validation_fails_on_empty_title(client):
    r = client.post("/api/todos", json={"title": ""})
    assert r.status_code == 422


def test_validation_fails_on_bad_priority(client):
    r = client.post("/api/todos", json={"title": "x", "priority": 5})
    assert r.status_code == 422


def test_404_on_unknown_id(client):
    r = client.patch("/api/todos/9999999", json={"title": "no-op"})
    assert r.status_code == 404


def test_delete_removes(client):
    new = client.post("/api/todos", json={"title": "消す"}).json()
    r = client.delete(f"/api/todos/{new['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/todos/{new['id']}")
    assert r2.status_code == 404
```

実行:

```bash
uv run pytest -v
```

!!! warning "テスト DB と本物 DB"
    `TestClient` は実際のサーバーは立ち上げず、**直接アプリを叩きます**。
    ただし DB アクセスは本物の PostgreSQL に行きます。
    本研修ではこれで十分ですが、CI でガチに分離したい場合は `tododb_test`
    のような別 DB を用意し、各テストの後にクリーンアップする仕組みを入れてください。

## 14.5 補足：psycopg のエラーをアプリ全体で受ける

`HTTPException` を投げれば自動でエラー JSON を返してくれますが、
**全体で統一したい**ときは例外ハンドラを書きます。

```python
# app/main.py（追記例）
from fastapi import Request
from fastapi.responses import JSONResponse
import psycopg.errors as pgerr


@app.exception_handler(pgerr.UniqueViolation)
async def unique_violation_handler(_: Request, exc: pgerr.UniqueViolation):
    return JSONResponse(
        status_code=409,
        content={"detail": "重複エラー"},
    )
```

詳しくは第17章で扱います。

## やってみよう

1. `/api/todos` の **クエリパラメータに `priority` を追加**する（指定された優先度のみ返す）。
2. **入力バリデーションを破る**リクエストを投げて、422 が返ることを確認する。
   例: `priority=5` や `title=""`、`due_on="2026-13-40"`。
3. `test_api.py` に **新しいテストを 1 つ追加**する。
   例: 「title だけ送って作成すると、priority が 2 で作られる」。

これで Part 5 はおしまいです。
次は [第 15 章 Jinja2でHTML](15-ui-jinja2.md) で、
**画面**を作っていきます。
