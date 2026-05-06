# 第13章 FastAPI入門 起動とDI

データ層ができたので、その上に **HTTP API** を載せます。
本研修では [FastAPI](https://fastapi.tiangolo.com/) を使います。
理由はシンプルで、**型ヒントがそのまま入力チェックと OpenAPI ドキュメントになる**から。

この章では「**FastAPI の最小構成と、依存性注入で接続を渡す形**」までを扱います。

## 13.1 最小のアプリ

`app/main.py` の最初の形:

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="ToDo App", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True}
```

起動:

```bash
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/docs   ← Swagger UI（自動生成のAPIドキュメント）
```

ブラウザで `http://127.0.0.1:8000/docs` を開くと、
**Swagger UI** が見えます。これだけで API の動作確認画面が手に入る。

## 13.2 ルーターを分ける

エンドポイントが増えてきたら、`routers/` ディレクトリに分けます。

```python
# app/routers/todos.py
from fastapi import APIRouter

router = APIRouter(tags=["todos"])


@router.get("/todos")
def list_todos():
    return [{"id": 1, "title": "サンプル"}]
```

`main.py` で組み込み:

```python
# app/main.py
from fastapi import FastAPI
from .routers import todos

app = FastAPI(title="ToDo App", version="0.1.0")
app.include_router(todos.router, prefix="/api")
```

これで `GET /api/todos` が動きます。

## 13.3 依存性注入（DI）の考え方

FastAPI の `Depends` は **「呼び出されたときに必要な値を作って差し込む」** 仕組みです。
わかりやすい例:

```python
from fastapi import Depends


def get_user_agent(request) -> str:
    return request.headers.get("user-agent", "unknown")


@router.get("/whoami")
def whoami(ua: str = Depends(get_user_agent)):
    return {"ua": ua}
```

`whoami` が呼ばれるたびに、FastAPI が `get_user_agent` を実行して `ua` に渡してくれます。
**「使う側が値を作るやり方を知らなくていい」**のが利点。

## 13.4 DI で DB 接続を渡す

ToDo アプリでは、各リクエストで **プールから接続を借りる**形にします。
これを DI でやると、ルーター本体がスッキリします。

```python
# app/routers/todos.py
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from ..db import connection

router = APIRouter(tags=["todos"])


def get_conn() -> Iterator[psycopg.Connection]:
    """リクエスト毎にプールから接続を借りる依存。"""
    with connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


@router.get("/todos")
def list_todos(conn: Conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, title FROM todos ORDER BY id")
        return cur.fetchall()
```

ポイント:

- **`Iterator` + `yield`** で書くと、yield の前が事前準備、yield の後が後始末になります。
  `with connection() as conn:` を使っているので、プールへの返却も自動。
- **`Annotated[..., Depends(...)]`** は FastAPI のお作法。再利用しやすいので別名にしてあります。
- ルーター内で `with connection()` を毎回書かなくていい。

!!! tip "DI でテストが楽になる"
    DI を使うと、テスト時に `app.dependency_overrides[get_conn] = ...` で
    「テスト用の接続を返す関数」に差し替えできます。研修ではテスト用 DB を分けないので
    この恩恵は薄いですが、**実務では強力な武器**です。

## 13.5 リクエスト中にトランザクションをまとめる

`get_conn` は `with connection() as conn:` を使っているので、
**1 リクエスト中の全 SQL が同じトランザクション**で実行されます。
ルーター内で例外が起きれば自動でロールバック、正常に終われば自動でコミット。

```python
@router.post("/todos")
def create_todo(payload: dict, conn: Conn):
    # この2つは同じトランザクションで実行される
    with conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s) RETURNING id", (payload["title"],))
        new_id = cur.fetchone()["id"]
        cur.execute("INSERT INTO todo_tags (todo_id, tag_id) VALUES (%s, %s)", (new_id, 1))
    return {"id": new_id}
```

中で例外を投げれば、**1 つめの INSERT も巻き戻されます**。

## 13.6 Swagger UI を試す

`http://127.0.0.1:8000/docs` を開くと、`/api/todos` が表示されます。
「Try it out」を押せば、ブラウザから直接リクエストを投げて結果を確認できます。

開発中はこれを **テストランナー代わりに**使うと捗ります。

## やってみよう

1. `GET /health` の他に、`GET /api/version` で `{"version": "0.1.0"}` を返す
   エンドポイントを追加する。
2. `get_conn` を **わざとエラーにする**（DSN を壊す）と、`/api/todos` のレスポンスが
   どう変わるか観察する。
3. **依存関数を別の依存関数から呼ぶ**ネスト構造を作ってみる
   （例: `get_request_id` を `get_conn` から呼ぶ）。

次は [第 14 章 CRUD API実装とテスト](14-api-crud.md) で、
**ToDo の CRUD を全部実装し、TestClient でテスト**します。
