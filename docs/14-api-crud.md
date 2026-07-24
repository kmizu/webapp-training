# 第14章 CRUD API実装とテスト

前章で FastAPI の基本と DI が動きました。
この章では **ToDo の CRUD すべて**を実装し、Pydantic でバリデーションを入れ、
最後に TestClient で **API のテスト**まで書きます。

## 14.1 入出力スキーマ（schemas.py）

API の **入力**と**出力**を [Pydantic](https://docs.pydantic.dev/latest/) で定義します。
第10章で見たように、**ドメインモデル（`models.py` の dataclass）と API スキーマ（ここの Pydantic モデル）は別物**でした。
ここではさらに一歩進んで、Pydantic 側も1つのクラスにまとめず、
`TodoOut`（出力用）・`TodoCreate`（作成用）・`TodoPatch`（部分更新用）の3つに分けています。

理由は単純で、**操作ごとに必須な項目が違う**からです。`TodoCreate` は新規作成なので `title` が必須ですが、
`TodoPatch` は「送られてきたフィールドだけ変える」部分更新のために全フィールドを `Optional` にしています。
もし1つのクラスで済ませようとすると、「作成のときは必須・更新のときは任意」という操作依存の制約を
型では表現できず、コードのあちこちに手書きの `if` チェックが増えてしまいます。

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

`Priority = Annotated[int, Field(ge=1, le=3)]` のように、[`Annotated`](https://docs.python.org/3/library/typing.html)
と Pydantic の `Field` を組み合わせて型エイリアスにしておくと、「優先度は1〜3の整数」という制約
（`ge`/`le` はそれぞれ「以上」「以下」の意味）を `TodoOut` と `TodoCreate` の両方で使い回せます。
同じように `TodoListQuery.filter` の `Literal["all", "open", "done"]` は、この3つの文字列**以外**を
受け付けない型です。範囲外の値（例えば `filter=archived`）を送ると、ルーター関数が呼ばれる前に
自動で 422 が返ります。

!!! note "`from_attributes=True` の意味"
    Pydantic v2 で `from_attributes=True` を付けると、
    **dataclass や ORM オブジェクトから直接変換**できます。
    つまり `TodoOut.model_validate(my_todo_dataclass)` のように書けます。
    これを付けないと `model_validate()` は辞書のような入力しか受け付けず、dataclass を渡すと
    バリデーションエラーになります。repository が返す `Todo` dataclass をそのまま
    `TodoOut.model_validate(todo)` に渡せているのは、この設定のおかげです。

## 14.2 ルーター本体（routers/todos.py）

`Conn` の依存（前章）はそのまま使います。ここでは ToDo に対する一覧・作成・取得・部分更新・
完了切替・削除という6つの操作を、それぞれ意味の合う
[HTTPメソッド](https://developer.mozilla.org/ja/docs/Web/HTTP/Methods)（GET / POST / PATCH / DELETE）
に割り当てます。

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

!!! note "FastAPI はパラメータの由来をどう見分けるか"
    このルーターには3種類のパラメータが登場します。FastAPI は関数シグネチャだけを見て、それぞれが**どこから来る値か**を自動的に判断してくれます。

    - パスの `{todo_id}` と同じ名前の引数は[パスパラメータ](https://fastapi.tiangolo.com/tutorial/path-params/)として扱われます（`get_todo(todo_id: int, ...)` など）。`/todos/abc` のように `int` に変換できない値を渡すと、ルーター関数が呼ばれる前に自動で 422 が返ります。
    - Pydantic モデルの型を持つ引数は[リクエストボディ](https://fastapi.tiangolo.com/tutorial/body/)として扱われ、JSON をパースしてバリデーションします（`create_todo(payload: TodoCreate, ...)` の `payload`）。
    - それ以外の単純な型の引数は[クエリパラメータ](https://fastapi.tiangolo.com/tutorial/query-params/)（`?key=value` の部分）として扱われます。`list_todos` では `TodoListQuery` を `Depends()` に渡すことで、`filter` と `q` という2つのクエリパラメータを1つの型にまとめて受け取っています。

    型と引数名の組み合わせだけでこれが決まるので、覚えてしまえば迷うことはありません。

ポイント:

- **`model_dump(exclude_unset=True)`** の `model_dump()` は Pydantic モデルを普通の `dict` に変換するメソッドです。
  `exclude_unset=True` を付けると「実際にリクエストに含まれていたキーだけ」が残った辞書になります。
  第11章で見た「未指定」と「明示的な NULL」を区別する話を思い出してください。API層ではこの
  `exclude_unset` でキーの有無を判定し、その結果を `_UNSET` 判定としてそのままリポジトリ層に
  引き渡す、という役割分担になっています。

!!! note "ステータスコードの使い分け（第8章の実装編）"
    第8章で決めた[ステータスコード](https://developer.mozilla.org/ja/docs/Web/HTTP/Status)の使い分けが、実際にどうコードに現れているか確認しておきましょう。

    - **201 Created**: `@router.post("/todos", ..., status_code=status.HTTP_201_CREATED)` のように、デコレータの引数で明示しています。
    - **204 No Content**: 同じように `status_code=status.HTTP_204_NO_CONTENT` を指定し、ボディを持たない `Response` を返しています。
    - **404 Not Found**: repository が `None` を返してきた箇所で、自分で `raise HTTPException(status_code=404, detail=...)` しています。
    - **422 Unprocessable Entity**: コード上のどこにも `422` という文字は出てきません。`TodoCreate` / `TodoPatch` のバリデーションに失敗すると、**ルーター関数が呼ばれる前に** FastAPI が自動で返してくれるからです。

    404 と 422 の違いはここが分かれ目です。**422 はリクエストの形そのものが壊れているとき**、**404 はリクエストの形は正しいが対象が見つからないとき**、と覚えておくと迷いません。

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

!!! tip "手動確認と自動テストの役割分担"
    `curl` も Swagger UI も、**人間がその場で1回動かして確認する**ための道具です。
    「今動くかどうか」をサッと見るのには向いていますが、確認するたびに自分の手で
    リクエストを組み立て直す必要があり、同じ確認を何度も繰り返す用途には向きません。
    次の 14.4 では、この確認を `TestClient` を使ってコードにし、`pytest` で
    **何度でも自動的に繰り返せる**形にします。

## 14.4 API のテスト

`tests/test_api.py`:

[`TestClient`](https://fastapi.tiangolo.com/tutorial/testing/) を使うと、実際に `uvicorn` を
起動しなくてもアプリに直接リクエストを送れます。14.3 の「手動で1回確認する」に対して、
ここからは**同じ確認をコードとして残し、`pytest` で何度でも実行できる**形にします。
`with TestClient(app) as c:` としておくと、アプリの起動・終了処理もテストの前後で
きちんと実行されます。

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

`test_validation_fails_on_*` は 14.2 で説明した 422（バリデーション失敗）を、
`test_404_on_unknown_id` と `test_delete_removes` の後半は 404（見つからない）を、
それぞれ実際に確認しているテストです。

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

ここまでの `HTTPException` は、**ルーター関数の中で「起きるとわかっている失敗」**
（IDが見つからない、など）を自分で検知して投げるものでした。一方、DB 側の制約違反
（例えばタグ名を重複して INSERT したときに起きる `UniqueViolation`）は、
`repositories.py` の奥で psycopg の例外として発生します。これをすべてのルーター関数で
`try/except` して回るのは大変ですし、書き忘れも起きやすいところです。

そこで使うのが**[グローバル例外ハンドラ](https://fastapi.tiangolo.com/tutorial/handling-errors/)**
（`@app.exception_handler(...)`）です。「アプリのどこでこの型の例外が発生しても、
まとめてここで処理する」という仕組みで、`main.py` に一箇所書くだけで全ルーターに効きます。

これを何も用意しないと、`UniqueViolation` はキャッチされないまま FastAPI まで届き、
`main.py` にすでにある `Exception` 用のフォールバックハンドラに落ちて、**何が悪かったのか
わからない `500 Internal Server Error`** になってしまいます。専用のハンドラを用意しておけば、
`409 Conflict` のように**原因が伝わるステータスコードとメッセージ**を返せます。

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
