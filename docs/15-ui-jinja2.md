# 第15章 Jinja2でHTML

API ができたので、ブラウザで触れる **画面**を作ります。
本研修では JavaScript フレームワーク（React / Vue など）は使わず、
**サーバーで HTML を組み立てる古典的な方式**にします。

この章では Jinja2 で **静的な画面**を作るところまでやります。
動的な部分更新は次章（htmx）で扱います。

## 15.1 Jinja2 とは

Jinja2 は Python 製のテンプレートエンジンです。
HTML の中に `{{ 変数 }}` や `{% for ... %}` を書ける、いわゆる「テンプレート」。

```html
<h1>こんにちは、{{ name }}さん</h1>
<ul>
  {% for t in todos %}
    <li>{{ t.title }}</li>
  {% endfor %}
</ul>
```

FastAPI には組み込みのサポートがあります。

## 15.2 静的ファイルとテンプレートを mount する

`app/main.py` に以下を追加します。

```python
# app/main.py
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
```

これで `app/static/style.css` が `http://127.0.0.1:8000/static/style.css` で配信されます。

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

`main.py` で組み込み:

```python
# app/main.py
from .routers import pages, todos

app.include_router(pages.router)
app.include_router(todos.router, prefix="/api")
```

## 15.4 base.html

全ページで共通する枠組みです。

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

`{% block xxx %}{% endblock %}` は **子テンプレートで上書きできる差し込み口**です。

## 15.5 index.html（一覧 + フォーム）

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

この時点では **フォームを送信するとページ全体が再読み込みされる**普通の動きです。
次章で htmx を入れて部分更新にします。

## 15.6 _list.html と _row.html（部分テンプレート）

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

部分テンプレートに分けておくと、次章で htmx から **「行だけ書き換える」**ときに
そのまま使い回せます。

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

Jinja2 は `{{ ... }}` で出力する値を **自動的に HTML エスケープ**します。
つまり `<script>alert(1)</script>` のようなタイトルを保存しても、
そのまま画面に文字として出るだけで、スクリプトは実行されません。

これを破るのが `{{ value | safe }}` というフィルタですが、**安易に使わない**
こと。XSS の入り口になります。

## やってみよう

1. **空状態のメッセージ**を変える（"該当する ToDo はありません" → "未完了の ToDo はありません" など）。
2. `_row.html` に **「期限が今日のもの」だけ赤く表示**する CSS クラスを足す。
   ヒント: テンプレート内で `t.due_on == today` を判定するため、
   `templates.env.globals["TODAY"] = date.today()` を `pages.py` に追記して使う。
3. `<script>alert("xss")</script>` という title の ToDo を `psql` で入れて、
   画面でどう表示されるか確認する（**素直に文字として表示される**はず）。

次は [第 16 章 htmxで動的UI](16-ui-htmx.md) で、
**ページ全体を再読み込みせずに、行や一覧だけを書き換える**動きを入れます。
