# 第12章 データアクセス層のテスト

第10〜11章で `repositories.py` を完成させ、`diff` で完成版と一致することも
確認しました。この章では、そのデータアクセス層に **pytest でテストを書きます**。

方針は、**モックを使わず、本物の PostgreSQL に対してテストを書く**ことです。
SQL のミス（カラム名の打ち間違い、`ORDER BY` の並び順、`ON CONFLICT` の
書き方など）は、DB を模した偽物に対して実行しても見つかりません。
第0章で用意した Docker の PostgreSQL に実際につないでテストを流すことで、
「書いた SQL が本当に動くか」を確認します。

リポジトリの `sample/todo-app/` は引き続き**答え合わせ用の完成版**です。
この章で写経する `tests/` のコードも、完成版 `sample/todo-app/tests/` の
実ファイルと同じ内容なので、写経が終わるたびに `diff` で答え合わせをします。

## 12.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- テストの独立性とは何か、ロールバックでどう実現するかを説明できる
- pytest のフィクスチャ（`@pytest.fixture`）と `yield` の流れを説明できる
- `uv add --group dev pytest` で開発用の依存を登録できる
- `tests/__init__.py` / `tests/conftest.py` / `tests/test_repositories.py` を
  写経し、`diff` で完成版と答え合わせできる
- `uv run pytest -v` を実行して **10 個のテストがすべてパス**することを確認できる

**所要時間の目安: 60 分**

この章で新しく作るのは `mytodo/tests/` ディレクトリと、その中の 3 ファイルだけです。
`app/` や `migrations/` には一切手を付けません。

!!! info "前提となる状態"
    - 第11章末時点の `mytodo/`（`app/` は完成版相当、`init-db` 適用済み）がある
    - 第0章の Docker の PostgreSQL が起動している（`docker compose up -d`）
    - シードデータが入った状態（`todos` 4 件、`tags` 3 件、`todo_tags` 2 件）である

## 12.2 前提知識

コードに入る前に、この章の鍵になる 3 つの考え方を押さえておきます。

!!! note "テストの独立性"
    テストは、**書いた順番や実行した順番に関係なく、いつ・何度実行しても
    同じ結果になる**べきです。これを **テストの独立性** と呼びます。

    もし `test_A` が作ったデータに `test_B` がこっそり乗っかって初めて
    パスする状態になっていると、`test_B` だけを単独で実行したら失敗する、
    実行順序を変えただけで結果が変わる、といった不安定なテストになります。
    しかも、どちらのテストが悪いのか切り分けるのに時間を取られます。

    DB を使うテストで独立性を確保するには、**各テストが自分で使った分だけ
    後片付けをする**のが一番素直な方法です。この章では、その後片付けに
    次に説明する **ロールバック** を使います。

!!! note "ロールバックによる後始末"
    第6章で学んだとおり、psycopg を `autocommit=False`（デフォルト）で
    使っている間、実行した `INSERT` / `UPDATE` / `DELETE` は
    **`commit()` を呼ぶまで確定しません**。`rollback()` を呼べば、
    そのトランザクションの中で行った変更はすべて巻き戻されます。

    この性質をテストに使います。つまり:

    ```text
    テスト開始
       ↓ 接続を開く（autocommit=False）
    テスト内でいろいろ INSERT / UPDATE / DELETE する（まだ未コミット）
       ↓ テスト終了
    conn.rollback()  ← すべて巻き戻るので、DB はテスト前の状態に戻る
    ```

    この方式のよいところは、**「何を片付けるべきか」をテスト側が
    知らなくてよい**ことです。テストが 10 件 INSERT しようが、タグを
    付け替えようが、ロールバック 1 回ですべて無かったことになります。
    そのおかげで「テストを実行しても DB の中身は実行前と変わらない」
    状態を毎回作れます。

!!! note "フィクスチャ（fixture）とは"
    第2章で名前だけ登場した **フィクスチャ** は、テスト関数に渡す
    「お膳立て」を pytest に任せる仕組みです。

    テストごとに同じ準備（ここでは DB 接続を開くこと）と後片付け
    （ロールバックして接続を閉じること）を毎回手で書くのは面倒ですし、
    どこかのテストで書き忘れると、前のテストの残骸が次のテストに
    持ち越されてしまいます。フィクスチャを使えば、この
    **セットアップとティアダウンをテスト関数の外に切り出して自動化**
    できるので、テスト本体は「何を確認したいか」だけに集中できます。

    使い方はシンプルで、テスト関数の引数にフィクスチャ名（この章では
    `conn`）を書くだけです。pytest が同名のフィクスチャ関数を探して
    実行し、その戻り値（正確には `yield` された値）を引数に
    渡してくれます
    （[pytest 公式の fixture ガイド](https://docs.pytest.org/en/stable/how-to/fixtures.html)）。

## 12.3 ここまでのファイル構成

まず現在地を確認します。第11章末時点の `mytodo/` は次の構成です。

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
│   └── repositories.py     第10〜11章で作成（完成版と一致済み）
├── migrations/
│   ├── 001_init.sql        第9章で作成・tododb に適用済み
│   └── 002_seed.sql        第9章で作成・tododb に適用済み
└── tests/                  ← この章で作成
    ├── __init__.py         この章で作成（空ファイル）
    ├── conftest.py         この章で作成
    └── test_repositories.py この章で作成
```

（第9章の「やってみよう」に取り組んだ人は、`migrations/` に
`003_add_memo.sql` もあるはずです。そのままで大丈夫です。）

なお、完成版の `sample/todo-app/tests/` にはこのほかに `test_api.py`
もありますが、あれは **第14章**（FastAPI のルーター）の写経対象なので、
この章では作りません。

## 12.4 pytest を dev 依存として導入する

第2章では `uv run --with pytest` という「その実行の間だけ pytest を
環境に追加する」形で pytest を使いました。あのとき予告したとおり、
ToDo アプリ本体のテストでは、開発用の依存としてプロジェクトに
**登録する**方法を使います。そのためのコマンドが
`uv add --group dev` です。

`mytodo/` の中で実行します。

```bash
uv add --group dev pytest
```

期待される出力（パッケージ数や時間は環境によって変わります）:

```text
Resolved 36 packages in ...
Audited 33 packages in ...
```

このコマンドは本来、「`pyproject.toml` の `[dependency-groups]` の
`dev` グループに `pytest` を追記し、ロックを更新してインストールする」
という 3 つのことを一度に行います。`--group dev` を付けると、
アプリの実行に必要な本体の依存（`dependencies`）とは別の、
**開発中だけ使う依存**として登録されます。テストランナーやリンターなど、
本番環境には要らない道具を入れるのが `dev` グループの定番の使い方です。

実は、第10章で `pyproject.toml` を完成版から写経したときに、
`[dependency-groups]` の `dev` に `pytest` と `httpx` が
**すでに登録済み**でした（`uv sync` は `dev` グループも
デフォルトでインストールするので、`.venv/` にも入っています）。
そのため、上のコマンドを実行しても `pyproject.toml` は変わらず、
「解決と監査だけ走って終わる」出力になります。`uv add` は何度
実行しても安全なので、新しい開発用ツールを入れたいときは
同じ形（たとえば `uv add --group dev pytest-cov`）で追加できます。

あわせて、第10章で写経した `pyproject.toml` の
`[tool.pytest.ini_options]` もここで効いてきます。

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

- `testpaths` …… 引数なしで `pytest` を実行したときに、
  テストを探す場所を `tests/` に限定します。
- `addopts` …… 毎回自動で付けるオプション。`-v`（verbose:
  テスト 1 件ごとに結果を表示）が既定で付きます。

## 12.5 `tests/__init__.py`（空ファイル）

まず `tests/` ディレクトリを作り、目印のファイルを置きます。

```bash
mkdir tests
```

`mytodo/tests/__init__.py` を**中身は空のまま**作成してください。

この空ファイルには重要な役割があります。`tests/__init__.py` があると、
pytest はテストファイルを `tests.test_repositories` という
**パッケージ経由の名前で import** しようとして、そのために
`tests/` の親ディレクトリ（つまり `mytodo/`）を import の検索パスに
追加します。そのおかげで、テストファイルの中の
`from app import repositories as repo` が正しく解決されます。
`__init__.py` が無いと `mytodo/` が検索パスに乗らず、
`ModuleNotFoundError: No module named 'app'` になることがあるので、
必ず置いてください（12.11 のつまずきポイントも参照）。

## 12.6 フィクスチャを定義する: `tests/conftest.py`

`conftest.py` は pytest が予約している特別なファイル名で、
同じディレクトリ（や配下のディレクトリ）にあるテストファイルから、
`import` しなくても自動的にフィクスチャを読み込んでくれます。
複数のテストファイルで共通して使うフィクスチャは、この
`conftest.py` に集約しておくのが定石です。

`mytodo/tests/conftest.py` を作成して、次の内容を書き写してください。

```python
import psycopg
import pytest
from psycopg.rows import dict_row

from app.config import settings


@pytest.fixture
def conn():
    """各テストごとに独立した接続を渡す。テスト後にロールバック。"""
    with psycopg.connect(settings.dsn, row_factory=dict_row, autocommit=False) as c:
        try:
            yield c
        finally:
            c.rollback()
```

ポイントになるのが **`yield` を挟んだ書き方**です。フィクスチャ関数は
`yield` の前が「テスト実行前のセットアップ」、テストが実行し終わって
戻ってきたところからが「テスト実行後のティアダウン」になります。
`conn` を受け取る各テスト関数は `yield c` で渡された接続 `c` を
そのまま使い、テストが終わると（成功しても失敗しても）関数の続きである
`finally: c.rollback()` が実行される、という流れです。

- **`row_factory=dict_row`**: 結果を辞書で受け取れるようにする設定です
  （第7章）。テストのコードでも本体と同じ感覚で行を読めるので、
  アサーションが書きやすくなります。
- **`autocommit=False`**: psycopg v3 のデフォルトですが、ここでは
  明示しています。これにより、テスト中に実行した `INSERT` / `UPDATE` は
  すべて 1 つのトランザクションの中に留まり、`commit()` を呼ばない限り
  確定しません（第6章）。
- **`try: yield c` / `finally: c.rollback()`**: `try/finally` で
  挟んでいるのは、**`assert` が失敗した場合でも、想定外の例外で
  落ちた場合でも、必ずロールバックを実行したい**からです。
  `finally` ブロックはどちらの経路を通っても必ず実行されるので、
  ロールバックし忘れて次のテストに汚れたデータを持ち越す事故を防げます。
- `with psycopg.connect(...) as c:` の `with` を抜けるとき、
  接続は自動で閉じられます。ロールバック → 切断、という順で
  後片付けが完了します。

なお、この `conn` フィクスチャは**テスト関数ごとに毎回実行**されます。
10 個のテストがあれば、接続を開いてはロールバックして閉じる、という
流れが 10 回繰り返されます。使い回しをしないことで、あるテストの
途中状態（開いたままのトランザクションなど）が別のテストに
漏れないようにしています。

!!! note "テスト内の `now()` はトランザクション開始時刻で固定される"
    各テストの書き込みは 1 つのトランザクションの中に留まるため、
    `created_at` / `updated_at` の既定値 `now()` はそのトランザクションの
    開始時刻で固定されます（第11章で触れた `now()` の性質そのものです）。
    つまり、1 つのテストの中で複数の ToDo を作っても、それらの
    `created_at` はすべて同じ値になります。時刻の前後関係を検証する
    テストを書くときは、この性質を念頭に置いてください。

## 12.7 リポジトリのテスト: `tests/test_repositories.py`

いよいよテスト本体です。第10〜11章で写経したリポジトリ関数に対する
テストが 10 本入っています。

`mytodo/tests/test_repositories.py` を作成して、次の内容を書き写してください。

```python
from datetime import date

from app import repositories as repo


def test_create_and_get(conn):
    todo = repo.create_todo(conn, title="テスト用", priority=1)
    assert todo.id > 0
    fetched = repo.get_todo(conn, todo.id)
    assert fetched is not None
    assert fetched.title == "テスト用"
    assert fetched.priority == 1
    assert fetched.done is False


def test_filter_open_done(conn):
    a = repo.create_todo(conn, title="やること")
    b = repo.create_todo(conn, title="完了済")
    repo.toggle_done(conn, b.id)

    open_ids = {t.id for t in repo.list_todos(conn, filter_="open")}
    done_ids = {t.id for t in repo.list_todos(conn, filter_="done")}

    assert a.id in open_ids
    assert b.id in done_ids
    assert a.id not in done_ids


def test_search_with_q(conn):
    repo.create_todo(conn, title="ミーティングの議事録")
    repo.create_todo(conn, title="家賃を振り込む")
    found = repo.list_todos(conn, q="議事")
    titles = [t.title for t in found]
    assert "ミーティングの議事録" in titles
    assert "家賃を振り込む" not in titles


def test_update_can_clear_due_on(conn):
    t = repo.create_todo(conn, title="期限あり", due_on=date(2026, 5, 30))
    updated = repo.update_todo(conn, t.id, due_on=None)
    assert updated is not None
    assert updated.due_on is None


def test_update_partial_keeps_other_fields(conn):
    t = repo.create_todo(conn, title="部分更新", priority=2, due_on=date(2026, 6, 1))
    updated = repo.update_todo(conn, t.id, title="変更後")
    assert updated is not None
    assert updated.title == "変更後"
    assert updated.priority == 2
    assert updated.due_on == date(2026, 6, 1)


def test_tags_attach_and_list(conn):
    t = repo.create_todo(conn, title="ジム", tag_names=["健康", "週次"])
    fetched = repo.get_todo(conn, t.id)
    assert fetched is not None
    names = sorted(g.name for g in fetched.tags)
    assert names == ["健康", "週次"]


def test_replace_tags_overrides_existing(conn):
    t = repo.create_todo(conn, title="タグ差し替え", tag_names=["A", "B"])
    repo.replace_tags(conn, t.id, ["C"])
    fetched = repo.get_todo(conn, t.id)
    assert fetched is not None
    assert [g.name for g in fetched.tags] == ["C"]


def test_delete_cascades_tags(conn):
    t = repo.create_todo(conn, title="削除予定", tag_names=["仕事"])
    assert repo.delete_todo(conn, t.id) is True
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM todo_tags WHERE todo_id = %s", (t.id,))
        assert cur.fetchone()["n"] == 0


def test_get_unknown_returns_none(conn):
    assert repo.get_todo(conn, 9999999) is None


def test_toggle_unknown_returns_none(conn):
    assert repo.toggle_done(conn, 9999999) is None
```

どのテストも引数に `conn` だけを書いています。これが 12.6 の
フィクスチャへの合図で、pytest がテストごとに新しい接続を用意して
渡してくれます。テスト関数の中では接続の開閉やロールバックを
**一切書かなくてよい**のがポイントです。

各テストが何を確認しているか、ざっと見ておきます。

- `test_create_and_get` は一番シンプルな「作って読める」の確認です。
  ここがコケるようなら、まず疑うべきはテストの書き方より
  DB 接続やテーブル定義そのものです。
- `test_filter_open_done` / `test_search_with_q` は、第10章の
  `list_todos` の `filter_` と `q` が意図どおり効くかの確認です。
  シードデータにも同じタイトル（「家賃を振り込む」）が含まれますが、
  ロールバック前提でシードと同じデータを作っても衝突しないことが
  わかる構成になっています。
- `test_update_can_clear_due_on` と `test_update_partial_keeps_other_fields`
  は、第11章で `_UNSET` センチネルを使って区別した
  **「指定なし」と「明示的に NULL」** が、実際に意図どおり動くかの
  確認です。ここをテストしておかないと、リファクタのときに一番
  壊れやすい部分が野放しになってしまいます。
- `test_tags_attach_and_list` 〜 `test_delete_cascades_tags` は、
  タグの多対多関連（`attach_tags` / `replace_tags` /
  `ON DELETE CASCADE`）のふるまいの確認です。
  `test_delete_cascades_tags` では、リポジトリ経由ではなく
  **自分でカーソルを開いて生 SQL で `todo_tags` を数える**ことで、
  カスケード削除が DB レベルで効いたことを直接確かめています。
- `test_get_unknown_returns_none` / `test_toggle_unknown_returns_none` は、
  存在しない `id` を渡したときの**異常系**です。正常系だけ
  テストしていると、こういう「境界を外れた入力」への対応漏れに
  気づけません。

どのテストもだいたい **Arrange（準備）→ Act（実行）→ Assert（検証）**
の 3 段構成になっていることにも注目してください。この形を意識して
書くと、テストの構造が毎回同じになるので、他の人（未来の自分も含む）
が読んだときに迷いません。

## 12.8 動作確認: `uv run pytest -v`

`mytodo/` の中で実行します。

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
collecting ... collected 10 items

tests/test_repositories.py::test_create_and_get PASSED                   [ 10%]
tests/test_repositories.py::test_filter_open_done PASSED                 [ 20%]
tests/test_repositories.py::test_search_with_q PASSED                    [ 30%]
tests/test_repositories.py::test_update_can_clear_due_on PASSED          [ 40%]
tests/test_repositories.py::test_update_partial_keeps_other_fields PASSED [ 50%]
tests/test_repositories.py::test_tags_attach_and_list PASSED             [ 60%]
tests/test_repositories.py::test_replace_tags_overrides_existing PASSED  [ 70%]
tests/test_repositories.py::test_delete_cascades_tags PASSED             [ 80%]
tests/test_repositories.py::test_get_unknown_returns_none PASSED         [ 90%]
tests/test_repositories.py::test_toggle_unknown_returns_none PASSED      [100%]

============================== 10 passed in 0.17s ==============================
```

**`10 passed` と表示されればこの章の動作確認は成功です。**
ヘッダの `configfile: pyproject.toml` と `testpaths: tests` は、
12.4 で確認した pytest の設定が読み込まれていることを示しています。
なお、`plugins:` の行は FastAPI の依存である anyio が pytest の
プラグインを提供しているために表示されるもので、内容は環境によって
変わります。

テストが 10 本ともグリーンでも、本当に後片付けが効いているかは
DB を見るまでわかりません。ロールバック方式の効果を確かめるため、
psql で `todos` の件数を見てみましょう（接続の手順は第3章と同じです）。

```sql
SELECT COUNT(*) FROM todos;
```

期待される出力:

```text
 count 
-------
     4
(1 row)
```

テストの中で何件も ToDo を作ったのに、**シードデータの 4 件のまま**
です。`conn` フィクスチャのロールバックで、テストが書き込んだ
データがすべて巻き戻されていることが確認できました。

## 12.9 答え合わせ: `diff` が空になることを確認

写経した 2 ファイルを完成版と答え合わせします
（`diff` コマンドは**リポジトリのルート**で実行してください）。

```bash
diff -u mytodo/tests/conftest.py sample/todo-app/tests/conftest.py
diff -u mytodo/tests/test_repositories.py sample/todo-app/tests/test_repositories.py
```

**両方とも何も表示されなければ完成版と一致しています。**
差分が出た場合の見方はこれまでの章と同じで、`-` で始まる行は
あなたのファイルにだけある行、`+` で始まる行は完成版にだけある行です。
コメントや空行の 1 行でも差分として表示されるので、
表示された行を見比べて写し直してください。

## 12.10 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] テストの独立性とは何か、それが崩れると何が困るのかを説明できる
- [ ] ロールバックによる後始末の仕組み（なぜテストの書き込みが
      DB に残らないのか）を説明できる
- [ ] フィクスチャの役割と、`yield` の前後でセットアップと
      ティアダウンが分かれる流れを説明できる
- [ ] `try/finally` でロールバックを挟む理由を説明できる
- [ ] `uv add --group dev pytest` が何をするコマンドか、
      第2章の `uv run --with pytest` との違いとともに説明できる
- [ ] `tests/__init__.py` を置く理由を説明できる
- [ ] `tests/` の 3 ファイルを写経し、2 つの `diff` がともに
      差分なしになった
- [ ] `uv run pytest -v` で `10 passed` を確認し、テスト後も
      `todos` が 4 件のままであることを psql で確認した

## 12.11 つまずきポイント

### `ModuleNotFoundError: No module named 'app'`

`tests/__init__.py` を作り忘れているか、`mytodo/` ではない場所で
`pytest` を実行しています。12.5 で説明したとおり、
`tests/__init__.py` があると pytest は `mytodo/` を import の
検索パスに追加するので、`from app import ...` が解決できるように
なります。空ファイルを置いて、**`mytodo/` の中で**実行してください。

### `psycopg.OperationalError: connection to server ... failed`

Docker の PostgreSQL が起動していません。リポジトリのルートで
`docker compose up -d` を実行してから（第0章）、もう一度
`uv run pytest -v` を試してください。この章のテストはモックを
使わず本物の DB に接続するので、DB が止まっていると全テストが
接続エラーで落ちます。

### テストが `FAILED` になる

まず落ち着いて出力を読みます。`>` で始まる行が失敗した `assert`、
その下の `E` で始まる行が「実際にはどういう値・エラーだったか」です。

リポジトリ側の写経ミスが原因のことが多いので、次の `diff` で
本体も答え合わせしてみてください（リポジトリのルートで実行）。

```bash
diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py
```

ここで差分が出たら、第10〜11章の写経に戻って修正します。
テストが「正しく壊れを検知している」状態なので、テストではなく
本体のほうを直すのが筋です。

### `collected 0 items` と表示されてテストが実行されない

pytest はデフォルトで `test_*.py` という名前のファイルの中の
`test_` で始まる関数だけをテストとして集めます。ファイル名の
スペル（`test_repostories.py` など）や、配置場所が `tests/` の
直下であることを確認してください。

## 12.12 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 並び順のテストを書く

第10章の `list_todos` は `done` → `due_on`（NULL は後ろ）→
`priority` → `id` の順で並び替えます。この並び順を確認するテストを
`test_repositories.py` に追加して、パスすることを確かめてください。

ヒント: シードデータが混ざると期待値が書きにくいので、
`q` で自分が作った ToDo だけに絞ると書きやすいです。

??? example "解答例"

    `mytodo/tests/test_repositories.py` の末尾に次のテストを追加します。

    ```python
    def test_list_todos_ordered_by_priority(conn):
        repo.create_todo(conn, title="並び順-低", priority=3)
        repo.create_todo(conn, title="並び順-高", priority=1)
        repo.create_todo(conn, title="並び順-中", priority=2)
        titles = [t.title for t in repo.list_todos(conn, q="並び順")]
        assert titles == ["並び順-高", "並び順-中", "並び順-低"]
    ```

    実行します。

    ```bash
    uv run pytest -v
    ```

    期待される出力（抜粋。テスト数が 11 本に増えています）:

    ```text
    tests/test_repositories.py::test_list_todos_ordered_by_priority PASSED [100%]

    ============================== 11 passed in ... ==============================
    ```

    3 件とも `due_on` は NULL 同士なので、`priority` の昇順
    （1 → 2 → 3）で並びます。`q="並び順"` でこのテストが作った
    3 件だけに絞っているので、シードデータや他のテストの残骸を
    気にせず期待値を書けます（もっとも、ロールバック方式なので
    残骸はそもそも残りませんが）。

    確認が終わったら、このテストは消しても残しても構いません。
    残す場合は、以降の章でテスト件数が 11 本として表示される点だけ
    注意してください。

### 問2 制約違反がエラーになることをテストする

第9章の `001_init.sql` では、`priority` に
`CHECK (priority BETWEEN 1 AND 3)` という制約を付けました。
`create_todo` に `priority=0` を渡すと例外が送出されることを
確認するテストを書いてください。

ヒント: pytest には「このブロックで指定した例外が出ること」を
検証する [`pytest.raises`](https://docs.pytest.org/en/stable/reference/reference.html#pytest.raises)
という仕組みがあります。送出される例外の型は、psycopg の
`psycopg.errors.CheckViolation` です。

??? example "解答例"

    `mytodo/tests/test_repositories.py` の先頭の import を次のように
    変更します。

    ```python
    from datetime import date

    import psycopg
    import pytest

    from app import repositories as repo
    ```

    そして末尾に次のテストを追加します。

    ```python
    def test_create_with_invalid_priority_raises(conn):
        with pytest.raises(psycopg.errors.CheckViolation):
            repo.create_todo(conn, title="不正な優先度", priority=0)
    ```

    実行します。

    ```bash
    uv run pytest -v
    ```

    期待される出力（抜粋）:

    ```text
    tests/test_repositories.py::test_create_with_invalid_priority_raises PASSED [100%]

    ============================== 11 passed in ... ==============================
    ```

    `with pytest.raises(...)` のブロック内で指定した例外が出れば
    パス、出なければ失敗、というテストです。「変な値を弾く」のは
    Python 側ではなく **DB の CHECK 制約** なので、このテストは
    モックを使わない方針だからこそ書けるものです。

    なお、例外が送出されたあとのトランザクションは PostgreSQL 側で
    「中断された」状態になり、同じ接続では後続のクエリを
    実行できなくなります（第6章）。このテストでは例外のあとに
    何もしていないので問題ありませんし、ティアダウンの
    `c.rollback()` がこの中断状態もきれいに片付けてくれます。

## まとめ

- テストは実行順に依らず同じ結果になるべき（テストの独立性）。
  DB を使うテストでは、**各テストの書き込みをロールバックで
  巻き戻す**ことで独立性を確保した
- pytest のフィクスチャは、セットアップとティアダウンを
  テスト関数の外に切り出す仕組み。`yield` の前が準備、後が後片付け。
  `try/finally` で挟めば失敗時も後片付けが必ず走る
- `conftest.py` に置いたフィクスチャは、同じディレクトリの
  テストから `import` なしで使える
- `tests/__init__.py`（空）は、pytest が `mytodo/` を import の
  検索パスに追加するために必要な目印
- `uv add --group dev pytest` は、開発用の依存を
  `[dependency-groups]` の `dev` グループに登録するコマンド
  （今回は第10章の写経済み `pyproject.toml` に含まれていたので、
  実行しても変更なしで終わる）
- `uv run pytest -v` で 10 本すべてパスし、テスト後も `todos` は
  シードデータの 4 件のままであることを確認した

これで Part 4 はおしまいです。
次は [第13章 FastAPI入門 起動とDI](13-api-fastapi.md) で、
**この層の上に Web API を載せます**。
