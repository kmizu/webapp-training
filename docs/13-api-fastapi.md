# 第13章 FastAPI入門 起動とDI

第12章までで、データアクセス層とそのテストが完成しました。
この章から、いよいよその上に **HTTP API** を載せていきます。
使うのは [FastAPI](https://fastapi.tiangolo.com/) です。

この章のゴールは「**uvicorn でサーバーを起動し、ルーターの骨格と
依存性注入（DI）の形を作る**」ことです。
`/api/todos` などのエンドポイント本体は第14章で実装するので、
この章の時点では Swagger UI にエンドポイントが 1 つも並ばないのが
**正しい状態**です。

リポジトリの `sample/todo-app/` は引き続き**答え合わせ用の完成版**です。

## 13.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- Web サーバー、ASGI、uvicorn の役割分担を説明できる
- `APIRouter` と `include_router`、`prefix` の関係を説明できる
- 依存性注入（DI）とは何か、`Depends` と `yield` の形とともに説明できる
- FastAPI が型ヒントと Pydantic でバリデーションし、`/docs` を
  自動生成する仕組みを説明できる
- `app/main.py` と `app/routers/`（`__init__.py` と `todos.py` の骨格）を
  写経し、uvicorn で起動して curl で動作確認できる

**所要時間の目安: 60 分**

この章で新しく作るのは 3 ファイルだけです
（`app/main.py`、`app/routers/__init__.py`、`app/routers/todos.py`）。
既存のファイルには一切手を付けません。

!!! info "前提となる状態"
    - 第12章末時点の `mytodo/`（`app/` は完成版相当、`tests/` あり）がある
    - 第0章の Docker の PostgreSQL が起動している（`docker compose up -d`）
    - `init-db` 適用済みで、シードデータが入った状態である

## 13.2 前提知識

コードに入る前に、この章の鍵になる 3 つの概念を押さえておきます。

!!! note "Web サーバーと ASGI / uvicorn"
    第8章で学んだとおり、Web アプリはクライアント（ブラウザなど）と
    サーバーの間で HTTP のリクエスト/レスポンスを往復させます。
    この「サーバー」を自分の PC 上で動かすのがこの章の作業です。

    ここで登場する部品は 2 つあり、役割が分かれています。

    - **FastAPI** …… 「どの URL にどのメソッドで来たら、どの関数を
      呼ぶか」を定義するためのフレームワーク。
      それ自体はネットワークをしゃべりません。
    - **uvicorn** …… 実際にポート（既定では 8000 番）を開いて
      HTTP リクエストを受け付け、FastAPI アプリに渡す実行エンジン。
      こういうサーバーを **ASGI サーバー** と呼びます。

    **ASGI** は「Python の Web フレームワークと Web サーバーの間の
    取り決め（インタフェース）」の名前です。FastAPI で作ったアプリは
    「ASGI アプリ」という形をしているので、ASGI に対応したサーバー
    （uvicorn のほか Hypercorn など）なら何でも動かせます。
    起動コマンド `uvicorn app.main:app` の `app.main:app` は、
    「**`app/main.py` の中の `app` という変数**（ASGI アプリ）を
    動かしてくれ」という指定です。

    なお、これまでの `python try_read.py` のようなスクリプトは
    実行して結果を出したら終了しましたが、**サーバーは起動しっぱなしの
    プロセス**です。止めるときは、起動しているターミナルで
    `Ctrl+C` を押します。curl での確認は**別のターミナル**から行います。

!!! note "依存性注入（DI）とは"
    **依存性注入（Dependency Injection, DI）** は、
    「関数が必要とするものを、関数の中で自分で組み立てる」のではなく、
    「**外側（フレームワーク）が用意して引数に差し込んでくれる**」
    形にする設計パターンです。

    実は、第12章でこの考え方をすでに体験しています。
    pytest のフィクスチャは「テスト関数の引数に `conn` と書くだけで、
    pytest が接続を用意して渡してくれる」仕組みでした。
    FastAPI の DI もほぼ同じで、エンドポイント関数の引数に
    「`conn` が欲しい」と書くと、FastAPI がリクエストのたびに
    接続を用意して渡してくれます。`yield` を使った
    「準備 → 渡す → 後片付け」の流れも、フィクスチャと同じ形です。

    DI にしておくと、各エンドポイントの関数は「接続の作り方」を
    知らなくて済み、接続の作り方を変えたくなったときも
    差し込む側（この章で作る `get_conn`）だけを直せばよくなります。

!!! note "Pydantic と `/docs` の自動生成"
    第10章の 10.2 で「Pydantic は第13章で登場します」と予告していた
    [Pydantic](https://docs.pydantic.dev/latest/) が、ここで登場します。

    FastAPI の大きな特徴は、**関数の型ヒントを読み取り、裏側で
    Pydantic を使ってリクエストの値を検証（バリデーション）する**ことです。
    たとえば第14章で「`priority` は 1〜3 の整数」という型を持つ
    Pydantic モデルを API の入力に指定すると、`priority` に `9` を
    送ったリクエストは、こちらが何も書かなくても自動的に
    `422 Unprocessable Content`（第8章のステータスコード表にあった
    「形は合っているが値がおかしい」）で弾かれます。

    さらに FastAPI は、型ヒントの情報から **OpenAPI スキーマ**
    （API の仕様を機械可読な JSON で表したもの）を自動生成し、
    それを描画した **Swagger UI** を `/docs` という URL で
    最初から提供します。つまり、型ヒントを正確に書くことが、そのまま
    正確なバリデーションと正確な API ドキュメントにつながります。

    この章で写経する骨格にはまだ Pydantic モデルは登場しません。
    モデルの定義ファイル `app/schemas.py` の写経は第14章で行います。
    いまは「**FastAPI は型ヒントと Pydantic で入力を検証し、
    `/docs` もそこから自動生成される**」という概念だけ押さえてください。

## 13.3 ここまでのファイル構成

まず現在地を確認します。第12章末時点の `mytodo/` は次の構成です。

```text
mytodo/
├── pyproject.toml          第10章で作成
├── uv.lock                 uv sync が自動生成
├── .venv/                  uv sync が自動生成
├── app/
│   ├── __init__.py         第10章で作成（空ファイル）
│   ├── config.py           第10章で作成
│   ├── db.py               第10章で作成
│   ├── cli.py              第10章で作成
│   ├── models.py           第10章で作成
│   ├── repositories.py     第10〜11章で作成（完成版と一致済み）
│   └── main.py             ← この章で作成
├── migrations/
│   ├── 001_init.sql        第9章で作成・tododb に適用済み
│   └── 002_seed.sql        第9章で作成・tododb に適用済み
├── tests/
│   ├── __init__.py         第12章で作成（空ファイル）
│   ├── conftest.py         第12章で作成
│   └── test_repositories.py 第12章で作成
└── app/routers/            ← この章で作成
    ├── __init__.py         この章で作成（空ファイル）
    └── todos.py            この章で作成（骨格。第14章で完成させる）
```

（最後の `app/routers/` は `app/` の中にあります。ツリーの見やすさのため
末尾に出しました。）

完成版の `sample/todo-app/app/` には、このほかに `schemas.py`
（Pydantic モデル）、`services.py`（業務ルール）、
`routers/pages.py`（HTML を返すルーター）、`templates/`、`static/`
がありますが、それらは第14〜16章で作ります。この章では
**JSON API 側の入口だけ**を先に立てます。

## 13.4 ルーターの骨格: `app/routers/`

エンドポイントが増えてきたとき、すべてを `main.py` に書いていくと
ファイルが肥大化して見通しが悪くなります。そこで FastAPI では、
**関連するエンドポイントをひとまとめにする箱**として
[`APIRouter`](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
を使い、機能ごとにファイルを分けるのが定石です。
このアプリでは `/api/todos` まわりを `routers/todos.py` に、
HTML の画面を返す側を `routers/pages.py`（第15章）に分けます。

まず `routers/` ディレクトリと目印のファイルを作ります。
`mytodo/` の中で実行してください。

```bash
mkdir app/routers
```

`mytodo/app/routers/__init__.py` を**中身は空のまま**作成してください。
`app/__init__.py`（第10章）と同じく、「このディレクトリは Python の
パッケージである」という目印です。

続いて、この章の主役である骨格を写経します。
`mytodo/app/routers/todos.py` を作成して、次の内容を書き写してください。

```python
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from ..db import connection

router = APIRouter(tags=["todos"])


def get_conn() -> Iterator[psycopg.Connection]:
    with connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
```

!!! warning "このファイルは骨格です"
    完成版の `routers/todos.py` には `/api/todos` の CRUD など
    7 つのエンドポイントが入っていますが、**この章で写経するのは
    ここまで（ルーター定義と `get_conn` の DI 部分）**です。
    エンドポイントはすべて第14章でこのファイルに追加します。
    そのため、この時点で完成版と `diff` を取ると差分が出ます。
    それが正しい状態です（差分の見方は 13.7 で説明します）。

上から順に見ていきます。

- `from ..db import connection` …… 第10章で写経した
  `db.py` の `connection()`（プールから接続を借りる自作
  コンテキストマネージャ）です。`..` は「1 つ上のパッケージ
  （`app/`）」を指します。
- `router = APIRouter(tags=["todos"])` …… ルーターの箱を作ります。
  `tags` は Swagger UI 上でエンドポイントをグループ分けする
  ラベルで、動作そのものには影響しません。
- `get_conn()` …… これが **DI で差し込む値を作る関数**（依存関数）です。
  `Iterator` + `yield` の形は第12章のフィクスチャと同じで、
  `yield` の前が準備（プールから接続を借りる）、`yield` で
  エンドポイント関数に接続を渡し、リクエストの処理が終わったら
  `yield` の後ろ（ここでは `with` ブロックを抜ける処理）が
  後片付けとして実行されます。
- `Conn = Annotated[psycopg.Connection, Depends(get_conn)]` ……
  [`Annotated`](https://docs.python.org/3/library/typing.html#typing.Annotated)
  は型ヒントに**追加情報をくっつける**標準機能で、ここでは
  「型は `psycopg.Connection` だが、実際の値は `Depends(get_conn)`
  によって注入される」という意味を持たせています。
  `Conn` という別名にしておくと、第14章で書く各エンドポイントは
  引数に `conn: Conn` と書くだけで DI が効くようになり、
  `Depends(get_conn)` を毎回書かずに済みます。

第14章で書くエンドポイントは、例えば完成版の `list_tags` のような
形になります（これは予告なので、まだ写さなくて大丈夫です。
`repo` は `repositories.py` を import したものです）。

```python
@router.get("/tags")
def list_tags(conn: Conn):
    return [{"id": g.id, "name": g.name} for g in repo.list_all_tags(conn)]
```

引数に `conn: Conn` があるだけで、FastAPI がこの関数を呼ぶたびに
`get_conn()` を実行し、プールから借りた接続を `conn` に
差し込んでくれる——それが DI の効果です。

!!! note "1 リクエスト = 1 トランザクション"
    `get_conn` は `with connection() as conn:` を使っているので、
    **1 回のリクエストの中で実行される SQL はすべて同じ
    トランザクション**に入ります。エンドポイントが正常に終われば
    `with` を抜けるときに自動でコミットされ、途中で例外が起きれば
    自動でロールバックされます（第6章の `with` とトランザクションの
    復習です）。そのあと接続はプールに返却されます。

    「1 リクエスト = 1 トランザクション」にしておけば、
    1 つのリクエストで複数の SQL を実行したときに途中で失敗しても、
    **中途半端な状態のデータが DB に残りません**。
    Web アプリでよく使われる定番の設計です。

## 13.5 アプリの起動点: `app/main.py`

最後に、アプリ全体の入口を作ります。
`mytodo/app/main.py` を作成して、次の内容を書き写してください。

```python
from fastapi import FastAPI

from .routers import todos

app = FastAPI(title="ToDo App", version="0.1.0")

app.include_router(todos.router, prefix="/api")
```

- `app = FastAPI(...)` …… **アプリケーション本体を 1 つ**作ります。
  `title` と `version` は `/docs` や `openapi.json` に表示される
  名前とバージョンです。
- `app.include_router(todos.router, prefix="/api")` ……
  13.4 で作ったルーターをアプリに組み込みます。
  `prefix="/api"` を付けると、ルーター内の全パスの先頭に
  `/api` が足されます。第14章で todos.py に `/todos` というパスの
  エンドポイントを追加すると、実際の URL は `/api/todos` になります。
  これは第8章の API 表の URL 設計（`/api/...` が JSON API）そのものです。

!!! warning "`main.py` は第15章・第17章で育ちます"
    完成版の `main.py` には、このほかに HTML 用ルーター
    （`pages`）の組み込み、静的ファイル（CSS）の公開、
    ログ設定、リクエストのログを残すミドルウェア、
    想定外の例外をまとめて処理するハンドラが入っています。
    これらは依存するファイル（`routers/pages.py` や `static/`）が
    まだ無いので、**第15章と第17章で追加して完成版と一致させます**。
    この章の `main.py` は、それらが無くても動く最小構成です。

## 13.6 起動と動作確認

いよいよサーバーを起動します。`mytodo/` の中で実行してください。

```bash
uv run uvicorn app.main:app --reload
```

期待される出力（パスやプロセス番号は環境によって変わります）:

```text
INFO:     Will watch for changes in these directories: ['/home/.../mytodo']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

`Application startup complete.` と出れば起動成功です。
`--reload` を付けていると、ファイルを保存するたびに自動で再起動します
（開発中は便利ですが、本番では外します。第18章で扱います）。
このターミナルはサーバーが使い続けるので、**このあとの curl は
別のターミナルを開いて**実行してください。

まず、Swagger UI が出ていることを確認します。

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
```

期待される出力:

```text
200
```

ブラウザで `http://127.0.0.1:8000/docs` を開くと、
**Swagger UI**（自動生成の API ドキュメント画面）が表示されます。
まだエンドポイントは 1 つもないので、真っ白な画面に
「ToDo App 0.1.0」というタイトルがあるだけですが、
これが第14章でエンドポイントがずらりと並ぶ画面の土台です。

次に、Swagger UI の元になっている OpenAPI スキーマの生データを
見てみます。

```bash
curl -s http://127.0.0.1:8000/openapi.json
```

期待される出力:

```json
{"openapi":"3.1.0","info":{"title":"ToDo App","version":"0.1.0"},"paths":{}}
```

`main.py` に書いた `title` と `version` が反映されています。
`paths` が空 `{}` なのは、まだエンドポイントを 1 つも
登録していないからです。

最後に、第14章で実装する URL を先に叩いてみます。

```bash
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/todos
```

期待される出力:

```text
{"detail":"Not Found"}
HTTP 404
```

**404 が返るのが正しい状態です。** ルーターは組み込み済みですが、
中にエンドポイントがまだ無いので、「その URL を処理する関数が
存在しない」という意味の 404（第8章）になります。
第14章でエンドポイントを実装すると、この URL が JSON を
返すようになります。

確認できたら、サーバーを動かしているターミナルで `Ctrl+C` を押して
停止してください。

期待される出力:

```text
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [12346]
INFO:     Stopping reloader process [12345]
```

## 13.7 答え合わせ: `diff` で完成版と比較する

写経した 3 ファイルを完成版と答え合わせします
（`diff` コマンドは**リポジトリのルート**で実行してください）。

```bash
diff -u mytodo/app/routers/__init__.py sample/todo-app/app/routers/__init__.py
diff -u mytodo/app/main.py sample/todo-app/app/main.py
diff -u mytodo/app/routers/todos.py sample/todo-app/app/routers/todos.py
```

判定の基準はファイルごとに違います。

- **`routers/__init__.py`** …… 両方とも空ファイルなので、
  **何も表示されなければ一致**です。
- **`main.py`** …… **差分が出るのが正しい状態**です。
  `-`（あなたのファイルにだけある行）が
  `from fastapi import FastAPI` と `from .routers import todos`
  の import 2 行だけで、残りはすべて `+`（完成版にだけある行）
  であることを確認してください。`+` の中身は 13.5 で触れた
  `pages` ルーター・静的ファイル・ログ・例外ハンドラで、
  第15章と第17章で追加します。
- **`routers/todos.py`** …… これも**差分が出るのが正しい状態**です。
  `-` が import 2 行（`from typing import Annotated` と
  `from fastapi import APIRouter, Depends`）だけで、
  残りはすべて `+` であることを確認してください。
  `+` の中身は第14章で写経するエンドポイント群と、
  そこで使う import です。

`-` の行が上記以外にある場合は写経ミスなので、
表示された行を見比べて写し直してください。

## 13.8 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] FastAPI と uvicorn の役割分担（どちらが HTTP を受け付けるか）を
      説明できる
- [ ] ASGI とは何か、`uvicorn app.main:app` の `app.main:app` が
      何を指すか説明できる
- [ ] 依存性注入（DI）とは何か、第12章のフィクスチャとの似ている点と
      ともに説明できる
- [ ] `Annotated[psycopg.Connection, Depends(get_conn)]` の意味と、
      `Conn` という別名にしておく利点を説明できる
- [ ] `include_router(..., prefix="/api")` を付けると URL がどうなるか
      説明できる
- [ ] FastAPI が型ヒントと Pydantic で何をしてくれるか
      （バリデーションと `/docs` の自動生成）を説明できる
- [ ] `uvicorn` で起動し、`/docs` が 200、`/api/todos` が 404 を
      返すことを curl で確認した
- [ ] 3 ファイルの `diff` が 13.7 の基準どおりの状態になった

## 13.9 つまずきポイント

### `ModuleNotFoundError: No module named 'app'`

`uv run uvicorn app.main:app` を **`mytodo/` の外**で実行したときの
エラーです。`app.main:app` は「いまいるディレクトリから見える
`app/` パッケージ」を探すので、`cd mytodo` で移動してから
実行してください。

### `error while attempting to bind on address ('127.0.0.1', 8000): address already in use`

8000 番ポートを別のプロセスが使っています。
前に起動した uvicorn を止め忘れていることが多いので、
そのターミナルで `Ctrl+C` を押してください。
どうしても分からなければ、別のポートで起動すれば回避できます。

```bash
uv run uvicorn app.main:app --reload --port 8001
```

この場合、確認用の URL も `http://127.0.0.1:8001/docs` のように
読み替えてください。

### curl が `Failed to connect to 127.0.0.1 port 8000` になる

サーバーが起動していません。uvicorn を動かしているターミナルで
エラーが出て止まっていないか、`Ctrl+C` で止めてしまっていないかを
確認してください。サーバーは起動している間だけ応答します。

### 保存した途端にサーバーが落ちた

`--reload` 付きで動かしていると、ファイルを保存した瞬間に
自動再起動が走ります。写経の途中（構文が未完成の状態）で保存すると、
再起動に失敗して Traceback が表示されます。
サーバーを動かしているターミナルに出ているエラーメッセージを読み、
指摘されたファイル・行を直して保存すれば、また自動で再起動します。

## 13.10 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 DI が本当に動くか、仮のエンドポイントで確かめる

この章の骨格にはエンドポイントが無いので、`get_conn` の DI は
まだ一度も動いていません。`routers/todos.py` の末尾に、
**借りた接続で `SELECT 1` を実行するだけ**の仮のエンドポイント
`GET /api/health` を追加して、DI 経由で DB につながることを
curl で確認してください。

??? example "解答例"

    `mytodo/app/routers/todos.py` の末尾に次を追加します。

    ```python
    @router.get("/health")
    def health(conn: Conn):
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"ok": True}
    ```

    `--reload` で起動中なら、保存しただけで自動再起動します。
    別ターミナルで実行します。

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/health
    ```

    期待される出力:

    ```text
    {"ok":true}
    HTTP 200
    ```

    `main.py` の `prefix="/api"` によって、パスは `/health` ではなく
    `/api/health` になっている点に注目してください。
    引数に `conn: Conn` と書いただけで、リクエストごとに
    プールから接続が借りられて渡されていることが確認できました。

    ブラウザで `http://127.0.0.1:8000/docs` を開き直すと、
    今度は `todos` のグループに `GET /api/health` が表示されています。
    「Try it out」から実行してみるのもよい確認です。

    確認が終わったら、このエンドポイントは**消して構いません**
    （消さなくても、第14章で `todos.py` を完成版に仕上げるときに
    整理されます）。

### 問2 `/api/version` を追加する

`routers/todos.py` の末尾に、`GET /api/version` で
`{"version": "0.1.0"}` を返すエンドポイントを追加してください
（これも仮のもので、確認後は消して構いません）。

??? example "解答例"

    ```python
    @router.get("/version")
    def version():
        return {"version": "0.1.0"}
    ```

    確認します。

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/version
    ```

    期待される出力:

    ```text
    {"version":"0.1.0"}
    HTTP 200
    ```

    このエンドポイントは DB を使わないので、引数の `conn: Conn` は
    要りません。引数に書かなければ DI も実行されない——
    「必要なものを引数に書くと、必要なものだけが注入される」のが
    DI の基本的な読み方です。

### 問3 OpenAPI スキーマの中身を見る

問1・問2のエンドポイントを追加した状態で `openapi.json` を
取得し、13.6 のとき（`"paths":{}` だった）と何が変わったかを
確認してください。

??? example "解答例"

    ```bash
    curl -s http://127.0.0.1:8000/openapi.json
    ```

    期待される出力（長いので構造だけ示します）:

    ```text
    "paths" の中に "/api/health" と "/api/version" の 2 つのキーが現れ、
    それぞれに HTTP メソッド（"get"）や tags（"todos"）などの
    情報がぶら下がっている
    ```

    `/docs`（Swagger UI）の画面は、この JSON を読んで描画されています。
    エンドポイントを増やすと `openapi.json` が変わり、
    それにつられて `/docs` の表示も変わる——
    **ドキュメントがコードから自動生成されている**ことを、
    自分の手で確かめられました。

## まとめ

- FastAPI は「URL と関数の対応」を定義するフレームワーク、
  uvicorn は HTTP を受け付けてアプリを動かす **ASGI サーバー**。
  `uvicorn app.main:app` の `app.main:app` は
  「`app/main.py` の `app` 変数」という指定
- エンドポイントは `APIRouter` で機能ごとのファイルに分け、
  `include_router(..., prefix="/api")` でアプリに組み込む
- **依存性注入（DI）** は「必要なものを外から引数に差し込んでもらう」
  仕組み。`yield` を使った `get_conn` と
  `Annotated[..., Depends(get_conn)]` の別名 `Conn` で、
  「リクエストごとにプールから接続を借りて渡す」を共通化した
  （第12章のフィクスチャと同じ発想）
- `with connection()` で借りた接続は、**1 リクエスト =
  1 トランザクション**になる。正常終了でコミット、例外でロールバック
- FastAPI は型ヒントと **Pydantic** でリクエストをバリデーションし、
  OpenAPI スキーマと `/docs`（Swagger UI）を自動生成する。
  Pydantic モデル本体（`schemas.py`）は第14章で写経する
- この時点では `/api/todos` が 404 を返すのが正しい状態。
  エンドポイントはこれから実装する

次は [第14章 CRUD API実装とテスト](14-api-crud.md) で、
`schemas.py` の Pydantic モデルを写経し、
`routers/todos.py` に **CRUD のエンドポイントをすべて実装**して、
`TestClient` でテストを書きます。
