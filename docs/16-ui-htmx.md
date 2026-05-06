# 第16章 htmxで動的UI

前章で静的な画面ができました。この章では **htmx** を入れて、
ページ全体を再読み込みせずに **行や一覧だけを書き換える**動きを作ります。

## 16.1 なぜ htmx か

- **JavaScript をほぼ書かなくていい**
- HTML の属性に `hx-post="/..."` などを書くだけで Ajax できる
- サーバーは普通に HTML（テンプレート）を返すだけ
- 学習コストが小さい
- 外部ライブラリは htmx 1 個（数十KB）で済む

「重厚長大じゃない」フロントエンドの代表選手です。

## 16.2 htmx の読み込み

`base.html` の `<head>` 内に script タグを追加します。

```html
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
```

これだけ。CDN から 1 ファイル落ちてくるだけで使えます。

## 16.3 htmx エンドポイントを作る

API は JSON を返しましたが、htmx 用は **HTML の断片**を返します。
`routers/pages.py` に追加します。

```python
# app/routers/pages.py（追加）
from datetime import date as _date
from fastapi import Form
from fastapi.responses import HTMLResponse


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
    return HTMLResponse("")  # 空で返す = 該当の行を空に置き換える
```

ポイント:

- HTML を返すのは `_list.html` と `_row.html`（前章で作った部分テンプレート）。
- フォーム送信は `Annotated[str, Form()]` で受ける。

## 16.4 フィルタと検索を htmx で

`index.html` のフィルタフォームを改造します。

```html
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
```

属性の意味:

| 属性 | 意味 |
|---|---|
| `hx-get="/partials/list"` | このフォームをトリガにすると GET を投げる |
| `hx-target="#todo-list"` | 返ってきた HTML をこの要素の中身に差し替える |
| `hx-trigger="..."` | いつトリガするか。複数の条件をカンマ区切り |
| `hx-include="this"` | フォーム自身の値をパラメータに含める |

`keyup changed delay:300ms` は **「キー入力後、300ms 経って値が変わってたら投げる」**
というデバウンス指定。検索で 1 文字打つたびに飛ばないようにする工夫。

## 16.5 追加フォームを htmx で

```html
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
```

`hx-on::after-request="this.reset()"` で、追加成功後にフォームを空にしています。

## 16.6 完了切替と削除（行だけ書き換え）

`_row.html` を htmx 対応に更新します。

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

- `hx-target="#todo-{{ t.id }}"` で **自分の行を対象**に。
- `hx-swap="outerHTML"` で **要素まるごと**置き換え（中身だけでなく `<tr>` ごと）。
- `hx-confirm` でブラウザの確認ダイアログを出す。事故防止。

これで、押したボタンの行だけが書き換わる動きになります。
全画面の再描画が要らないので体感がきびきびします。

## 16.7 動かしてみる

```bash
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/
```

入力フォームで追加 → 一覧が更新される、
チェックボックスを押すと行だけが書き換わる、
削除ボタンを押すと行が消える——
これだけ動けば十分なフロントエンドです。

## 16.8 アクセシビリティと簡単な配慮

- ボタンには `aria-label` を付ける
- フォームには必ず `<label>` を関連付ける
- `:focus-visible` のスタイルを残す（キーボード操作の可視性）
- 削除には `hx-confirm` を付ける（事故防止）

最小実装なので深追いしませんが、**「キーボードで全機能を使えるか」**
だけは意識すると、UI のクオリティがぐっと上がります。

## 16.9 デバッグの見方

ブラウザの DevTools の **Network タブ**を開きながら操作してみてください。
htmx は **普通の Ajax**を投げているだけなので、

- リクエストの URL とパラメータ
- レスポンスの HTML 断片

が全部見えます。期待した HTML が返っていないときは、まずここを確認します。

## やってみよう

1. **タグの追加 UI** を htmx で実装する。
   ヒント: 行内に小さな input + ボタンを置き、`hx-post` で `/htmx/todos/{id}/tags` を叩く。
2. 行の **タイトルをダブルクリックで編集**できるようにする。
   ヒント: `hx-trigger="dblclick"` でフォーム部品に置き換える。
3. リクエスト中に **ローディング表示**を入れる。
   ヒント: htmx は `htmx-request` クラスを自動で付与する。CSS で見せる。

これで Part 6 はおしまいです。
次は [第 17 章 設定・ログ・例外ハンドリング](17-finishing.md) で、
**他人が触っても壊れない**ようにする仕上げに入ります。
