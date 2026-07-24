# 第12章 データアクセス層のテスト

前 2 章で書いた `repositories.py` に **pytest でテスト**を書きます。
DB を実際に立てて、**本物の PostgreSQL に対してテストを書く**方針です。
モックではなく実物を使うほうが、SQL のミスをちゃんと拾えます。

## 12.1 テストの方針

テストは、**書いた順番や実行した順番に関係なく、いつ・何度実行しても同じ結果になる**べきです。
これを「テストの独立性」と呼びます。もし `test_A` が作ったデータに `test_B` がこっそり
乗っかって初めてパスする、という状態になっていると、`test_B` だけを実行したら失敗する、
実行順序を変えただけで結果が変わる、といった不安定なテストになってしまいます。しかも
どちらのテストが悪いのか切り分けるのに時間を取られます。この章では、**各テストが自分で
使った分だけ後片付けをする**（＝ロールバックする）ことで独立性を確保します。

- 本物の `tododb` を使う（研修なので分けない）
- 各テストは **トランザクションを開いて、最後にロールバック** する
  → テスト間で副作用が残らない
- `pytest.fixture` で **接続を毎回渡す**

```text
test_xxx 関数
   ↓ conn fixture が
psycopg.connect(autocommit=False)
   ↓ テスト内でいろいろ INSERT / UPDATE
   ↓ テスト終了
conn.rollback()  ← すべて巻き戻る
```

**fixture** は、テスト関数に渡す「お膳立て」を pytest に任せる仕組みです。テストごとに
同じ準備（ここでは DB 接続を開くこと）と後片付け（ロールバックして接続を閉じること）を
毎回手で書くのは面倒ですし、どこかのテストで書き忘れると前のテストの残骸が次のテストに
持ち越されてしまいます。fixture を使えば、この**セットアップとティアダウンをテスト関数の
外に切り出して自動化**できるので、テスト本体は「何を確認したいか」だけに集中できます
（詳しくは [pytest公式のfixtureガイド](https://docs.pytest.org/en/stable/how-to/fixtures.html)）。

## 12.2 conftest.py

`tests/conftest.py` を作ります。`conftest.py` は pytest が予約している特別なファイル名で、
同じディレクトリ（や配下のディレクトリ）にあるテストファイルから、`import` しなくても
自動的に fixture を読み込んでくれます。複数のテストファイルで共通して使う fixture は、
この `conftest.py` に集約しておくのが定石です。

```python
# tests/conftest.py
import psycopg
import pytest
from psycopg.rows import dict_row

from app.config import settings


@pytest.fixture
def conn():
    """各テストごとに独立した接続を渡す。テスト後にロールバック。"""
    with psycopg.connect(
        settings.dsn,
        row_factory=dict_row,
        autocommit=False,
    ) as c:
        try:
            yield c
        finally:
            c.rollback()
```

ポイントになるのが **`yield` を挟んだ書き方**です。fixture 関数は `yield` の前が
「テスト実行前のセットアップ」、テストが実行し終わって戻ってきたところからが
「テスト実行後のティアダウン」になります。`conn` を受け取る各テスト関数は `yield c` で
渡された接続 `c` をそのまま使い、テストが終わると（成功しても失敗しても）関数の続きである
`finally: c.rollback()` が実行される、という流れです。

- **`row_factory=dict_row`**: 結果を辞書で受け取れるようにする設定です（第7章）。
  テストのコードでも `fetched["title"]` のように本体のコードと同じ感覚で読めるので、
  アサーションが書きやすくなります。
- **`autocommit=False`**（psycopg v3 のデフォルトですが、ここでは明示しています）:
  これにより、テスト中に実行した `INSERT` / `UPDATE` はすべて 1 つのトランザクションの
  中に留まり、`commit()` を呼ばない限り確定しません
  （[psycopgのトランザクション](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)）。
- **`try: yield c` / `finally: c.rollback()`**: `try/finally` で挟んでいるのは、
  **`assert` が失敗した場合でも、想定外の例外で落ちた場合でも、必ずロールバックを
  実行したい**からです。`finally` ブロックはどちらの経路を通っても必ず実行されるので、
  ロールバックし忘れて次のテストに汚れたデータを持ち越す事故を防げます。

このロールバックのおかげで、**「テストを実行してもDBの中身は実行前と変わらない」**
という状態を毎回作れます。これが 12.1 で触れた「テストの独立性」を、実際のコードで
実現している部分です。

## 12.3 リポジトリのテスト

`tests/test_repositories.py`:

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
    updated = repo.update_todo(conn, t.id, due_on=None)  # 「明示的に NULL」
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

ポイント:

- `test_create_and_get` が一番シンプルな「作って読める」の確認です。ここがコケるようなら、
  まず疑うべきはテストの書き方より DB 接続やテーブル定義そのものです。
- `test_update_can_clear_due_on` と `test_update_partial_keeps_other_fields` は、
  第11章で `_UNSET` センチネルを使って区別した「指定なし」と「明示的に NULL」が、
  実際に意図どおり動くかを確認しています。ここをテストしておかないと、リファクタ時に
  一番壊れやすい部分が野放しになってしまいます。
- `test_tags_attach_and_list` 〜 `test_delete_cascades_tags` は、タグの多対多関連
  （`attach_tags` / `replace_tags` / `ON DELETE CASCADE`）のふるまいの確認です。
- `test_get_unknown_returns_none` と `test_toggle_unknown_returns_none` は、
  存在しない `id` を渡したときの異常系です。正常系だけテストしていると、こういう
  「境界を外れた入力」への対応漏れに気づけません。

## 12.4 実行

```bash
uv run pytest -v
```

緑 10 個並べばOK。失敗したら、エラーメッセージを読みながら直していきます。

## 12.5 テストを書くコツ

- **1 テスト = 1 つの主張**: 「フィルタが正しく効く」をテストするのに、
  ついでに「タグも引けてる」を主張すると、壊れたとき原因切り分けが面倒。
  **失敗したテストの名前を見ただけで、何が壊れたか見当がつく**のが理想形です。
- **AAA パターン**: Arrange（準備）→ Act（実行）→ Assert（検証）の 3 段。
  上の例も基本この形になっています。**この 3 段を意識して書くと、テストの構造が
  毎回同じ形になるので、他の人（未来の自分も含む）が読んだときに迷いません。**
- **境界値**: 0 件、1 件、大量。`q=""`、`q=None`。優先度 1 と 3。
  **バグは「いつも通りのケース」より「端っこのケース」に潜んでいることが多い**ので、
  正常系だけでなく境界も意識して書きます。
- **異常系も書く**: 存在しない id で None / False が返ること、
  違反を起こしたら例外が出ること。**「起きてほしくないこと」を明示的にテストしておくと、
  将来誰かが（自分自身も含めて）うっかり壊したときにすぐ気づけます。**

!!! warning "テストが落ちたとき本物のテーブルに残骸が残ったら"
    `tests/conftest.py` のロールバックは、`try/finally` で挟んであるおかげで、
    **テストが正常に終わった場合**にも、**`assert` の失敗や想定外の例外でテストが
    落ちた場合**にも効きます。それでも気持ち悪いときは
    `psql` で `\dt`、`SELECT * FROM todos` を見て確認してください。
    ロールバック前のクエリが残ることはありません。

## 12.6 テストカバレッジ

**カバレッジ（網羅率）**とは、テストを実行したときに、アプリのコードのうち
**何 % の行（やブランチ）が実際に実行されたか**を示す指標です。時間があれば
`pytest-cov` を入れて見てみるのもよい習慣です。`--cov-report=term-missing` を
付けると、一度も実行されなかった行番号まで教えてくれるので、「このエラー処理、
実はテストで一度も通っていない」といった見落としに気づけます。

```bash
uv add --group dev pytest-cov
uv run pytest --cov=app --cov-report=term-missing
```

!!! warning "カバレッジ 100% はゴールではない"
    カバレッジが測っているのは **「その行が実行されたか」だけ**で、
    **「その行の結果が正しいと確認できたか」までは保証しません**。極端な話、
    `assert` を 1 つも書かずに関数を呼ぶだけのテストでも、その関数の行は
    「実行された」とカウントされてカバレッジは上がってしまいます。つまり
    **カバレッジ 100% ≠ バグがない** です。カバレッジは「テストが足りていない
    場所」を見つけるための道具であって、そこにあるテストの質までは測ってくれません。
    品質を支えるのは、あくまで 12.5 で見たような**意味のあるアサーション**の方です。

研修としてはここまではマストではありません。
**「自分の手で 1 行ずつ書いた関数に、自分でテストを書いて、緑にする」** 体験を
1 度でもしておくと、その後の安心感がぐっと違います。

## やってみよう

1. **「期限切れの ToDo だけ返す関数」** を `repositories.py` に追加し、
   そのテストを `test_repositories.py` に書く。
2. テストが緑になったら、わざと実装を壊して **赤くなる**ことを確認する。
3. `assert` を `assert ... == ...` ではなく `assertEqual` にしてみて、
   pytest の出力がどう変わるか比較する（実は pytest なら `assert` だけで十分）。

これで Part 4 はおしまいです。
次は [第 13 章 FastAPI入門 起動とDI](13-api-fastapi.md) で、
**この層の上に Web API を載せます**。
