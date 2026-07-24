# 第15章 Jinja2でHTML

API ができたので、ブラウザで触れる **画面**を作ります。
本研修では JavaScript フレームワーク（React / Vue など）は使わず、
**サーバーで HTML を組み立てる古典的な方式**にします。

この章では Jinja2 で **静的な画面**を作るところまでやります。
動的な部分更新は次章（htmx）で扱います。

## 15.1 Jinja2 とは

HTML を返すだけなら、Python の f-string で `f"<li>{t.title}</li>"` のように文字列を
組み立てることもできます。ですが ToDo が何十件も並ぶ一覧や、`if` で表示を出し分ける
ような画面になってくると、HTML タグと Python のロジックが文字列の中でぐちゃぐちゃに
混ざり、すぐ読みにくくなります。さらに、ユーザーの入力（ToDo のタイトルなど）を
そのまま文字列結合で埋め込んでしまうと **XSS**（15.9 で扱います）の温床にもなります。
「見た目は HTML のまま書きつつ、動的な部分だけを差し込みたい」というニーズに応えるのが
**テンプレートエンジン**です。

[Jinja2](https://jinja.palletsprojects.com/) は Python 製のテンプレートエンジンです。
HTML の中に `{{ 変数 }}` や `{% for ... %}` を書ける、いわゆる「テンプレート」。

```html
<h1>こんにちは、{{ name }}さん</h1>
<ul>
  {% for t in todos %}
    <li>{{ t.title }}</li>
  {% endfor %}
</ul>
```

`{{ ... }}` は**値を出力する式**、`{% ... %}` は `for` や `if` のような**制御構文**、
とおおまかに役割が分かれています。この2つの記法だけで、ほとんどのテンプレートは書けます。

FastAPI には組み込みのサポートがあります（[FastAPI公式: テンプレート](https://fastapi.tiangolo.com/advanced/templates/)）。
Jinja2 をそのまま使うための薄いラッパークラス `Jinja2Templates` が用意されていて、
テンプレートを置くディレクトリを指定するだけで使えます。設定は次の 15.3 で行います。

## 15.2 静的ファイルとテンプレートを mount する

CSS のような**静的ファイル**（リクエストのたびに中身が変わらない、ディスク上のファイルを
そのまま返すもの）は、これまで作ってきた `@router.get(...)` のような**動的なエンドポイント**
とは性質が違います。1ファイルごとに専用のルート関数を書いていたら、ファイルが増えるたびに
コードが増えますし、拡張子に応じた `Content-Type` の設定なども自前でやる必要が出てきます。
そこで FastAPI（の土台である Starlette）は、ある URL プレフィックスの下を丸ごと
「ファイルをそのまま配信する専用アプリ」に委譲できる仕組みを持っています。これが
`app.mount(...)` です。

`app/main.py` に以下を追加します。

```python
# app/main.py
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
```

`app.mount("/static", StaticFiles(directory=...), name="static")` は、**`/static` から
始まる URL をまるごと `StaticFiles` という別のアプリに任せる**、という意味です
（[FastAPI公式: 静的ファイル](https://fastapi.tiangolo.com/tutorial/static-files/)）。
`StaticFiles` はファイルの拡張子から適切な `Content-Type` を判定したり、
存在しないファイルには自動で 404 を返したりする面倒を代わりに引き受けてくれます。

これで `app/static/style.css` が `http://127.0.0.1:8000/static/style.css` で配信されます。

!!! tip "`Path(__file__)` で場所を固定する理由"
    `_BASE = Path(__file__).resolve().parent` は、**このファイル（`main.py`）自身が
    置かれている場所**を起点にして `static` ディレクトリを探しています。
    `"app/static"` のような相対パスを直接書いてしまうと、`uvicorn` を
    どのディレクトリから起動したか（カレントディレクトリ）によって見つかったり
    見つからなかったりする、という事故が起きます。`__file__` はこのモジュールの
    ファイルパス、`.resolve()` はそれを絶対パスに変換するメソッドです
    （[`pathlib`](https://docs.python.org/3/library/pathlib.html)）。
    起動場所に関係なく常に同じディレクトリを指せるので、こちらのほうが安全です。

テンプレートディレクトリは `app/templates/` を使います。

```text
app/
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── _list.html
│   └── _row.html
└── static/
    └── style.css
```

`_` で始まるファイル名は **「他のテンプレートから include される部分」** という習慣です（pages の本体ではない、という目印）。
このような、単体では完結しない小さな部品を**部分テンプレート（パーシャル）**と呼びます。
何のためにわざわざ分けておくのかは 15.6 で詳しく説明します。

## 15.3 ページ用ルーター（routers/pages.py）

API は `/api/...` でしたが、画面用は `/`（ルート）に置きます。

```python
# app/routers/pages.py
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Request
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
templates.env.globals["PRIORITY_LABEL"] = PRIORITY_LABEL   # 全テンプレートから参照可能


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
```

ポイント:

- `Jinja2Templates(directory=_TEMPLATES_DIR)` は、**テンプレートを探すディレクトリを
  1つ知っているオブジェクト**です。中身は Jinja2 の `Environment` を FastAPI 用に
  薄くラップしたもので、アプリ起動時に一度だけ作ればよく、リクエストのたびに
  作り直す必要はありません。
- `templates.env` で、ラップされている **Jinja2 の `Environment` そのもの**に
  アクセスできます。`templates.env.globals` はテンプレート側から常に参照できる
  変数の置き場所で、ここに `PRIORITY_LABEL` を登録しておくと、以降どのテンプレートでも
  `{{ PRIORITY_LABEL[...] }}` のように **コンテキストに含めなくても**参照できます
  （`_row.html` で使っています）。
- `templates.TemplateResponse(request, "index.html", {...})` は**第一引数が必ず
  `request`**です。`Jinja2Templates` は内部で `request` を使ってテンプレート側から
  `url_for()` のようなヘルパーを呼べるようにしているため、渡し忘れるとエラーになります。
  第二引数がテンプレートファイル名、第三引数の辞書が **コンテキスト（context）**
  （テンプレート内で `{{ todos }}` のように参照できる変数の集合）です。
- `filter: Literal["all", "open", "done"] = "all"` は、前章で `TodoListQuery` に
  使ったのと同じ `Literal` 型を、クエリパラメータの型ヒントとして直接使っています。
  `?filter=xxx` のように許可していない値が来ると、FastAPI が自動で 422 を返してくれます。

`main.py` で組み込み:

```python
# app/main.py
from .routers import pages, todos

app.include_router(pages.router)
app.include_router(todos.router, prefix="/api")
```

## 15.4 base.html

全ページで共通する枠組みです。`<head>` の中身やヘッダー・フッターは、`index.html` だけでなく
将来増えるページ全部で同じものを使い回したいはずです。ページごとに全文コピペしてしまうと、
フッターの文言を1つ変えるだけで全ファイルを直すはめになります。そこで Jinja2 の
**テンプレート継承**を使い、共通部分を1つの「土台」テンプレートにまとめておきます。

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}ToDo{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
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

`{% block xxx %}{% endblock %}` は **子テンプレートで上書きできる差し込み口（プレースホルダー）**です。
`base.html` 自身は「骨組み」だけを持ち、`title` や `main` の中身はデフォルト値
（あるいは空）にしておいて、あとは `{% extends %}` した子テンプレート側に埋めてもらいます。
実際の使い方は次の 15.5 で見ます。

## 15.5 index.html（一覧 + フォーム）

`{% extends "base.html" %}` を先頭に書くと、このテンプレートは `base.html` を
土台として使う、という意味になります。`{% block main %}...{% endblock %}` で
囲んだ内容が、`base.html` 側の同じ名前の `block` にそのまま差し込まれます。
`extends` はテンプレートファイルの一番最初に1回だけ書く決まりです。

```html
{% extends "base.html" %}
{% block main %}
<section class="filters">
  <form method="get" action="/">
    <label><input type="radio" name="filter" value="all"  {% if filter=='all'  %}checked{% endif %}> 全て</label>
    <label><input type="radio" name="filter" value="open" {% if filter=='open' %}checked{% endif %}> 未完了</label>
    <label><input type="radio" name="filter" value="done" {% if filter=='done' %}checked{% endif %}> 完了</label>
    <input type="search" name="q" value="{{ q }}" placeholder="検索...">
    <button type="submit">適用</button>
  </form>
</section>

<section id="todo-list">
  {% include "_list.html" %}
</section>
{% endblock %}
```

`{% include "_list.html" %}` は `extends` とは別物です。`extends` が
「ページ全体の骨組みを1つ選ぶ」ものなのに対し、`include` は**その場に別テンプレートの
中身をそのまま埋め込む**命令で、1つのテンプレートの中で何度でも、好きな場所に書けます。
一覧表示のような**繰り返し使う部品**を切り出すのに向いています。

この時点では **フォームを送信するとページ全体が再読み込みされる**普通の動きです。
次章で htmx を入れて部分更新にします。

## 15.6 _list.html と _row.html（部分テンプレート）

`_list.html` の `{% if todos|length == 0 %}` に出てくる `|length` は
**Jinja2 のフィルタ**です。`値 | フィルタ名` という書き方で、値を加工した結果を
式の中で使えます。ここでは Python の `len(todos)` に近いことをしていますが、
テンプレートの中では組み込み関数ではなく、こうしたフィルタとして提供されています。

`_list.html`:

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

`_row.html`:

```html
<tr id="todo-{{ t.id }}" class="{% if t.done %}done{% endif %}">
  <td>{% if t.done %}☑{% else %}☐{% endif %}</td>
  <td class="title">{{ t.title }}</td>
  <td>{{ t.due_on or '—' }}</td>
  <td>{{ PRIORITY_LABEL[t.priority] }}</td>
  <td class="tags">
    {% for g in t.tags %}<span class="tag">{{ g.name }}</span>{% endfor %}
  </td>
</tr>
```

`{{ t.due_on or '—' }}` は、Jinja2 の式の中でも Python とほぼ同じ `or` 演算子が
使えることを利用して、`due_on` が `None`（期限なし）のときだけ `'—'` を表示する、
という意味です。`{{ PRIORITY_LABEL[t.priority] }}` は 15.3 で
`templates.env.globals` に登録した辞書を、そのまま添字アクセスで参照しています。

部分テンプレートに分けておくと、次章で htmx から **「行だけ書き換える」**ときに
そのまま使い回せます。もし `_list.html` の中身を `index.html` に直接書いてしまっていたら、
「一覧全体を返すページ」と「一覧の断片だけを返すエンドポイント」（次章で作ります）とで、
同じ `<table>` の組み立てロジックを2箇所に重複して書くはめになります。
テンプレートとして切り出しておけば、どちらの場合も `{% include %}` するだけで済み、
中身は1箇所で管理できます。

## 15.7 静的 CSS（最小限）

`app/static/style.css`:

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

.filters form { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.filters input[type="search"] { flex: 1; padding: 6px 8px; border: 1px solid #ccd; border-radius: 6px; }

.todos { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }
.todos th, .todos td { padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; }
.todos tr.done .title { text-decoration: line-through; color: #888; }

.empty { text-align: center; color: #888; padding: 24px; background: #fff; border-radius: 8px; }

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

## 15.8 動かしてみる

```bash
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/
```

一覧が見えるはず。フィルタや検索を変えると、URL のクエリパラメータが変わって
**ページ全体が再読み込み**されることを確認してください。

## 15.9 Jinja2 の自動エスケープ

**[XSS（クロスサイトスクリプティング）](https://developer.mozilla.org/ja/docs/Web/Security/Attacks/XSS)**
は、悪意のある入力（たとえば ToDo のタイトル）に埋め込まれた `<script>` タグなどが、
そのままブラウザで実行されてしまう脆弱性です。放置すると、攻撃者が他のユーザーの
ブラウザ上で任意のスクリプトを動かせてしまい、Cookie の盗み見や画面の改ざんにつながります。

Jinja2 は `{{ ... }}` で出力する値を **自動的に HTML エスケープ**します。
具体的には `<` を `&lt;`、`>` を `&gt;`、`&` を `&amp;` のような**文字参照**に
変換してから出力するので、ブラウザはそれを「タグの開始」とは解釈できません。
つまり `<script>alert(1)</script>` のようなタイトルを保存しても、
そのまま画面に文字として出るだけで、スクリプトは実行されません。FastAPI の
`Jinja2Templates` はこの自動エスケープをデフォルトで有効にした状態でテンプレートを
読み込むので、こちらで何か設定しなくても最初から安全な状態になっています。

これを破るのが `{{ value | safe }}` というフィルタです。「このテンプレート側で
自分が書いた、信頼できる HTML 文字列だから、エスケープせずそのまま出力してよい」
という場面のための機能ですが、**ユーザー入力に対して安易に使わない**こと。
使ってしまうと自動エスケープが無効になり、XSS の入り口になります。

## やってみよう

1. **空状態のメッセージ**を変える（"該当する ToDo はありません" → "未完了の ToDo はありません" など）。
2. `_row.html` に **「期限が今日のもの」だけ赤く表示**する CSS クラスを足す。
   ヒント: テンプレート内で `t.due_on == today` を判定するため、
   `templates.env.globals["TODAY"] = date.today()` を `pages.py` に追記して使う。
3. `<script>alert("xss")</script>` という title の ToDo を `psql` で入れて、
   画面でどう表示されるか確認する（**素直に文字として表示される**はず）。

次は [第 16 章 htmxで動的UI](16-ui-htmx.md) で、
**ページ全体を再読み込みせずに、行や一覧だけを書き換える**動きを入れます。
