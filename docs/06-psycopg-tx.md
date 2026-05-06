# 第6章 プレースホルダとトランザクション

前章で「動く」ようになりました。
この章では「**安全に動かす**」ための 2 本柱を扱います。

- プレースホルダで SQL インジェクションを防ぐ
- トランザクションで整合性を保つ

## 6.1 プレースホルダ：絶対のルール

SQL の値を埋め込むときは、**プレースホルダ `%s`** を使います。

```python
# OK ✅
cur.execute("SELECT * FROM users WHERE name = %s", (name,))

# NG ❌（やってはいけない）
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
```

なぜ NG かというと、**SQL インジェクション**という攻撃が成立するからです。
たとえば `name = "x'; DROP TABLE users; --"` を渡されたら、テーブルが消えます。

プレースホルダの `%s` は **psycopg 専用**の書き方で、
Python の文字列フォーマット（`%`）と **似ているけど別物**です。
psycopg が値の型を見て、**安全なエスケープ**をしてくれます。

複数の値を渡す:

```python
cur.execute(
    "SELECT * FROM todos WHERE priority = %s AND done = %s",
    (1, False),
)
```

`IN (...)` で複数値を渡したいときは、PostgreSQL の `ANY` を使うとシンプルです。

```python
ids = [1, 2, 3]
cur.execute("SELECT * FROM todos WHERE id = ANY(%s)", (ids,))
```

!!! warning "識別子（テーブル名・カラム名）はプレースホルダで渡せない"
    `cur.execute("SELECT * FROM %s", (table_name,))` はエラーになります。
    識別子を動的に組み立てる必要があるときは、`psycopg.sql` モジュールの
    `Identifier` を使ってください（研修では使いません）。

## 6.2 トランザクション：psycopg v3 の流儀

psycopg v3 では、**`with psycopg.connect(...)` を使うとトランザクションが自動管理されます**。

```python
def add_todo(title: str) -> int:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (title) VALUES (%s) RETURNING id",
            (title,),
        )
        return cur.fetchone()[0]
    # ↑ ここを抜けるとき、例外がなければ COMMIT
```

途中で例外が起きるとどうなるか:

```python
def buggy() -> None:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", ("成功する",))
        cur.execute("INSERT INTO todos (title) VALUES (%s)", (None,))  # ← NOT NULL 違反
```

`title` は `NOT NULL` なので 2 つめの INSERT で例外が出ます。
そして **最初の INSERT も巻き戻される（保存されない）**。
これが psycopg v3 の自動トランザクションの動きです。

## 6.3 明示的に commit / rollback する

`with` を使わない場合や、複数の操作を 1 トランザクションにまとめたい場合は、
`conn.commit()` / `conn.rollback()` を明示的に呼びます。

```python
conn = psycopg.connect(DSN)
try:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ...")
        cur.execute("UPDATE ...")
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

ただし、これは `with` で書けばほぼ同じことなので、**普通は `with` を使う**のが楽で安全です。

## 6.4 autocommit モード（軽く触れる）

`psycopg.connect(DSN, autocommit=True)` にすると、毎クエリごとに COMMIT されます。
**マイグレーションのようにトランザクションを跨いだ DDL を流したいとき**などに使います。
研修ではほとんど出てきません。

## 6.5 例外を Python 側で拾う

整合性違反などは psycopg.errors として届きます。
よく使うものだけ覚えておけば十分です。

| 例外 | 起きる状況 |
|---|---|
| `psycopg.errors.UniqueViolation` | UNIQUE 制約違反（同じ name のタグを再投入など） |
| `psycopg.errors.NotNullViolation` | NOT NULL のカラムに NULL を入れた |
| `psycopg.errors.CheckViolation` | CHECK 制約違反（priority=5 など） |
| `psycopg.errors.ForeignKeyViolation` | 親レコードがない |

```python
import psycopg
import psycopg.errors as pgerr

try:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO tags (name) VALUES (%s)", ("家事",))
        cur.execute("INSERT INTO tags (name) VALUES (%s)", ("家事",))  # 重複
except pgerr.UniqueViolation as e:
    print("そのタグはもうあるよ:", e)
```

!!! note "`current transaction is aborted` が出たら"
    1 つのトランザクションの中で SQL がエラーになると、その後の SQL は全部
    `current transaction is aborted` になります。
    `with` ブロックを抜ける、`conn.rollback()` を呼ぶ、のどちらかで復帰してください。

## やってみよう

1. **わざと例外を投げる**コードを書いて、ロールバックの挙動を `psql` で確認する。
   例: `INSERT` を 2 回呼んで、2 つめが NOT NULL 違反になるようにする。
   1 つめも入っていないことを `SELECT COUNT(*)` で確認。
2. UNIQUE 制約のあるテーブル（タグなど）に **同じ値を 2 回 INSERT** して、
   `UniqueViolation` を Python 側で拾ってみる。
3. f-string で SQL を組み立てる **危ないコードを試して**、
   `'; DROP TABLE ... --` のような入力でどうなるか自分で観察する
   （**自分の DB で試すこと**！）。

次は [第 7 章 dict_rowとコネクションプール](07-psycopg-pool.md) で、
**実用的な使い勝手**を整えます。
