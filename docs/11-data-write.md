# 第11章 リポジトリ（Write系）とタグの多対多

前章で読み取りができました。今度は **書き込み系**を実装します。

- 作成（INSERT）
- 部分更新（UPDATE）
- 削除（DELETE）
- 完了/未完了の切替（toggle）
- タグの付け替え（多対多の扱い）

## 11.1 ToDo を作る：`create_todo`

```python
def create_todo(
    conn: psycopg.Connection,
    *,
    title: str,
    due_on: date | None = None,
    priority: int = 2,
    tag_names: list[str] | None = None,
) -> Todo:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO todos (title, due_on, priority)
            VALUES (%s, %s, %s)
            RETURNING id, title, done, due_on, priority, created_at, updated_at
            """,
            (title, due_on, priority),
        )
        todo = _row_to_todo(cur.fetchone())

    if tag_names:
        attach_tags(conn, todo.id, tag_names)
        todo.tags = list_tags_for_todo(conn, todo.id)

    return todo
```

`RETURNING` は PostgreSQL の拡張構文で、`INSERT`/`UPDATE`/`DELETE` した行の値をその場で
受け取れます（[DML: データ操作言語](https://www.postgresql.org/docs/current/dml.html)）。
`INSERT` したあとにもう一度 `SELECT` で取り直す、という2回目の往復をせずに済むのが利点です。
`id`（`SERIAL` で自動採番）や `created_at`/`updated_at`（`DEFAULT now()`）のように
**DB側が自動で決める値**は、INSERT する前の Python コードからは中身が分からないので、
`RETURNING` で「今どんな値になったか」を1回のクエリで教えてもらうわけです。

タグが指定されていれば、別関数 `attach_tags` で関連付けます（後述）。`create_todo` は
最初から最後まで同じ `conn` を使っているので、
[psycopgのトランザクション](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
の単位としては1つにまとまっています。途中で `attach_tags` が失敗すれば、`INSERT` した
ToDo 本体も含めて丸ごとロールバックされ、中途半端な ToDo だけが残ることはありません。

## 11.2 完了/未完了を切り替える：`toggle_done`

```python
def toggle_done(conn: psycopg.Connection, todo_id: int) -> Todo | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE todos
               SET done = NOT done,
                   updated_at = now()
             WHERE id = %s
            """,
            (todo_id,),
        )
        if cur.rowcount == 0:
            return None
    return get_todo(conn, todo_id)
```

`SET done = NOT done` のように **DB 側の値を反転**させると、
読み取って書き戻す競合（取得と更新の間に別の人が変えるリスク）を避けられます。
もし Python 側で `get_todo` して `done` を反転し、`update_todo(..., done=not todo.done)`
と書き戻す実装にすると、その「取得」と「書き戻し」の間に別のリクエストが同じ行を
更新した場合、後から書き込んだ側が相手の変更を握りつぶしてしまいます
（read-modify-write 競合と呼ばれるバグの典型パターンです）。反転そのものを
`NOT done` として DB 側の1文で完結させれば、この競合は構造的に起こりません。

`cur.rowcount == 0` を見て `None` を返しているのにも意味があります。`UPDATE` は
`WHERE` に一致する行が無くてもエラーにはならず、「0行更新」という形で静かに
成功してしまいます。`rowcount` を確認しないと、存在しない `todo_id` を渡されたことに
呼び出し側が気づけません。

## 11.3 削除する：`delete_todo`

```python
def delete_todo(conn: psycopg.Connection, todo_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        return cur.rowcount > 0
```

`todo_tags` の関連は **第9章で `ON DELETE CASCADE` を入れたので自動で消えます**。
もしこれを付けていなければ、`delete_todo` の前に自分で
`DELETE FROM todo_tags WHERE todo_id = %s` を呼んで後片付けするか、外部キー制約に
阻まれて `todos` 側の `DELETE` 自体が失敗するか、どちらかの面倒に対処する必要が
あります。`ON DELETE CASCADE` は、この関連テーブルの後片付けを DB 側に任せてしまう
仕組みです。

## 11.4 部分更新：`update_todo`（重要）

ここがいちばん工夫が要るところです。
**「指定なし」と「明示的に NULL（期限を消したい）」を区別**したい。

これは REST API の **PATCH**（部分更新）を実装するときに必ずぶつかる問題です。
「クライアントがそのフィールドをリクエストに含めなかった」（＝今の値のままにしたい）のか、
「そのフィールドに `null` を明示的に指定した」（＝値を消したい）のかは、本来まったく
別の意味を持ちます。

普通に `due_on: date | None = None` にしてしまうと、`update_todo(t.id)` と
`update_todo(t.id, due_on=None)` の区別がつきません。デフォルト値としての `None` と、
「NULLにしたい」という意味の `None` が、同じ値になってしまうからです。

そこで、`None` とは別に「未指定」を表す専用の値、**sentinel（番人値）** を用意します。
`object()` は呼び出すたびに新しい一意なオブジェクトを作るので、他のどんな値とも
区別できます。同じ発想は Python 標準ライブラリにも登場します。たとえば
[`dataclasses`](https://docs.python.org/3/library/dataclasses.html) モジュールは
`MISSING` という sentinel を使って「`field()` にデフォルト値が指定されたかどうか」を
判定しています。

```python
from typing import Any

_UNSET: Any = object()


def update_todo(
    conn: psycopg.Connection,
    todo_id: int,
    *,
    title: str | None = None,
    due_on: date | None | Any = _UNSET,
    priority: int | None = None,
    done: bool | None = None,
    tag_names: list[str] | None = None,
) -> Todo | None:
    sets: list[str] = []
    params: list = []
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if due_on is not _UNSET:           # ← ここがポイント
        sets.append("due_on = %s")
        params.append(due_on)
    if priority is not None:
        sets.append("priority = %s")
        params.append(priority)
    if done is not None:
        sets.append("done = %s")
        params.append(done)

    if sets:
        sets.append("updated_at = now()")
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE todos SET {', '.join(sets)} WHERE id = %s",
                (*params, todo_id),
            )
            if cur.rowcount == 0:
                return None

    if tag_names is not None:
        replace_tags(conn, todo_id, tag_names)

    return get_todo(conn, todo_id)
```

比較に `==` ではなく `if due_on is not _UNSET:` と **`is`** を使っているのは大事な
ポイントです。sentinel は「値が等しいかどうか」ではなく「その特定のオブジェクトそのもの
であるかどうか」（オブジェクトの同一性・identity）を確かめたいので、`is` で比較するのが
定石です。`None` かどうかを判定するときに `== None` ではなく `is None` を使うのと
同じ理由ですね。また引数の型ヒントに
[`Any`](https://docs.python.org/3/library/typing.html) を含めているのは、
`_UNSET` が `date | None` のどちらでもない特別な値であることを型チェッカーにも
伝えるためです。

呼び方:

```python
# title だけ変える（他はそのまま）
repo.update_todo(conn, t.id, title="変更後")

# 期限を消したい（明示的に NULL）
repo.update_todo(conn, t.id, due_on=None)

# 期限を入れたい
repo.update_todo(conn, t.id, due_on=date(2026, 6, 1))
```

!!! tip "API 側ではどう使う？"
    第14章の FastAPI ルーターでは、Pydantic の `model_dump(exclude_unset=True)`
    を使って、**リクエストに含まれていたキーだけ**を repository に渡します。
    `_UNSET` を使うのはリポジトリ層、JSON で来たかどうかを見るのは API 層、と
    役割を分けるとすっきりします。

## 11.5 タグの多対多：`attach_tags` / `replace_tags`

ToDo とタグは **多対多**の関係です。1つの ToDo に複数のタグを付けられますし、
1つのタグは複数の ToDo で使い回されます。`todos` テーブルに `tags TEXT[]` のような
配列カラムを持たせて済ませたくもなりますが、それだと同じタグ名の表記ゆれ
（「健康」と「けんこう」など）を防げませんし、タグの名前を変更したくなったときに
全 ToDo の配列を1つずつ書き換える羽目になります。第9章で見たように、`todo_tags` という
**ジャンクションテーブル（中間テーブル）** を挟んで「タグ本体は `tags` に1件だけ持ち、
ToDo との対応関係だけを `todo_tags` に記録する」形にすれば、タグ名の管理は `tags` 側に
一元化できます。これがリレーショナル DB で多対多を表現する定石です。

タグは「無ければ作って、関連付ける」処理が要ります。

```python
def attach_tags(conn: psycopg.Connection, todo_id: int, names: list[str]) -> None:
    if not names:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(n,) for n in names],
        )
        cur.execute(
            "SELECT id, name FROM tags WHERE name = ANY(%s)",
            (names,),
        )
        tag_ids = [row["id"] for row in cur.fetchall()]
        cur.executemany(
            """
            INSERT INTO todo_tags (todo_id, tag_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            [(todo_id, tid) for tid in tag_ids],
        )


def replace_tags(conn: psycopg.Connection, todo_id: int, names: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todo_tags WHERE todo_id = %s", (todo_id,))
    attach_tags(conn, todo_id, names)
```

ポイント:

- **`ON CONFLICT DO NOTHING`** で「既にあれば無視」。
  `tags.name` の [UNIQUE制約](https://www.postgresql.org/docs/current/ddl-constraints.html)
  のおかげで、同じ名前を 2 回入れてもエラーにならない。この `INSERT ... ON CONFLICT` は
  一般に **upsert**（INSERTしつつ、重複時はUPDATEしたり無視したりする書き方）と
  呼ばれます。これが無いと「まず `SELECT` して存在確認 → 無ければ `INSERT`」という
  2段階の処理が必要になりますが、その確認と挿入の間に別のリクエストが先に同じ名前を
  INSERT してしまう競合（check-then-act の隙間を突かれるバグ）が起こり得ます。
  `ON CONFLICT DO NOTHING` なら1文で完結するので、この隙間そのものが生まれません。
- `todo_tags` への `INSERT ... ON CONFLICT DO NOTHING` は、`(todo_id, tag_id)` の
  複合主キーが実質的な UNIQUE 制約として働くので、同じ ToDo に同じタグを2回
  `attach_tags` しても重複した関連行ができません。
- 名前から `id` を引くために `WHERE name = ANY(%s)` を使っています。psycopg は
  Python の `list` を渡すと自動で PostgreSQL の配列型にアダプトしてくれるので、
  `IN (%s, %s, %s, ...)` のように可変長のプレースホルダを自分で組み立てなくて済みます
  （[psycopg3 パラメータの渡し方](https://www.psycopg.org/psycopg3/docs/basic/params.html)）。
- `replace_tags` は **「現在のタグを全消し → 新しいセットを付ける」** という素直な実装。
  量が少ないので差分計算をせずシンプルにしています。`DELETE` と `INSERT` の2文に
  分かれていますが、同じ `conn` 上で実行されるので1つのトランザクションの中に収まり、
  「`DELETE` だけ成功して `INSERT` が失敗した」という中途半端な状態が他のリクエストから
  見えることはありません。

## 11.6 動作確認

```python
# scripts/try_write.py
from datetime import date
from app.db import connection
from app import repositories as repo

with connection() as conn:
    t = repo.create_todo(
        conn, title="ジムに行く",
        due_on=date(2026, 5, 30),
        priority=1,
        tag_names=["健康", "週次"],
    )
    print("created:", t.id, [g.name for g in t.tags])

    repo.toggle_done(conn, t.id)
    print("toggled")

    repo.replace_tags(conn, t.id, ["健康"])
    print("tags replaced")

    print("delete:", repo.delete_todo(conn, t.id))
```

## やってみよう

1. `update_todo` を呼ぶときに、**`title` だけ更新したのに `priority` も上書きされていないか**を
   `psql` で確認する（updated_at だけが変わるはず）。
2. **同じ ToDo に同じタグを 2 回 attach** してみて、`todo_tags` に重複が入らないことを確認する。
3. **存在しない `id` で `update_todo` / `toggle_done` / `delete_todo`** を呼んだとき、
   それぞれが `None` / `False` を返すことを確認する。

次は [第 12 章 データアクセス層のテスト](12-data-tests.md) で、
**ここまで書いた関数に pytest でテストを書きます**。
