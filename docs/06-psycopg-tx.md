# 第6章 プレースホルダとトランザクション

第5章で、Python から PostgreSQL を「動かす」ことはできるようになりました。
この章では「**安全に動かす**」ための 2 本柱を扱います。

- **プレースホルダ**で SQL インジェクションを防ぐ
- **トランザクション**でデータの整合性を保つ

どちらも Web アプリケーションを作るうえで必須の知識です。

## 6.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- SQL インジェクションがどういう攻撃か、具体例で説明できる
- `%s` プレースホルダが Python の `%` 書式と別物であると説明できる
- 複数の値やリストを `%s` / `ANY(%s)` で安全に渡せる
- `with` ブロックによる COMMIT / ROLLBACK の自動管理を説明できる
- `conn.commit()` / `conn.rollback()` を明示的に呼ぶコードが書ける
- `psycopg.errors` の例外を Python 側で拾って処理できる

**所要時間の目安: 60〜90 分**

この章でも、書くコードはすべてリポジトリルート直下の `practice/` ディレクトリに置き、
実行はリポジトリのルートで `uv run --with 'psycopg[binary]' python ...` で行います
（第5章と同じ決まりです）。`todos` テーブルに 7 行入っている前提で進めます。

## 6.2 前提知識

手を動かす前に、この章の主役となる 2 つの概念を押さえておきましょう。

!!! note "SQL インジェクションとは"
    **SQL インジェクション**は、入力フォームなどから渡された「値」に
    **SQL の命令を紛れ込ませる**攻撃です。

    たとえば、名前でユーザーを検索する機能があったとします。
    入力された文字列をそのまま SQL に連結して組み立てるコードだと、
    攻撃者が名前の欄に

    ```text
    x'; DROP TABLE users; --
    ```

    と入力するだけで、SQL が次のように組み立てられてしまいます。

    ```sql
    SELECT * FROM users WHERE name = 'x'; DROP TABLE users; --'
    ```

    閉じクォート `'` でいったん文字列を終わらせ、`;` で新しい文を始め、
    `--` で残りをコメントアウトする、という仕掛けです。
    結果として意図しない `DROP TABLE` が実行され、テーブルが消えます。
    「値」のつもりで受け取ったところに「命令」を差し込める、というのがこの攻撃の本質です。

    防ぎ方はシンプルで、**値を SQL 文字列に連結しない**ことです。
    この章で扱うプレースホルダが、そのための仕組みです。

!!! note "コミット（COMMIT）とロールバック（ROLLBACK）"
    第4章で psql から `BEGIN` → `COMMIT` / `ROLLBACK` を体験しました。
    おさらいすると、

    - **コミット（COMMIT）**: トランザクションの中で行った変更を**確定**する
    - **ロールバック（ROLLBACK）**: トランザクションの中で行った変更を
      **全部なかったことにする**

    の 2 つでした。psql では自分で `BEGIN` と打ち込んでトランザクションを
    始めましたが、psycopg からの操作では**自動でトランザクションが始まり**、
    確定・取消のタイミングを Python 側で制御します。それがこの章の後半の話です。

## 6.3 プレースホルダ: 値を安全に渡す

第5章で「値は `%s` プレースホルダで渡す」というルールを覚えました。
改めて、やっていいこととダメなことを並べます。

```python
# OK: SQL 文と値を別々に渡す
cur.execute("SELECT * FROM todos WHERE title = %s", (title,))

# NG: やってはいけない（値を SQL 文字列に連結している）
cur.execute(f"SELECT * FROM todos WHERE title = '{title}'")
cur.execute("SELECT * FROM todos WHERE title = '" + title + "'")
```

NG の書き方だと、6.2 で見た SQL インジェクションが成立します。
OK の書き方（`cur.execute(sql, params)` のように SQL 文とパラメータを別々に渡す形）では、
psycopg が文字列を組み立ててから送るのではなく、
**SQL 本体とパラメータを分離したまま** PostgreSQL サーバーに送信します
（[psycopg のパラメータの渡し方](https://www.psycopg.org/psycopg3/docs/basic/params.html)）。
サーバー側は「これは値であって SQL の構文ではない」と分かった状態で受け取るので、
値の中に `'` や `;` が混じっていても命令として解釈されることがありません。

!!! warning "プレースホルダの `%s` は Python の「% 書式」ではありません"
    Python には `"値は %s です" % (x,)` という古い文字列書式があります。
    psycopg の `%s` は見た目こそ同じですが、**まったく別の仕組み**です。

    - psycopg の `%s` は **psycopg が独自に解釈する印**で、
      SQL 文の文字列とパラメータを `execute` に別々に渡したときだけ意味を持ちます
    - 値の型が数値でも日付でも、**常に `%s`** を使います。
      `%d` や `%f` は存在しません（使うとエラーになります。6.8 を参照）
    - 自分で `%` 演算子で書式化してから `execute` に渡すと、
      結局文字列連結と同じことになるので意味がありません

### SQL インジェクションの入力が「ただのデータ」になることを確認する

攻撃文字列をそのままタイトルとして `INSERT` してみます。
`practice/injection_demo.py` を作ってください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

evil = "x'; DROP TABLE todos; --"

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute("INSERT INTO todos (title) VALUES (%s) RETURNING id", (evil,))
    new_id = cur.fetchone()[0]

    cur.execute("SELECT id, title FROM todos WHERE id = %s", (new_id,))
    print(cur.fetchone())

    cur.execute("DELETE FROM todos WHERE id = %s", (new_id,))
    print("deleted:", cur.rowcount)
```

```bash
uv run --with 'psycopg[binary]' python practice/injection_demo.py
```

期待される出力（`id` の数字は、これまでに `INSERT` した回数によって変わります。
第5章までの手順どおり進めた場合は `10` です）:

```text
(10, "x'; DROP TABLE todos; --")
deleted: 1
```

見てのとおり、`'; DROP TABLE todos; --` は命令としてではなく、
**ただの文字列データ**としてそのまま保存されました（そして最後に消しています）。
もしこれが f-string で連結されていたら、テーブルごと消えていたところです。
プレースホルダの「値と SQL を分けて送る」仕組みが、
そのまま SQL インジェクション対策になっていることがわかります。

### 複数の値・リストを渡す

値が複数あるときは、`%s` を並べてタプルで渡します。
リスト（個数が変わりうる値の集合）を渡したいときは、
PostgreSQL の `ANY` を使うとシンプルです。
`practice/multi_values.py` を作ってください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT id, title FROM todos WHERE priority = %s AND done = %s",
        (1, False),
    )
    print(cur.fetchall())

    ids = [1, 2, 3]
    cur.execute("SELECT id, title FROM todos WHERE id = ANY(%s) ORDER BY id", (ids,))
    for row in cur.fetchall():
        print(row)
```

```bash
uv run --with 'psycopg[binary]' python practice/multi_values.py
```

期待される出力:

```text
[(2, '健康診断の予約')]
(1, '牛乳を買う')
(2, '健康診断の予約')
(3, '領収書の整理')
```

`IN (1, 2, 3)` のように文字列で組み立てたくなるところですが、それをやると結局
SQL インジェクションの入り口を作ってしまいます。
**`ANY(%s)` ならリストを丸ごと 1 つのパラメータとして安全に渡せる**ので、
値の個数が変わっても SQL 文字列自体を組み立て直す必要がありません。

!!! note "値が 1 つでも `(value,)` と書く"
    第5章でも触れましたが、`(title,)` の**末尾のカンマ**が必要です。
    カンマがない `(title)` はタプルではなく単なる値なので、エラーになります
    （6.8 の「つまずきポイント」も参照）。

!!! warning "識別子（テーブル名・カラム名）はプレースホルダで渡せない"
    `cur.execute("SELECT * FROM %s", (table_name,))` はエラーになります。
    `%s` で渡せるのはあくまで「値」だけです。
    識別子を動的に組み立てる必要があるときは、`psycopg.sql` モジュールの
    `Identifier` を使ってください（研修では使いません）。

## 6.4 トランザクション: `with` による自動管理

第5章で「`with psycopg.connect(...)` は、閉じるだけでなく、
例外が起きていなければ COMMIT、起きていれば ROLLBACK まで自動でやってくれる」
と紹介しました。ここではその動きを確認します。

psycopg v3 は接続を開いた時点で **`autocommit=False` がデフォルト**になっていて、
明示的に `commit()` を呼ぶまでは、実行した SQL はトランザクションの中に
入ったまま確定しません（[psycopg のトランザクション](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)）。
`with` ブロックを使うと、この確定・取消を自動でやってくれます。

- ブロックを最後まで例外なく抜けた → **COMMIT**
- 途中で例外が起きてブロックを抜けた → **ROLLBACK**

### 例外が起きると全部ロールバックされることを確認する

わざと失敗するコードを書いてみます。
1 つめの `INSERT` は成功し、2 つめが `title` の `NOT NULL` 制約に違反する、
という状況です。`practice/rollback_demo.py` を作ってください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

try:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", ("これは入らない",))
        cur.execute("INSERT INTO todos (title) VALUES (%s)", (None,))  # NOT NULL 違反
except psycopg.errors.NotNullViolation:
    print("例外を捕捉しました: 2 つめの INSERT は失敗")

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM todos WHERE title = %s", ("これは入らない",))
    print("count =", cur.fetchone()[0])
```

```bash
uv run --with 'psycopg[binary]' python practice/rollback_demo.py
```

期待される出力:

```text
例外を捕捉しました: 2 つめの INSERT は失敗
count = 0
```

2 つめの `INSERT` で例外が起きたため、`with` ブロックは ROLLBACK され、
**成功していたはずの 1 つめの INSERT も保存されていない**（`count = 0`）
ことが確認できました。

これは「複数の操作をひとまとまりの単位として扱う」というトランザクションの性質
（**原子性**、第4章で触れた ACID の A）そのものです。
1 つでも失敗したら、途中まで成功していた分も含めてなかったことにする、
という考え方です。

## 6.5 明示的に commit() / rollback() する

`with` を使わずにコネクションを自分で管理する場合は、
`conn.commit()` / `conn.rollback()` を明示的に呼びます。
`practice/manual_tx.py` を作って、`rollback()` で変更を自分で取り消してみます。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

conn = psycopg.connect(DSN)
try:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO todos (title) VALUES (%s)", ("ロールバックで消える行",))
        print("INSERT は成功")
    conn.rollback()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM todos WHERE title = %s", ("ロールバックで消える行",))
        print("count =", cur.fetchone()[0])
finally:
    conn.close()
```

```bash
uv run --with 'psycopg[binary]' python practice/manual_tx.py
```

期待される出力:

```text
INSERT は成功
count = 0
```

`INSERT` 自体は成功していますが、`commit()` せずに `rollback()` したので、
行は残っていません。`commit()` を呼ばない限り、変更はずっと未確定のままです。

自分で管理する場合の定型パターンは次のとおりです。

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

役割分担はシンプルです。**`try` の中が最後まで正常に終わったら `commit()`**、
**`except` で捕まえたら `rollback()`** してから `raise` で呼び出し元に伝える、
**`finally` では成功・失敗にかかわらず必ず `close()`** する、という 3 段構えです。
ただし、これは `with` で書けばほぼ同じことなので、**普通は `with` を使う**のが
楽で安全です。

!!! note "autocommit モード（参考）"
    `psycopg.connect(DSN, autocommit=True)` にすると、SQL を 1 文実行するたびに
    その場で COMMIT されるようになります。裏を返すと、複数の文を 1 つの
    トランザクションにまとめる（どれかが失敗したら全部なかったことにする）
    ことはできなくなります。
    マイグレーションのようにトランザクションの中で実行できないコマンドを
    流したいときなどに使うもので、研修ではほとんど出てきません。

## 6.6 例外を Python 側で拾う

制約違反などの DB エラーは、`psycopg.errors` 以下の例外クラスとして Python 側に届きます。
PostgreSQL はエラーごとに SQLSTATE というコードを持っていて、psycopg はそれをもとに
細かく分類された例外クラスを用意しています。よく使うものは次のとおりです。

| 例外 | 起きる状況 |
|---|---|
| `psycopg.errors.UniqueViolation` | UNIQUE 制約違反（同じ値を 2 回入れた） |
| `psycopg.errors.NotNullViolation` | NOT NULL のカラムに NULL を入れた |
| `psycopg.errors.ForeignKeyViolation` | 参照先の行がない（外部キー制約違反） |

これらは全部 **`psycopg.Error`**（さらにたどると組み込みの `Exception`）を
継承しています。「制約違反だけ個別に処理したい」なら `UniqueViolation` のように
具体的なクラスで、「DB まわりで何か失敗したらまとめて捕まえたい」なら
`except psycopg.Error:` のように広く、用途に応じて捕まえる粒度を選べます。

### UniqueViolation を拾って処理を続ける

同じ値を 2 回入れて `UniqueViolation` を起こし、拾ってみます。
ここでは、後片付けの手間も DB を汚す心配もないよう、
**コネクションを閉じると自動で消える一時テーブル**（`CREATE TEMP TABLE`）で試します。
`practice/unique_demo.py` を作ってください。

```python
import psycopg
import psycopg.errors as pgerr

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

conn = psycopg.connect(DSN)
try:
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE demo_users (name TEXT UNIQUE)")
        cur.execute("INSERT INTO demo_users VALUES (%s)", ("たろう",))

        try:
            with conn.transaction():
                cur.execute("INSERT INTO demo_users VALUES (%s)", ("たろう",))  # 重複
        except pgerr.UniqueViolation:
            print("UniqueViolation を捕捉: 同じ name は入れられません")

        cur.execute("SELECT COUNT(*) FROM demo_users")
        print("demo_users の行数 =", cur.fetchone()[0])
finally:
    conn.close()
```

```bash
uv run --with 'psycopg[binary]' python practice/unique_demo.py
```

期待される出力:

```text
UniqueViolation を捕捉: 同じ name は入れられません
demo_users の行数 = 1
```

新しい登場人物が 2 つあります。

- `CREATE TEMP TABLE ...` は、そのコネクションの中だけで有効な一時テーブルを
  作ります。`conn.close()` と一緒に自動で消えるので、練習用に便利です
- `with conn.transaction():` は、コネクションの中に**小さなトランザクションの
  区切り**を作ります。ブロック内で例外が起きると、**そのブロックの中だけ**が
  ロールバックされ、ブロックの外（1 件目の `INSERT`）は生き残ります。
  だから最後の件数は `1` です

「重複したらエラーメッセージを返して処理を続けたい」という、
アプリでよくある場面の基本形です。

!!! note "`current transaction is aborted` が出たら"
    1 つのトランザクションの中で SQL がエラーになると、その後の SQL は全部
    `current transaction is aborted` というエラーになります。
    PostgreSQL が「エラーの起きたトランザクションの中身はもう信用できない」と
    みなし、`ROLLBACK` されるまで新しい SQL を受け付けなくなる安全策です
    （第4章で psql でも見ましたね）。
    `with` ブロックを抜けるか、`conn.rollback()` を呼ぶか、
    上の例のように `with conn.transaction():` で区切るか、のどれかで復帰してください。

## 6.7 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] SQL インジェクションの仕組みを、`'; DROP TABLE ... --` の例で説明できる
- [ ] `%s` が Python の `%` 書式ではなく、psycopg 専用の印だと説明できる
- [ ] プレースホルダが安全な理由（SQL と値を分けて送る）を説明できる
- [ ] 複数の値をタプルで、リストを `ANY(%s)` で渡せた
- [ ] `with` ブロックが例外なしなら COMMIT、例外ありなら ROLLBACK することを確認できた
- [ ] `conn.commit()` / `conn.rollback()` を明示的に呼ぶコードが書けた
- [ ] `psycopg.errors.UniqueViolation` を `try` / `except` で拾えた

## 6.8 つまずきポイント

### `%d` は使えない

```text
psycopg.ProgrammingError: only '%s', '%b', '%t' are allowed as placeholders, got '%d'
```

数値だからといって `%d` と書いてしまった場合のエラーです。
psycopg のプレースホルダは**型に関係なく常に `%s`** です。
int の `1` でも `WHERE id = %s` と書き、値はタプルで `(1,)` と渡します。

### パラメータのタプルのカンマ忘れ

```text
TypeError: object of type 'int' has no len()
```

`cur.execute("... WHERE id = %s", (new_id))` のように、
第 2 引数の**末尾のカンマを忘れた**ときのエラーです。
`(new_id)` はタプルではなく単なる int なので、
psycopg が「パラメータの並び」として扱えずに落ちています。
`(new_id,)` とカンマを付けてください（値が 1 つでも同じです）。

### `current transaction is aborted`

```text
psycopg.errors.InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block
```

同じトランザクションの中で**前の SQL がエラーになったまま**、
次の SQL を実行したときのエラーです（6.6 の note 参照）。
`conn.rollback()` でトランザクションをいったん終わらせるか、
部分ロールバックしたい箇所を `with conn.transaction():` で囲ってください。

### commit し忘れて INSERT が消える

エラーが出ないので気づきにくいのですが、`with` を使わずに
`psycopg.connect()` したコードで **`commit()` を呼び忘れる**と、
`INSERT` したはずの行がどこにも残りません
（`conn.close()` しても自動では確定されず、ロールバックされます）。
`with` を使わない理由がない限り、`with psycopg.connect(...)` で囲って
自動コミットに任せるのが確実です。

## 6.9 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
ファイルはすべて `practice/` に作り、実行は `uv run --with 'psycopg[binary]' python ...` です。
どの問題も、終わったあと `todos` は元の 7 行のまま残る作りになっています。

### 問1 ロールバックを体験する

`practice/q1_rollback.py` を書いて、次の流れを 1 つのスクリプトでやってください。

1. 最初に `SELECT COUNT(*) FROM todos` で件数を表示する（`before`）
2. `INSERT` を 2 回実行する。2 つめは `title` に `None` を渡してわざと失敗させる
3. `psycopg.errors.NotNullViolation` を拾ってメッセージを表示する
4. もう一度件数を表示し（`after`）、**1 つめの INSERT も残っていない**ことを確認する

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM todos")
        print("before =", cur.fetchone()[0])

    try:
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO todos (title) VALUES (%s)", ("練習: 入るはずの行",))
            cur.execute("INSERT INTO todos (title) VALUES (%s)", (None,))
    except psycopg.errors.NotNullViolation:
        print("例外が起きてロールバックされました")

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM todos")
        print("after =", cur.fetchone()[0])
    ```

    期待される出力:

    ```text
    before = 7
    例外が起きてロールバックされました
    after = 7
    ```

    2 つめの `with` ブロックが例外で抜けたため、その中の `INSERT` は
    **1 つめも 2 つめも確定されません**でした。`before` と `after` が
    一致していれば、ロールバックが効いている証拠です。

### 問2 複数条件をプレースホルダで検索する

`practice/q2_where.py` を書いてください。

- 「`priority = 2` かつ `done = FALSE`」の ToDo の `id` と `title` を、
  `id` 順に取り出して 1 行ずつ表示する
- **2 つの条件値はどちらも `%s` プレースホルダで渡す**こと

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title FROM todos WHERE priority = %s AND done = %s ORDER BY id",
            (2, False),
        )
        for row in cur.fetchall():
            print(row)
    ```

    期待される出力:

    ```text
    (1, '牛乳を買う')
    (4, '家賃を振り込む')
    (5, '車検の見積もり')
    (6, '週次の振り返り')
    (7, '歯医者の予約')
    ```

    `False` のような Python の値も、そのままタプルに入れて渡せます。
    SQL の `FALSE` と書き方が違いますが、psycopg が適切に変換してくれます。

### 問3 UPDATE して、ロールバックで元に戻す

`practice/q3_update.py` を書いてください。`with` は使わず、
`conn.commit()` / `conn.rollback()` を自分で呼ぶ形にします。

1. `id = 1` の ToDo の `done` を `TRUE` に `UPDATE` し、`rowcount` を表示する
2. `SELECT` で更新後の行を表示する
3. `conn.rollback()` して、もう一度 `SELECT` で表示する（元に戻っているはず）
4. `finally` で `conn.close()` する

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    conn = psycopg.connect(DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE todos SET done = TRUE WHERE id = %s", (1,))
            print("updated:", cur.rowcount)

            cur.execute("SELECT id, title, done FROM todos WHERE id = %s", (1,))
            print("更新直後:", cur.fetchone())

            conn.rollback()

            cur.execute("SELECT id, title, done FROM todos WHERE id = %s", (1,))
            print("rollback 後:", cur.fetchone())
    finally:
        conn.close()
    ```

    期待される出力:

    ```text
    updated: 1
    更新直後: (1, '牛乳を買う', True)
    rollback 後: (1, '牛乳を買う', False)
    ```

    トランザクションの中では更新が見えていますが、`rollback()` で
    なかったことにできています。「試しに変更してみて、確認したら取り消す」
    という調査のやり方は、実務でもよく使います。

## まとめ

- SQL インジェクションは、値を SQL 文字列に連結することで成立する攻撃。
  **値は必ずプレースホルダ `%s` で渡す**
- `%s` は **psycopg 専用**の印で、Python の `%` 書式とは別物。型に関係なく常に `%s`
- psycopg は SQL 本体とパラメータを分けてサーバーに送るので、
  値の中の `'` や `;` が命令として解釈されない
- リストは `ANY(%s)` で丸ごと渡せる。`IN (...)` を文字列連結で作らない
- `with psycopg.connect(...)` は、例外なしで抜ければ **COMMIT**、
  例外で抜ければ **ROLLBACK** を自動で行う
- 自分で管理する場合は `conn.commit()` / `conn.rollback()` を明示的に呼ぶ
- DB のエラーは `psycopg.errors` の例外として拾える。
  部分ロールバックには `with conn.transaction():` が使える

次は [第7章 dict_rowとコネクションプール](07-psycopg-pool.md) で、
結果を辞書として受け取る方法や、接続を使い回すコネクションプールなど、
**実用的な使い勝手**を整えていきます。
