# 第16章 htmxで動的UI

前章で静的な画面ができました。この章では **htmx** を入れて、
ページ全体を再読み込みせずに **行や一覧だけを書き換える**動きを作ります。

## 16.1 なぜ htmx か

- **JavaScript をほぼ書かなくていい**
- HTML の属性に `hx-post="/..."` などを書くだけで Ajax できる
- サーバーは普通に HTML（テンプレート）を返すだけ
- 学習コストが小さい
- 外部ライブラリは [htmx](https://htmx.org/docs/) 1 個（数十KB）で済む

「重厚長大じゃない」フロントエンドの代表選手です。

React や Vue のような SPA フレームワークでは、サーバーは JSON だけを返し、
「その JSON をどう画面に反映するか」をブラウザ側の JavaScript が組み立てます。
htmx はここが逆で、**「Ajax の挙動そのものを HTML 属性として宣言する」**という発想を
採ります。`hx-get`/`hx-post` で「どの URL にどのメソッドでリクエストするか」、
`hx-target` で「返ってきた HTML をどこに差し込むか」を HTML の中に直接書けるので、
`addEventListener` でイベントを拾ったり `fetch()` の結果をパースして DOM を書き換えたり
する定型コードが要りません。そして返ってくるのは JSON ではなく **HTML の断片**です。
ブラウザ側は「もらった HTML をそのまま差し込む」だけでよく、JSON を画面表示に変換する
ロジックを JavaScript 側に持つ必要がありません。

!!! note "htmx のリクエスト〜画面反映の流れ"
    1. ユーザーが要素を操作する（クリック・入力・フォーム送信など）。
       きっかけになる操作は `hx-trigger` で指定できます（省略時は要素ごとの既定値）。
    2. htmx が `hx-get`/`hx-post` などで指定した URL に Ajax リクエストを送る。
    3. サーバーが HTML の断片をレスポンスとして返す。
    4. htmx がそれを `hx-target` で指定した要素に、`hx-swap` で指定した方法で差し込む。

    この一連の流れが、すべて HTML 属性の組み合わせだけで完結します。

もうひとつ大事なのが**「画面のどこを書き換えるか」**という観点です。フォーム送信のたびに
ページ全体を読み込み直すと、通信量が増えるだけでなく、スクロール位置のリセットや一瞬の
画面点滅で体感が悪くなります。htmx なら「変わった部分だけ」を狙って差し替えられるので、
それ以外の入力途中の値やスクロール位置はそのまま保たれます。この章では一覧全体だけでなく
**行 1 本だけを差し替える**ところまでやります。

## 16.2 htmx の読み込み

`base.html` の `<head>` 内に script タグを追加します。

```html
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
```

これだけ。CDN から 1 ファイル落ちてくるだけで使えます。

読み込まれた htmx は、ページ内の `hx-*` 属性を持つ要素を自動的に見つけてイベントを
仕込みます。しかも一度きりの走査ではなく、**htmx 自身が差し込んだ新しい HTML の中に
`hx-*` 属性があれば、それにも自動で反応**します。つまり「一覧を書き換えたら、
新しく増えた行のボタンにもう一度 JavaScript でイベントを付け直す」といった作業が
要りません。要素が増えても減っても、`hx-*` を書いておくだけで面倒を見てくれます。

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
  一覧ページの初回表示（`index.html` の `{% include %}`）と htmx からの部分更新の
  両方で**同じテンプレートを使い回す**ので、見た目のロジックを二重に書かずに済みます。
- フォーム送信は `Annotated[str, Form()]` で受けます。ブラウザの `<form>` は既定で
  `application/x-www-form-urlencoded` 形式でデータを送るので、JSON を前提にした
  Pydantic モデルではそのまま受け取れません。FastAPI の
  [`Form()`](https://fastapi.tiangolo.com/) はこの形式のフィールドを1つずつ受け取る
  ための仕組みで、htmx がフォームから送るリクエストもこの形式に従います。

!!! note "GET・POST・DELETE の使い分け"
    4つのエンドポイントは、扱う操作に合わせて
    [HTTP メソッド](https://developer.mozilla.org/ja/docs/Web/HTTP/Methods)を使い分けています。

    - `list_partial` は **GET**：一覧を取得するだけでサーバー側の状態を変えないので、
      素直に GET が使えます。
    - `htmx_create` は **POST**：呼ぶたびに新しい ToDo が1件増えます。同じリクエストを
      2回送れば結果も2回分変わるので、
      [冪等](https://developer.mozilla.org/ja/docs/Glossary/Idempotent)ではありません。
    - `htmx_toggle` も **POST**：「今の状態を反転する」操作で、目的の状態そのものを
      指定するわけではないため、2回叩けば元に戻ってしまいます。これも冪等ではありません。
    - `htmx_delete` は **DELETE**：「対象が存在しない状態にする」のが目的なので、
      同じ ID に2回叩いても最終的な状態は変わりません（2回目は「もう無い」という
      エラーになるかもしれませんが）。これが冪等なメソッドの典型例です。

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

15章の静的フォームにあった「適用」ボタンが、ここでは消えていることに気づいたでしょうか。
`hx-trigger` に `change`（ラジオボタンの切り替え）と `keyup`（検索入力）を直接指定して
いるので、ボタンを押さなくても操作した瞬間にリクエストが飛びます。`submit` も
トリガ条件に残してあるのは、検索欄で Enter キーを押したときに発生するフォームの
`submit` イベントを htmx 側で拾うためです。拾わずにいると、ブラウザの標準動作である
ページ全体のリロードが起きてしまいます。

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
`hx-on::イベント名` は、htmx が発火するカスタムイベント（ここでは `htmx:afterRequest`）に
インラインでハンドラを書ける仕組みです。イベント名の `:` 区切りが `-` 区切りの属性名に
変換され、`this` はその属性が付いている要素（＝このフォーム）を指します。
`addEventListener` を別の JavaScript ファイルに書かなくても、HTML の中だけで完結できる
のが htmx らしいところです。なお `afterRequest` はリクエストが成功しても失敗しても発火
するので、サーバー側でエラーになった場合もフォームはリセットされる点は覚えておくと
よいでしょう。

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
  `hx-swap` を省略したときの既定値は `innerHTML`（対象要素の**中身**だけを差し替え、
  タグ自身は残す）です。今回はチェック状態によって `<tr class="done">` の `class`
  属性そのものが変わるので、`<tr>` タグごと入れ替わる `outerHTML` を明示的に
  指定しないと、見た目（取り消し線）が更新されません。
- `hx-confirm` でブラウザの確認ダイアログを出す。事故防止。ブラウザ標準の
  `confirm()` を呼ぶだけの簡易な仕組みなので見た目のカスタマイズはできませんが、
  コード1行で「本当に消していいか」を挟めるお手軽さが利点です。

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

非同期 UI では、アクセシビリティへの配慮が抜け落ちやすい落とし穴があります。
ページ全体の読み込みが発生する通常のフォーム送信と違い、htmx による部分更新は
**ブラウザの画面遷移という「合図」なしに** DOM の一部だけがこっそり書き換わります。
スクリーンリーダーはページ遷移をきっかけに新しい内容を読み上げますが、一部分だけの
差し替えではそのきっかけが発生しないため、変化に気づけないことがあります。また
`outerHTML` で要素ごと入れ替えると、そこにあった DOM ノードは一度破棄されるので、
そこにフォーカスが当たっていた場合は**フォーカスの位置が失われる**リスクもあります。
「動きが軽快になった」代わりに「今何が起きたか」が伝わりにくくなる——これが非同期 UI
でアクセシビリティが後回しにされがちな理由です。最小実装であるこの章のサンプルでは
踏み込みませんが、本格的に作り込むときは `aria-live` 属性で更新箇所を「読み上げて
ほしい領域」として宣言する、といった対策があります。

この章のサンプルで最低限やっていることは次の4つです。

- ボタンには `aria-label` を付ける（✓や×のような記号だけでは、スクリーンリーダーが
  何のボタンか読み上げられないため）
- フォームには必ず `<label>` を関連付ける（入力欄にフォーカスしたとき、何を入力する欄
  かを読み上げてもらうため）
- `:focus-visible` のスタイルを残す（キーボード操作の可視性。CSS リセットで消して
  しまいがちなフォーカスの輪郭線を、キーボード操作している人のために残しておく）
- 削除には `hx-confirm` を付ける（事故防止）

最小実装なので深追いしませんが、**「キーボードで全機能を使えるか」**
だけは意識すると、UI のクオリティがぐっと上がります。

## 16.9 デバッグの見方

ブラウザの DevTools の **Network タブ**を開きながら操作してみてください。
htmx は **普通の Ajax**を投げているだけなので、

- リクエストの URL とパラメータ
- レスポンスの[ステータスコード](https://developer.mozilla.org/ja/docs/Web/HTTP/Status)
- レスポンスの HTML 断片

が全部見えます。期待した HTML が返っていないときは、まずここを確認します。

!!! tip "画面が反応しないときはステータスコードを見る"
    htmx は既定では 200番台（成功）のレスポンスだけを画面に反映します。
    サーバー側で例外が起きて 500 番台が返っていたり、パスやパラメータが違っていて
    404 が返っていたりすると、**リクエストは飛んでいるのに画面は何も変わらない**
    という状態になります。「クリックしても何も起きない」と感じたら、まず Network
    タブでステータスコードを確認してみてください。

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
