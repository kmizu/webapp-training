# 第13章 FastAPI入門 起動とDI

データ層ができたので、その上に **HTTP API** を載せます。
本研修では [FastAPI](https://fastapi.tiangolo.com/) を使います。
理由はシンプルで、**[型ヒント](https://peps.python.org/pep-0484/)がそのまま入力チェックと OpenAPI ドキュメントになる**から。
入力チェック用のコードやAPIドキュメントを別途手で書かなくていい、というのが他のフレームワークに対する大きな強みです。

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

`app = FastAPI(...)` で **アプリケーション本体を1つ**作り、`@app.get("/health")` のような
**パスオペレーションデコレータ**を関数につけると「この関数は `GET /health` を処理する」と
FastAPI に登録されます。関数名自体は何でもよく、FastAPI が見ているのはデコレータに
書いたパスと HTTP メソッドの組み合わせです。

起動:

```bash
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/docs   ← Swagger UI（自動生成のAPIドキュメント）
```

[`uvicorn`](https://www.uvicorn.org/) は **ASGI サーバー**——FastAPI で組み立てたアプリケーションを
実際に HTTP で受け付けて動かす実行エンジンです。FastAPI 自体は「リクエストが来たらどう処理するか」を
定義するだけで、ソケットを開いて HTTP をしゃべる部分は uvicorn が担当しています。
`--reload` を付けるとコードを保存するたびに自動で再起動してくれるので開発中は便利ですが、
本番運用では外します（第18章で扱います）。

ブラウザで `http://127.0.0.1:8000/docs` を開くと、
**Swagger UI** が見えます。これだけで API の動作確認画面が手に入る。

!!! note "Swagger UI の正体"
    この画面は自分で書いたものではありません。FastAPI が各エンドポイントの型ヒントから
    **OpenAPI スキーマ**（`http://127.0.0.1:8000/openapi.json` で生データを確認できます）を
    自動生成し、それを Swagger UI が読んで描画しています。つまり型ヒントを正確に書くことが、
    そのまま正確な API ドキュメントにつながります。

## 13.2 ルーターを分ける

エンドポイントが増えてきたら、`routers/` ディレクトリに分けます。
機能ごとのエンドポイントをすべて `main.py` に書いていくと、増えるたびにファイルが肥大化して
見通しが悪くなるので、**関連するエンドポイントをひとまとめにする箱**として
[`APIRouter`](https://fastapi.tiangolo.com/tutorial/) を使います。

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
`todos.py` 側では `/todos` としか書いていませんが、`include_router` の `prefix="/api"` が
ルーター内の全パスの先頭に `/api` を足してくれるので、実際には `/api/todos` になります。
`APIRouter(tags=["todos"])` の `tags` は Swagger UI 上でエンドポイントをグループ分けする
ラベルで、動作には影響しません。

## 13.3 依存性注入（DI）の考え方

FastAPI の [`Depends`](https://fastapi.tiangolo.com/tutorial/dependencies/) は
**「呼び出されたときに必要な値を作って差し込む」** 仕組みです。
これは **依存性注入（Dependency Injection, DI）** と呼ばれる設計パターンの実装で、
「関数の中で必要なものを自分で組み立てる」代わりに「外から渡してもらう」形にします。
これをやらずに毎回関数の中で組み立てていると、同じ準備コードのコピペが増えるうえに、
テストのときに本物のリクエストや DB を用意しないと動かせなくなってしまいます。
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

ToDo アプリでは、各リクエストで
**[プールから接続を借りる](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)**形にします。
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
  `get_conn` は呼ばれるたびに `yield` のところで一度止まり、そこで作った `conn` が
  エンドポイント関数に渡されます。リクエスト処理が終わる（または例外で終わる）と、
  FastAPI が関数の続き——ここでは `with` ブロックを抜ける処理——を実行してくれます。
  第2章で見た [`with` 文](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement)
  の「後始末を保証する」考え方が、DI の世界でも同じ形で効いています。
- **`Annotated[..., Depends(...)]`** は FastAPI のお作法。再利用しやすいので別名にしてあります。
  [`Annotated`](https://docs.python.org/3/library/typing.html) は型ヒントに
  **追加情報をくっつける**ための標準機能で、ここでは「型は `psycopg.Connection` だが、
  実際の値は `Depends(get_conn)` によって注入される」という意味を持たせています。
  `Conn` という別名にしておくことで、複数のエンドポイントで `conn: Conn` と書くだけで済み、
  `Depends(get_conn)` を毎回書かずに済みます。
- ルーター内で `with connection()` を毎回書かなくていい。

!!! tip "DI でテストが楽になる"
    DI を使うと、テスト時に `app.dependency_overrides[get_conn] = ...` で
    「テスト用の接続を返す関数」に差し替えできます。研修ではテスト用 DB を分けないので
    この恩恵は薄いですが、**実務では強力な武器**です。詳しくは
    [FastAPI公式のテストガイド](https://fastapi.tiangolo.com/tutorial/testing/)や、
    次章で使う `TestClient` も参照してください。

## 13.5 リクエスト中にトランザクションをまとめる

`get_conn` は `with connection() as conn:` を使っているので、
**1 リクエスト中の全 SQL が同じトランザクション**で実行されます。
ルーター内で例外が起きれば自動でロールバック、正常に終われば自動でコミット。

これは **「1 リクエスト = 1 トランザクション」**という、Web アプリでよく使われる設計です
（[psycopgのトランザクション制御](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)、
[PostgreSQLのトランザクション入門](https://www.postgresql.org/docs/current/tutorial-transactions.html)）。
こうしておけば、複数の SQL のうち途中で失敗したものがあっても、
**中途半端な状態のデータが DB に残らない**ことが保証されます。
もし各 SQL を別々のトランザクションで実行していたら、2つめの INSERT が失敗しても
1つめの INSERT だけが確定してしまい、「タグだけ紐付いていない ToDo」のような
不整合データが生まれかねません。

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

!!! note "手で試すのと自動テストは別物"
    Swagger UI での確認はあくまで**人間が手で試す**ためのものです。
    毎回手でクリックして確認するのは繰り返しの検証には向かないので、
    リグレッション（前は動いていたのに壊れること）を防ぐための
    **自動テスト**は次章で `TestClient` を使って書きます。

## やってみよう

1. `GET /health` の他に、`GET /api/version` で `{"version": "0.1.0"}` を返す
   エンドポイントを追加する。
2. `get_conn` を **わざとエラーにする**（DSN を壊す）と、`/api/todos` のレスポンスが
   どう変わるか観察する。
3. **依存関数を別の依存関数から呼ぶ**ネスト構造を作ってみる
   （例: `get_request_id` を `get_conn` から呼ぶ）。

次は [第 14 章 CRUD API実装とテスト](14-api-crud.md) で、
**ToDo の CRUD を全部実装し、TestClient でテスト**します。
