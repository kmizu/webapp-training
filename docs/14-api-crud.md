# 第14章 CRUD API実装とテスト

第13章で FastAPI アプリの起動と DI の骨格ができました。
この章では、その骨格の上に **ToDo の CRUD すべて**を実装します。
入出力のスキーマ（`schemas.py`）と業務ルール（`services.py`）を写経し、
`routers/todos.py` を完成版に丸ごと差し替えて、最後に TestClient で
**API のテスト**まで書きます。

リポジトリの `sample/todo-app/` は引き続き**答え合わせ用の完成版**です。
この章で写経する 4 ファイルはすべて完成版の実ファイルと同じ内容なので、
写経が終わったら `diff` で答え合わせをします。

## 14.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- HTTP メソッド（GET / POST / PATCH / DELETE）と CRUD の対応を説明できる
- ステータスコード（200 / 201 / 204 / 404 / 422）の使い分けを説明できる
- Pydantic モデルで API の入力・出力を定義し、バリデーションが
  どこで行われるかを説明できる
- `app/schemas.py`・`app/services.py` を写経できる
- `app/routers/todos.py` を完成版に差し替え、7 つのエンドポイントを
  実装できる
- curl で CRUD を一通り動作確認できる
- `tests/test_api.py` を写経し、`uv run pytest -v` で
  **18 個のテストがすべてパス**することを確認できる
- 写経した 4 ファイルの `diff` が完成版と**差分なし**になることを
  確認できる

**所要時間の目安: 90 分**

この章で新しく作るのは `app/schemas.py`、`app/services.py`、
`tests/test_api.py` の 3 ファイルです。
`app/routers/todos.py` は第13章の骨格を**完成版に丸ごと差し替えます**。
それ以外のファイル（`main.py` など）には一切手を付けません。

!!! info "前提となる状態"
    - 第13章末時点の `mytodo/`（`app/main.py` と `app/routers/` の
      骨格があり、uvicorn で起動できる）がある
    - 第0章の Docker の PostgreSQL が起動している（`docker compose up -d`）
    - `init-db` 適用済みで、シードデータが入った状態である

## 14.2 前提知識

コードに入る前に、この章の鍵になる 2 つの概念を押さえておきます。

!!! note "HTTP メソッドとステータスコード"
    第8章で設計したとおり、この API では操作ごとに意味の合う
    [HTTP メソッド](https://developer.mozilla.org/ja/docs/Web/HTTP/Methods)
    を使い分けます。

    - **GET** …… 読み取り（一覧・1件取得）。成功すると **200**
    - **POST** …… 新規作成。成功すると **201 Created**
      （作成以外の POST、たとえば完了切替の toggle は **200**）
    - **PATCH** …… 部分更新（送られたフィールドだけ変える）。
      成功すると **200**
    - **DELETE** …… 削除。成功すると **204 No Content**
      （返すボディがない）

    これに加えて、失敗時のステータスコードが 2 つ登場します。
    **404 Not Found** は「リクエストの形は正しいが、指定された ID の
    ToDo が存在しない」とき。**422 Unprocessable Content** は
    「JSON の文法（形）は正しいが、スキーマの制約（必須・型・範囲）を
    満たさない値が入っている」ときです。この章のルーターでは、
    404 は自分で `raise HTTPException(...)` して返し、422 は
    Pydantic のバリデーションが**自動で**返します。

!!! note "Pydantic によるバリデーション"
    第13章で概念を紹介した [Pydantic](https://docs.pydantic.dev/latest/)
    を、この章で実際に使います。ポイントは
    「**バリデーションのルールは型として書く**」ことです。

    たとえば 14.4 で写経する `TodoCreate` には
    「`title` は 1〜200 文字の文字列」「`priority` は 1〜3 の整数」
    という制約が型に書かれています。FastAPI はエンドポイント関数を
    呼ぶ**前に**、届いた JSON をこの型に照らして検証します。
    ルールに合わないリクエストは関数の中に入ることなく
    自動で 422 が返るので、エンドポイント側に手書きのチェックを
    並べなくて済みます。

    この「壊れたリクエストは入口で弾く」仕組みがあるので、
    ルーターやリポジトリの中では「値は正しい形で届いている」
    前提でコードを書けます。

## 14.3 ここまでのファイル構成

まず現在地を確認します。第13章末時点の `mytodo/` は次の構成です。

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
│   ├── main.py             第13章で作成（最小構成）
│   ├── routers/
│   │   ├── __init__.py     第13章で作成（空ファイル）
│   │   └── todos.py        第13章で作成（骨格）→ この章で完成版に差し替え
│   ├── schemas.py          ← この章で作成
│   └── services.py         ← この章で作成
├── migrations/
│   ├── 001_init.sql        第9章で作成・tododb に適用済み
│   └── 002_seed.sql        第9章で作成・tododb に適用済み
└── tests/
    ├── __init__.py         第12章で作成（空ファイル）
    ├── conftest.py         第12章で作成
    ├── test_repositories.py 第12章で作成
    └── test_api.py         ← この章で作成
```

完成版の `sample/todo-app/app/` には、このほかに `routers/pages.py`、
`templates/`、`static/` がありますが、それらは第15〜16章で作ります。
`main.py` の残りの部分も第15章と第17章で育てます。
この章では **JSON API 側を完成させます**。

## 14.4 入出力スキーマ: `app/schemas.py`

最初に、API の**入力**と**出力**の形を定義します。
第10章で見たように、**ドメインモデル（`models.py` の dataclass）と
API スキーマ（ここの Pydantic モデル）は別物**でした。
ここではさらに、Pydantic 側も 1 つのクラスにまとめず、
`TodoOut`（出力用）・`TodoCreate`（作成用）・`TodoPatch`（部分更新用）
の 3 つに分けています。

理由は単純で、**操作ごとに必須な項目が違う**からです。
`TodoCreate` は新規作成なので `title` が必須ですが、
`TodoPatch` は「送られてきたフィールドだけ変える」部分更新のために
全フィールドを省略可能にしています。
もし 1 つのクラスで済ませようとすると、「作成のときは必須・
更新のときは任意」という操作依存の制約を型では表現できず、
コードのあちこちに手書きの `if` チェックが増えてしまいます。

`mytodo/app/schemas.py` を作成して、次の内容を書き写してください。

```python
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

`Priority = Annotated[int, Field(ge=1, le=3)]` のように、
[`Annotated`](https://docs.python.org/3/library/typing.html#typing.Annotated)
と Pydantic の `Field` を組み合わせて型エイリアスにしておくと、
「優先度は 1〜3 の整数」という制約（`ge` / `le` はそれぞれ
「以上」「以下」の意味）を `TodoOut`・`TodoCreate`・`TodoPatch` の
3 か所で使い回せます。
同じように `TodoListQuery.filter` の `Literal["all", "open", "done"]`
は、この 3 つの文字列**以外**を受け付けない型です。
範囲外の値（たとえば `filter=archived`）を送ると、ルーター関数が
呼ばれる前に自動で 422 が返ります。

!!! note "`from_attributes=True` の意味"
    Pydantic v2 で `from_attributes=True` を付けると、
    **dataclass や ORM オブジェクトから直接変換**できます。
    つまり `TodoOut.model_validate(my_todo_dataclass)` のように書けます。
    これを付けないと `model_validate()` は辞書のような入力しか
    受け付けず、dataclass を渡すとバリデーションエラーになります。
    14.6 のルーターで、リポジトリが返す `Todo` dataclass をそのまま
    `TodoOut.model_validate(todo)` に渡せているのは、この設定の
    おかげです。

## 14.5 業務ルール: `app/services.py`

続いて、第8章の設計で「業務ルール（薄く）」と決めていた services 層の
ファイルを作ります。

`mytodo/app/services.py` を作成して、次の内容を書き写してください。

```python
from datetime import date


def validate_due_on(due_on: date | None) -> tuple[bool, str | None]:
    """期限の業務ルール。極端な未来は受け付けない。"""
    if due_on is None:
        return True, None
    if (due_on - date.today()).days > 365 * 50:
        return False, "期限がだいぶ未来すぎます"
    return True, None
```

中身は 1 関数だけです。「期限が 50 年以上先なら拒否する」という
**業務上の判断**を、Pydantic のバリデーション（データの形のチェック）
とは別の場所に置いています。`True/False` とメッセージのペアを返す形に
してあるので、呼び出し側は HTTP のエンドポイント以外（CLI やテスト）
からでも同じ判定を再利用できます。

!!! note "この章のエンドポイントからは、まだ呼ばれません"
    完成版の `routers/todos.py` は `services.py` を import して
    **いません**。このファイルは「業務ルールを置く場所」を先に
    用意するための写経で、この章の CRUD は Pydantic と DB 制約だけで
    動きます。`validate_due_on` をエンドポイントに組み込む方法は
    **第17章**で扱います。いまは「層の置き場所が先にできた」
    という理解で進んで大丈夫です。

## 14.6 ルーターの完成: `app/routers/todos.py`

いよいよ本題です。第13章で写経した骨格を、**完成版に丸ごと
差し替えます**。骨格の内容（`APIRouter`、`get_conn`、`Conn`）は
完成版にも同じ形で残りますが、import 行が変わる関係で一部分だけの
書き換えでは済まないため、**骨格と同じ部分も含めて、ファイル全体を
次の内容で上書きしてください**。

`mytodo/app/routers/todos.py` を、次の内容で**丸ごと上書き**して
ください。

```python
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
```

骨格からの変更点を上から順に見ていきます。

- **import の書き換え** …… 骨格の `from typing import Annotated` は
  `from typing import Annotated, Any` に、`from fastapi import APIRouter, Depends`
  は `HTTPException`・`Response`・`status` を加えた行に変わります。
  さらに 3 行増えています。
    - `from .. import repositories as repo` …… 第10〜11章で作った
      リポジトリ層。SQL はすべてここに閉じているので、ルーターは
      関数名を呼ぶだけです。
    - `from ..repositories import _UNSET` …… 第11章で定義した
      「未指定」の目印です。**`repositories.py` の中の 1 つを
      import する**のがポイントで、ここで自分で `object()` を
      新たに作ってしまうと別物になるため、リポジトリ側の
      `due_on is not _UNSET` 判定がすべて「指定あり」とみなされて
      壊れます。import 行まで正確に写してください。
    - `from ..schemas import ...` …… 14.4 で写経した Pydantic
      モデルです。

追加されるエンドポイントは 7 つです。`main.py` の `prefix="/api"` が
付くので、実際の URL は先頭に `/api` が付きます。

- `GET /todos` …… 一覧。クエリパラメータ `filter` と `q` を
  `TodoListQuery` で受け取る
- `POST /todos` …… 新規作成。成功すると **201**
- `GET /todos/{todo_id}` …… 1 件取得。なければ **404**
- `PATCH /todos/{todo_id}` …… 部分更新。なければ **404**
- `POST /todos/{todo_id}/toggle` …… 完了フラグの切り替え。
  成功すると **200**、なければ **404**
- `DELETE /todos/{todo_id}` …… 削除。成功すると **204**、
  なければ **404**
- `GET /tags` …… タグの一覧

!!! note "FastAPI はパラメータの由来をどう見分けるか"
    このルーターには 3 種類のパラメータが登場します。
    FastAPI は関数シグネチャだけを見て、それぞれが**どこから来る値か**
    を自動的に判断してくれます。

    - パスの `{todo_id}` と同じ名前の引数は
      [パスパラメータ](https://fastapi.tiangolo.com/tutorial/path-params/)
      として扱われます（`get_todo(todo_id: int, ...)` など）。
      `/todos/abc` のように `int` に変換できない値を渡すと、
      ルーター関数が呼ばれる前に自動で 422 が返ります。
    - Pydantic モデルの型を持つ引数は
      [リクエストボディ](https://fastapi.tiangolo.com/tutorial/body/)
      として扱われ、JSON をパースしてバリデーションします
      （`create_todo(payload: TodoCreate, ...)` の `payload`）。
    - `list_todos` の `query: Annotated[TodoListQuery, Depends()]` は、
      `TodoListQuery` 自体を依存関数のように解決することで、
      `filter` と `q` という 2 つの
      [クエリパラメータ](https://fastapi.tiangolo.com/tutorial/query-params/)
      を 1 つの型にまとめて受け取っています。

    型と引数名の組み合わせだけでこれが決まるので、
    覚えてしまえば迷うことはありません。

ポイント:

- **`response_model=TodoOut`** …… デコレータに返り値の型を
  教えています。リポジトリが返した `Todo` dataclass を
  `TodoOut.model_validate(todo)` で変換して返すと、FastAPI が
  JSON に変換し、`/docs` のスキーマにも反映されます。
- **`model_dump(exclude_unset=True)`** …… `model_dump()` は
  Pydantic モデルを普通の `dict` に変換するメソッドです。
  `exclude_unset=True` を付けると「実際にリクエストに含まれていた
  キーだけ」が残った辞書になります。第11章で見た「未指定」と
  「明示的な NULL」を区別する話の API 版です。API 層ではこの
  `exclude_unset` でキーの有無を判定し、その結果を `_UNSET` 判定
  としてリポジトリ層に引き渡す、という役割分担になっています。
  これがあるので、`{"due_on": null}`（期限を消す）と
  `{}`（何も変えない）を区別できます。

!!! note "ステータスコードの使い分け（第8章の実装編）"
    第8章で決めた[ステータスコード](https://developer.mozilla.org/ja/docs/Web/HTTP/Status)
    の使い分けが、実際にどうコードに現れているか確認しておきましょう。

    - **201 Created**: `@router.post("/todos", ..., status_code=status.HTTP_201_CREATED)`
      のように、デコレータの引数で明示しています。
    - **204 No Content**: 同じように `status_code=status.HTTP_204_NO_CONTENT`
      を指定し、ボディを持たない `Response` を返しています。
    - **404 Not Found**: リポジトリが `None` を返してきた箇所で、
      自分で `raise HTTPException(status_code=404, detail=...)` して
      います。
    - **422 Unprocessable Content**: コード上のどこにも `422` という
      文字は出てきません。`TodoCreate` / `TodoPatch` / `TodoListQuery`
      のバリデーションに失敗すると、**ルーター関数が呼ばれる前に**
      FastAPI が自動で返してくれるからです。

    **422 は JSON の形は正しいがスキーマの制約を満たさないとき**、
    **404 はリクエストの形は正しいが対象が見つからないとき**、
    と覚えておくと迷いません。

## 14.7 動作確認: curl で CRUD を叩く

実装した API を curl で動かしてみます。
出力を読みやすくするため、まず DB を初期状態（シードの 4 件だけ）
に戻しておきます。`mytodo/` の中で実行してください。

```bash
uv run python -m app.cli reset-db
uv run python -m app.cli init-db
```

期待される出力:

```text
reset done
```

```text
apply  001_init
apply  002_seed
```

（`couldn't stop thread ...` という警告行が出ることがありますが、
第10章で見たとおり無害な警告です。）

続けてサーバーを起動します。

```bash
uv run uvicorn app.main:app --reload
```

期待される出力は第13章と同じで、最後に
`INFO:     Application startup complete.` と出れば起動成功です。
このあとの curl は**別のターミナル**を開いて実行してください。

まず一覧を取得します。シードデータの 4 件が返るはずです。

```bash
curl -s http://127.0.0.1:8000/api/todos | jq .
```

期待される出力（`due_on` と `created_at` / `updated_at` は実行した
日時で変わります）:

```json
[
  {
    "id": 1,
    "title": "牛乳を買う",
    "done": false,
    "due_on": "2026-08-15",
    "priority": 2,
    "tags": [
      {
        "id": 1,
        "name": "家事"
      }
    ],
    "created_at": "2026-08-14T11:00:45.623472+09:00",
    "updated_at": "2026-08-14T11:00:45.623472+09:00"
  },
  {
    "id": 2,
    "title": "健康診断の予約",
    "done": false,
    "due_on": "2026-08-16",
    "priority": 1,
    "tags": [
      {
        "id": 3,
        "name": "健康"
      }
    ],
    "created_at": "2026-08-14T11:00:45.623472+09:00",
    "updated_at": "2026-08-14T11:00:45.623472+09:00"
  },
  {
    "id": 4,
    "title": "家賃を振り込む",
    "done": false,
    "due_on": "2026-09-01",
    "priority": 1,
    "tags": [],
    "created_at": "2026-08-14T11:00:45.623472+09:00",
    "updated_at": "2026-08-14T11:00:45.623472+09:00"
  },
  {
    "id": 3,
    "title": "過去の領収書を整理",
    "done": false,
    "due_on": null,
    "priority": 3,
    "tags": [],
    "created_at": "2026-08-14T11:00:45.623472+09:00",
    "updated_at": "2026-08-14T11:00:45.623472+09:00"
  }
]
```

第9章で流したシードデータが、そのまま JSON になって返ってきました。
期限順（`due_on` が NULL のものは最後）に並んでいるのは、
第10章で `list_todos` に書いた `ORDER BY` の効果です。

次に新規作成です。期限・優先度・タグ付きで 1 件登録します。

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/todos \
  -H 'content-type: application/json' \
  -d '{"title":"パスポート更新", "due_on":"2026-09-30", "priority":1, "tags":["役所"]}'
```

期待される出力（`created_at` / `updated_at` は実行した日時で
変わります）:

```text
{"id":5,"title":"パスポート更新","done":false,"due_on":"2026-09-30","priority":1,"tags":[{"id":4,"name":"役所"}],"created_at":"2026-08-14T11:01:08.606426+09:00","updated_at":"2026-08-14T11:01:08.606426+09:00"}
HTTP 201
```

**201** が返り、採番された `id`（ここでは 5）が含まれています。
タグの `役所` は `tags` テーブルになかった名前ですが、第11章で
写経した upsert（`ON CONFLICT DO NOTHING`）のおかげで
新しいタグとして自動で作られ、紐付けられています。

以降の例では、この `id: 5` の ToDo を操作対象にします。
**自分の環境で返ってきた `id` に読み替えて**実行してください。

完了フラグを切り替えます。

```bash
curl -s -X POST http://127.0.0.1:8000/api/todos/5/toggle | jq .
```

期待される出力（`updated_at` だけが更新され、`done` が `true` に
変わります）:

```json
{
  "id": 5,
  "title": "パスポート更新",
  "done": true,
  "due_on": "2026-09-30",
  "priority": 1,
  "tags": [
    {
      "id": 4,
      "name": "役所"
    }
  ],
  "created_at": "2026-08-14T11:01:08.606426+09:00",
  "updated_at": "2026-08-14T11:01:09.125131+09:00"
}
```

次は部分更新です。`{"due_on": null}` を送って、**期限を消します**。

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/todos/5 \
  -H 'content-type: application/json' \
  -d '{"due_on": null}' | jq .
```

期待される出力（`due_on` が `null` になります）:

```json
{
  "id": 5,
  "title": "パスポート更新",
  "done": true,
  "due_on": null,
  "priority": 1,
  "tags": [
    {
      "id": 4,
      "name": "役所"
    }
  ],
  "created_at": "2026-08-14T11:01:08.606426+09:00",
  "updated_at": "2026-08-14T11:01:09.437107+09:00"
}
```

JSON で `null` を明示的に送ったので「期限を NULL に更新する」と
解釈されました。`model_dump(exclude_unset=True)` と `_UNSET` の
仕組みがなければ、「キーが無かった」のか「null が送られた」のかを
区別できず、この操作は書けませんでした。

削除します。`-i` を付けるとレスポンスヘッダも表示されます。

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/todos/5 -i
```

期待される出力（日付は変わります）:

```text
HTTP/1.1 204 No Content
date: Fri, 14 Aug 2026 02:01:09 GMT
server: uvicorn

```

**204** は「成功したが返すボディはない」という意味なので、
ヘッダだけが返ります。消えたことを 1 件取得で確認します。

```bash
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/todos/5
```

期待される出力:

```text
{"detail":"todo not found"}
HTTP 404
```

存在しない ID なので、ルーターの `raise HTTPException(status_code=404, ...)`
が効いて **404** が返りました。

最後に、わざと壊れたリクエストを送ってみます。
`priority` の範囲は 1〜3 なので、`5` は弾かれるはずです。

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/todos \
  -H 'content-type: application/json' \
  -d '{"title":"x", "priority":5}'
```

期待される出力:

```text
{"detail":[{"type":"less_than_equal","loc":["body","priority"],"msg":"Input should be less than or equal to 3","input":5,"ctx":{"le":3}}]}
HTTP 422
```

**ルーター関数は一度も呼ばれていません**。Pydantic が入口で
「`body` の `priority` は 3 以下でなければならない」と判定して、
自動で 422 とエラーの内訳（`detail`）を返しました。
`loc`（どこが悪いか）と `msg`（何が悪いか）の読み方は、
自分でバリデーションエラーに出会ったときの手がかりになります。

ブラウザで `http://127.0.0.1:8000/docs` を開くと、
第13章では真っ白だった **Swagger UI** に、いま実装した
7 つのエンドポイントがずらりと並んでいます。
「Try it out」から同じ操作を画面で試すこともできます。

!!! tip "手動確認と自動テストの役割分担"
    curl も Swagger UI も、**人間がその場で 1 回動かして確認する**
    ための道具です。「今動くかどうか」をサッと見るのには向いて
    いますが、確認するたびに自分の手でリクエストを組み立て直す
    必要があり、同じ確認を何度も繰り返す用途には向きません。
    次の 14.8 では、この確認を `TestClient` を使ってコードにし、
    `pytest` で**何度でも自動的に繰り返せる**形にします。

## 14.8 API のテスト: `tests/test_api.py`

[`TestClient`](https://fastapi.tiangolo.com/tutorial/testing/) を使うと、
実際に `uvicorn` を起動しなくてもアプリに直接リクエストを送れます。
14.7 の「手動で 1 回確認する」に対して、ここからは**同じ確認を
コードとして残し、`pytest` で何度でも実行できる**形にします。

`mytodo/tests/test_api.py` を作成して、次の内容を書き写してください。

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_via_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_create_then_list(client):
    r = client.post("/api/todos", json={"title": "API経由で追加"})
    assert r.status_code == 201
    body = r.json()
    new_id = body["id"]
    assert body["title"] == "API経由で追加"
    assert body["done"] is False

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

上から順に見ていきます。

- `client` フィクスチャ …… 第12章の `conn` フィクスチャと同じ
  形です。`with TestClient(app) as c:` としておくと、アプリの
  起動・終了処理もテストの前後できちんと実行されます。
  テスト関数は引数に `client` と書くだけで、HTTP クライアント
  （のような見た目のオブジェクト）を受け取れます。
- `test_health_via_docs` …… `/docs` が 200 を返すかの
  疎通確認です。
- `test_create_then_list` …… 14.7 の curl でやった
  「作って → 一覧に出る」をそのままコードにしたものです。
- `test_toggle_changes_done` / `test_patch_clears_due_on` ……
  toggle と「`{"due_on": null}` で期限を消す」部分更新の確認です。
- `test_validation_fails_on_*` …… 14.6 で説明した 422
  （バリデーション失敗）を実際に確認しています。
- `test_404_on_unknown_id` と `test_delete_removes` の後半 ……
  404（見つからない）を確認しています。

実行します。`mytodo/` の中で実行してください
（uvicorn は動かしたままでも、止めていても構いません。
TestClient はサーバーとは別にアプリを直接叩きます）。

```bash
uv run pytest -v
```

期待される出力（Python や pytest のバージョン、所要時間は
環境によって変わります）:

```text
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /home/.../mytodo
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2
collecting ... collected 18 items

tests/test_api.py::test_health_via_docs PASSED                           [  5%]
tests/test_api.py::test_create_then_list PASSED                          [ 11%]
tests/test_api.py::test_toggle_changes_done PASSED                       [ 16%]
tests/test_api.py::test_patch_clears_due_on PASSED                       [ 22%]
tests/test_api.py::test_validation_fails_on_empty_title PASSED           [ 27%]
tests/test_api.py::test_validation_fails_on_bad_priority PASSED          [ 33%]
tests/test_api.py::test_404_on_unknown_id PASSED                         [ 38%]
tests/test_api.py::test_delete_removes PASSED                            [ 44%]
tests/test_repositories.py::test_create_and_get PASSED                   [ 50%]
tests/test_repositories.py::test_filter_open_done PASSED                 [ 55%]
tests/test_repositories.py::test_search_with_q PASSED                    [ 61%]
tests/test_repositories.py::test_update_can_clear_due_on PASSED          [ 66%]
tests/test_repositories.py::test_update_partial_keeps_other_fields PASSED [ 72%]
tests/test_repositories.py::test_tags_attach_and_list PASSED             [ 77%]
tests/test_repositories.py::test_replace_tags_overrides_existing PASSED  [ 83%]
tests/test_repositories.py::test_delete_cascades_tags PASSED             [ 88%]
tests/test_repositories.py::test_get_unknown_returns_none PASSED         [ 94%]
tests/test_repositories.py::test_toggle_unknown_returns_none PASSED      [100%]

======================== 18 passed, 2 warnings in ... ========================
```

**`18 passed` と表示されればこの章の動作確認は成功です。**
第12章の 10 本に、この章の 8 本が増えて 18 本になりました。
末尾の `2 warnings` は、使っているライブラリのバージョンに関する
お知らせ（非推奨機能の予告など）で、テストの失敗ではありません。

!!! warning "API のテストは開発 DB に行を残します"
    第12章のテストは `conn` フィクスチャがロールバックするので
    DB を汚しませんでしたが、この章のテストは違います。
    `TestClient` はサーバーを立てずにアプリを直接叩きますが、
    DB アクセスは `get_conn` 経由で**本物のプール接続**に行き、
    リクエストごとに**コミット**されます（「1 リクエスト =
    1 トランザクション」の正常終了側です）。
    つまり、API テストを実行するたびに、開発用の `tododb` に
    テストが作った行が**そのまま残ります**。

    実際に見てみましょう。pytest を 1 回流したあと、psql で
    件数を数えます（接続の手順は第3章と同じです）。

    ```sql
    SELECT COUNT(*) FROM todos;
    ```

    ```text
     count
    -------
         7
    (1 row)
    ```

    シードの 4 件のはずが 7 件に増えています
    （作って消すテストがあるため、増え方は実行内容で変わります）。
    本研修ではこの挙動で十分ですが、CI できちんと分離したい場合は
    `tododb_test` のような別 DB を用意し、各テストの後に
    クリーンアップする仕組みを入れるのが定石です。

後片付けをして、DB を初期状態に戻しておきます。
`mytodo/` の中で実行してください。

```bash
uv run python -m app.cli reset-db
uv run python -m app.cli init-db
```

期待される出力:

```text
reset done
```

```text
apply  001_init
apply  002_seed
```

これで `todos` はシードの 4 件だけに戻ります。
このテキストでは、**API テストを流したら最後にこの 2 コマンドで
掃除する**、という習慣にしてください。

確認が終わったら、uvicorn を動かしているターミナルで `Ctrl+C` を
押してサーバーを止めてください。

## 14.9 答え合わせ: `diff` で完成版と比較する

この章で写経・差し替えした 4 ファイルを完成版と答え合わせします
（`diff` コマンドは**リポジトリのルート**で実行してください）。

```bash
diff -u mytodo/app/schemas.py sample/todo-app/app/schemas.py
diff -u mytodo/app/services.py sample/todo-app/app/services.py
diff -u mytodo/app/routers/todos.py sample/todo-app/app/routers/todos.py
diff -u mytodo/tests/test_api.py sample/todo-app/tests/test_api.py
```

この章では、**4 つとも何も表示されなければ一致**です。
第13章では `todos.py` の差分が出るのが正しい状態でしたが、
この章で完成版に丸ごと差し替えたので、差分なしになります。
差分が出たら写経ミスなので、表示された行を見比べて写し直してください。

なお `main.py` は、この時点ではまだ差分が出るのが正しい状態です
（第15章と第17章で追加して、最終的に一致させます）。

## 14.10 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] GET / POST / PATCH / DELETE がそれぞれどの操作に対応するか、
      成功時のステータスコードとともに説明できる
- [ ] 404 と 422 の違い（どちらが自動で返るかも含めて）を説明できる
- [ ] 入出力のスキーマを `TodoOut` / `TodoCreate` / `TodoPatch` の
      3 つに分ける理由を説明できる
- [ ] `from_attributes=True` が何を可能にするか説明できる
- [ ] `model_dump(exclude_unset=True)` と `_UNSET` の組み合わせで
      何を区別しているか説明できる
- [ ] `_UNSET` を `repositories.py` から import する理由
      （自分で `object()` を作ってはいけない理由）を説明できる
- [ ] curl で一覧・作成・切替・部分更新・削除を一通り確認した
- [ ] `uv run pytest -v` で `18 passed` を確認した
- [ ] API テストが開発 DB に行を残す理由を説明でき、
      `reset-db` と `init-db` で後片付けした
- [ ] 4 ファイルの `diff` がすべて差分なしになった

## 14.11 つまずきポイント

### uvicorn の起動時に `ImportError: cannot import name '_UNSET' from 'app.repositories'` と出る

第10〜11章で写経した `repositories.py` が完成版と一致していません
（`_UNSET` は第11章で追加された定数です）。
リポジトリのルートで次を実行し、差分があれば第11章に戻って
写経し直してください。

```bash
diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py
```

### POST や PATCH が 422 で弾かれる

送った JSON がスキーマに合っていません。
レスポンスの `detail` にある `loc`（どの項目か）と `msg`
（何がおかしいか）を読みましょう。よくある原因は、
キー名のタイポ（`titl` など）、`priority` に 1〜3 以外の値、
`due_on` の日付形式の間違い（`2026-13-40` のような存在しない日付）
です。

### pytest が接続エラーで全滅する

`psycopg.OperationalError: connection to server ... failed` が
大量に出る場合は、Docker の PostgreSQL が起動していません。
リポジトリのルートで `docker compose up -d` を実行してから
（第0章）、もう一度 `uv run pytest -v` を試してください。
この章のテストもモックを使わず本物の DB に接続します。

### curl やテストのあと、`GET /api/todos` の結果が増えている

壊れているのではなく、14.8 の警告で見たとおりの**仕様**です。
この API はリクエストごとにコミットするので、curl や TestClient
経由で作った ToDo はそのまま DB に残ります。
初期状態に戻したいときは、`reset-db` と `init-db` を実行してください。

## 14.12 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 いろいろな「壊れたリクエスト」で 422 の中身を観察する

14.7 では `priority: 5` で 422 を確かめました。
ほかにも 422 になるリクエストはいくつもあります。
次の 2 つを試して、それぞれの `detail` が何を教えてくれるかを
確認してください。

- 存在しない日付: `{"title":"x", "due_on":"2026-13-40"}`
- 範囲外の filter: `GET /api/todos?filter=archived`

??? example "解答例"

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/todos \
      -H 'content-type: application/json' \
      -d '{"title":"x", "due_on":"2026-13-40"}'
    ```

    期待される出力:

    ```text
    {"detail":[{"type":"date_from_datetime_parsing","loc":["body","due_on"],"msg":"Input should be a valid date or datetime, month value is outside expected range of 1-12","input":"2026-13-40","ctx":{"error":"month value is outside expected range of 1-12"}}]}
    HTTP 422
    ```

    続いてクエリパラメータのほうです。

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" 'http://127.0.0.1:8000/api/todos?filter=archived'
    ```

    期待される出力:

    ```text
    {"detail":[{"type":"literal_error","loc":["query","filter"],"msg":"Input should be 'all', 'open' or 'done'","input":"archived","ctx":{"expected":"'all', 'open' or 'done'"}}]}
    HTTP 422
    ```

    `loc` が `["body", "due_on"]` と `["query", "filter"]` で
    始まりが違う点に注目してください。リクエストボディの項目なのか
    クエリパラメータなのかも、エラーの場所として教えてくれます。
    `TodoListQuery` の `Literal` が効いて、ルーター関数に届く前に
    弾かれていることも確認できました。

### 問2 デフォルト値を確認するテストを追加する

`tests/test_api.py` に、「`title` だけ送って作成すると、
`priority` が省略時の既定値 2 で作られる」ことを確認するテストを
1 本追加して、実行してください。

??? example "解答例"

    `mytodo/tests/test_api.py` の末尾に次を追加します。

    ```python
    def test_default_priority_is_2(client):
        r = client.post("/api/todos", json={"title": "既定値の確認"})
        assert r.status_code == 201
        assert r.json()["priority"] == 2
    ```

    実行します（API テストだけに絞るならファイルを指定します）。

    ```bash
    uv run pytest tests/test_api.py -v
    ```

    期待される出力（抜粋）:

    ```text
    collecting ... collected 9 items
    ...
    tests/test_api.py::test_default_priority_is_2 PASSED
    ...
    ========================= 9 passed, 2 warnings in ... =========================
    ```

    `TodoCreate` の `priority: Priority = 2` という既定値が、
    API 越しにも効いていることが確認できました。
    確認が終わったら、`reset-db` と `init-db` で DB を掃除して
    おきましょう（この追加テストの行も残ります）。

### 問3 `services.py` の業務ルールを直接呼んでみる

14.5 で写経した `validate_due_on` は、まだどのエンドポイントからも
呼ばれていません。HTTP を通さなくても、普通の Python 関数として
直接試せることを確認してください。

??? example "解答例"

    `mytodo/` の中で実行します。

    ```bash
    uv run python -c "
    from datetime import date
    from app.services import validate_due_on
    print(validate_due_on(None))
    print(validate_due_on(date(2026, 12, 31)))
    print(validate_due_on(date(2099, 1, 1)))
    "
    ```

    期待される出力:

    ```text
    (True, None)
    (True, None)
    (False, '期限がだいぶ未来すぎます')
    ```

    引数が `None` の場合と、実行した日から 50 年以内の日付は
    `True`（許可）、50 年より先の日付は `False` とメッセージが
    返ります。こういう「業務の判断」を 1 関数にまとめておくと、
    基準が変わったときに直す場所が 1 か所で済みます。
    エンドポイントへの組み込み方は第17章で扱います。

## まとめ

- API の入出力は **Pydantic モデル**（`schemas.py`）で定義する。
  `TodoOut` / `TodoCreate` / `TodoPatch` のように**操作ごとに
  分ける**と、「必須かどうか」が操作によって違う制約を型で
  表現できる
- ルーターは SQL を書かず、リポジトリ層の関数を呼んで
  `TodoOut.model_validate(...)` で返すだけ。
  HTTP メソッドとステータスコード（201 / 204 / 404）の対応は
  デコレータと `HTTPException` で表現する
- **422 は Pydantic が自動で返す**（スキーマの制約を満たさない）、
  **404 は自分で `raise` する**（対象が見つからない）
- 部分更新は `model_dump(exclude_unset=True)` で「送られたキー」を
  判定し、`_UNSET`（`repositories.py` から import）で
  「未指定」と「明示的な NULL」を区別する
- `TestClient` を使うと、サーバーを立てずに API のテストが書ける。
  ただし DB には**本物の接続でコミット**されるので、テスト後は
  `reset-db` と `init-db` で掃除する
- `services.py` は業務ルールの置き場所。この章では写経だけで、
  エンドポイントへの組み込みは第17章で扱う

これで Part 5（API）の中核はおしまいです。
次は [第15章 Jinja2でHTML](15-ui-jinja2.md) で、
同じリポジトリ層の上に**画面**を作っていきます。
