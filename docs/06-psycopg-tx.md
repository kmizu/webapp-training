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
文字列連結で SQL を組み立てると、ユーザーが入力した文字列がそのまま **SQL の構文の一部**として
解釈されてしまいます。たとえば `name = "x'; DROP TABLE users; --"` を渡されたら、閉じクォート `'`
でいったん文字列リテラルを終わらせ、`;` で新しい文を始め、`--` で残りをコメントアウトする、という
組み立てになってしまい、意図しない `DROP TABLE` が実行されてテーブルが消えます。
攻撃者からすると、「値」のつもりで受け取ったところに「命令」を差し込めてしまう、というのがこの
攻撃の本質です。

プレースホルダの `%s` は **psycopg 専用**の書き方で、
Python の文字列フォーマット（`%`）と **似ているけど別物**です。
`cur.execute(sql, params)` のように SQL 文とパラメータを別々に渡すと、psycopg は
文字列を組み立ててから送るのではなく、**SQL 本体とパラメータを分離したまま** PostgreSQL
サーバーに送信します（[psycopgのパラメータの渡し方](https://www.psycopg.org/psycopg3/docs/basic/params.html)）。
サーバー側は「これは値であって SQL の構文ではない」と分かった状態で受け取るので、値の中に
`'` や `;` が混じっていても構文の一部として解釈されることがありません。これが f-string での
文字列連結と決定的に違うところで、psycopg が値の型を見て **安全なエスケープ**をしてくれる、
という説明の実体でもあります。

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

複数の値を `IN (1, 2, 3)` のように文字列で組み立てたくなるところですが、それをやると結局
SQL インジェクションの入り口を作ってしまいます。**`ANY(%s)` ならリストや配列を丸ごと 1 つの
パラメータとして安全に渡せる**ので、値の個数が変わっても SQL 文字列自体を組み立て直す必要が
ありません。

!!! warning "識別子（テーブル名・カラム名）はプレースホルダで渡せない"
    `cur.execute("SELECT * FROM %s", (table_name,))` はエラーになります。
    識別子を動的に組み立てる必要があるときは、`psycopg.sql` モジュールの
    `Identifier` を使ってください（研修では使いません）。

## 6.2 トランザクション：psycopg v3 の流儀

**トランザクション**とは、複数の SQL 文を「全部成功させるか、全部なかったことにするか」の
どちらかにまとめる単位です（[PostgreSQLのトランザクション入門](https://www.postgresql.org/docs/current/tutorial-transactions.html)）。
psycopg v3 は接続を開いた時点で **`autocommit=False` がデフォルト**になっていて、明示的に
`commit()` を呼ぶまでは実行した SQL は「トランザクションの中に入ったまま」で確定しません。
これは「1 文実行するたびに勝手に確定してしまう」事故を防ぐための、安全側に倒したデフォルト
です。

psycopg v3 では、**`with psycopg.connect(...)` を使うとトランザクションが自動管理されます**
（詳しくは [psycopgのトランザクション](https://www.psycopg.org/psycopg3/docs/basic/transactions.html) を参照）。

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

`with` ブロックを最後まで例外なく実行できた場合は、`autocommit=False` のままでも psycopg が
自動的に `conn.commit()` を呼んでくれます。逆に言うと、`with` を使わずに `psycopg.connect()`
だけを呼んでいる場合は、明示的に `commit()` するまでずっと未確定のトランザクションが残り
続けることになります。

途中で例外が起きるとどうなるか:

```python
def buggy() -> None:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", ("成功する",))
        cur.execute("INSERT INTO todos (title) VALUES (%s)", (None,))  # ← NOT NULL 違反
```

`title` は `NOT NULL` なので 2 つめの INSERT で例外が出ます。
そして **最初の INSERT も巻き戻される（保存されない）**。
これは「複数の操作をひとまとまりの単位として扱う」というトランザクションの原則（**原子性**、
英語では atomicity）そのものです。1 つでも失敗したら、途中まで成功していた分も含めて
なかったことにする、という考え方です。これが psycopg v3 の自動トランザクションの動きです。

## 6.3 明示的に commit / rollback する

`with` を使わない場合や、複数の操作を 1 トランザクションにまとめたい場合は、
`conn.commit()` / `conn.rollback()` を明示的に呼びます。たとえば「複数の関数にまたがって
同じコネクションを使い回し、最後にまとめて確定したい」といったケースでは、
`with psycopg.connect(...)` の自動コミットに任せず、自分でタイミングをコントロールしたく
なります。

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

この形の役割分担はシンプルです。**`try` の中が最後まで正常に終わったら `commit()`**、
**`except` で捕まえたら `rollback()`** して未確定の変更を消してから `raise` で呼び出し元に
伝える、**`finally` では成功・失敗にかかわらず必ず `close()`** してコネクションを解放する、
という 3 段構えです。`close()` を `finally` に置くのは、`commit()` や `rollback()` 自体が
失敗した場合でもコネクションを確実に片付けるためです。

ただし、これは `with` で書けばほぼ同じことなので、**普通は `with` を使う**のが楽で安全です。

## 6.4 autocommit モード（軽く触れる）

`psycopg.connect(DSN, autocommit=True)` にすると、`with` ブロックの終了を待たず、
**SQL を 1 文実行するたびにその場で COMMIT** されるようになります。裏を返すと、複数の文を
まとめて 1 つのトランザクションとして扱う（＝どれかが失敗したら全部なかったことにする）
ことはできなくなる、というトレードオフです。

典型的には、**マイグレーションのようにトランザクションを跨いだ DDL を流したいとき**などに
使います。たとえば PostgreSQL の `CREATE INDEX CONCURRENTLY` や `VACUUM` は、そもそも
トランザクションブロックの中では実行できないという制約があり、こうしたコマンドを流すには
`autocommit=True` が必須になります。
研修ではほとんど出てきません。

## 6.5 例外を Python 側で拾う

整合性違反などは psycopg.errors として届きます。
psycopg は PostgreSQL がエラーごとに持っている SQLSTATE というコードをもとに、
`psycopg.errors` 以下に細かく分類された例外クラスを用意しています。これらは全部
**`psycopg.Error`**（さらにたどると組み込みの `Exception`）を継承しているので、
「制約違反だけ個別に処理したい」なら `UniqueViolation` のように具体的なクラスで、
「DB まわりで何か失敗したらまとめて捕まえたい」なら `except psycopg.Error:` のように
広く、用途に応じて捕まえる粒度を選べます（Python の例外処理そのものについては
[Pythonチュートリアルの例外処理](https://docs.python.org/3/tutorial/errors.html) も参照
してください）。
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
    `current transaction is aborted` になります。これは PostgreSQL が「エラーの起きた
    トランザクションの中身はもう信用できない」とみなし、`ROLLBACK` されるまで新しい SQL の
    実行を受け付けない、という安全策です。中途半端な状態のまま次の SQL を実行させない、
    と考えると理にかなっています。
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
