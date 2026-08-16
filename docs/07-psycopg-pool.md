# 第7章 dict_rowとコネクションプール

第6章までで、Python から PostgreSQL を「動かす」「安全に動かす」ことは
できるようになりました。この章では「**実用的に使える**」状態に近づけます。

- 行を辞書で受け取る `dict_row`
- 接続を使い回す `ConnectionPool`
- 第10章以降の写経で登場する `app/db.py` の原型

## 7.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- 接続確立にコストがかかる理由と、プールで使い回す意味を説明できる
- `row_factory=dict_row` を指定して、行を辞書として受け取れる
- `ConnectionPool` から `with pool.connection()` で接続を借りて返せる
- モジュールレベルのプール、`get_pool()`、`connection()` という
  `app/db.py` の構造を説明できる

**所要時間の目安: 60 分**

この章でも、書くコードはすべてリポジトリルート直下の `practice/` ディレクトリに
置き、実行はリポジトリのルートで `uv run` で行います。
これまでと違うのは、`psycopg-pool` という**別パッケージも必要になる**点です。
実行コマンドは次の形になります（`--with` を 2 つ並べます）。

```bash
uv run --with 'psycopg[binary]' --with psycopg-pool python practice/xxx.py
```

`todos` テーブルに 7 行入っている前提で進めます。

## 7.2 前提知識

この章の主役はコネクションプールです。まず「なぜ必要なのか」を押さえておきましょう。

!!! note "接続を 1 本張るにはコストがかかる"
    第5章から何気なく書いてきた `psycopg.connect(...)` ですが、裏側では
    けっこう重い処理が行われています。

    1. クライアントと PostgreSQL サーバーの間で **TCP 接続**を確立する
    2. ユーザー名とパスワードによる**認証**のやり取りをする
    3. サーバー側で、この接続専用の**バックエンドプロセス**を起動する

    1 回だけなら数十ミリ秒程度で済みますが、Web アプリでは
    **リクエストごとに** DB アクセスが発生します。毎回ゼロから接続を張っていると、
    この確立コストがすべてレスポンスタイムに乗ってしまいますし、
    短時間に大量のプロセス起動・終了が起きてサーバー側の負荷にもなります。

!!! note "コネクションプールのたとえ"
    **コネクションプール**は、接続を「使うたびに新しく作る」のではなく、
    **あらかじめ何本か作っておいて使い回す**仕組みです。

    イメージは**共用の社有車**です。営業に出かけるたびに新車を買っていたら
    お金も時間もかかります。そこで会社が数台を駐車場に用意しておき、

    - 使いたい人が**鍵を借りて**出かける（接続の**貸し出し**）
    - 帰ってきたら**鍵を返す**（接続の**返却**）
    - 全部出払っていたら、誰かが戻るまで**待つ**（空きが出るまで待機）

    という運用にする、という話です。プールの中の接続は張られたままなので、
    借りるときのコストはほぼゼロです。
    鍵を返し忘れる人が続くと駐車場が空っぽになり、次の人が借りられなくなる、
    というトラブルまでそのまま対応しています（7.7 の `PoolTimeout` を参照）。

## 7.3 dict_row: 行を辞書で受け取る

これまでの章では、`fetchone()` / `fetchall()` の結果は**タプル**でした。
タプルだと「`row[0]` が `id`、`row[1]` が `title`」という対応を
自分で覚えておく必要があり、`SELECT` の列をあとから追加・並べ替えすると
その対応がズレて、離れた場所のバグとして現れます。

psycopg には、行をどんな形（タプル・辞書・自作クラスなど）に変換するかを
差し替えられる
[`row_factory`](https://www.psycopg.org/psycopg3/docs/advanced/rows.html)
という仕組みがあり、そこに `dict_row` を渡すと**辞書（dict）**で受け取れます。
`practice/dictrow_demo.py` を作ってください。

```python
import psycopg
from psycopg.rows import dict_row

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title, done FROM todos ORDER BY id")
    row = cur.fetchone()
    print(type(row))
    print(row)
    print(row["title"])
```

```bash
uv run --with 'psycopg[binary]' python practice/dictrow_demo.py
```

期待される出力:

```text
<class 'dict'>
{'id': 1, 'title': '牛乳を買う', 'done': False}
牛乳を買う
```

受け取った `row` は本物の `dict` で、`row["title"]` のように
**カラム名でアクセス**できます。`row[1]` より「今どのカラムを扱っているか」が
一目でわかりますし、`SELECT` に列を足しても既存コードが壊れにくくなります。
この研修では **常に `dict_row` を使う**方針で進めます。

!!! tip "`class_row` で dataclass に直接変換する手もある"
    `psycopg.rows.class_row(MyClass)` を使うと、行を直接 dataclass の
    インスタンスに詰めて返せます。研修では「`dict_row` で取って、
    第10〜11章のリポジトリ層で dataclass に詰め直す」方針なので、
    こういう仕組みもある、という程度の紹介にとどめます。

## 7.4 コネクションプールで接続を使い回す

7.2 で見たとおり、接続確立にはコストがかかるので、
**作った接続を使い回す**のが実用的なコードの定石です。
psycopg 用のプールは
[`psycopg_pool`](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
という別パッケージで提供されています。

接続が本当に使い回されているかを確かめてみましょう。
PostgreSQL では `SELECT pg_backend_pid()` で、
**今つながっているバックエンドプロセスの PID** を調べられます。
2 回連続で借りて PID を比べれば、同じ接続が返ってきたかどうかがわかります。
`practice/pool_demo.py` を作ってください。

```python
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

pool = ConnectionPool(DSN, min_size=1, max_size=1, kwargs={"row_factory": dict_row})

with pool.connection() as conn, conn.cursor() as cur:
    cur.execute("SELECT pg_backend_pid()")
    print("1回目:", cur.fetchone()["pg_backend_pid"])

with pool.connection() as conn, conn.cursor() as cur:
    cur.execute("SELECT pg_backend_pid()")
    print("2回目:", cur.fetchone()["pg_backend_pid"])

pool.close()
```

```bash
uv run --with 'psycopg[binary]' --with psycopg-pool python practice/pool_demo.py
```

期待される出力（PID の数字は実行のたびに変わります。
大事なのは **2 行が同じ数字になる**ことです）:

```text
1回目: 2156964
2回目: 2156964
```

新しく `connect` し直したら別のバックエンドプロセス（= 別の PID）になるはずです。
同じ PID が返ってきたということは、**1 回目に借りた接続が返却され、
2 回目でそのまま貸し出された**ということです。

動きを整理すると次のとおりです。

- `with pool.connection() as conn:` で **プールから接続を借りる**
- ブロックを抜けると自動で **プールに返却される**
- 借りようとしたときに全部が貸し出し中だと、空きが出るまで**待機**し、
  それでも空かなければタイムアウトの例外になる（7.7 の `PoolTimeout`）

!!! note "`min_size` と `max_size` の意味"
    `min_size` はプールが常に維持しておく最低接続数、
    `max_size` は同時に貸し出せる接続数の上限です。
    `max_size` を上げすぎると、PostgreSQL 側の同時接続数の上限
    （`max_connections` パラメータ、デフォルトは 100）を圧迫するので、
    アプリの並列度に見合った値にとどめるのが基本です。

また、`kwargs={"row_factory": dict_row}` で、
**プールが作るすべての接続に `dict_row` を適用**しています。
これを書き忘れると、借りてきた接続からは普通のタプルが返ってきます
（7.7 の「辞書のはずがタプルが返ってくる」を参照）。

## 7.5 アプリで使う形にする: `get_pool()` と `connection()`

プールをアプリ全体で使うとき、行き当たりばったりに
`ConnectionPool(...)` を作るわけにはいきません。
プールは **アプリに 1 つ**作って、みんなで共有するものです。
ここで、第10章以降の写経で登場する `app/db.py` の原型を体験しておきます。
`practice/db_pool.py` を作ってください。

```python
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DSN, min_size=1, max_size=10, kwargs={"row_factory": dict_row}
        )
    return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
```

この 3 つの部品の役割は次のとおりです。

- `_pool` …… **モジュールレベルの変数**として、プールをただ 1 つ保持する
- `get_pool()` …… **最初に呼ばれたときだけ** `ConnectionPool` を作って返す
  （2 回目以降は作り直さない）。モジュールを `import` しただけでは
  DB に接続しにいかないようにする、**遅延初期化**のテクニックです
- `connection()` …… 呼び出し側が `with connection() as conn:` と書くだけで
  済むようにする、貸し出し・返却の窓口

!!! note "`@contextmanager` で自分の `with` 文を作る"
    `contextmanager` は標準ライブラリ
    [`contextlib`](https://docs.python.org/3/library/contextlib.html)
    が提供するデコレータで、**`yield` を 1 回だけ使うジェネレータ関数**を
    `with` 文で使えるコンテキストマネージャに変換してくれます。
    `yield` の手前が「入るときの処理」、`yield` のあとが「抜けるときの処理」に
    対応します。ここでは `with connection() as conn:` に入るときに
    `pool.connection()` から接続を借り、ブロックを抜けると実行が再開して
    自動でプールに返却されます。ここではその `contextlib` を実際に使って、
    接続の貸し出しと返却を自分の `with` 文にまとめています。

使う側はこんなにすっきりします。同じファイルの末尾に足して実行してみてください。

```python
with connection() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title FROM todos WHERE done = %s ORDER BY id", (False,))
    for row in cur.fetchall():
        print(row["id"], row["title"])
```

```bash
uv run --with 'psycopg[binary]' --with psycopg-pool python practice/db_pool.py
```

期待される出力:

```text
1 牛乳を買う
2 健康診断の予約
4 家賃を振り込む
5 車検の見積もり
6 週次の振り返り
7 歯医者の予約
```

呼び出し側は `get_pool()` や `psycopg_pool` の存在をまったく意識せず、
`with connection() as conn:` だけで接続を借りて返せています。
第10章以降で写経する `mytodo/app/db.py` は、この構造をほぼそのまま採用しています
（違いは、接続情報を直書きの `DSN` ではなく設定オブジェクト `settings` から
取る点だけです。設定まわりは第17章で扱います）。

## 7.6 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] 接続確立のコスト（TCP・認証・バックエンドプロセス）を説明できる
- [ ] プールの「貸し出し・返却・待機」の流れをたとえ話で説明できる
- [ ] `row_factory=dict_row` で行を辞書として受け取り、`row["title"]` で読めた
- [ ] `with pool.connection()` で借りた接続が、返却後に使い回されることを確認できた
- [ ] `min_size` / `max_size` の意味を説明できる
- [ ] `get_pool()` が遅延初期化になっている理由を説明できる
- [ ] `with connection() as conn:` で接続を借りてクエリを実行できた

## 7.7 つまずきポイント

### `psycopg_pool` が見つからない

```text
ModuleNotFoundError: No module named 'psycopg_pool'
```

実行コマンドに `--with psycopg-pool` を付け忘れています。
コネクションプールは psycopg 本体とは**別パッケージ**なので、
`uv run --with 'psycopg[binary]' --with psycopg-pool python ...` のように
`--with` を 2 つ並べてください。

### `PoolTimeout` が発生する

```text
psycopg_pool.PoolTimeout: couldn't get a connection after 30.00 sec
```

プールの接続を**全部借りっぱなし**にしていて、空きが出るまで待っても
返ってこなかった、というエラーです。原因のほとんどは返却漏れで、
`with pool.connection() as conn:` を使わずに `pool.getconn()` で借りて
返さなかった、といったコードにあります。
**借りたら必ず `with` で囲って自動返却する**のが予防策です。
どうしても不足するなら `max_size` の見直しを検討します。

### 辞書のはずがタプルが返ってくる

```text
TypeError: tuple indices must be integers or slices, not str
```

`row["title"]` と書いたのに `row` がタプルだった、というエラーです。
`psycopg.connect(...)` や `ConnectionPool(...)` に
`row_factory=dict_row`（プールの場合は `kwargs={"row_factory": dict_row}`）
を**渡し忘れています**。プールでは接続ごとに指定するのではなく、
プールを作るときの `kwargs` でまとめて指定する点に注意してください。

## 7.8 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
ファイルはすべて `practice/` に作り、実行は
`uv run --with 'psycopg[binary]' --with psycopg-pool python ...` です
（問1 は `dict_row` しか使わないので `--with psycopg-pool` はなくても動きます）。
どの問題も、終わったあと `todos` は元の 7 行のまま残る作りになっています。

### 問1 dict_row でチェックリストを表示する

`practice/q1_checklist.py` を書いてください。
`todos` の全行を `id` 順に取り出し、`done` が `TRUE` なら `[x]`、
`FALSE` なら `[ ]` を付けて、次のようなチェックリスト形式で表示します
（**カラムへのアクセスは必ず `row["title"]` のようなキー名で**行うこと）。

```text
[ ] 牛乳を買う
[x] 領収書の整理
```

??? example "解答例"

    ```python
    import psycopg
    from psycopg.rows import dict_row

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT title, done FROM todos ORDER BY id")
        for row in cur.fetchall():
            mark = "x" if row["done"] else " "
            print(f"[{mark}] {row['title']}")
    ```

    期待される出力:

    ```text
    [ ] 牛乳を買う
    [ ] 健康診断の予約
    [x] 領収書の整理
    [ ] 家賃を振り込む
    [ ] 車検の見積もり
    [ ] 週次の振り返り
    [ ] 歯医者の予約
    ```

    `row` が辞書なので、「`row["done"]` が真なら `x`」という読みやすい
    コードになります。タプルだと `row[1]` になって、どのカラムか
    いちいち思い出す必要がありました。

### 問2 接続の使い回しを確認する

`practice/q2_pool.py` を書いてください。

1. `min_size=1, max_size=1` のプールを作る
2. `with pool.connection()` を **2 回連続で**使い、それぞれの中で
   `SELECT pg_backend_pid()` を実行して PID を表示する
3. 2 つの PID を比較し、同じなら「同じ接続が使い回されています」と表示する

??? example "解答例"

    ```python
    from psycopg_pool import ConnectionPool

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    pool = ConnectionPool(DSN, min_size=1, max_size=1)

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        pid1 = cur.fetchone()[0]
        print("1回目:", pid1)

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        pid2 = cur.fetchone()[0]
        print("2回目:", pid2)

    print("同じ接続が使い回されています" if pid1 == pid2 else "別の接続でした")
    pool.close()
    ```

    期待される出力（PID の数字は実行のたびに変わります）:

    ```text
    1回目: 2157129
    2回目: 2157129
    同じ接続が使い回されています
    ```

    1 回目の `with` を抜けた時点で接続がプールに返却され、
    2 回目はそれをそのまま借りています。`max_size=1` なので
    使い回されることが確実に観察できます。

### 問3 `get_pool()` / `connection()` を写して INSERT する

`practice/q3_dbhelper.py` を書いてください。7.5 の `get_pool()` と
`connection()` を**自分で写したうえで**、使う側のコードを書きます。

1. `with connection() as conn:` で接続を借りる
2. `title` が「プールの練習」の行を `INSERT ... RETURNING id, title, done` で
   追加し、返ってきた辞書を表示する
3. 同じブロック内でその行を `DELETE` し、削除件数を表示する（DB を元に戻す）

??? example "解答例"

    ```python
    from collections.abc import Iterator
    from contextlib import contextmanager

    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    _pool: ConnectionPool | None = None


    def get_pool() -> ConnectionPool:
        global _pool
        if _pool is None:
            _pool = ConnectionPool(
                DSN, min_size=1, max_size=10, kwargs={"row_factory": dict_row}
            )
        return _pool


    @contextmanager
    def connection() -> Iterator[psycopg.Connection]:
        pool = get_pool()
        with pool.connection() as conn:
            yield conn


    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (title) VALUES (%s) RETURNING id, title, done",
            ("プールの練習",),
        )
        print("追加:", cur.fetchone())

        cur.execute("DELETE FROM todos WHERE title = %s", ("プールの練習",))
        print("削除:", cur.rowcount, "件")
    ```

    期待される出力（`id` の数字は、これまでに `INSERT` を試した回数によって
    変わります。第6章の練習問題まで済ませた状態なら `20` です。
    第5章末で `13` まで消費済みで、第6章のデモと練習問題で
    さらに 6 つ消費しています。ロールバックされたり
    `NOT NULL` 違反で失敗したりした `INSERT` でも
    シーケンスの番号は消費されるため、次は `20` になります）:

    ```text
    追加: {'id': 20, 'title': 'プールの練習', 'done': False}
    削除: 1 件
    ```

    `kwargs={"row_factory": dict_row}` が効いているので、
    `RETURNING` の結果も辞書で受け取れています。
    この「窓口は `connection()` だけ、中身はプール」という構造が、
    第10章以降の `app/db.py` そのものです。

## まとめ

- 接続確立には TCP・認証・バックエンドプロセス起動のコストがかかるので、
  **作った接続はプールで使い回す**
- `row_factory=dict_row` を指定すると、行を**辞書**で受け取れる。
  `row["title"]` のようにカラム名で読めて、列の追加・並べ替えに強い
- `with pool.connection() as conn:` で**借りて**、ブロックを抜けて**返す**。
  返却漏れは `PoolTimeout` の原因になる
- プールは `kwargs={"row_factory": dict_row}` で、
  作る接続すべての設定をまとめて指定する
- アプリではプールをモジュールに 1 つ保持し、`get_pool()`（遅延初期化）と
  `connection()`（`@contextmanager` の窓口）で隠蔽する。
  これが第10章以降の `app/db.py` の構造

これで Part 2 はおしまいです。
次は [第8章 要件・画面・API設計](08-design-app.md) から、
**実際の ToDo アプリの設計**に入ります。
