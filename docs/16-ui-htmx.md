# 第16章 htmxで動的UI

第15章では、`hx-` で始まる属性や `/htmx/...` というエンドポイントを
「おまじない」として写経し、ページ全体を読み込み直さない**部分更新**で
ToDo アプリが動くことを確認しました。この章では新しいコードは書きません。
あのおまじないの正体——**htmx** というライブラリと、第15章で写経した
4 箇所の部品（`base.html` の script タグ、`index.html` の 2 つのフォーム、
`_row.html` のボタン、`pages.py` の htmx 用エンドポイント）の仕組みを、
1 つずつ解説します。

## 16.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- 部分更新とは何か、ページ全体の再読み込みとの違いを説明できる
- htmx の `hx-get` / `hx-post` / `hx-delete` / `hx-target` /
  `hx-swap` / `hx-trigger` の役割を説明できる
- 第15章で写経した 4 箇所の htmx 部品が、どう組み合わさって
  部分更新を実現しているか説明できる
- ブラウザの DevTools と curl で、htmx のリクエストと
  レスポンスを観察できる
- 新しい `hx-` 属性を自分で試して、挙動の変化を観察できる

**所要時間の目安: 45 分**

!!! info "前提となる状態"
    - 第15章末時点の `mytodo/` がある（ブラウザで一覧・絞り込み・
      追加・切替・削除が動き、`pages.py`・テンプレート・CSS の
      `diff` が完成版と差分なし）
    - 第0章の Docker の PostgreSQL が起動している
      （`docker compose up -d`）
    - シードデータが入った状態である（この章の動作確認で
      初期状態に戻します）

## 16.2 前提知識

第15章で写経した部品を読み解く前に、鍵になる概念を 3 つ
押さえておきます。

!!! note "部分更新とは"
    昔ながらの Web アプリでは、リンクを開くたび、フォームを送るたびに
    **ページ全体の HTML を受け取り直して画面を丸ごと描き換える**のが
    普通でした。第15章の画面でも、htmx を抜きにすれば絞り込みフォームの
    送信は「`GET /?filter=open` というページ全体の再読み込み」です。

    **部分更新**はこれと対照的で、サーバーからは**変わった部分の
    HTML だけ**を受け取り、ブラウザ上の JavaScript がページの
    その部分だけを書き換えます。ページ全体を読み直さないので、
    通信量が減るだけでなく、スクロール位置や入力途中の値、
    フォーカスがそのまま保たれ、画面のチラつきも起きません。
    一般には Ajax（Asynchronous JavaScript and XML）と呼ばれる
    仕組みの一種です。

!!! note "htmx の属性（`hx-get` など）の仕組み"
    [htmx](https://htmx.org/docs/) は、**Ajax の挙動を HTML の属性として
    宣言する**ための小さな JavaScript ライブラリです（1 ファイル、
    数十 KB）。React や Vue のような SPA フレームワークでは、
    サーバーは JSON だけを返し、「その JSON をどう画面に反映するか」を
    ブラウザ側の JavaScript が組み立てます。htmx はここが逆で、
    画面に関する指定をすべて HTML の中に書きます。

    基本的な属性は 4 つです。

    | 属性 | 役割 |
    |---|---|
    | `hx-get` / `hx-post` / `hx-delete` など | どの URL に、どの HTTP メソッドでリクエストを送るか |
    | `hx-trigger` | いつリクエストを送るか（省略時は要素ごとの既定値） |
    | `hx-target` | 返ってきた HTML をどの要素に差し込むか（CSS セレクタ） |
    | `hx-swap` | どう差し込むか（中身だけか、要素ごとかなど） |

    ページが読み込まれると、htmx はページ内の `hx-` 属性を持つ要素を
    自動で見つけてイベントを仕込みます。しかも一度きりの走査ではなく、
    **htmx 自身が差し込んだ新しい HTML の中に `hx-` 属性があれば、
    それにも自動で反応**します。つまり「一覧を書き換えたら、新しく
    増えた行のボタンに JavaScript でイベントを付け直す」といった
    作業が要りません。

    このおかげで、`addEventListener` でイベントを拾ったり、
    `fetch()` の結果をパースして DOM を書き換えたりする定型コードを
    自分で書かなくて済みます。

!!! note "HTML フラグメント"
    第13〜14章で作った API が返していたのは **JSON** でした。
    htmx に返すのは JSON ではなく **HTML の断片（フラグメント）**です。
    `<!doctype html>` から始まる完全な HTML 文書ではなく、
    `<table>...</table>` や `<tr>...</tr>` のような、ページの
    一部分だけを切り出したものです。

    サーバー側の作りは第15章の `GET /` とほとんど同じで、違うのは
    **描画するテンプレートが部分テンプレート（`_list.html` や
    `_row.html`）になる**点だけです。ブラウザ側は「もらった断片を
    そのまま `hx-target` の場所に差し込む」だけでよく、JSON を
    画面表示に変換するロジックを持つ必要がありません。

    第15章で「一覧の組み立てを部分テンプレートに切り出した」のは、
    まさにこのためでした。初回表示（`index.html` からの
    `{% include %}`）と htmx からの部分更新の両方で同じテンプレートを
    使い回せるので、見た目のロジックを二重に書かずに済んでいます。

## 16.3 htmx の読み込み: `base.html` の script タグ

1 つ目の部品です。15.5 で「おまじない」として写経した、
`mytodo/app/templates/base.html` の `<head>` 内の 1 行を
見返します。

```html
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
```

CDN（ここでは [unpkg](https://unpkg.com/)）から htmx 2.0.3 を
読み込んでいるだけです。npm でインストールしたりビルドしたりする
必要はなく、これだけでページ内の `hx-` 属性がすべて有効になります。

CDN から読み込めない環境（オフラインの社内ネットワークなど）では、
この script タグは失敗して htmx 自体が存在しない状態になります。
その場合 `hx-` 属性はブラウザにとって「知らない属性」なので単に
無視され、絞り込みフォームは通常の GET 送信（ページ全体の
再読み込み）として動きます。htmx がいなくても画面が壊れないように
作られている、という点は覚えておくとよいでしょう。

## 16.4 HTML の断片を返すエンドポイント: `pages.py`

2 つ目の部品です。15.4 の warning で「第16章で説明します」と
予告していた、`mytodo/app/routers/pages.py` の後半を見返します。

```python
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

`index`（`GET /`）との違いは、**返すものが HTML 文書全体か断片か**
だけです。DB アクセスも DI もテンプレートの描画方法も同じなので、
第15章までの知識だけで読めるはずです。上から順に見ていきます。

- `list_partial` …… 絞り込みのたびに htmx から呼ばれ、
  **`_list.html`（表の断片）だけ**を返します。クエリパラメータの
  受け方は `index` とまったく同じです。`index` がコンテキストに
  `filter` や `q` も渡していたのに対し、こちらは `todos` だけを
  渡しています。`_list.html` の中で使うのは `todos` だけなので、
  これで十分だからです。
- `htmx_create` …… 追加フォームから呼ばれます。登録したあと
  **最新の一覧全体**（`_list.html`）を返すので、ブラウザ側は
  一覧をまるごと新しいものに差し替えます。「1 件追加したら
  1 行だけ返す」のではなく一覧ごと返す設計にしているのは、
  追加後の並び順（期限順）をサーバー側のロジックに任せられる
  からです。
- `htmx_toggle` …… 完了切替のボタンから呼ばれ、更新後の
  **その 1 行だけ**（`_row.html`）を返します。`toggle_done` で
  反転したあと `get_todo` で取り直しているのは、テンプレートに
  渡すための最新の値が必要だからです。
- `htmx_delete` …… 削除のボタンから呼ばれ、**空のレスポンス**
  （`HTMLResponse("")`）を返します。16.7 で見る
  `hx-swap="outerHTML"` と組み合わさって、「行を空っぽの HTML で
  置き換える = 行が画面から消える」という動きになります。

`htmx_create` の引数にある `Annotated[str, Form()]` は、
**HTML フォームの送信データを 1 項目ずつ受け取る**ための宣言です。
ブラウザの `<form>` は既定で `application/x-www-form-urlencoded`
形式（`title=牛乳を買う&priority=2` のような見た目）でデータを
送ります。JSON を前提にした Pydantic モデルではこの形式をそのまま
受け取れないので、FastAPI の
[`Form()`](https://fastapi.tiangolo.com/tutorial/request-forms/) を
使います。htmx がフォームから送るリクエストもこの形式に従うので、
通常のフォーム送信と同じ受け口でよい、というわけです。

!!! note "GET・POST・DELETE の使い分け"
    4 つのエンドポイントは、扱う操作に合わせて
    [HTTP メソッド](https://developer.mozilla.org/ja/docs/Web/HTTP/Methods)を使い分けています。

    - `list_partial` は **GET**：一覧を取得するだけでサーバー側の
      状態を変えないので、素直に GET が使えます。
    - `htmx_create` は **POST**：呼ぶたびに新しい ToDo が 1 件
      増えます。同じリクエストを 2 回送れば結果も 2 回分変わるので、
      [冪等](https://developer.mozilla.org/ja/docs/Glossary/Idempotent)ではありません。
    - `htmx_toggle` も **POST**：「今の状態を反転する」操作で、
      目的の状態そのものを指定するわけではないため、2 回叩けば
      元に戻ってしまいます。これも冪等ではありません。
    - `htmx_delete` は **DELETE**：「対象が存在しない状態にする」のが
      目的なので、同じ ID に 2 回叩いても最終的な状態は変わりません。
      これが冪等なメソッドの典型例です。

## 16.5 `hx-get` で絞り込み: フィルタフォーム

3 つ目の部品です。`mytodo/app/templates/index.html` の
フィルタフォームを、今度は `hx-` 属性に注目して見返します。

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

このフォームの 1 回の動きは、16.2 の前提知識で見た流れそのままです。

1. ユーザーがラジオボタンを切り替える、検索欄に入力するなどする
   （`hx-trigger` で指定したタイミング）。
2. htmx が `hx-get` の URL（`/partials/list`）に GET を送る。
   `hx-include="this"` により、フォーム内の入力値
   （`filter` と `q`）がクエリパラメータとして付きます。
3. サーバー（16.4 の `list_partial`）が `_list.html` を描画して
   返す。
4. htmx が返ってきた断片を `hx-target` の `#todo-list`
   （`index.html` 内の `<section id="todo-list">`）の中身に
   差し替える。

`hx-trigger` の値は少し込み入っているので、分解します。

- `change from:input[name='filter']` …… `filter` という name を
  持つ input（ラジオボタン）の値が変わったとき。`from:...` は
  「イベントの発生元をこのセレクタの要素に限定する」指定です。
- `submit` …… フォームの送信時。検索欄で Enter キーを押したときに
  発生します。これを拾わずにいると、ブラウザの標準動作である
  ページ全体の再読み込みが起きてしまいます。
- `keyup changed delay:300ms from:input[name='q']` …… 検索欄での
  キー入力。`changed` は「値が実際に変わったときだけ」、
  `delay:300ms` は「最後の入力から 300ms 待ってから送る」という
  指定で、組み合わせると**デバウンス**（連続入力中は送らず、
  入力が止まってから 1 回だけ送る）になります。検索で 1 文字
  打つたびにリクエストが飛ばないようにする工夫です。

複数の条件はカンマ区切りで並べられます。「適用」ボタンがなくても
操作した瞬間に一覧が更新されるのは、この `hx-trigger` のおかげです。

## 16.6 `hx-post` で追加: 追加フォーム

`index.html` のもう 1 つのフォームです。

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

`hx-post="/htmx/todos"` で 16.4 の `htmx_create` を呼び、
返ってきた一覧の断片で `#todo-list` の中身を差し替えます。
`hx-trigger` を書いていないので、`<form>` の既定値である
`submit`（送信時）がトリガになります。`hx-include` も書いて
いませんが、フォーム要素の場合は**フォーム内の入力値が自動で
送信に含まれる**ため、書く必要がありません（16.5 のフィルタ
フォームに `hx-include="this"` があったのは、ラジオボタンや
検索欄での `change` / `keyup` がトリガのときにフォームの値を
明示的に含めるためです）。

残る `hx-on::after-request="this.reset()"` は、**リクエストが
終わったあとにフォームを空にする**指定です。`hx-on::イベント名`
は、htmx が発火するカスタムイベント（ここでは `htmx:afterRequest`）
にインラインでハンドラを書ける仕組みで、`this` はその属性が
付いている要素（このフォーム）を指します。`addEventListener` を
別の JavaScript ファイルに書かなくても HTML の中で完結できるのが
htmx らしいところです。なお `afterRequest` は成功でも失敗でも
発火するので、サーバー側でエラーになった場合もフォームは
リセットされる点は覚えておくとよいでしょう。

## 16.7 行だけ書き換える: 完了切替と削除

4 つ目の部品です。15.7 の末尾で予告した、
`mytodo/app/templates/_row.html` のボタンを見返します。

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

ここまでのフォーム 2 つは「一覧全体（`#todo-list`）を差し替える」
ものでしたが、行のボタンは**自分の行 1 本だけ**を差し替えます。
そのための仕掛けが 2 つあります。

- `hx-target="#todo-{{ t.id }}"` …… 差し替え先を**自分の行**
  にしています。`_row.html` の先頭にある `id="todo-{{ t.id }}"`
  により、各行は `todo-1`、`todo-2` のように一意の id を持つので、
  `hx-target` のセレクタでその行だけを正確に指せます。
  `{{ t.id }}` の部分は Jinja2 が描画時に実際の ID に置き換える
  ため、サーバーから返ってきた HTML の中では `hx-target="#todo-1"`
  のような具体的な値になっています。
- `hx-swap="outerHTML"` …… **`<tr>` 要素ごと**置き換える指定です。
  省略したときの既定値は `innerHTML` で、対象要素の**中身だけ**を
  差し替え、タグ自身は残します。完了切替では `<tr class="done">` の
  `class` 属性そのものが変わる（取り消し線はこのクラスで
  付いています）ので、`<tr>` ごと入れ替わる `outerHTML` でないと
  見た目が更新されません。削除では 16.4 の `htmx_delete` が返す
  **空のレスポンスで `<tr>` ごと置き換わる**ので、行が画面から
  消えます。

削除ボタンの `hx-confirm="削除してええ？"` は、リクエストを送る前に
ブラウザ標準の確認ダイアログを挟む指定です。`confirm()` を呼ぶだけの
簡易な仕組みなので見た目のカスタマイズはできませんが、コード 1 行で
「本当に消していいか」を挟める手軽さが利点です。

なお、切り替え後の新しい行にも同じ `hx-` 属性が書かれていますが、
16.2 で見たとおり htmx は**差し込んだ新しい HTML の中の `hx-`
属性にも自動で反応**します。だから何度でも続けて切り替えられる
わけです。

## 16.8 動作確認: ブラウザと curl で観察する

第15章で「動いた」ことは確認済みなので、ここでは**裏側でどんな
リクエストとレスポンスが行き来しているか**を観察します。

まず DB を初期状態（シードの 4 件だけ）に戻し、サーバーを
起動します。`mytodo/` の中で実行してください。

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

```bash
uv run uvicorn app.main:app --reload
```

最後に `INFO:     Application startup complete.` と出れば起動
成功です。このあとの curl は**別のターミナル**を開いて実行して
ください。

**ブラウザで `http://127.0.0.1:8000/` を開き、DevTools の
Network タブを表示した状態で**、次の操作を試してみましょう。

- 検索欄に `牛乳` と入力する → 少し間を置いてから
  `/partials/list?q=...` へのリクエストが 1 回だけ飛び、
  一覧が 1 件に絞られる（デバウンスが効いている）
- 下のフォームから新しい ToDo を追加する → `/htmx/todos` への
  POST が飛び、一覧に行が増える。フォームは空に戻る
- 行の `☐` を押す → `/htmx/todos/{id}/toggle` への POST が飛び、
  その行だけが `☑` と取り消し線付きに書き換わる
- `×` を押す → 確認ダイアログのあと `/htmx/todos/{id}` への
  DELETE が飛び、その行だけが消える

Network タブで各リクエストを選ぶと、URL・パラメータ・
ステータスコード・返ってきた HTML の断片が全部見えます。
htmx は**普通の HTTP リクエスト**を投げているだけなので、
特別なデバッグツールは要りません。

同じことを curl からも確認します。まず絞り込み用の
エンドポイントです（さきほどのブラウザ操作でデータが変わっている場合は、
上の `reset-db` と `init-db` をもう一度実行してから試して
ください）。

```bash
curl -s "http://127.0.0.1:8000/partials/list?filter=open" | grep 'class="title"'
```

期待される出力（シードの 4 件、期限順）:

```html
      <td class="title">牛乳を買う</td>
      <td class="title">健康診断の予約</td>
      <td class="title">家賃を振り込む</td>
      <td class="title">過去の領収書を整理</td>
```

`GET /` が返す完全な HTML 文書と違い、`<!doctype html>` や
`<head>` を含まない**断片**が返っていることがわかります
（先頭から `<table class="todos">` が始まります）。

次は完了切替です。シードの先頭（`牛乳を買う`）の ID は `1`
なので、その toggle を叩きます。

```bash
curl -s -X POST http://127.0.0.1:8000/htmx/todos/1/toggle
```

期待される出力（`<tr>` 1 本だけ。`class="done"` が付き、
ボタンが `☑` に変わっています）:

```html
<tr id="todo-1" class="done">
  <td>
    <button
      class="toggle"
      aria-label="完了切替"
      hx-post="/htmx/todos/1/toggle"
      hx-target="#todo-1"
      hx-swap="outerHTML"
    >☑</button>
  </td>
  <td class="title">牛乳を買う</td>
```

（実際にはこの後に期限・優先度・タグ・削除ボタンのセルが
続きます。）

テンプレートの中の `{{ t.id }}` が `1` に、`{% if t.done %}`
の分岐が `done` と `☑` に置き換わった、**描画済みの断片**
です。これがそのままブラウザの該当行に差し込まれます。

最後に削除です。

```bash
curl -s -w "HTTP %{http_code}\n" -X DELETE http://127.0.0.1:8000/htmx/todos/1
```

期待される出力（ボディは空で、ステータスだけが表示されます）:

```text
HTTP 200
```

「空のレスポンスで `<tr>` を置き換える = 行が消える」という
16.7 の説明を、裏側から確認できました。

確認が終わったら、DB を初期状態に戻して uvicorn を
`Ctrl+C` で止めてください。

```bash
uv run python -m app.cli reset-db
uv run python -m app.cli init-db
```

## 16.9 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] 部分更新とは何か、ページ全体の再読み込みと比べた利点を
      説明できる
- [ ] htmx が `hx-get` / `hx-target` / `hx-trigger` / `hx-swap`
      の 4 つの属性で何を指定しているか説明できる
- [ ] htmx に返すレスポンスが JSON ではなく HTML フラグメント
      である理由を説明できる
- [ ] `base.html` の script タグ 1 行で `hx-` 属性が有効に
      なる仕組みと、CDN が読めない環境でどうなるかを説明できる
- [ ] `pages.py` の 4 つの htmx 用エンドポイントが、それぞれ
      どの部分テンプレート（または空のレスポンス）を返すか
      説明できる
- [ ] `hx-swap="outerHTML"` と既定値 `innerHTML` の違いと、
      完了切替・削除で `outerHTML` が必要な理由を説明できる
- [ ] 検索欄の `keyup changed delay:300ms` が何をしているか
      説明できる
- [ ] ブラウザで追加・完了切替・削除・絞り込みを試し、
      DevTools の Network タブでリクエストとレスポンスを
      観察した

## 16.10 つまずきポイント

### クリックしても何も起きない（リロードもしない）

htmx は既定では **200 番台のレスポンスだけ**を画面に反映します。
サーバー側で例外が起きて 500 が返っていたり、パスやパラメータが
違って 404 や 422 が返っていたりすると、**リクエストは飛んでいるのに
画面は何も変わらない**状態になります。DevTools の Network タブで
ステータスコードを確認してください。uvicorn を動かしている
ターミナルに Traceback が出ていれば、そちらも手がかりになります。

### `hx-` 属性がまったく効かない（送信するとページ全体が再読み込みされる）

`base.html` の script タグで CDN から htmx を読み込めていない
可能性が高いです。DevTools の Network タブで
`https://unpkg.com/htmx.org@2.0.3` へのリクエストが失敗して
いないか確認してください。オフライン環境など CDN に届かない
場合、16.3 で見たとおり `hx-` 属性は無視され、フォームは通常の
GET 送信として動きます（その場合も絞り込み自体は動くので、
「部分更新にならない」という形で気づきます）。

### 完了切替で取り消し線が付かない、削除で行が入れ子になる

`hx-swap="outerHTML"` の書き忘れ・書き損じが典型です。既定値の
`innerHTML` だと `<tr>` の**中身**だけが差し替わるので、
`<tr class="done">` の `class` が更新されず取り消し線が付きません。
削除では `<tr>` の中に空文字が入るだけで、行の枠が残ってしまいます。
`_row.html` のボタンを見直してください
（第15章の `diff` で差分が出ていないか確認するのも有効です）。

### 検索しても絞り込まれない

`hx-trigger` の指定を書き換えてしまっていないか確認してください。
特に `keyup changed delay:300ms from:input[name='q']` の
`from:...` を外すと、フォーム内のどの要素の keyup でも
リクエストが飛ぶようになり、意図と違う挙動になります。
Network タブで「入力したときに `/partials/list` へのリクエストが
飛んでいるか」を見るのが切り分けの第一歩です。

## 16.11 やってみよう

本章は新規の写経がない分、htmx の小さな拡張を自分で試して
みましょう。解答例は折りたたんであるので、まず自分で考えてから
見比べてください。

### 問1 デバウンスを体感する

フィルタフォームの `delay:300ms` を `delay:1ms` に変えて、
検索欄に何文字か入力したときのリクエストの飛び方を Network タブで
比較してください。観察したら元に戻します。

??? example "解答例"

    `mytodo/app/templates/index.html` の `hx-trigger` を次のように
    変えます（`300` を `1` にするだけです）。

    ```html
    hx-trigger="change from:input[name='filter'], submit, keyup changed delay:1ms from:input[name='q']"
    ```

    ブラウザで Network タブを開き、検索欄に `ぎゅうにゅう` のように
    数文字入力すると、**1 文字ごとに `/partials/list` への
    リクエストが飛ぶ**ことがわかります。元の `delay:300ms` では、
    入力が止まってから 1 回だけ飛びます。

    連続した入力のたびにサーバーへリクエストを送ると無駄が多い
    ため、検索のような入力系ではデバウンスを効かせるのが定石です。
    確認したら `delay:300ms` に戻してください。

### 問2 `hx-swap` を変えてみる

完了切替ボタンの `hx-swap="outerHTML"` を外す（＝既定値の
`innerHTML` にする）と、何が起きるか観察してください。
観察したら元に戻します。

??? example "解答例"

    `mytodo/app/templates/_row.html` の toggle ボタンから
    `hx-swap="outerHTML"` の行を外します。

    ```html
    <button
      class="toggle"
      aria-label="完了切替"
      hx-post="/htmx/todos/{{ t.id }}/toggle"
      hx-target="#todo-{{ t.id }}"
    >{% if t.done %}☑{% else %}☐{% endif %}</button>
    ```

    ブラウザで `☐` を押すと、ボタンは `☑` に変わるのに
    **取り消し線が付きません**。返ってきた `<tr class="done">...`
    という断片の**中身だけ**が既存の `<tr>` の内側に差し込まれ、
    `<tr>` タグ自身（とその `class` 属性）は古いまま残るためです。
    DevTools の Elements タブで行の中を見ると、`<tr>` の内側に
    さらに `<td>` たちが入れ子になった、崩れた構造が確認できます。

    `class` 属性ごと更新したいので、差し替えは `outerHTML` で
    行う必要がありました。確認したら `hx-swap="outerHTML"` を
    戻してください。

### 問3 送信中のインジケータを出す

追加フォームに `hx-indicator` を使って、**リクエスト送信中だけ
「送信中...」と表示する**仕組みを追加してください。ヒント:
htmx はリクエストの間、指定した要素に `htmx-request` クラスを
自動で付け外しします。表示・非表示は CSS で制御します。

??? example "解答例"

    `mytodo/app/templates/index.html` の追加フォームに、
    `hx-indicator` 属性と表示用の要素を追加します。

    ```html
    <form
      hx-post="/htmx/todos"
      hx-target="#todo-list"
      hx-indicator="#add-indicator"
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
      <span id="add-indicator" class="htmx-indicator">送信中...</span>
    </form>
    ```

    `mytodo/app/static/style.css` の末尾に、htmx 公式ドキュメント
    推奨のスタイルを追加します。

    ```css
    .htmx-indicator { opacity: 0; transition: opacity 200ms ease-in; }
    .htmx-request .htmx-indicator { opacity: 1; }
    .htmx-request.htmx-indicator { opacity: 1; }
    ```

    ブラウザで ToDo を追加すると、リクエストの間だけ
    「送信中...」が表示されます（ローカル環境では一瞬で終わるので
    見えにくい場合は、DevTools の Network タブのスロットリングで
    通信速度を落とすと観察しやすいです）。

    `hx-indicator` に書いたセレクタの要素へ、リクエスト中だけ
    `htmx-request` クラスが付く——これも「属性に宣言するだけで
    挙動が変わる」htmx らしい仕組みです。確認したら元に戻すか、
    そのまま残しても構いません（以降の章の写経では
    `diff` の差分として現れる点だけ意識しておいてください）。

## まとめ

- **部分更新**は、サーバーから HTML の断片だけを受け取り、
  ページの一部だけを書き換える仕組み。スクロール位置や入力途中の
  値が保たれ、画面のチラつきもない
- **htmx** は Ajax の挙動を HTML 属性として宣言するライブラリ。
  `hx-get` / `hx-post` / `hx-delete` でリクエスト先とメソッド、
  `hx-target` で差し込み先、`hx-trigger` でタイミング、
  `hx-swap` で差し込み方を指定する
- `base.html` の script タグ 1 行で CDN から読み込むだけで
  使える。htmx は差し込んだ新しい HTML の中の `hx-` 属性にも
  自動で反応する
- サーバー側は **HTML フラグメント**を返す。第15章で切り出した
  部分テンプレート（`_list.html`・`_row.html`）を、初回表示と
  部分更新で使い回している
- 完了切替と削除は `hx-target="#todo-{{ t.id }}"` と
  `hx-swap="outerHTML"` で**行 1 本だけ**を差し替える。
  削除は空のレスポンスで行ごと置き換える
- 動作がおかしいときは DevTools の Network タブで**リクエストの
  URL・ステータスコード・返ってきた HTML**を見る。htmx は
  200 番台以外を画面に反映しない

これで ToDo アプリの画面側は完成です。
次は [第17章 設定・ログ・例外ハンドリング](17-finishing.md) で、
**他人が触っても壊れない**ようにする仕上げに入ります。
