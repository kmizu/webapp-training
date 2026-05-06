# 第12章 データアクセス層のテスト

前 2 章で書いた `repositories.py` に **pytest でテスト**を書きます。
DB を実際に立てて、**本物の PostgreSQL に対してテストを書く**方針です。
モックではなく実物を使うほうが、SQL のミスをちゃんと拾えます。

## 12.1 テストの方針

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

## 12.2 conftest.py

`tests/conftest.py` を作ります。同じ階層のテストファイル全部から自動で読まれます。

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

## 12.4 実行

```bash
uv run pytest -v
```

緑 10 個並べばOK。失敗したら、エラーメッセージを読みながら直していきます。

## 12.5 テストを書くコツ

- **1 テスト = 1 つの主張**: 「フィルタが正しく効く」をテストするのに、
  ついでに「タグも引けてる」を主張すると、壊れたとき原因切り分けが面倒。
- **AAA パターン**: Arrange（準備）→ Act（実行）→ Assert（検証）の 3 段。
  上の例も基本この形になっています。
- **境界値**: 0 件、1 件、大量。`q=""`、`q=None`。優先度 1 と 3。
- **異常系も書く**: 存在しない id で None / False が返ること、
  違反を起こしたら例外が出ること。

!!! warning "テストが落ちたとき本物のテーブルに残骸が残ったら"
    `tests/conftest.py` のロールバックは、**テストが正常に終わった場合**にも、
    **テスト中に例外が出た場合**にも効きます。それでも気持ち悪いときは
    `psql` で `\dt`、`SELECT * FROM todos` を見て確認してください。
    ロールバック前のクエリが残ることはありません。

## 12.6 テストカバレッジ

時間があれば `pytest-cov` を入れて、カバレッジを見るのもよい習慣です。

```bash
uv add --group dev pytest-cov
uv run pytest --cov=app --cov-report=term-missing
```

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
