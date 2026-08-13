# 第11章 リポジトリ（Write系）とタグの多対多

第10章で、ToDo アプリの「読み取り系」が動くようになりました。
あの時点の `repositories.py` は、完成版と `diff` を取ると
「Write 系の関数と `_UNSET`、先頭の import 2 行のぶんだけ
完成版のほうが長い」状態で、それらの `+` 行はこの章で写経すると予告していました。
この章ではその予告を回収し、`mytodo/app/repositories.py` に
**書き込み系の関数を追記して完成版と完全一致**させます。

書き込み系とは、次の 6 つの関数です。

- 作成（INSERT）: `create_todo`
- 部分更新（UPDATE）: `update_todo`
- 完了/未完了の切替: `toggle_done`
- 削除（DELETE）: `delete_todo`
- タグの付け替え（多対多の扱い）: `attach_tags` / `replace_tags`

## 11.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- 多対多とは何か、JOIN テーブル（中間テーブル）でどう表すかを説明できる
- UPSERT（`INSERT ... ON CONFLICT`）が何をする構文かを説明できる
- `repositories.py` に Write 系 6 関数と `_UNSET`、import 2 行を追記できる
- `diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py` で
  **差分なし**を確認できる
- 使い捨てスクリプト `try_write.py` で作成・更新・削除・タグ付け替えを
  実際に動かせる

**所要時間の目安: 90 分**

この章で新しく作るファイルはありません。既存の `mytodo/app/repositories.py`
への**追記**が本体で、あとは動作確認用の使い捨てスクリプト
`mytodo/try_write.py` を 1 つ作るだけです。

引き続き、リポジトリの `sample/todo-app/` は**答え合わせ用の完成版**です。
読者の皆さんが作るのは `mytodo/` の中のファイルで、
写経が終わるたびに完成版と `diff` で答え合わせをします。

まず現在地を確認します。第10章末時点の `mytodo/` は次の構成です。

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
│   └── repositories.py     第10章で作成（Read系のみ）← この章で Write 系を追記
├── migrations/
│   ├── 001_init.sql        第9章で作成・tododb に適用済み
│   └── 002_seed.sql        第9章で作成・tododb に適用済み
├── try_read.py             第10章で作成（使い捨て。残っていても構いません）
└── try_write.py            この章で作成（動作確認用の使い捨て）
```

（第9章の「やってみよう」に取り組んだ人は、`migrations/` に
`003_add_memo.sql` もあるはずです。そのままで大丈夫です。）

この章が触るのは `repositories.py` への追記と `try_write.py` の作成だけで、
他のファイルには手を付けません。

## 11.2 前提知識

コードに入る前に、この章の鍵になる 2 つの考え方を押さえておきます。

!!! note "多対多と JOIN テーブル（中間テーブル）"
    ToDo とタグは **多対多** の関係です。1 つの ToDo に複数のタグを
    付けられますし、1 つのタグは複数の ToDo で使い回されます。
    リレーショナル DB では、この関係を **JOIN テーブル（中間テーブル）**
    と呼ばれる「対応関係だけを記録するテーブル」で表すのが定石です。
    第9章で作った `todo_tags` がそれです。

    シードデータ投入直後の 3 テーブルは、それぞれ次のようになっています。

    **todos**

    | id | title |
    |----|--------------|
    | 1 | 牛乳を買う |
    | 2 | 健康診断の予約 |
    | 3 | 過去の領収書を整理 |
    | 4 | 家賃を振り込む |

    **todo_tags**（中間テーブル）

    | todo_id | tag_id |
    |---------|--------|
    | 1 | 1 |
    | 2 | 3 |

    **tags**

    | id | name |
    |----|------|
    | 1 | 家事 |
    | 2 | 仕事 |
    | 3 | 健康 |

    `todo_tags` の行 `(1, 1)` は「`todos` の id=1（牛乳を買う）に
    `tags` の id=1（家事）が付いている」という意味です。
    `todos` 側にも `tags` 側にも相手の情報を持たせず、
    **対応関係だけを中間テーブルに集める**のがポイントです。

    この形にしておくと、タグ名の管理は `tags` テーブル 1 か所に
    一元化できます。もし `todos` テーブルに `tags TEXT[]` のような
    配列カラムで持たせると、同じタグの表記ゆれ（「健康」と「けんこう」など）を
    防げませんし、タグ名を変更したくなったときに全 ToDo の配列を
    1 つずつ書き換える羽目になります。

!!! note "UPSERT: `INSERT ... ON CONFLICT`"
    タグを付ける処理では「その名前のタグが無ければ作り、あればそのまま使う」
    という操作が必要です。素直に書くと「まず `SELECT` で存在確認 →
    無ければ `INSERT`」の 2 段階になりますが、この確認と挿入の間に
    別のリクエストが先に同じ名前を INSERT してしまう競合
    （check-then-act の隙間を突かれるバグ）が起こり得ます。

    PostgreSQL の **`INSERT ... ON CONFLICT DO NOTHING`** は、
    「挿入しようとして UNIQUE 制約にぶつかったら、エラーにせず無視する」
    という構文で、この処理を 1 文で完結させられます。
    このように「INSERT しつつ、重複時は UPDATE したり無視したりする」
    書き方は一般に **UPSERT**（UPDATE + INSERT）と呼ばれます
    （[PostgreSQL 公式ドキュメント: INSERT](https://www.postgresql.org/docs/current/sql-insert.html)）。
    1 文で完結するので、check-then-act の隙間そのものが生まれません。

## 11.3 追記の全体像

第10章末の `diff` で見た `+` 行（完成版にだけある行）は、
次の 4 か所に対応しています。この章では上から順に追記していきます。

```text
mytodo/app/repositories.py
├── 先頭の import        …… import 2 行を追加（11.4）
├── import の直後        …… _UNSET を追加（11.4）
├── # ---------- Todo ---------- の直後
│                        …… create_todo を追加（11.5）
├── get_todo の直後      …… update_todo / toggle_done / delete_todo を追加（11.6 / 11.7）
└── ファイルの末尾       …… attach_tags / replace_tags を追加（11.8）
```

Read 系の関数（`list_todos` / `get_todo` / `list_all_tags` /
`list_tags_for_todo`）と変換ヘルパー（`_row_to_tag` / `_row_to_todo`）は
**第10章で書いたものをそのまま使います**。この章では触りません。

!!! tip "追記するときの空行のルール"
    関数と関数の間は **空行 2 行** で区切るのが Python の流儀（PEP 8）です。
    追記位置や空行の数が多少ずれても動作には影響しませんが、
    11.9 の `diff` で差分として検出されるので、そこで整えてください。

## 11.4 import 2 行と `_UNSET`

まず土台からです。`mytodo/app/repositories.py` の**先頭**に
`from datetime import date` と `from typing import Any` の 2 行を追記します。
追記後、ファイルの先頭は次のようになります。

```python
from datetime import date
from typing import Any

import psycopg

from .models import Tag, Todo
```

- `date` …… `create_todo` / `update_todo` の引数 `due_on` の型ヒントで使います。
- `Any` …… 次に追加する `_UNSET` の型ヒントで使います。

続けて、`mytodo/app/repositories.py` の import の直後
（`_row_to_tag` の前）に次の内容を追記してください。

```python
# Sentinel: "due_on を渡さない" と "明示的に NULL" を区別するため
_UNSET: Any = object()
```

`_UNSET` は 11.6 の `update_todo` で使う **sentinel（番人値）** です。
`object()` は呼び出すたびに新しい一意なオブジェクトを作るので、
他のどんな値とも区別できます。何のための値なのかは 11.6 で詳しく見ます。

## 11.5 ToDo を作る: `create_todo`

`mytodo/app/repositories.py` の `# ---------- Todo ----------` の直後
（`list_todos` の前）に次の内容を追記してください。

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

ポイントは 2 つです。

- **`RETURNING`** は PostgreSQL の拡張構文で、
  `INSERT` / `UPDATE` / `DELETE` した行の値をその場で受け取れます
  （[DML: データ操作言語](https://www.postgresql.org/docs/current/dml.html)）。
  `id`（`SERIAL` で自動採番）や `created_at` / `updated_at`
  （`DEFAULT now()`）のように **DB 側が自動で決める値** は、
  INSERT する前の Python コードからは中身がわかりません。
  `RETURNING` で「今どんな値になったか」を 1 回のクエリで教えてもらうので、
  INSERT のあとにもう一度 SELECT で取り直す、という 2 回目の往復が不要です。
- タグが指定されていれば、11.8 で追加する `attach_tags` で関連付けます。
  `create_todo` は最初から最後まで同じ `conn` を使っているので、
  全体が 1 つのトランザクションにまとまっています。
  途中で `attach_tags` が失敗すれば、INSERT した ToDo 本体も含めて
  丸ごとロールバックされ、中途半端な ToDo だけが残ることはありません。

## 11.6 部分更新: `update_todo`（この章の山場）

`mytodo/app/repositories.py` の `get_todo` の直後に次の内容を追記してください。

```python
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
    if due_on is not _UNSET:
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

ここがいちばん工夫の要るところです。部分更新では
**「指定なし」と「明示的に NULL（期限を消したい）」を区別** したいのです。

これは REST API の **PATCH**（部分更新）を実装するときに必ずぶつかる問題です。
「クライアントがそのフィールドをリクエストに含めなかった」
（＝今の値のままにしたい）のか、「そのフィールドに `null` を明示的に
指定した」（＝値を消したい）のかは、本来まったく別の意味を持ちます。

普通に `due_on: date | None = None` にしてしまうと、
`update_todo(t.id)` と `update_todo(t.id, due_on=None)` の区別がつきません。
デフォルト値としての `None` と「NULL にしたい」という意味の `None` が、
同じ値になってしまうからです。

そこで 11.4 で追加した sentinel `_UNSET` の出番です。
`due_on` のデフォルト値を `None` ではなく `_UNSET` にしておけば、
「`due_on is _UNSET` なら未指定（更新しない）」
「`due_on is None` なら明示的に NULL にする」と判定できます。
同じ発想は Python 標準ライブラリにも登場します。たとえば
[`dataclasses`](https://docs.python.org/3/library/dataclasses.html) モジュールは
`MISSING` という sentinel を使って「`field()` にデフォルト値が指定されたか
どうか」を判定しています。

あわせて、読み方のポイントが 3 つあります。

- 比較に `==` ではなく `if due_on is not _UNSET:` と **`is`** を
  使っているのは大事なポイントです。sentinel は「値が等しいかどうか」ではなく
  「その特定のオブジェクトそのものであるかどうか」（オブジェクトの同一性）を
  確かめたいので、`is` で比較するのが定石です。
  `None` かどうかを判定するときに `== None` ではなく `is None` を使うのと
  同じ理由です。
- 型ヒントが `date | None | Any` となっているのは、`_UNSET` が
  `date | None` のどちらでもない特別な値であることを、
  **人間の読み手に明示する**のが主目的です。
  （厳密には、union に `Any` が混ざると型チェッカー上は `Any` と
  同じ扱いに潰れてしまうので、型チェッカーへの情報としては
  効いていません。ドキュメントとしての注記と考えてください。）
- `sets` と `params` は、第10章の `list_todos` の WHERE 句と同じく
  **ペアで、同じ順番に追加**します。どのカラムが指定されたかで
  SET 句の中身が変わるので、`UPDATE` 文は f-string で動的に組み立てています。
  組み立てるのはあくまで「カラム名と `%s` の並び」だけで、
  **値はすべてプレースホルダ経由** なので、第6章の SQL インジェクションの
  注意には抵触しません。

呼び方は次の 3 通りです。

```python
# title だけ変える（他はそのまま）
repo.update_todo(conn, t.id, title="変更後")

# 期限を消したい（明示的に NULL）
repo.update_todo(conn, t.id, due_on=None)

# 期限を入れたい
repo.update_todo(conn, t.id, due_on=date(2030, 1, 1))
```

!!! tip "API 側ではどう使う？"
    第14章の FastAPI ルーターでは、Pydantic の
    `model_dump(exclude_unset=True)` を使って、
    **リクエストに含まれていたキーだけ** を repository に渡します。
    `_UNSET` を使うのはリポジトリ層、JSON で来たかどうかを見るのは
    API 層、と役割を分けるとすっきりします。

## 11.7 完了の切替と削除: `toggle_done` / `delete_todo`

`mytodo/app/repositories.py` の `update_todo` の直後に次の内容を追記してください。

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


def delete_todo(conn: psycopg.Connection, todo_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        return cur.rowcount > 0
```

`toggle_done` のポイント:

- `SET done = NOT done` のように **DB 側の値を反転** させると、
  読み取って書き戻す競合を避けられます。もし Python 側で `get_todo` して
  `done` を反転し、`update_todo(..., done=not todo.done)` と書き戻す実装に
  すると、その「取得」と「書き戻し」の間に別のリクエストが同じ行を更新した
  場合、後から書き込んだ側が相手の変更を握りつぶしてしまいます
  （read-modify-write 競合と呼ばれるバグの典型パターンです）。
  反転そのものを `NOT done` として DB 側の 1 文で完結させれば、
  この競合は構造的に起こりません。
- `cur.rowcount == 0` を見て `None` を返しているのにも意味があります。
  `UPDATE` は `WHERE` に一致する行が無くてもエラーにはならず、
  「0 行更新」という形で静かに成功してしまいます。`rowcount` を確認しないと、
  存在しない `todo_id` を渡されたことに呼び出し側が気づけません。

`delete_todo` のポイント:

- `todo_tags` の関連は、第9章で外部キーに **`ON DELETE CASCADE`** を
  入れたので、ToDo を消すと自動で消えます。もしこれを付けていなければ、
  `delete_todo` の前に自分で `DELETE FROM todo_tags WHERE todo_id = %s`
  を呼んで後片付けするか、外部キー制約に阻まれて `todos` 側の `DELETE`
  自体が失敗するか、どちらかの面倒に対処する必要があります。
- 削除できたかどうかを `rowcount > 0` の真偽値で返します。
  `DELETE` も `UPDATE` と同じく、一致する行が無くてもエラーになりません。

## 11.8 タグの多対多: `attach_tags` / `replace_tags`

最後に、11.2 で見た多対多を書き込む側から実装します。
`mytodo/app/repositories.py` の末尾（`list_tags_for_todo` の後）に
次の内容を追記してください。

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

`attach_tags` は「タグが無ければ作って、関連付ける」を 3 段階で行います。

1. **`tags` への UPSERT**: `INSERT ... ON CONFLICT (name) DO NOTHING` で、
   無ければ作り、あれば無視します。`tags.name` の
   [UNIQUE 制約](https://www.postgresql.org/docs/current/ddl-constraints.html)
   のおかげで、同じ名前を 2 回入れてもエラーになりません。
   11.2 で見た UPSERT の実例です。
2. **名前から id を引く**: `WHERE name = ANY(%s)` に Python のリストを
   そのまま渡しています。psycopg がリストを PostgreSQL の配列型に
   アダプトしてくれるので、`IN (%s, %s, %s, ...)` のように可変長の
   プレースホルダを自分で組み立てなくて済みます
   （[psycopg3 パラメータの渡し方](https://www.psycopg.org/psycopg3/docs/basic/params.html)）。
3. **`todo_tags` への UPSERT**: `(todo_id, tag_id)` の複合主キーが
   実質的な UNIQUE 制約として働くので、`ON CONFLICT DO NOTHING` により、
   同じ ToDo に同じタグを 2 回 `attach_tags` しても重複した関連行が
   できません。

`replace_tags` は **「現在のタグを全消し → 新しいセットを付ける」** という
素直な実装です。量が少ないので差分計算をせずシンプルにしています。
`DELETE` と `INSERT` の 2 文に分かれていますが、同じ `conn` 上で実行される
ので 1 つのトランザクションの中に収まり、「`DELETE` だけ成功して
`INSERT` が失敗した」という中途半端な状態が他のリクエストから見えることは
ありません。

## 11.9 答え合わせ: `diff` が空になることを確認

追記が全部終わったら、完成版と答え合わせします
（`diff` コマンドは **リポジトリのルート** で実行してください）。

```bash
diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py
```

**何も表示されなければ完成版と一致しています。差分なしがこの章のゴールです。**

第10章末では「`+` 行（Write 系の関数と `_UNSET`、import 2 行）は
第11章で写経する」と予告していました。その `+` 行をすべて写経し終えたので、
ここで差分が消える、という流れです。

差分が残っている場合の見方は第10章と同じです。

- **`-`（マイナス）で始まる行がある** …… あなたのファイルにだけある行。
  第10章の写経部分をうっかり書き換えてしまったか、追記位置がずれています。
- **`+`（プラス）で始まる行がある** …… 完成版にだけある行。
  追記し忘れている関数や import があるか、空行の数がずれています。

## 11.10 動作確認: `try_write.py`

写経した Write 系の関数を、実際に動かしてみます。
`mytodo/try_write.py` を作成して、次の内容を書き写してください
（これは完成版にはない、**動作確認用の使い捨てスクリプト** です。
第10章の `try_read.py` と同じ位置づけです）。

```python
from datetime import date

from app import repositories as repo
from app.db import connection

with connection() as conn:
    t = repo.create_todo(
        conn,
        title="ジムに行く",
        due_on=date(2030, 1, 1),
        priority=1,
        tag_names=["健康", "週次"],
    )
    print("created:", t.id, t.title, t.done, t.due_on, t.priority)
    print("tags:", [g.name for g in t.tags])

    t = repo.toggle_done(conn, t.id)
    print("toggled:", t.done)

    t = repo.update_todo(conn, t.id, title="ジムで筋トレ")
    print("updated:", t.title, "| due_on:", t.due_on, "| priority:", t.priority)

    t = repo.update_todo(conn, t.id, due_on=None)
    print("due_on cleared:", t.due_on)

    repo.replace_tags(conn, t.id, ["健康"])
    t = repo.get_todo(conn, t.id)
    print("tags replaced:", [g.name for g in t.tags])

    print("update 999:", repo.update_todo(conn, 999, title="存在しない"))
    print("toggle 999:", repo.toggle_done(conn, 999))

    print("delete:", repo.delete_todo(conn, t.id))
    print("delete 999:", repo.delete_todo(conn, 999))
```

`mytodo/` の中で実行します。

```bash
uv run python try_write.py
```

期待される出力:

```text
created: 5 ジムに行く False 2030-01-01 1
tags: ['健康', '週次']
toggled: True
updated: ジムで筋トレ | due_on: 2030-01-01 | priority: 1
due_on cleared: None
tags replaced: ['健康']
update 999: None
toggle 999: None
delete: True
delete 999: False
```

出力の読み方:

- `created:` の行で、作った ToDo の中身（`RETURNING` で受け取った値）が
  そのまま返ってきています。`id` は `SERIAL` の自動採番なので、
  第9〜10章でデータを入れ直したり、このスクリプトを再実行したりすると
  **5 以外の数字になります**。数字が違っていても、それ以外が合っていれば
  問題ありません。
- `tags:` は `['健康', '週次']`。`週次` は `tags` テーブルに無かった名前
  ですが、`attach_tags` の UPSERT で自動的に作られています。
- `updated:` の行では、`title` だけを指定して更新したのに
  `due_on` と `priority` が変わっていません。`_UNSET` と `None` の
  デフォルトによる「指定されなかったカラムは更新しない」が効いています。
- 直後の `due_on cleared: None` と対比すると、「何も指定しない」
  （＝そのまま）と「`due_on=None` を指定する」（＝NULL に更新）の
  違いがはっきりわかります。
- 存在しない `id`（999）に対して、`update_todo` / `toggle_done` は
  `None`、`delete_todo` は `False` を返しました。`rowcount` の
  チェックが効いている証拠です。
- スクリプトの最後で作った ToDo を `delete_todo` で消しているので、
  `todos` と `todo_tags` は実行前の状態に戻ります。

### 後片付け

`try_write.py` は使い捨てなので、確認が終わったら削除します。

```bash
rm try_write.py
```

もう 1 か所だけ後片付けが必要です。`attach_tags` が自動で作った
タグ **`週次`** が `tags` テーブルに残っています
（タグ本体は、ToDo を消しても残る設計です。`ON DELETE CASCADE` が
消すのは中間テーブル `todo_tags` の行だけです）。
psql で次を実行して消しておきましょう（接続の手順は第3章と同じです）。

```sql
DELETE FROM tags WHERE name = '週次';
```

期待される出力:

```text
DELETE 1
```

これで DB はシードデータだけの状態に戻りました。

## 11.11 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] 多対多とは何か、なぜ JOIN テーブル（中間テーブル）で表すのかを説明できる
- [ ] `INSERT ... ON CONFLICT DO NOTHING`（UPSERT）が何をする構文か、
      「SELECT で確認してから INSERT」と比べた利点とともに説明できる
- [ ] `RETURNING` を使うと何がうれしいかを説明できる
- [ ] `update_todo` で `_UNSET`（sentinel）を使う理由、
      「未指定」と「明示的に NULL」の区別とともに説明できる
- [ ] sentinel の比較に `==` ではなく `is` を使う理由を説明できる
- [ ] `toggle_done` で `SET done = NOT done` と 1 文で反転する理由
      （read-modify-write 競合）を説明できる
- [ ] `repositories.py` に Write 系 6 関数と `_UNSET`、import 2 行を追記し、
      `diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py` が
      差分なしになった
- [ ] `try_write.py` で作成・更新・タグ付け替え・削除を動かし、
      後片付け（スクリプトの削除と `週次` タグの削除）まで済ませた

## 11.12 つまずきポイント

### `NameError: name 'date' is not defined` / `name 'Any' is not defined`

11.4 の import 2 行（`from datetime import date` /
`from typing import Any`）の追加を忘れています。
これらは `create_todo` / `update_todo` の型ヒントと `_UNSET` の定義で
使うので、無いと `repositories.py` を import した時点でエラーになります。

### `psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "tags_name_key"`

`attach_tags` の `ON CONFLICT (name) DO NOTHING` を写し忘れています。
シードデータに既にある名前（`健康` など）を INSERT しようとして、
UNIQUE 制約にぶつかっています。11.8 のコードと見比べてください。

### `diff` で差分が消えない

追記位置や空行の数がずれているのが典型的な原因です。
11.3 の全体像と照らし、どの関数の前後に追記すべきかを確認してください。
`+` の行が空行だけ、という差分なら、空行を 1 行足すか消すかで一致します。
関数の中身そのものに差分がある場合は、第10章の写経部分を
書き換えてしまっている可能性もあるので、`-` の行が無いかを先に確認してください。

### `try_write.py` の `created:` の id が 5 ではない

`id` は `SERIAL` の自動採番なので、これまでに INSERT した回数ぶんだけ
進みます。再実行のたびに 6、7…… と増えていくのが正常な動作です。
期待出力と id 以外が合っていれば問題ありません。

## 11.13 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 同じタグを 2 回 attach しても重複しないことを確かめる

ある ToDo に対して `attach_tags(conn, t.id, ["健康"])` を **2 回連続で**
呼び、`todo_tags` に重複した行ができないことを `psql` で確認してください。

??? example "解答例"

    使い捨てスクリプト（たとえば `mytodo/try_attach.py`）で試します。

    ```python
    from app import repositories as repo
    from app.db import connection

    with connection() as conn:
        t = repo.create_todo(conn, title="重複テスト", tag_names=["健康"])
        repo.attach_tags(conn, t.id, ["健康"])
        repo.attach_tags(conn, t.id, ["健康"])
        print("todo_id:", t.id)
    ```

    期待される出力（`todo_id` は実行のたびに変わります）:

    ```text
    todo_id: 5
    ```

    psql で確認します（`5` の部分は表示された `todo_id` に合わせてください）。

    ```sql
    SELECT COUNT(*) FROM todo_tags WHERE todo_id = 5;
    ```

    期待される出力:

    ```text
     count 
    -------
         1
    (1 row)
    ```

    `ON CONFLICT DO NOTHING` のおかげで、何回 attach しても
    `(todo_id, tag_id)` の組は 1 行のままです。
    確認が終わったら、スクリプトとテスト用の ToDo を片付けておきましょう。
    確実に片付けるには psql で
    `DELETE FROM todos WHERE title = '重複テスト';` を実行します
    （スクリプトに `repo.delete_todo(conn, t.id)` を足して再実行しても、
    初回の実行で残った行は消えない点に注意してください）。

### 問2 `title` だけ更新して他のカラムが変わらないことを確かめる

既存の ToDo（たとえば `id=1`）に対して
`repo.update_todo(conn, 1, title="牛乳を2本買う")` を呼び、
`priority` や `due_on` が変わっておらず、`updated_at` だけが
更新されていることを確認してください。

??? example "解答例"

    使い捨てスクリプト（たとえば `mytodo/try_partial.py`）で、
    **更新の前後を別の接続で** 取得して比較します。

    ```python
    from app import repositories as repo
    from app.db import connection

    with connection() as conn:
        before = repo.get_todo(conn, 1)

    with connection() as conn:
        repo.update_todo(conn, 1, title="牛乳を2本買う")

    with connection() as conn:
        after = repo.get_todo(conn, 1)

    print("title:", before.title, "->", after.title)
    print("priority 不変:", before.priority == after.priority)
    print("due_on 不変:", before.due_on == after.due_on)
    print("updated_at 更新:", after.updated_at > before.updated_at)
    ```

    期待される出力:

    ```text
    title: 牛乳を買う -> 牛乳を2本買う
    priority 不変: True
    due_on 不変: True
    updated_at 更新: True
    ```

    `with connection()` を 3 つに分けているのには理由があります。
    更新の前後で **コミットを挟み、別トランザクションとして確定した値**を
    読むほうが、検証として確実だからです。

    !!! note "`now()` はトランザクション開始時刻で固定される"
        PostgreSQL の `now()` は、呼ばれた時刻ではなく
        **そのトランザクションが始まった時刻**を返します。
        そのため、同じトランザクション（同じ `with` ブロック）の中で
        何度 `now()` を呼んでも同じ値になり、「本来ずれるはずの時刻」
        同士を同一トランザクション内で比較すると、同じ値に見えることが
        あります。この性質は、第12章でテストデータの時刻を扱うときにも
        関係してきます。

    なお、今回の before / after の比較自体は、同一トランザクションで
    行っても（before はシード投入時の過去の時刻なので）結果は変わりません。
    それでも接続を分ける書き方を採用しているのは、「更新された行を
    コミット後に読み直す」という検証の形を毎回同じにしておくほうが
    癖として安全だからです。

    確認が終わったら、`repo.update_todo(conn, 1, title="牛乳を買う")` で
    タイトルを元に戻し、スクリプトを削除しておきましょう。

### 問3 `replace_tags` に空リストを渡すとどうなるか確かめる

タグの付いた ToDo（たとえば `id=1`）に対して
`repo.replace_tags(conn, 1, [])` を呼ぶと何が起こるか、
結果を `get_todo` で確認してください。`attach_tags` の先頭の
`if not names: return` とあわせて考えると、挙動を予想できるはずです。

??? example "解答例"

    使い捨てスクリプト（たとえば `mytodo/try_replace.py`）で試します。

    ```python
    from app import repositories as repo
    from app.db import connection

    with connection() as conn:
        print("before:", [g.name for g in repo.get_todo(conn, 1).tags])
        repo.replace_tags(conn, 1, [])
        print("after:", [g.name for g in repo.get_todo(conn, 1).tags])
    ```

    期待される出力:

    ```text
    before: ['家事']
    after: []
    ```

    `replace_tags` はまず `todo_tags` からその ToDo の行を全削除し、
    続けて `attach_tags` を呼びますが、空リストなら
    `if not names: return` で何もしません。結果として
    **タグの全解除** になります。「空リストを渡すと既存のタグが消える」
    ことを知らないと驚く挙動なので、仕様として意識しておきましょう。

    確認が終わったら、`repo.replace_tags(conn, 1, ["家事"])` で
    元に戻し、スクリプトを削除しておきましょう。

## まとめ

- Write 系のリポジトリ関数は、INSERT / UPDATE / DELETE を
  `repositories.py` に集める、というレイヤー分けのルールに従って追加した
- `RETURNING` を使うと、DB 側が自動で決める値（`id` や `created_at`）を
  INSERT と同じ 1 回のクエリで受け取れる
- 部分更新では「未指定」と「明示的に NULL」を区別するため、
  `_UNSET` という sentinel をデフォルト値に使い、`is` で比較する
- `UPDATE` / `DELETE` は一致行が 0 でもエラーにならないので、
  `rowcount` を見て `None` / `False` を返す
- 多対多の書き込みは「タグ本体への UPSERT → id 取得 →
  中間テーブルへの UPSERT」の 3 段階。`ON CONFLICT DO NOTHING` で
  重複を構造的に防ぐ
- この章末で `diff -u mytodo/app/repositories.py sample/todo-app/app/repositories.py` が
  差分なしになり、`repositories.py` は完成版と一致した

次は [第12章 データアクセス層のテスト](12-data-tests.md) で、
**ここまで書いた関数に pytest でテストを書きます**。
