# 第3章 PostgreSQLのおさらい① DDL/DML/SELECT

この章から、データベースの準備運動です。
「SQL を昔少しだけ触ったことがある」「ほぼ初めて」という状態を前提に、
**psql の起動のしかた**から始めて、テーブルの作成・データの追加・参照・更新・削除までを
ひととおり自分の手で動かします。

この章で作る `todos` テーブルは、このあとの章（第4章以降）でもそのまま使います。
写して動かすたびに実行結果を自分の画面で確認しながら進めてください。

## 3.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- `psql` を起動・終了し、`\dt` / `\d` でテーブルを確認できる
- `CREATE TABLE` でテーブルを作り、型と制約（`NOT NULL` / `DEFAULT` / `PRIMARY KEY`）の意味を説明できる
- `INSERT` / `SELECT` / `UPDATE` / `DELETE` の基本形を書いて、結果を読める
- `NULL` の扱い（`IS NULL`）と、`WHERE` を忘れた `UPDATE` / `DELETE` の危険さを説明できる
- `BEGIN` / `COMMIT` / `ROLLBACK` で「失敗してもやり直せる」操作ができる

**所要時間の目安: 90〜120 分**

## 3.2 前提知識: リレーショナルDBとSQL

手を動かす前に、言葉の整理だけしておきましょう。
難しい理屈は後回しで、「何のことか」がわかれば十分です。

!!! note "リレーショナルデータベースとは"
    **リレーショナルデータベース**（RDB）は、データを **表（テーブル）** の形で
    管理するデータベースです。PostgreSQL はその代表的な製品のひとつです。

    イメージは「厳格なスプレッドシート」です。

    - **テーブル**: データを入れる表そのもの（例: `todos`）。列の名前と型を先に決めておく
    - **行（レコード）**: データ 1 件分（例: 「牛乳を買う」という ToDo 1 件）
    - **列（カラム）**: 項目（例: `title`、`done`）。各列には型があり、
      `title` に日付を入れるような混在は許されない

    スプレッドシートと違うのは、この「型の決まり」をデータベース側が強制してくれる点です。
    おかしなデータが紛れ込むのを入口で止めてくれるので、アプリから安心して使えます。

!!! note "SQL と psql の関係"
    **SQL** は、リレーショナルデータベースへの指示を書くための**言語**です。
    `SELECT`（読む）や `INSERT`（追加する）といった文が SQL です。

    **psql** は、その SQL を PostgreSQL に送るための**コマンドラインツール**です。
    第0章で接続確認に使ったものです。psql 以外の道具（この研修では第5章以降の Python コード）から
    送る SQL も、中身はまったく同じ言語です。

    なお、`\dt` や `\q` のように `\` から始まるものは SQL ではなく、
    **psql 独自のメタコマンド**（便利なショートカット）です。
    Python のコードからは使えないもの、と区別しておいてください。

SQL は大きく 2 種類に分かれます。この分類を意識しておくと、
「今は器を作っているのか、中身をいじっているのか」が整理できます。

- **DDL**（Data Definition Language）: テーブルの**形**を定義する。
  `CREATE TABLE`（作る）/ `ALTER TABLE`（変える）/ `DROP TABLE`（消す）
- **DML**（Data Manipulation Language）: テーブルの**中身**を操作する。
  `INSERT`（追加）/ `SELECT`（参照）/ `UPDATE`（更新）/ `DELETE`（削除）

この章では DDL から `CREATE TABLE` を、DML は 4 つすべてを扱います。

## 3.3 psql の基本操作

### 起動と終了

まず、第0章で作った PostgreSQL コンテナが動いているか確認します。
動いていなければ起動してください。

```bash
docker compose up -d
```

期待される出力（すでに起動済みの場合）:

```text
[+] Running 1/1
 ✔ Container webapp-training-db  Running
```

psql で接続します。第0章と同じ、2 つの方法のどちらでも構いません。

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb
    ```

    パスワードを聞かれたら `todo` と入力します（入力中は画面に何も表示されません）。

=== "コンテナの中で psql を使う"

    ```bash
    docker exec -it webapp-training-db psql -U todo -d tododb
    ```

期待される出力:

```text
psql (16.x)
Type "help" for help.

tododb=#
```

最後の行の **`tododb=#`** が psql のプロンプトです。
「`tododb` というデータベースに接続中ですよ」という意味で、
ここに SQL を打ち込んで Enter を押すと実行されます。

終了するときは `\q` です。SQL ではなく psql のメタコマンドなので、セミコロンは付けません。

```text
\q
```

（何も表示されず、元のターミナルに戻ります）

### SQL はセミコロンで実行される

psql では、**セミコロン（`;`）を打って Enter を押した時点**で SQL が実行されます。
試しに、接続中のデータベース名と現在時刻を聞いてみましょう。

```sql
SELECT current_database(), now();
```

期待される出力（時刻は実行したタイミングのものになります）:

```text
 current_database |              now              
------------------+-------------------------------
 tododb           | 2026-08-09 01:56:06.835046+09
(1 row)
```

セミコロンを忘れて Enter を押すと、文がまだ続いていると判断されて
プロンプトが `tododb=#` から **`tododb-#`** に変わり、実行されずに待たされます。
この状態に迷い込んだときの対処は「つまずきポイント」を参照してください。

### テーブルを眺めるメタコマンド

この章でよく使うメタコマンドは次の 2 つです。

- `\dt` … テーブルの**一覧**を表示する
- `\d テーブル名` … そのテーブルの**構造**（列・型・制約）を表示する

いまはテーブルが 1 つもないはずです。試しに `\dt` を打ってみましょう。

```text
\dt
```

期待される出力:

```text
Did not find any relations.
```

この表示で正解です。次の節でテーブルを作ったあと、もう一度 `\dt` を打つと表示が変わるはずです。

## 3.4 テーブルを作る（CREATE TABLE）

ToDo を保存するテーブルを作ります。
[`CREATE TABLE`](https://www.postgresql.org/docs/current/sql-createtable.html) 文で、
列の名前・型・制約をまとめて宣言します。次の SQL を psql に打ち込んでください
（複数行に分かれていても、最後の `;` を打って Enter するまで実行されません）。

```sql
CREATE TABLE todos (
    id          SERIAL PRIMARY KEY,
    title       TEXT        NOT NULL,
    done        BOOLEAN     NOT NULL DEFAULT FALSE,
    due_on      DATE,
    priority    SMALLINT    NOT NULL DEFAULT 2,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

期待される出力:

```text
CREATE TABLE
```

`CREATE TABLE` と返ってくれば成功です。エラーメッセージが出た場合は、
打ち間違いがないか（綴り・カンマ・カッコ）を確認してください。

これで「before」→「after」でいうと、テーブルが 0 個から 1 個になりました。
`\dt` で確認してみます。

```text
\dt
```

期待される出力:

```text
       List of relations
 Schema | Name  | Type  | Owner 
--------+-------+-------+-------
 public | todos | table | todo
(1 row)
```

さっきまで `Did not find any relations.` だった一覧に、`todos` が現れました。
次に `\d todos` で構造を見てみます。

```text
\d todos
```

期待される出力:

```text
                                       Table "public.todos"
   Column   |           Type           | Collation | Nullable |              Default              
------------+--------------------------+-----------+----------+-----------------------------------
 id         | integer                  |           | not null | nextval('todos_id_seq'::regclass)
 title      | text                     |           | not null | 
 done       | boolean                  |           | not null | false
 due_on     | date                     |           |          | 
 priority   | smallint                 |           | not null | 2
 created_at | timestamp with time zone |           | not null | now()
 updated_at | timestamp with time zone |           | not null | now()
Indexes:
    "todos_pkey" PRIMARY KEY, btree (id)
```

宣言したとおりの列が並んでいるのがわかります。
この定義で覚えておきたいポイントは 4 つです。

- **`SERIAL`** は「自動採番される整数」のショートカットです。内部では専用の連番カウンター
  （シーケンス）が作られ、`INSERT` で値を省略すると自動で次の番号が割り当てられます。
  `\d` の出力で `id` の `Default` が `nextval('todos_id_seq'::regclass)` になっているのが
  その印です。自分で「今の最大値+1」を計算するコードを書かずに済み、
  複数人が同時に `INSERT` しても番号が衝突しません。
  新しめの PostgreSQL では `GENERATED ALWAYS AS IDENTITY` を推奨することもありますが、
  研修ではわかりやすい `SERIAL` を使います。
- **`NOT NULL`** は「この列は空にしてはいけない」という[制約](https://www.postgresql.org/docs/current/ddl-constraints.html)です。
  `title` を入れ忘れた `INSERT` を DB 側がエラーで止めてくれます。アプリ側のチェックだけに
  頼ると、バグや別経路からの書き込みで空データが紛れ込むことがあるため、
  DB にも「最後の砦」として制約を持たせておくと安心です。
- **`DEFAULT`** は「`INSERT` で省略されたときに自動で入る値」です。
  `done`（`false`）や `priority`（`2`）、`created_at`（`now()` = 現在時刻）に付いているので、
  これらは `INSERT` のたびに明示しなくても埋まります。`NOT NULL` と `DEFAULT` は両方書くのが基本です。
- **`PRIMARY KEY`** は「行を一意に特定するための列」の宣言です。`id` が主キーなので、
  「`id = 3` の ToDo」と指定すれば必ず 1 行に絞れます。主キーには自動的にインデックス
  （高速な検索のための仕組み）が張られ、あとで扱う `UPDATE` / `DELETE` で
  「狙った 1 行だけ」を確実に指定するための土台になります。

型については、使ったものだけざっくり押さえておけば十分です。

| 型 | 用途 |
|---|---|
| `TEXT` | 長さ自由の文字列 |
| `BOOLEAN` | 真偽値（`TRUE` / `FALSE`） |
| `DATE` | 日付（`'2026-08-10'` のように書く） |
| `SMALLINT` | 小さな整数 |
| `TIMESTAMPTZ` | タイムゾーン付きの日時 |

!!! note "時刻は基本 TIMESTAMPTZ で"
    タイムゾーンを持たない `TIMESTAMP` という型もありますが、サーバーとクライアントで
    時刻の解釈が食い違ってズレる事故が起きやすいので、この研修では
    「時刻を保存するなら基本 `TIMESTAMPTZ`」と覚えておけば十分です。

## 3.5 行を増やす（INSERT）

作ったテーブルに、行を追加していきます。
まず 1 行ずつ、3 行入れてみましょう。

```sql
INSERT INTO todos (title) VALUES ('牛乳を買う');
INSERT INTO todos (title, due_on, priority) VALUES ('健康診断の予約', '2026-08-10', 1);
INSERT INTO todos (title, done) VALUES ('領収書の整理', TRUE);
```

期待される出力（3 回とも同じ表示です）:

```text
INSERT 0 1
```

`INSERT 0 1` の最後の数字が「追加された行数」です。1 行入ったので `1` です。

ここで注目してほしいのが、**指定していない列の扱い**です。
1 行目は `title` しか指定していませんが、`id` は `SERIAL` の自動採番、
`done` と `priority` と時刻 2 つは `DEFAULT` の値で自動的に埋まり、`due_on` は
何も指定されないので **`NULL`**（値がない、という特別な状態）になります。

また、`INSERT INTO todos (title, ...)` のように**カラム名を明示している**のもポイントです。
カラムを省略して `INSERT INTO todos VALUES (...)` と書くこともできますが、その場合は
テーブル定義の列順どおりに値を並べる必要があり、あとで誰かがカラムを増やしたり
順番を変えたりしたときに値がズレて壊れます。少し長くなっても、
カラム名を明示するほうが事故が少なく安全です。

複数行は、1 つの `INSERT` にまとめることもできます。

```sql
INSERT INTO todos (title, due_on) VALUES
    ('家賃を振り込む', '2026-08-25'),
    ('車検の見積もり', '2026-09-01'),
    ('週次の振り返り', '2026-08-09');
```

期待される出力:

```text
INSERT 0 3
```

今度は `INSERT 0 3` と、3 行入ったことがわかります。
まとめて書くと `INSERT` を 3 回発行するよりサーバーとの通信回数が減るので、
入れたい件数が多いほど効いてきます。

この時点で、テーブルの中身はこうなっているはずです（時刻の列は省略しています）。

```text
 id |     title      | done |   due_on   | priority 
----+----------------+------+------------+----------
  1 | 牛乳を買う     | f    |            |        2
  2 | 健康診断の予約 | f    | 2026-08-10 |        1
  3 | 領収書の整理   | t    |            |        2
  4 | 家賃を振り込む | f    | 2026-08-25 |        2
  5 | 車検の見積もり | f    | 2026-09-01 |        2
  6 | 週次の振り返り | f    | 2026-08-09 |        2
```

最後に、便利な `RETURNING` 句を試します。`INSERT` の末尾に付けると、
**今入れた行の値**をその場で返してくれます。

```sql
INSERT INTO todos (title) VALUES ('歯医者の予約') RETURNING id, created_at;
```

期待される出力（時刻と `id` は実行ごとに変わります）:

```text
 id |          created_at           
----+-------------------------------
  7 | 2026-08-09 01:56:06.835046+09
(1 row)

INSERT 0 1
```

自動採番された `id` がすぐわかるのがわかると思います。
`RETURNING` がないと「`INSERT` した直後にもう一度 `SELECT` して `id` を取得する」という
書き方をしがちですが、それだと 2 回の問い合わせの間に別の行が挿入されて、
狙った行を取り違えるおそれがあります。`RETURNING` なら 1 回の文で確実に取れます。
あとで Python から呼び出すときに、生成された `id` を取るのに使います。

## 3.6 行を読む（SELECT）

ここからは [`SELECT`](https://www.postgresql.org/docs/current/sql-select.html) です。
「どの列を」「どのテーブルから」「どんな条件で」取るかを指定します。

まず、入れたばかりの全行を見てみましょう。

```sql
SELECT id, title, done, due_on, priority FROM todos;
```

期待される出力:

```text
 id |     title      | done |   due_on   | priority 
----+----------------+------+------------+----------
  1 | 牛乳を買う     | f    |            |        2
  2 | 健康診断の予約 | f    | 2026-08-10 |        1
  3 | 領収書の整理   | t    |            |        2
  4 | 家賃を振り込む | f    | 2026-08-25 |        2
  5 | 車検の見積もり | f    | 2026-09-01 |        2
  6 | 週次の振り返り | f    | 2026-08-09 |        2
  7 | 歯医者の予約   | f    |            |        2
(7 rows)
```

`done` の列は `t` / `f`（`TRUE` / `FALSE` の表示）、`due_on` の空欄は `NULL` です。
なお、全カラムを取る `SELECT * FROM todos;` という書き方もありますが、
psql で自分の目で確認するだけならともかく、アプリのコードから呼ぶ `SELECT` では
**必要なカラムだけを明示する**のが基本です。`SELECT *` のままだと、あとでカラムを
追加したときに意図せず余分なデータまで取ってきたり、コードがどのカラムに依存して
いるのか読み取りにくくなったりします。この章でも、以降はカラムを明示して書きます。

### WHERE: 条件で絞る

`WHERE` で条件を付けると、合う行だけが返ります。
「完了していない ToDo」を取ってみましょう。

```sql
SELECT id, title, done FROM todos WHERE done = FALSE;
```

期待される出力:

```text
 id |     title      | done 
----+----------------+------
  1 | 牛乳を買う     | f
  2 | 健康診断の予約 | f
  4 | 家賃を振り込む | f
  5 | 車検の見積もり | f
  6 | 週次の振り返り | f
  7 | 歯医者の予約   | f
(6 rows)
```

`done` が `t` の行（`id = 3`）が消えて 6 行になりました。

### ORDER BY: 並び替える

`ORDER BY` で並び順を指定します。「期限が近い順に、期限が未設定のものは最後に」
という、ToDo アプリらしい並びにしてみます。

```sql
SELECT id, title, due_on, priority FROM todos ORDER BY due_on NULLS LAST, priority;
```

期待される出力:

```text
 id |     title      |   due_on   | priority 
----+----------------+------------+----------
  6 | 週次の振り返り | 2026-08-09 |        2
  2 | 健康診断の予約 | 2026-08-10 |        1
  4 | 家賃を振り込む | 2026-08-25 |        2
  5 | 車検の見積もり | 2026-09-01 |        2
  1 | 牛乳を買う     |            |        2
  3 | 領収書の整理   |            |        2
  7 | 歯医者の予約   |            |        2
(7 rows)
```

ポイントは 2 つです。

- カンマで区切ると複数の並びキーを指定できます。まず `due_on` の昇順、
  同じ `due_on` 同士では `priority` の順です
- `NULLS LAST` は「`NULL`（期限未設定）を最後に回す」指定です。
  PostgreSQL は昇順では `NULL` を最後に置くのがデフォルトですが、こうして明示して
  おくと「期限が近い順、未設定は後回し」という意図が読み手に伝わります

### LIKE / IN: あいまいな条件・複数の候補

```sql
SELECT id, title FROM todos WHERE title LIKE '%振%';
SELECT id, title, priority FROM todos WHERE priority IN (1, 2);
```

期待される出力（順に）:

```text
 id |     title      
----+----------------
  4 | 家賃を振り込む
  6 | 週次の振り返り
(2 rows)
```

```text
 id |     title      | priority 
----+----------------+----------
  1 | 牛乳を買う     |        2
  2 | 健康診断の予約 |        1
  3 | 領収書の整理   |        2
  4 | 家賃を振り込む |        2
  5 | 車検の見積もり |        2
  6 | 週次の振り返り |        2
  7 | 歯医者の予約   |        2
(7 rows)
```

- `LIKE` の `%` は「任意の 0 文字以上」にマッチするワイルドカードです
  （ちょうど 1 文字にマッチさせたいなら `_`）。`'%振%'` は「`振` をどこかに含む」の意味です
- `IN (1, 2)` は `priority = 1 OR priority = 2` の短縮形で、比較したい値が増えるほど
  `IN` のほうが読みやすくなります

### NULL の扱い: IS NULL / IS NOT NULL

期限が未設定（`NULL`）の行だけを取りたいときは、専用の書き方が必要です。

```sql
SELECT id, title, due_on FROM todos WHERE due_on IS NULL;
```

期待される出力:

```text
 id |    title     | due_on 
----+--------------+--------
  1 | 牛乳を買う   | 
  3 | 領収書の整理 | 
  7 | 歯医者の予約 | 
(3 rows)
```

逆は `IS NOT NULL` です。

```sql
SELECT id, title, due_on FROM todos WHERE due_on IS NOT NULL;
```

期待される出力:

```text
 id |     title      |   due_on   
----+----------------+------------
  2 | 健康診断の予約 | 2026-08-10
  4 | 家賃を振り込む | 2026-08-25
  5 | 車検の見積もり | 2026-09-01
  6 | 週次の振り返り | 2026-08-09
(4 rows)
```

!!! note "なぜ = NULL が使えないのか"
    `NULL` は「値がない」という特別な状態であって、他の値と等しいかどうかを比較できる
    普通の値ではありません。`due_on = NULL` と書くと、結果は `TRUE` にも `FALSE` にも
    ならず、常に「不明（UNKNOWN）」という第三の結果になります。`WHERE` 句は「不明」と
    判定された行を結果に含めないため、`= NULL` では**どんなデータでも 0 行**になります。
    エラーにもならず黙って 0 行が返るので、気づきにくいミスです。
    だから専用の `IS NULL` / `IS NOT NULL` を使う必要があります。

## 3.7 行を変える（UPDATE）・消す（DELETE）

### UPDATE で更新する

`id = 1` の ToDo を完了にしてみましょう。
ただし、`UPDATE` は失敗すると取り返しが付かないので、**`BEGIN` でトランザクションを
開始してから実行し、確認してから `COMMIT` する**形で進めます。

```sql
BEGIN;
UPDATE todos SET done = TRUE, updated_at = now() WHERE id = 1;
SELECT id, title, done FROM todos WHERE id = 1;
COMMIT;
```

期待される出力:

```text
BEGIN
UPDATE 1
 id |   title    | done 
----+------------+------
  1 | 牛乳を買う | t
(1 row)

COMMIT
```

読み方はこうです。

- `UPDATE 1` は「1 行が更新された」の意味です。`WHERE` に合った行数が出るので、
  思ったより多い（あるいは 0 行）だったら条件が違うサインです
- 直後の `SELECT` で、更新前（before）は `done = f` だった行が `t` に変わった
  （after）ことを確認してから `COMMIT` で確定しています

もし確認の時点で「違うな」と思ったら、`COMMIT` の代わりに `ROLLBACK;` と打てば、
`BEGIN` 以降の変更が全部なかったことになります。
psql は何もしなければ **1 文ごとに即座に確定（オートコミット）** するので、
「とりあえず `BEGIN` してから触る」だけで、間違いに気づいたときにやり直せる安全網になります。
[トランザクション](https://www.postgresql.org/docs/current/tutorial-transactions.html)の
詳しい仕組みは次章で扱います。

### DELETE で削除する（今回は取り消してみる）

完了済み（`done = TRUE`）の行を全部消す `DELETE` を試します。
ここではあえて、**実行したあとに `ROLLBACK` で取り消す**ところまでやってみましょう。
「消したけれど戻せる」ことを体験するのが目的です。

```sql
BEGIN;
DELETE FROM todos WHERE done = TRUE;
SELECT id, title, done FROM todos WHERE done = TRUE;
ROLLBACK;
SELECT id, title, done FROM todos WHERE done = TRUE;
```

期待される出力:

```text
BEGIN
DELETE 2
 id | title | done 
----+-------+------
(0 rows)

ROLLBACK
 id |    title     | done 
----+--------------+------
  3 | 領収書の整理 | t
  1 | 牛乳を買う   | t
(2 rows)
```

- `DELETE 2` で、完了済みの 2 行（before: `id = 1` と `id = 3`）が消え、
  直後の `SELECT` は `(0 rows)`（after）になりました
- `ROLLBACK` のあとに同じ `SELECT` を打つと、2 行が元どおり戻っています

このテーブルは第4章でも使うので、**ここでは `ROLLBACK` で元に戻しておいてください**。

!!! danger "WHERE を忘れると全行に効く"
    `UPDATE` と `DELETE` はどちらも `WHERE` で指定した行**だけ**に効きます。
    裏を返せば、`WHERE` を書き忘れるとテーブルの**全行**が対象になります。
    `UPDATE todos SET done = TRUE;` は全行が完了になり、`DELETE FROM todos;` は
    全行が消えます。`SELECT` で `WHERE` を忘れても「全部見える」だけで実害は
    ありませんが、`UPDATE` / `DELETE` では実データが書き換わったり消えたりします。
    実行後の `UPDATE 7` のような件数表示は、**毎回必ず目で確認**するクセを付けましょう。
    そして本番の DB を psql で触るときは、まず `BEGIN;` して、結果を `SELECT` で
    確認してから `COMMIT;` する習慣にしてください。

!!! note "テーブル自体を消したいときは DROP TABLE"
    練習用のテーブルごと消したいときは `DROP TABLE todos;` です。
    存在しないテーブルに対してはエラーになるので、何度実行しても安全にしたい
    スクリプトでは `DROP TABLE IF EXISTS todos;` のように `IF EXISTS` を付けるのが定石です。
    今は消さないでください。このテーブルは第4章以降でも使います
    （本格的に設計し直すのは第9章です）。

## 3.8 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] `psql` を起動・終了（`\q`）できる
- [ ] `\dt` でテーブル一覧、`\d todos` でテーブル構造を表示できた
- [ ] `CREATE TABLE` で `todos` を作り、`SERIAL` / `NOT NULL` / `DEFAULT` / `PRIMARY KEY` の意味を説明できる
- [ ] `INSERT` で行を追加し、`INSERT 0 1` のような件数表示を読めた。`RETURNING` で採番された `id` を取れた
- [ ] `SELECT` に `WHERE` / `ORDER BY` / `LIKE` / `IN` / `IS NULL` を付けて結果を絞れた
- [ ] `= NULL` が使えない理由を説明できる
- [ ] `BEGIN` → `UPDATE` → `SELECT` で確認 → `COMMIT`（または `ROLLBACK`）の流れで更新できた
- [ ] `WHERE` を忘れた `UPDATE` / `DELETE` が全行に効くことを説明できる

## 3.9 つまずきポイント

### セミコロンを忘れて実行されない

SQL を打って Enter しても、何も実行されずプロンプトがこう変わることがあります。

```text
tododb=# SELECT * FROM todos
tododb-# 
```

`=#` が `-#` に変わったら、**文がまだ終わっていない**（セミコロン待ち）という合図です。
そのまま `;` だけ打って Enter すれば実行されます。文自体をやめたいときは
`Ctrl` + `C` でキャンセルできます。

### `= NULL` で 0 行になる

```text
tododb=# SELECT id, title FROM todos WHERE due_on = NULL;
 id | title 
----+-------
(0 rows)
```

エラーにはなりませんが、期限が `NULL` の行があるのに 0 行しか返りません。
3.6 で説明したとおり、`NULL` との比較は `=` ではなく `IS NULL` を使います。

```sql
SELECT id, title FROM todos WHERE due_on IS NULL;
```

### 文字列をダブルクォートで囲んでしまう

```text
tododb=# INSERT INTO todos (title) VALUES ("牛乳");
ERROR:  column "牛乳" does not exist
LINE 1: INSERT INTO todos (title) VALUES ("牛乳");
                                          ^
```

SQL では、**文字列はシングルクォート（`'`）**で囲みます。
ダブルクォート（`"`）はテーブル名やカラム名などの「識別子」を囲む記号なので、
「`牛乳` というカラムなんてない」というエラーになります。
`'牛乳'` に直してください。

### psql に接続できない

```text
psql: error: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

PostgreSQL コンテナが起動していません。リポジトリのルートで
`docker compose up -d` を実行し、`docker compose ps` で `STATUS` が `Up` に
なっていることを確認してから接続し直してください。

## 3.10 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
すべて psql の中で実行します。ここで作った `todos` テーブル（7 行）が
入っている前提です。

### 問1 練習用の行を追加する

次の条件で 1 行 `INSERT` し、追加した行を `SELECT` で確認してください。

- `title` は `'練習用の行'`、`priority` は `3`
- `INSERT` には `RETURNING id` を付けて、採番された `id` を表示する
- 確認の `SELECT` は「`priority = 3` の行」を取る形にする

??? example "解答例"

    ```sql
    INSERT INTO todos (title, priority) VALUES ('練習用の行', 3) RETURNING id;
    SELECT id, title, priority FROM todos WHERE priority = 3;
    ```

    期待される出力（`id` は実行ごとに変わります）:

    ```text
     id 
    ----
      8
    (1 row)

    INSERT 0 1
     id |   title    | priority 
    ----+------------+----------
      8 | 練習用の行 |        3
    (1 row)
    ```

    `RETURNING id` の出力で採番された `id`（ここでは `8`）がわかり、
    直後の `SELECT` でその行がテーブルに入っていることを確認できました。

### 問2 未完了で優先度が 1 の ToDo を取る

「`done = FALSE` で、かつ `priority = 1`」の行の `id`、`title`、`priority` を
取る `SELECT` を書いてください。条件が 2 つあるときは `AND` でつなぎます。

??? example "解答例"

    ```sql
    SELECT id, title, priority FROM todos WHERE done = FALSE AND priority = 1;
    ```

    期待される出力:

    ```text
     id |     title      | priority 
    ----+----------------+----------
      2 | 健康診断の予約 |        1
    (1 row)
    ```

    `AND` は「両方の条件を満たす行」です。なお `OR` にすると
    「どちらか片方でも満たせばよい」になり、結果が大きく変わるので、
    日本語の条件文をどちらに翻訳すべきか立ち止まって考えるクセを付けましょう。

### 問3 期限が 1 週間以内の未完了 ToDo を取る

「未完了で、期限が今日から 7 日以内（`due_on <= current_date + 7`）」の行を、
期限が近い順に取る `SELECT` を書いてください。

- `current_date` は「今日の日付」を返す PostgreSQL の関数です
- 期限が `NULL` の行は条件に合わない（比較できない）ので、自動的に除かれます

??? example "解答例"

    ```sql
    SELECT id, title, due_on FROM todos
     WHERE done = FALSE AND due_on <= current_date + 7
     ORDER BY due_on;
    ```

    期待される出力（2026-08-09 に実行した場合の例。実行日によって結果は変わります）:

    ```text
     id |     title      |   due_on   
    ----+----------------+------------
      6 | 週次の振り返り | 2026-08-09
      2 | 健康診断の予約 | 2026-08-10
    (2 rows)
    ```

    `current_date + 7` のように、日付には整数を足して「何日後」を計算できます。
    データが日付で書き死にしていないので、いつ実行しても「今日から 1 週間」の
    意味になるのがポイントです。

### 問4 更新の before / after を確認する

`id = 2` の ToDo を完了（`done = TRUE`）に更新してください。
本文と同じく、`BEGIN` で始めて、**更新前と更新後の両方を `SELECT` で確認**してから
`COMMIT` してください。

??? example "解答例"

    ```sql
    BEGIN;
    SELECT id, title, done FROM todos WHERE id = 2;   -- before
    UPDATE todos SET done = TRUE, updated_at = now() WHERE id = 2;
    SELECT id, title, done FROM todos WHERE id = 2;   -- after
    COMMIT;
    ```

    期待される出力:

    ```text
    BEGIN
     id |     title      | done 
    ----+----------------+------
      2 | 健康診断の予約 | f
    (1 row)

    UPDATE 1
     id |     title      | done 
    ----+----------------+------
      2 | 健康診断の予約 | t
    (1 row)

    COMMIT
    ```

    before が `f`、after が `t` になっているのがわかります。
    `UPDATE 1` の件数表示で「1 行だけに効いた」ことも確認できました。
    件数が `0` なら `WHERE` の条件（ここでは `id = 2`）を間違えているサインです。

    なお、確認が終わったあと、第4章に向けて元に戻しておきたい場合は
    `UPDATE todos SET done = FALSE WHERE id = 2;` で戻せます（戻さなくても
    第4章の手順には影響しません）。

### 問5 練習用の行を消して後片付け

問1 で追加した行（`'練習用の行'`）を `DELETE` で消し、
消えたことを `SELECT` で確認してください。
問1 の `RETURNING` で返ってきた `id` を `WHERE` に使うのが確実です。

??? example "解答例"

    ```sql
    DELETE FROM todos WHERE id = 8;   -- 問1で返ってきた id に合わせる
    SELECT id, title FROM todos WHERE priority = 3;
    ```

    期待される出力:

    ```text
    DELETE 1
     id | title 
    ----+-------
    (0 rows)
    ```

    `DELETE 1` で 1 行だけ消え、確認の `SELECT` も `(0 rows)` になりました。
    `id` で指定したので、他の行にはまったく影響していません。
    「主キーで 1 行を指定して操作する」という、安全な更新・削除の基本形です。

## まとめ

- **リレーショナルDB** はデータを「テーブル（行と列）」で管理する。列には型があり、
  DB 側がデータの整合性を守ってくれる
- **SQL** は DB への指示を書く言語。**psql** はそれを対話的に打つ道具。
  `\dt` / `\d` / `\q` は SQL ではなく psql のメタコマンド
- **DDL** はテーブルの形を定義する SQL（`CREATE TABLE` など）、
  **DML** は中身を操作する SQL（`INSERT` / `SELECT` / `UPDATE` / `DELETE`）
- `INSERT` はカラム名を明示する。`INSERT 0 1` のような件数表示と `RETURNING` を活用する
- `SELECT` は `WHERE` で絞り、`ORDER BY` で並び替える。`NULL` の比較は `IS NULL`
- `UPDATE` / `DELETE` は `WHERE` を忘れると全行に効く。`BEGIN` → 実行 → `SELECT` で
  確認 → `COMMIT` / `ROLLBACK` の流れを習慣にする

この章で作った `todos` テーブルは消さずに残しておいてください。
次は [第4章 PostgreSQLのおさらい② JOIN・集約・トランザクション](04-postgres-join-tx.md) で、
このテーブルを題材に、複数テーブルの扱いやトランザクションの仕組みを掘り下げます。
