# 第15章 Jinja2でHTML

第14章までで、JSON を返す API が完成しました。
この章では、その上に **ブラウザで触れる画面**を作ります。
本研修では JavaScript フレームワーク（React / Vue など）は使わず、
**サーバー側で HTML を組み立てて返す**方式（サーバーサイドレンダリング）
を採ります。HTML の組み立てに使うのがテンプレートエンジンの
**Jinja2** です。

リポジトリの `sample/todo-app/` は引き続き**答え合わせ用の完成版**です。
この章で写経する `routers/pages.py`、`templates/` の 4 ファイル、
`static/style.css` はすべて完成版の実ファイルと同じ内容なので、
写経が終わったら `diff` で答え合わせをします。
`main.py` は import 行ごと書き換えて pages ルーターと静的ファイルを
組み込みます（残りの部分は第17章で追加し、そこで完成版と一致します）。

## 15.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- サーバーサイドレンダリングとは何か、SPA との違いを説明できる
- テンプレートエンジンの役割と、Jinja2 の `{{ }}` / `{% %}` の
  書き方を説明できる
- テンプレート継承（`extends` / `block`）と部分テンプレート
  （`include`）の違いを説明できる
- `app/routers/pages.py`、`app/templates/`（4 ファイル）、
  `app/static/style.css` を写経できる
- `app/main.py` に pages ルーターと静的ファイルのマウントを
  追加できる
- ブラウザで ToDo の一覧・絞り込み・追加・切替・削除が動くことを
  確認できる
- 写経した 6 ファイルの `diff` が完成版と**差分なし**になり、
  `main.py` の差分が「第17章で追加する部分のみ」になることを
  確認できる

**所要時間の目安: 75 分**

!!! info "前提となる状態"
    - 第14章末時点の `mytodo/`（JSON API が完成し、
      `uv run pytest -v` が 18 本パスする）がある
    - 第0章の Docker の PostgreSQL が起動している（`docker compose up -d`）
    - `init-db` 適用済みで、シードデータが入った状態である

## 15.2 前提知識

コードに入る前に、この章の鍵になる概念を押さえておきます。

!!! note "サーバーサイドレンダリングとは"
    第13〜14章で作った API が返していたのは **JSON** でした。
    JSON は「データの入れ物」であって画面ではないので、それを
    人間が読める見た目にするには、受け取った側（ブラウザ上の
    JavaScript など）が別途組み立てる必要があります。
    React / Vue のような SPA（シングルページアプリケーション）では
    まさにこの分担で、サーバーは JSON だけを返し、
    画面の組み立てはブラウザ側の JavaScript が担います。

    **サーバーサイドレンダリング（SSR）** はその逆で、
    **サーバーが HTML を完成させてから返す**方式です。
    ブラウザは届いた HTML を表示するだけでよく、画面組み立ての
    ロジックをブラウザ側に持つ必要がありません。
    この章で作る `GET /` は、JSON ではなく **HTML 文書**を返す
    エンドポイントです。歴史のある古典的な方式で、
    「サーバー側の Python だけで画面まで完結させたい」
    本研修のような構成に向いています。

!!! note "テンプレートエンジンの役割"
    HTML を返すだけなら、Python の f-string で
    `f"<li>{t.title}</li>"` のように文字列を組み立てることもできます。
    ですが ToDo が何十件も並ぶ一覧や、`if` で表示を出し分ける画面に
    なってくると、HTML タグと Python のロジックが文字列の中で
    混ざり合い、すぐ読みにくくなります。
    「見た目は HTML のまま書きつつ、動的な部分だけを差し込みたい」
    というニーズに応えるのが**テンプレートエンジン**です。

    [Jinja2](https://jinja.palletsprojects.com/) は Python 製の
    テンプレートエンジンで、HTML の中に次の 2 種類の記法を
    埋め込めます。

    ```html
    <h1>こんにちは、{{ name }}さん</h1>
    <ul>
      {% for t in todos %}
        <li>{{ t.title }}</li>
      {% endfor %}
    </ul>
    ```

    - `{{ ... }}` …… **値を出力する式**
    - `{% ... %}` …… `for` や `if` のような**制御構文**

    この 2 つだけで、ほとんどのテンプレートは書けます。
    FastAPI には Jinja2 をそのまま使うための薄いラッパー
    `Jinja2Templates` が用意されていて
    （[FastAPI公式: テンプレート](https://fastapi.tiangolo.com/advanced/templates/)）、
    テンプレートを置くディレクトリを指定するだけで使えます。
    設定は 15.4 で行います。

!!! warning "Jinja2 の自動エスケープと XSS"
    ユーザーの入力（ToDo のタイトルなど）をそのまま HTML に
    埋め込んでしまうと、**[XSS（クロスサイトスクリプティング）](https://developer.mozilla.org/ja/docs/Web/Security/Attacks/XSS)**
    の温床になります。悪意のある入力に埋め込まれた `<script>` タグが
    そのままブラウザで実行されてしまう脆弱性で、放置すると
    攻撃者が他のユーザーのブラウザ上で任意のスクリプトを
    動かせてしまいます。

    Jinja2 は `{{ ... }}` で出力する値を**自動的に HTML エスケープ**
    します。具体的には `<` を `&lt;`、`>` を `&gt;`、`&` を `&amp;`
    のような**文字参照**に変換してから出力するので、ブラウザはそれを
    「タグの開始」とは解釈できません。つまり
    `<script>alert(1)</script>` というタイトルを保存しても、
    画面にはそのまま文字として出るだけで、スクリプトは実行されません。
    FastAPI の `Jinja2Templates` はこの自動エスケープを
    デフォルトで有効にした状態でテンプレートを読み込むので、
    こちらで何か設定しなくても最初から安全な状態になっています。

    これを破るのが `{{ value | safe }}` というフィルタです。
    「自分が書いた信頼できる HTML 文字列だから、エスケープせず
    そのまま出力してよい」という場面のための機能ですが、
    **ユーザー入力に対して安易に使わない**でください。
    使うと自動エスケープが無効になり、XSS の入り口になります。
    実際にエスケープが効くことは、15.14 のやってみようで確認します。

## 15.3 ここまでのファイル構成

まず現在地を確認します。第14章末時点の `mytodo/` は次の構成です。

```text
mytodo/
├── pyproject.toml          第10章で作成（jinja2・python-multipart 入り）
├── uv.lock                 uv sync が自動生成
├── .venv/                  uv sync が自動生成
├── app/
│   ├── __init__.py         第10章で作成（空ファイル）
│   ├── config.py           第10章で作成
│   ├── db.py               第10章で作成
│   ├── cli.py              第10章で作成
│   ├── models.py           第10章で作成
│   ├── repositories.py     第10〜11章で作成（完成版と一致済み）
│   ├── schemas.py          第14章で作成（完成版と一致済み）
│   ├── services.py         第14章で作成（完成版と一致済み）
│   ├── main.py             第13章で作成（最小構成）→ この章で上書き
│   ├── routers/
│   │   ├── __init__.py     第13章で作成（空ファイル）
│   │   ├── todos.py        第14章で作成（完成版と一致済み）
│   │   └── pages.py        ← この章で作成
│   ├── templates/          ← この章で作成
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── _list.html
│   │   └── _row.html
│   └── static/             ← この章で作成
│       └── style.css
├── migrations/
│   ├── 001_init.sql        第9章で作成・tododb に適用済み
│   └── 002_seed.sql        第9章で作成・tododb に適用済み
└── tests/
    ├── __init__.py         第12章で作成（空ファイル）
    ├── conftest.py         第12章で作成
    ├── test_repositories.py 第12章で作成
    └── test_api.py         第14章で作成
```

Jinja2 と python-multipart（フォーム送信の解析に必要）は、
第10章で写経した `pyproject.toml` の依存にすでに入っています。
新しいパッケージの追加は不要です。

先にディレクトリだけ作っておきます。`mytodo/` の中で実行してください。

```bash
mkdir app/templates app/static
```

## 15.4 ページ用ルーター: `app/routers/pages.py`

API は `/api/...` に置きましたが、画面用のルーターは `/`（ルート）
側に置きます。`mytodo/app/routers/pages.py` を作成して、
次の内容を書き写してください。

```python
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
```

!!! warning "htmx 用のエンドポイントは第16章で説明します"
    このファイルの後半にある `list_partial`（`/partials/list`）と
    `htmx_create` / `htmx_toggle` / `htmx_delete`（`/htmx/...`）の
    4 つ、およびそれらが使う `Form`・`_date` の import は、
    **第16章で扱う htmx という仕組みのための部品**です。
    JSON ではなく **HTML の断片**（部分テンプレートの描画結果）を
    返す点以外は `index` と同じ仕組みなので、本章では詳しい説明を
    省略し、そのまま写経してください。本章末の `diff` 答え合わせで
    「差分なし」にするために、省略せず全文写す必要があります。

上から順に見ていきます。

- `_TEMPLATES_DIR` …… テンプレートを探すディレクトリです。
  `pages.py` は `app/routers/` にあるので、
  `Path(__file__).resolve().parent.parent` で `app/` に上がり、
  その下の `templates/` を指しています。`Path(__file__)` を
  起点にする理由は 15.9 の tip で説明します。
- `templates = Jinja2Templates(directory=...)` ……
  **テンプレートを探すディレクトリを 1 つ知っているオブジェクト**
  です。中身は Jinja2 の `Environment` を FastAPI 用に薄く
  ラップしたもので、アプリ起動時に一度だけ作ればよく、
  リクエストのたびに作り直す必要はありません。
- `get_conn` と `Conn` …… 第13〜14章の `routers/todos.py` と
  まったく同じ DI の形です。ページ側のエンドポイントでも
  「1 リクエスト = 1 トランザクション」になります。
- `templates.env.globals["PRIORITY_LABEL"] = ...` ……
  `templates.env` で、ラップされている **Jinja2 の
  `Environment` そのもの**にアクセスできます。`globals` は
  テンプレート側から常に参照できる変数の置き場所で、ここに
  `PRIORITY_LABEL` を登録しておくと、以降どのテンプレートでも
  `{{ PRIORITY_LABEL[...] }}` のように**コンテキストに含めなくても**
  参照できます（15.7 の `_row.html` で使います）。
- `@router.get("/", response_class=HTMLResponse)` ……
  このルーターには `prefix` を付けずに組み込む（15.9）ので、
  URL はそのまま `GET /` です。`response_class=HTMLResponse` は
  「返すのは JSON ではなく HTML」という宣言で、`/docs` 上の表示や
  レスポンスの `Content-Type` に反映されます。
- `templates.TemplateResponse(request, "index.html", {...})` ……
  **第一引数が必ず `request`** です。`Jinja2Templates` は内部で
  `request` を使うため、渡し忘れるとエラーになります。
  第二引数がテンプレートファイル名、第三引数の辞書が
  **コンテキスト（context）**——テンプレート内で
  `{{ todos }}` のように参照できる変数の集合です。
- `filter: Literal["all", "open", "done"] = "all"` ……
  第14章で `TodoListQuery` に使ったのと同じ `Literal` 型を、
  クエリパラメータの型ヒントとして直接使っています。
  `?filter=xxx` のように許可していない値が来ると、
  FastAPI が自動で 422 を返します（15.10 で確認します）。

## 15.5 土台テンプレート: `app/templates/base.html`

全ページで共通する枠組みです。`<head>` の中身やヘッダー・フッターは、
`index.html` だけでなく将来増えるページ全部で同じものを使い回したい
はずです。ページごとに全文コピペしてしまうと、フッターの文言を
1 つ変えるだけで全ファイルを直すはめになります。そこで Jinja2 の
**テンプレート継承**を使い、共通部分を 1 つの「土台」テンプレートに
まとめておきます。

`mytodo/app/templates/base.html` を作成して、次の内容を書き写して
ください。

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}ToDo{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://unpkg.com/htmx.org@2.0.3"></script>
</head>
<body>
  <header>
    <h1>ToDo</h1>
  </header>
  <main>
    {% block main %}{% endblock %}
  </main>
  <footer>
    <small>Python + PostgreSQL ToDoアプリ研修</small>
  </footer>
</body>
</html>
```

- `{% block xxx %}{% endblock %}` …… **子テンプレートで上書きできる
  差し込み口（プレースホルダー）**です。`base.html` 自身は骨組み
  だけを持ち、`title` や `main` の中身は `{% extends %}` した
  子テンプレート側が埋めます（15.6 で見ます）。
- `<link rel="stylesheet" href="/static/style.css">` ……
  15.8 で作る CSS ファイルを読み込みます。`/static` から始まる
  URL がどう配信されるかは 15.9 で説明します。
- `<script src="https://unpkg.com/htmx.org@2.0.3"></script>` ……
  **第16章で使う htmx の読み込み**です。本章ではおまじないとして
  そのまま写経してください。これがあるため、本章末の画面はすでに
  部分更新（ページ全体を読み込み直さない書き換え）で動きますが、
  その原理は第16章で説明します。なお、CDN から読み込めない
  環境では `hx-` 属性は単に無視され、絞り込みフォームは通常の
  GET 送信（ページ全体の再読み込み）として動きます。

## 15.6 一覧ページ: `app/templates/index.html`

`{% extends "base.html" %}` を先頭に書くと、このテンプレートは
`base.html` を土台として使う、という意味になります。
`{% block main %}...{% endblock %}` で囲んだ内容が、`base.html` 側の
同じ名前の `block` にそのまま差し込まれます。
`extends` はテンプレートファイルの一番最初に 1 回だけ書く決まりです。

`mytodo/app/templates/index.html` を作成して、次の内容を書き写して
ください。

```html
{% extends "base.html" %}
{% block main %}
<section class="filters">
  <form
    hx-get="/partials/list"
    hx-target="#todo-list"
    hx-trigger="change from:input[name='filter'], submit, keyup changed delay:300ms from:input[name='q']"
    hx-include="this"
  >
    <label><input type="radio" name="filter" value="all"  {% if filter=='all'  %}checked{% endif %}> 全て</label>
    <label><input type="radio" name="filter" value="open" {% if filter=='open' %}checked{% endif %}> 未完了</label>
    <label><input type="radio" name="filter" value="done" {% if filter=='done' %}checked{% endif %}> 完了</label>
    <input type="search" name="q" value="{{ q }}" placeholder="検索..." autocomplete="off">
  </form>
</section>

<section id="todo-list">
  {% include "_list.html" %}
</section>

<section class="add">
  <form
    hx-post="/htmx/todos"
    hx-target="#todo-list"
    hx-on::after-request="this.reset()"
  >
    <input type="text" name="title" required placeholder="やること..." maxlength="200">
    <input type="date" name="due_on">
    <select name="priority" aria-label="優先度">
      <option value="1">高</option>
      <option value="2" selected>中</option>
      <option value="3">低</option>
    </select>
    <button type="submit">追加</button>
  </form>
</section>
{% endblock %}
```

- `{% if filter=='all' %}checked{% endif %}` …… コンテキストの
  `filter`（15.4 の `index` が渡した値）に応じて、該当する
  ラジオボタンだけに `checked` を付けています。`?filter=open` で
  開き直したとき「未完了」が選ばれた状態になるのはこの仕組みです。
- `value="{{ q }}"` …… 検索欄にいまの検索語を表示し直しています。
  ここでも自動エスケープが効くので、検索語に `<` が含まれていても
  安全です。
- `{% include "_list.html" %}` …… `extends` とは別物です。
  `extends` が「ページ全体の骨組みを 1 つ選ぶ」ものなのに対し、
  `include` は**その場に別テンプレートの中身をそのまま埋め込む**
  命令で、1 つのテンプレートの中で何度でも、好きな場所に書けます。
  中身は 15.7 で作ります。
- `hx-get` / `hx-target` / `hx-post` などの `hx-` で始まる属性 ……
  第16章の htmx 用の宣言です。本章ではそのまま写経してください。

## 15.7 部分テンプレート: `_list.html` と `_row.html`

`_` で始まるファイル名は、**「他のテンプレートから include される
部分」という習慣**（ページの本体ではない、という目印）です。
このような、単体では完結しない小さな部品を
**部分テンプレート（パーシャル）**と呼びます。

`mytodo/app/templates/_list.html` を作成して、次の内容を書き写して
ください。

```html
{% if todos|length == 0 %}
  <p class="empty">該当する ToDo はありません。</p>
{% else %}
<table class="todos">
  <thead>
    <tr>
      <th>状態</th>
      <th>やること</th>
      <th>期限</th>
      <th>優先</th>
      <th>タグ</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    {% for t in todos %}
      {% include "_row.html" %}
    {% endfor %}
  </tbody>
</table>
{% endif %}
```

続いて `mytodo/app/templates/_row.html` を作成して、次の内容を
書き写してください。

```html
<tr id="todo-{{ t.id }}" class="{% if t.done %}done{% endif %}">
  <td>
    <button
      class="toggle"
      aria-label="完了切替"
      hx-post="/htmx/todos/{{ t.id }}/toggle"
      hx-target="#todo-{{ t.id }}"
      hx-swap="outerHTML"
    >{% if t.done %}☑{% else %}☐{% endif %}</button>
  </td>
  <td class="title">{{ t.title }}</td>
  <td>{{ t.due_on or '—' }}</td>
  <td>{{ PRIORITY_LABEL[t.priority] }}</td>
  <td class="tags">
    {% for g in t.tags %}<span class="tag">{{ g.name }}</span>{% endfor %}
  </td>
  <td>
    <button
      class="del"
      aria-label="削除"
      hx-delete="/htmx/todos/{{ t.id }}"
      hx-target="#todo-{{ t.id }}"
      hx-swap="outerHTML"
      hx-confirm="削除してええ？"
    >×</button>
  </td>
</tr>
```

ポイント:

- `todos|length` の `|length` は **Jinja2 のフィルタ**です。
  `値 | フィルタ名` という書き方で、値を加工した結果を式の中で
  使えます。Python の `len(todos)` に近い意味ですが、テンプレートの
  中では組み込み関数ではなくフィルタとして提供されています。
- `{{ t.due_on or '—' }}` …… Jinja2 の式の中でも Python とほぼ
  同じ `or` 演算子が使えます。`due_on` が `None`（期限なし）の
  ときだけ `'—'` を表示します。
- `{{ PRIORITY_LABEL[t.priority] }}` …… 15.4 で
  `templates.env.globals` に登録した辞書を、そのまま添字アクセスで
  参照しています。コンテキストに含めなくても使えるのが globals の
  効果です。
- `{% for t in todos %}{% include "_row.html" %}{% endfor %}` ……
  `include` はループの中でも使えます。`_row.html` の中では、
  ループ変数 `t` がそのまま見えています（include 先には呼び出し元の
  コンテキストが引き継がれます）。
- `_row.html` のボタンについている `hx-post` / `hx-delete` /
  `hx-target` / `hx-swap` も第16章の htmx 用です。

なぜわざわざ部分テンプレートに分けるのかというと、第16章で
**「一覧全体ではなく、一覧の断片や行 1 本だけを返す」**エンドポイント
（15.4 で写経した `/partials/list` や `/htmx/...`）から同じ見た目を
再利用するためです。もし `<table>` の組み立てを `index.html` に
直接書いていたら、同じロジックを 2 箇所に重複して書くはめに
なります。切り出しておけば、ページ全体を返すときも断片だけ返す
ときも `{% include %}` するだけで済み、中身は 1 箇所で管理できます。

## 15.8 静的ファイル: `app/static/style.css`

見た目を整える CSS です。`mytodo/app/static/style.css` を作成して、
次の内容を書き写してください。

```css
* { box-sizing: border-box; }
body {
  font-family: system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif;
  margin: 0;
  background: #f7f7f9;
  color: #222;
  line-height: 1.6;
}
header, main, footer {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px;
}
header h1 { margin: 8px 0; font-size: 1.5rem; }

.filters form {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.filters input[type="search"] {
  flex: 1;
  min-width: 160px;
  padding: 6px 8px;
  border: 1px solid #ccd;
  border-radius: 6px;
}

.todos {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.todos th, .todos td {
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
  text-align: left;
  vertical-align: middle;
}
.todos th { font-size: 0.85em; color: #666; background: #fafafc; }
.todos tr.done .title { text-decoration: line-through; color: #888; }
.toggle, .del {
  cursor: pointer;
  border: none;
  background: transparent;
  font-size: 1.1em;
  padding: 4px 8px;
}
.toggle:focus-visible, .del:focus-visible {
  outline: 2px solid #88a; outline-offset: 2px;
}
.del { color: #b00020; }

.empty {
  text-align: center;
  color: #888;
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}

.add form {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.add input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 6px 8px;
  border: 1px solid #ccd;
  border-radius: 6px;
}
.add input[type="date"], .add select {
  padding: 6px 8px;
  border: 1px solid #ccd;
  border-radius: 6px;
}
.add button {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  background: #4a5cc8;
  color: #fff;
  cursor: pointer;
}
.add button:hover { background: #3a4cb8; }

.tag {
  display: inline-block;
  font-size: 0.78em;
  padding: 1px 8px;
  margin-right: 4px;
  background: #eef;
  border-radius: 999px;
  color: #449;
}

footer { text-align: center; color: #888; }
```

クラス名はテンプレート側と対応しています。たとえば
`.todos tr.done .title` は、`_row.html` で `done` クラスが付いた
行のタイトルに取り消し線を引く指定です。CSS の細かい説明は
本研修の範囲外なので、写経して雰囲気を掴めば十分です。

## 15.9 `main.py` に pages ルーターと静的ファイルを組み込む

最後に、第13章で作った最小構成の `main.py` を育てます。
import 行が変わる関係で一部分だけの書き換えでは済まないため、
**ファイル全体を次の内容で上書きしてください**。

`mytodo/app/main.py` を、次の内容で**丸ごと上書き**してください。

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import pages, todos

app = FastAPI(title="ToDo App", version="0.1.0")

_BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")

app.include_router(pages.router)
app.include_router(todos.router, prefix="/api")
```

ポイント:

- `app.mount("/static", StaticFiles(directory=...), name="static")`
  …… CSS のような**静的ファイル**（リクエストのたびに中身が
  変わらないファイル）は、`@router.get(...)` のような動的な
  エンドポイントとは性質が違います。1 ファイルごとに専用のルート
  関数を書いていたら、ファイルが増えるたびにコードが増えます。
  そこで、**`/static` から始まる URL をまるごと `StaticFiles`
  という別のアプリに任せる**のが `app.mount(...)` です
  （[FastAPI公式: 静的ファイル](https://fastapi.tiangolo.com/tutorial/static-files/)）。
  `StaticFiles` は拡張子から適切な `Content-Type` を判定したり、
  存在しないファイルに自動で 404 を返したりする面倒を引き受けて
  くれます。これで `app/static/style.css` が
  `http://127.0.0.1:8000/static/style.css` で配信されます。
- `app.include_router(pages.router)` …… ページ用ルーターは
  `prefix` なしで組み込みます。`pages.py` の `@router.get("/")` が
  そのまま `GET /` になります。

!!! tip "`Path(__file__)` で場所を固定する理由"
    `_BASE = Path(__file__).resolve().parent` は、**このファイル
    （`main.py`）自身が置かれている場所**を起点にして `static`
    ディレクトリを探しています。`"app/static"` のような相対パスを
    直接書くと、`uvicorn` をどのディレクトリから起動したか
    （カレントディレクトリ）によって見つかったり見つからなかったり
    する事故が起きます。`__file__` はこのモジュールのファイルパス、
    `.resolve()` はそれを絶対パスに変換するメソッドです
    （[`pathlib`](https://docs.python.org/3/library/pathlib.html)）。
    起動場所に関係なく常に同じディレクトリを指せるので安全です。
    15.4 の `_TEMPLATES_DIR` が `.parent.parent` だったのも
    同じ発想です（`pages.py` は `app/` の 1 階層下にあるため）。

!!! warning "`main.py` は第17章で完成します"
    完成版の `main.py` には、このほかにログ設定、リクエストの
    ログを残すミドルウェア、想定外の例外をまとめて処理する
    ハンドラが入っています。これらは**第17章で追加して完成版と
    一致させます**。この章の時点で完成版と `diff` を取ると差分が
    出ますが、それが正しい状態です（差分の見方は 15.11 で
    説明します）。

## 15.10 動作確認: ブラウザで画面を見る

いよいよ画面を動かします。まず、第14章の curl やテストで残った
行を掃除して、DB を初期状態（シードの 4 件だけ）に戻しておきます。
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

（`couldn't stop thread ...` という警告行が出ることがありますが、
第10章で見たとおり無害な警告です。）

続けてサーバーを起動します。

```bash
uv run uvicorn app.main:app --reload
```

期待される出力は第13章と同じで、最後に
`INFO:     Application startup complete.` と出れば起動成功です。
このあとの curl は**別のターミナル**を開いて実行してください。

**ブラウザで `http://127.0.0.1:8000/` を開いてください。**
CSS の効いた一覧画面に、シードの 4 件（牛乳を買う、
健康診断の予約、家賃を振り込む、過去の領収書を整理）が
表で並んでいるはずです。次の操作を試してみましょう。

- 「未完了」「完了」のラジオボタンや検索欄で一覧が絞り込まれる
- 下のフォームから新しい ToDo を追加できる
- 各行の `☐` を押すと `☑` になり、タイトルに取り消し線が付く
- `×` を押すと（確認ダイアログのあと）行が消える

`base.html` の `<script>` と各テンプレートの `hx-` 属性が効いて
いる環境では、これらの操作は**ページ全体の再読み込みではなく、
一覧や行の部分だけの書き換え**で動きます。なぜそうなるかは
第16章で説明するので、いまは「動いた」ことの確認だけで大丈夫です。

curl 側からも確認しておきます。まず `GET /` が HTML を返すことです。

```bash
curl -s http://127.0.0.1:8000/ | grep 'class="title"'
```

期待される出力（順序は期限順です）:

```html
  <td class="title">牛乳を買う</td>
  <td class="title">健康診断の予約</td>
  <td class="title">家賃を振り込む</td>
  <td class="title">過去の領収書を整理</td>
```

第14章まで JSON を返していたのと同じリポジトリ層から、
今度は HTML が組み立てられて返ってきています。

静的ファイルの配信も確認します。

```bash
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8000/static/style.css
```

期待される出力:

```text
200 text/css; charset=utf-8
```

15.9 で `mount` した `StaticFiles` が、拡張子から `text/css` を
判定して返しています。

最後に、許可していない `filter` を送ってみます。

```bash
curl -s -w "\nHTTP %{http_code}\n" "http://127.0.0.1:8000/?filter=xxx"
```

期待される出力:

```text
{"detail":[{"type":"literal_error","loc":["query","filter"],"msg":"Input should be 'all', 'open' or 'done'","input":"xxx","ctx":{"expected":"'all', 'open' or 'done'"}}]}
HTTP 422
```

ページ用のエンドポイントでも、`Literal` の型ヒントのおかげで
ルーター関数が呼ばれる前に自動で 422 が返りました。
第14章の JSON API と同じバリデーションが効いています。

確認が終わったら、uvicorn を動かしているターミナルで `Ctrl+C` を
押してサーバーを止めてください。

## 15.11 答え合わせ: `diff` で完成版と比較する

写経したファイルを完成版と答え合わせします
（`diff` コマンドは**リポジトリのルート**で実行してください）。

```bash
diff -u mytodo/app/routers/pages.py sample/todo-app/app/routers/pages.py
diff -u mytodo/app/templates/base.html sample/todo-app/app/templates/base.html
diff -u mytodo/app/templates/index.html sample/todo-app/app/templates/index.html
diff -u mytodo/app/templates/_list.html sample/todo-app/app/templates/_list.html
diff -u mytodo/app/templates/_row.html sample/todo-app/app/templates/_row.html
diff -u mytodo/app/static/style.css sample/todo-app/app/static/style.css
diff -u mytodo/app/main.py sample/todo-app/app/main.py
```

判定の基準はファイルで分かれます。

- **`pages.py`・`templates/` の 4 ファイル・`style.css`** ……
  **何も表示されなければ一致**です。差分が出たら写経ミスなので、
  表示された行を見比べて写し直してください
  （やってみようで手を加えた場合は、元に戻してから比較します）。
- **`main.py`** …… **差分が出るのが正しい状態**です。
  `-`（あなたのファイルにだけある行）が
  `from fastapi import FastAPI` の 1 行だけで、残りはすべて
  `+`（完成版にだけある行）であることを確認してください。
  `-` の行が import に現れるのは、完成版ではこの行が
  `from fastapi import FastAPI, Request` に変わるためです。
  `+` の中身はログ設定・リクエストログのミドルウェア・
  例外ハンドラとその import で、**第17章で追加します**。

## 15.12 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] サーバーサイドレンダリングとは何か、SPA との分担の違いを
      説明できる
- [ ] テンプレートエンジンを使う理由（f-string での文字列組み立ての
      何がつらいか）を説明できる
- [ ] Jinja2 の `{{ }}` と `{% %}` の役割の違いを説明できる
- [ ] `extends` / `block`（テンプレート継承）と `include`
      （部分テンプレート）の違いを説明できる
- [ ] `templates.TemplateResponse(...)` の 3 つの引数
      （`request`・テンプレート名・コンテキスト）を説明できる
- [ ] `templates.env.globals` に登録すると何がうれしいか説明できる
- [ ] `app.mount("/static", StaticFiles(...))` が何をしているか
      説明できる
- [ ] `Path(__file__)` で場所を固定する理由を説明できる
- [ ] Jinja2 の自動エスケープが XSS をどう防ぐか説明できる
- [ ] ブラウザで一覧・絞り込み・追加・切替・削除が動くことを確認した
- [ ] 6 ファイルの `diff` が差分なし、`main.py` の差分が
      15.11 の基準どおりになった

## 15.13 つまずきポイント

### `jinja2.exceptions.TemplateNotFound: index.html`

テンプレートの置き場所が違います。`_TEMPLATES_DIR` は
`pages.py` から見て `app/templates/` を指すので、
`mytodo/templates/` や `app/routers/templates/` に作ってしまった
場合は `app/templates/` に移してください。`--reload` で動かしている
途中にファイルを動かした場合は、いったん `Ctrl+C` で止めてから
起動し直すと確実です。

### 画面は出るが CSS が効かない

ブラウザで `http://127.0.0.1:8000/static/style.css` を直接開いて
ください。404 なら静的ファイルの配信が動いていません。
原因の候補は、`main.py` の上書きを忘れている（`mount` が無い）、
`style.css` を `app/static/` 以外に作ってしまった、のどちらかです。
`main.py` を直したら uvicorn を再起動してください。

### uvicorn の起動時に `ModuleNotFoundError: No module named 'jinja2'`（または `'multipart'`）

依存パッケージがまだインストールされていません。
`jinja2` と `python-multipart` は第10章で写経した
`pyproject.toml` の依存に入っているので、`mytodo/` の中で
`uv sync` を実行してから起動し直してください。

### ブラウザが真っ白、または 500 Internal Server Error になる

uvicorn を動かしているターミナルに Traceback が出ているはずなので、
まずそれを読みます。`psycopg.OperationalError` が見える場合は
Docker の PostgreSQL が起動していません。リポジトリのルートで
`docker compose up -d` を実行してください。
なお、いまの `main.py` には第17章で追加する例外ハンドラがまだ
無いので、エラー時は素の Traceback がそのまま出ます。
それが現時点では正常な動作です。

## 15.14 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 空のときのメッセージを変える

`_list.html` の「該当する ToDo はありません。」を、自分の言葉
（たとえば「なにも見つかりませんでした」）に変えて、実際に
空の状態の画面で表示を確認してください。
ヒント: 検索欄に存在しない文字列を入れると 0 件になります。

??? example "解答例"

    `mytodo/app/templates/_list.html` の 2 行目を次のように変えます。

    ```html
      <p class="empty">なにも見つかりませんでした。</p>
    ```

    サーバーを起動してブラウザの検索欄に `zzz` などと入れるか、
    curl で確認します。

    ```bash
    curl -s -G http://127.0.0.1:8000/ --data-urlencode "q=zzz" | grep empty
    ```

    期待される出力:

    ```html
      <p class="empty">なにも見つかりませんでした。</p>
    ```

    `{% if todos|length == 0 %}` の分岐が実際に通っていることが
    確認できました。確認が終わったら文言を元に戻すか、
    15.11 の `diff` で差分として残っていることを意識しておいて
    ください（第16章に進む前に元に戻すのがおすすめです）。

### 問2 自動エスケープを確かめる

`<script>alert("xss")</script>` というタイトルの ToDo を API 経由で
登録し、画面（と `GET /` の HTML）でどう表示されるか確認して
ください。

??? example "解答例"

    第14章の API 経由で登録します。

    ```bash
    curl -s -X POST http://127.0.0.1:8000/api/todos \
      -H 'content-type: application/json' \
      -d '{"title":"<script>alert(\"xss\")</script>"}'
    ```

    期待される出力（`201` で作られます。`id`・`created_at` などは
    環境によって変わるため一部省略しています）:

    ```text
    {"id":5,"title":"<script>alert(\"xss\")</script>","done":false,...}
    ```

    ブラウザで `http://127.0.0.1:8000/` を開くと、スクリプトは
    **実行されず**、タイトルがそのまま文字として表示されます。
    返ってくる HTML を見ると、エスケープされていることが
    わかります。

    ```bash
    curl -s http://127.0.0.1:8000/ | grep 'class="title"'
    ```

    期待される出力（抜粋）:

    ```html
      <td class="title">&lt;script&gt;alert("xss")&lt;/script&gt;</td>
    ```

    `<` が `&lt;` に変換されているので、ブラウザはこれを
    タグではなく文字として表示します。Jinja2 の自動エスケープが
    黙って守ってくれていることが確認できました。

    確認が終わったら掃除しておきます（`5` は自分の環境で返ってきた
    `id` に読み替えてください）。

    ```bash
    curl -s -X DELETE http://127.0.0.1:8000/api/todos/5
    ```

### 問3 「期限が今日のもの」だけ赤くする

`_row.html` に、**期限が今日の ToDo だけ赤く表示する**仕組みを
追加してください。ヒント: テンプレート内で `t.due_on` と今日の
日付を比較するため、15.4 と同じ要領で
`templates.env.globals` に今日の日付を登録します。

??? example "解答例"

    `mytodo/app/routers/pages.py` の `PRIORITY_LABEL` の登録の直後に
    1 行追加します（`date` は `_date` という名前で import 済み
    です）。

    ```python
    templates.env.globals["TODAY"] = _date.today()
    ```

    `mytodo/app/templates/_row.html` の期限のセルを次のように
    変えます。

    ```html
      <td{% if t.due_on == TODAY %} class="due-today"{% endif %}>{{ t.due_on or '—' }}</td>
    ```

    `mytodo/app/static/style.css` の末尾に追加します。

    ```css
    .due-today { color: #b00020; font-weight: bold; }
    ```

    期限が今日の ToDo を画面のフォームから登録すると、その行の
    期限だけが赤くなります。`globals` に登録した値が
    どのテンプレートからも参照できること、テンプレートの式の中で
    `==` による比較ができることが確認できました。

    この改造を入れると 15.11 の `diff` に差分が出るので、
    第16章に進む前に 3 ファイルとも元に戻しておきましょう。

## まとめ

- **サーバーサイドレンダリング**は、サーバーが HTML を完成させて
  返す方式。ブラウザは表示するだけでよい
- **Jinja2** はテンプレートエンジン。`{{ }}` で値を出力、
  `{% %}` で制御構文を書く。FastAPI では `Jinja2Templates` が
  薄いラッパーとして用意されている
- `extends` / `block` で**ページの骨組みを共通化**し、
  `include` で**繰り返し使う部品（部分テンプレート）を埋め込む**。
  `_` 始まりのファイル名は部分テンプレートの目印
- `templates.env.globals` に登録した値は、すべてのテンプレートから
  コンテキストなしで参照できる
- 静的ファイルは `app.mount("/static", StaticFiles(...))` で
  丸ごと配信する。場所の指定は `Path(__file__)` 起点にすると
  起動場所に左右されない
- `{{ }}` の出力は**自動エスケープ**されるので XSS に強い。
  `| safe` はユーザー入力に使わない
- この章で `pages.py`・テンプレート・CSS は完成版と一致した。
  `main.py` の残り（ログ・ミドルウェア・例外ハンドラ）は
  第17章で追加する

次は [第16章 htmxで動的UI](16-ui-htmx.md) で、この章で写経した
`hx-` 属性と `/htmx/...` エンドポイントの正体——
**ページ全体を再読み込みせずに、行や一覧だけを書き換える**仕組みを
解説します。
