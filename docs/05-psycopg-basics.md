# 第5章 psycopg入門 接続と基本のCRUD

第3〜4章では psql から直接 SQL を打ち込みました。
この章からはいよいよ **Python から PostgreSQL を操作**します。
第0章で Docker に立てたデータベースに Python スクリプトから接続し、
第3章で作った `todos` テーブルを読み書きするところまでを、自分の手で動かします。

## 5.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- クライアント/サーバーモデルと「ドライバ」の役割を説明できる
- DSN（接続文字列）を書いて、Python から PostgreSQL に接続できる
- コネクションとカーソルを `with` 文で開き、閉じ忘れのないコードが書ける
- `SELECT` の結果を `fetchone()` / `fetchall()` で受け取れる
- `%s` プレースホルダで値を渡して `INSERT` でき、`RETURNING id` で採番された `id` を受け取れる

**所要時間の目安: 60〜90 分**

この章でも、書くコードはすべてリポジトリルート直下の `practice/` ディレクトリに置き、
実行はリポジトリのルートで行います（第2章と同じ決まりです）。

## 5.2 前提知識: クライアント/サーバーとドライバ

手を動かす前に、登場人物の整理をしておきましょう。
難しい理屈は後回しで、「何のことか」がわかれば十分です。

!!! note "クライアント/サーバーモデル"
    PostgreSQL は **サーバー** として動き続け、**クライアント** からの接続を待ち受けています。
    第0章で Docker に立てた `webapp-training-db` がそのサーバーです。

    クライアントは「PostgreSQL に接続して SQL を送る側」の総称です。
    第3〜4章で使った psql もクライアントのひとつで、この章で書く Python スクリプトは
    もうひとつのクライアントになります。サーバー 1 台に対して、
    psql と Python スクリプトが**同時に**接続していても構いません。

!!! note "ドライバとは"
    Python スクリプトと PostgreSQL の間で会話を取り持つライブラリを **ドライバ** と呼びます。
    PostgreSQL はネットワーク越しに独自のプロトコル（決まりごと）でやり取りするので、
    Python の標準機能だけでは直接話しかけられません。

    本研修では PostgreSQL 用ドライバの [`psycopg`](https://www.psycopg.org/psycopg3/)（バージョン 3）を使います。
    ドライバは言語ごとに別のものがあり（Java なら JDBC、Ruby なら pg gem など）、
    「アプリから DB に接続する = その言語のドライバを使う」と考えておけば大丈夫です。

!!! note "コネクションとカーソル"
    ドライバを使った DB 操作は、次の 2 段構えで動きます。

    - **コネクション**: PostgreSQL サーバーとの通信路そのもの。
      まずこれを 1 本確立してからでないと何もできない
    - **カーソル**: コネクションの上に作る「SQL を送って結果を受け取る窓口」。
      SQL の実行はすべてカーソル経由で行う

    イメージとしては、コネクションが電話回線、カーソルがその電話で交わす
    ひとつひとつの会話、という関係です。
    1 本のコネクションの中に複数のカーソルを開くこともできますが、
    この章では「コネクション 1 つにつきカーソル 1 つ」で進めます。

!!! note "DSN（接続文字列）"
    **DSN**（Data Source Name）は、接続に必要な情報を 1 本の文字列にまとめたものです。
    第0章でメモした接続情報を `key=value` の形で並べます。

    ```text
    host=localhost port=5432 dbname=tododb user=todo password=todo
    ```

    ホスト名やパスワードをバラバラの引数で渡すよりも 1 か所にまとまっているほうが、
    あとで設定ファイルや環境変数に切り出しやすくなります（第17章で扱います）。
    DSN の書き方の一覧は [psycopg のドキュメント](https://www.psycopg.org/psycopg3/docs/basic/usage.html) にあります。

## 5.3 psycopg を用意する

このリポジトリの `pyproject.toml` には psycopg が入っていません。
第2章の pytest と同じく、`uv run --with` で**実行のたびに一時的に用意する**形で進めます。
まず、使えることを確認しておきましょう。

```bash
uv run --with 'psycopg[binary]' python -c "import psycopg; print(psycopg.__version__)"
```

期待される出力（バージョンの数字は多少変わることがあります）:

```text
3.3.4
```

!!! note "`psycopg[binary]` の `[binary]` とは"
    PostgreSQL との通信に必要なクライアントライブラリ（libpq）を
    **Python のパッケージに同梱**してくれる指定です。
    これがないと環境によってはインストールに失敗することがあるため、
    研修では `[binary]` 付きで統一します。

## 5.4 接続確認スクリプトを書く

まず、接続の確認だけを行う小さなスクリプトを自分で書きます。
`practice/check_connection.py` を新しく作って、次の内容を写してください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        row = cur.fetchone()
        print("接続成功:", row[0])
```

リポジトリのルートで実行します（PostgreSQL コンテナが動いていなければ、
先に `docker compose up -d` で起動してください）。

```bash
uv run --with 'psycopg[binary]' python practice/check_connection.py
```

期待される出力（バージョンやコンパイラの部分は環境によって変わります）:

```text
接続成功: PostgreSQL 16.x (...) on x86_64-pc-linux-gnu, compiled by gcc ...
```

`接続成功:` と表示されれば、Python から PostgreSQL への通信路が確立できています。
エラーが出た場合は、5.8 の「つまずきポイント」を見てください。

この 10 行に、この章の大事な要素が全部入っています。

- `psycopg.connect(DSN)` が作る `conn` が **コネクション**、
  `conn.cursor()` が作る `cur` が **カーソル** です
- `cur.execute(...)` で SQL を送り、`cur.fetchone()` で結果を 1 行受け取ります。
  `SELECT version()` の結果は 1 行しかないので `fetchone()` で十分です
- どちらも `with` 文で囲っています。第2章で学んだとおり、
  ブロックを抜けるときに**自動で閉じる**ためです

`with psycopg.connect(...)` は、閉じるだけでなく、**例外が起きていなければ COMMIT、
起きていれば ROLLBACK** まで自動でやってくれます。
接続を閉じ忘れると PostgreSQL 側にコネクションが残り続け、積み重なるとやがて
「これ以上接続できない」状態になるので、これは地味に効いてくる保証です
（トランザクションの詳しい話は第6章で扱います）。

## 5.5 SELECT で行を取り出す

次は、第3章で作った `todos` テーブルの中身を Python から読んでみます。
`practice/select_todos.py` を作ってください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, title FROM todos ORDER BY id")
    for row in cur.fetchall():
        print(row)
```

```bash
uv run --with 'psycopg[binary]' python practice/select_todos.py
```

期待される出力（第3〜4章の手順どおり進めた場合の 7 行です）:

```text
(1, '牛乳を買う')
(2, '健康診断の予約')
(3, '領収書の整理')
(4, '家賃を振り込む')
(5, '車検の見積もり')
(6, '週次の振り返り')
(7, '歯医者の予約')
```

psql で見たときと同じ中身が、Python の世界に届いているのがわかります。

ここで覚えておきたいのが、`execute` と `fetch` の**二段構え**です。
`cur.execute(...)` は SQL を実行するだけで、結果はいったんカーソルの中に保持されます。
そこから必要な分だけ取り出すのが `fetch` 系のメソッドです。

- `fetchone()`: 1 行だけ取り出す
- `fetchmany(n)`: n 行まとめて取り出す
- `fetchall()`: 残りを全部取り出す

**大量データに `fetchall()` を使わない**よう注意してください。
全行をいっぺんに Python のメモリに載せてしまいます。
件数が多い可能性があるときは `fetchmany(n)` で少しずつ処理します。

なお、各行は `SELECT` に書いた**カラムの順番そのままのタプル**です。
今回の例だと `row[0]` が `id`、`row[1]` が `title` です。
カラム名でアクセスしたい場合は `dict_row` という仕組みがあります（第7章で扱います）。

## 5.6 INSERT で行を追加する

今度は逆に、Python から行を追加します。
`practice/insert_todo.py` を作ってください。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute(
        "INSERT INTO todos (title) VALUES (%s) RETURNING id",
        ("psycopg からのテスト",),
    )
    new_id = cur.fetchone()[0]
    print("inserted id =", new_id)

    cur.execute("SELECT id, title FROM todos WHERE id = %s", (new_id,))
    print(cur.fetchone())
```

```bash
uv run --with 'psycopg[binary]' python practice/insert_todo.py
```

期待される出力（`id` は実行ごとに変わります。第3章の練習問題まで済ませた状態なら `9` です）:

```text
inserted id = 9
(9, 'psycopg からのテスト')
```

`INSERT` が Python から確かに PostgreSQL に届き、psql でやったのと同じように
自動採番まで行われていることがわかります。

### プレースホルダ `%s` で値を渡す

SQL の中の値を `%s` と書き、実際の値を `execute` の第 2 引数にタプルで渡す
書き方は**プレースホルダ**と呼びます。この章でいちばん大事なルールです。

psycopg が Python の型（`str` / `int` / `bool` / `None` など）を見て、
適切な形にエスケープ・変換してから SQL に埋め込んでくれるので、
**絶対に文字列連結や f-string で値を埋め込まないでください**。
安全でないだけでなく、引用符の扱いなどでそもそも壊れやすいです。
この話の詳細（SQL インジェクション対策）は第6章で扱います。

!!! tip "値が 1 つでも `(value,)` と書く"
    `("psycopg からのテスト",)` のように**末尾のカンマ**が必要です。
    カンマがない `("psycopg からのテスト")` はタプルではなく単なる文字列です。
    psycopg はパラメータを「タプルかリスト」として受け取ります。

!!! note "psycopg のプレースホルダは `%s`"
    Python の文字列書式の `%s` と見た目が同じですが、別の仕組みです。
    psycopg が独自に解釈する印で、値の型が数値でも文字列でも、
    常に `%s` を使います（`%d` などはありません）。

### INSERT と同時に採番された id を受け取る

`INSERT` を実行しただけでは、DB 側で自動採番された `id` が何になったかは
Python 側にはわかりません。`RETURNING id` を付けると、**INSERT と同じ 1 回の
やり取りで**生成された値を受け取れるので、わざわざ別の `SELECT` を投げて
調べ直す必要がなくなります（第3章でも同じことをしましたね）。

### 練習用の行を消しておく

テスト用に入れた行は、このあとの章に影響しないよう消しておきましょう。
`practice/delete_todo.py` を作って実行します。

```python
import psycopg

DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    cur.execute("DELETE FROM todos WHERE title = %s", ("psycopg からのテスト",))
    print("deleted:", cur.rowcount)
```

```bash
uv run --with 'psycopg[binary]' python practice/delete_todo.py
```

期待される出力:

```text
deleted: 1
```

`cur.rowcount` は、直前の SQL で何行が影響を受けたかを返します。
`1` なら狙った 1 行だけが消えています。
`UPDATE` / `DELETE` を Python から安全に扱う話は、第6章で詳しく扱います。

## 5.7 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] クライアント/サーバーモデルと、ドライバの役割を説明できる
- [ ] 自分の環境の接続情報から DSN を書ける
- [ ] 接続確認スクリプトを自分で書き、`接続成功:` と表示できた
- [ ] コネクションとカーソルの関係、`with` で囲う理由を説明できる
- [ ] `SELECT` の結果を `fetchone()` / `fetchall()` で取り出せた
- [ ] `%s` プレースホルダで値を渡して `INSERT` できた。文字列連結がダメな理由を説明できる
- [ ] `RETURNING id` で採番された `id` を受け取れた

## 5.8 つまずきポイント

### `No module named 'psycopg'`

```text
ModuleNotFoundError: No module named 'psycopg'
```

`uv run python ...` に `--with 'psycopg[binary]'` を付け忘れています。
このリポジトリには psycopg が常備されていないので、実行のたびに `--with` が必要です。

### 接続が拒否される（Connection refused）

```text
psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

（環境によっては `connection to server at "localhost" (::1), port 5432 failed` のように
ホスト名付きで表示されることもあります。いずれも `Connection refused` が目印です）

**PostgreSQL のコンテナが起動していない**サインです。
`docker compose up -d` を実行し、`docker compose ps` で `STATUS` が `Up` に
なっていることを確認してから実行し直してください。
第3章で psql が出していた接続拒否とまったく同じ原因が、今度は Python から出ただけです。

### パスワード認証に失敗する

```text
psycopg.OperationalError: connection failed: ... FATAL:  password authentication failed for user "todo"
```

DSN の `password=` が間違っています。研修環境のパスワードは `todo` です
（第0章の接続情報の表を確認してください）。
`user=` の打ち間違いでも同じ系統のエラーになります。

### データベースが存在しない

```text
psycopg.OperationalError: connection failed: ... FATAL:  database "todo" does not exist
```

DSN の `dbname=` が間違っています。接続先は `tododb` です
（`todo` はユーザー名で、データベース名ではありません）。
`dbname` に指定するデータベースは**すでに存在している**必要があります。
psql で `\l` を実行すると、存在するデータベースの一覧を確認できます。

## 5.9 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
ファイルはすべて `practice/` に作り、実行は `uv run --with 'psycopg[binary]' python ...` です。
ここまでの章どおり `todos` に 7 行入っている前提です。

### 問1 条件付きの SELECT を Python から

「`priority = 1` の ToDo」を取るスクリプト `practice/q1_priority.py` を書いてください。
ポイントは、**`1` を SQL に直接書き込まず、`%s` プレースホルダで渡す**ことです。

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title FROM todos WHERE priority = %s", (1,))
        for row in cur.fetchall():
            print(row)
    ```

    期待される出力:

    ```text
    (2, '健康診断の予約')
    ```

    `WHERE priority = 1` と埋め込んでも動きますが、練習のうちから
    「値は必ずプレースホルダで渡す」に統一しておくのが安全です。

### 問2 INSERT → id を受け取る → 後片付け

`practice/q2_insert.py` を書いて、次の一連の流れを 1 つのスクリプトでやってください。

1. `INSERT ... RETURNING id` で ToDo を 1 件追加し、採番された `id` を表示する
   （タイトルは自由。例では `'牛乳を買い足す'`、`priority` は `1`）
2. 返ってきた `id` を使ってその行を `DELETE` し、後片付けする

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (title, priority) VALUES (%s, %s) RETURNING id",
            ("牛乳を買い足す", 1),
        )
        new_id = cur.fetchone()[0]
        print("inserted id =", new_id)

        cur.execute("DELETE FROM todos WHERE id = %s", (new_id,))
        print("deleted:", cur.rowcount)
    ```

    期待される出力（`id` は実行ごとに変わります）:

    ```text
    inserted id = 10
    deleted: 1
    ```

    `RETURNING id` で受け取った値を、そのまま次の SQL のパラメータに使い回せるのが
    ポイントです。「追加したものは自分で消す」ことで、`todos` テーブルを元の 7 行に
    保っています。

### 問3 まとめて INSERT する

`executemany` を使って、3 件の ToDo をまとめて追加するスクリプト
`practice/q3_many.py` を書いてください。

- タイトルは自由です（例では「朝食を作る」「昼食を作る」「夕食を作る」）
- 追加後に `SELECT COUNT(*)` で件数を確認する
- 最後に、追加した 3 件を `DELETE` して元に戻す（`executemany` は `DELETE` にも使えます）

??? example "解答例"

    ```python
    import psycopg

    DSN = "host=localhost port=5432 dbname=tododb user=todo password=todo"

    titles = ["朝食を作る", "昼食を作る", "夕食を作る"]

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO todos (title) VALUES (%s)",
            [(t,) for t in titles],
        )
        cur.execute("SELECT COUNT(*) FROM todos")
        print("total =", cur.fetchone()[0])

        cur.executemany("DELETE FROM todos WHERE title = %s", [(t,) for t in titles])
        cur.execute("SELECT COUNT(*) FROM todos")
        print("total =", cur.fetchone()[0])
    ```

    期待される出力（この章の手順どおり進めた場合）:

    ```text
    total = 10
    total = 7
    ```

    ループで 1 件ずつ `execute` すると、そのたびに Python と PostgreSQL の間で
    通信が発生します。`executemany` はまとめて送るぶん通信回数が減るので、
    たくさん入れる場合はその方が速くなります。

## まとめ

- PostgreSQL は**サーバー**、psql や Python スクリプトは**クライアント**。
  言語ごとの**ドライバ**（Python では psycopg）が間を取り持つ
- 接続情報は **DSN**（`key=value` の接続文字列）にまとめる
- **コネクション**は通信路、**カーソル**は SQL を送る窓口。
  `with` 文で囲うと閉じ忘れを防げる
- `SELECT` の結果は `fetchone()` / `fetchall()` で取り出す。行はカラム順のタプル
- 値は**プレースホルダ `%s`** で渡す。文字列連結や f-string で SQL に値を埋め込まない
- `INSERT ... RETURNING id` で、採番された `id` を 1 回のやり取りで受け取れる

次は [第6章 プレースホルダとトランザクション](06-psycopg-tx.md) で、
**値を安全に渡す仕組み**の中身と、トランザクション（COMMIT / ROLLBACK）の
正しい使い方を Python から扱います。
