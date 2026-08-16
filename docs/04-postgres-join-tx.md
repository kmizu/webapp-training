# 第4章 PostgreSQLのおさらい② JOIN・集約・トランザクション

第3章では `todos` テーブル 1 つを相手に、作成・追加・参照・更新・削除をひととおり動かしました。
この章ではその続きとして、**まとめて数える（集約）**、**複数のテーブルをまたぐ（JOIN）**、
**複数の SQL をひとまとめに確定する（トランザクション）** の 3 つを自分の手で試します。

引き続き第3章で作った `todos` テーブル（7 行）を題材にします。
写して動かすたびに、実行結果を自分の画面で確認しながら進めてください。

## 4.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- `COUNT` などの集約関数と `GROUP BY` で「グループごとの件数」を取れる
- `FILTER (WHERE ...)` で「条件付きの件数」を 1 つのクエリで取れる
- 主キー・外部キーの役割を説明できる
- 中間テーブルを挟んだ多対多のテーブルを作り、`INNER JOIN` / `LEFT JOIN` を使い分けられる
- 複数の SQL を 1 つのトランザクションにまとめ、失敗時に `ROLLBACK` で全部取り消せる

**所要時間の目安: 90〜120 分**

## 4.2 前提知識: 主キー・外部キーとトランザクション

手を動かす前に、この章で使う概念を整理しておきましょう。

!!! note "主キーと外部キー"
    **主キー**（`PRIMARY KEY`）は「行を一意に特定するための列」です。
    第3章で `todos` の `id` に付けたもので、「`id = 3` の ToDo」と指定すれば
    必ず 1 行に絞れる、という土台でした。

    **外部キー**（`FOREIGN KEY`）は、「この列の値は、別のテーブルの主キーとして
    実在していなければならない」という[制約](https://www.postgresql.org/docs/current/ddl-constraints.html)です。
    たとえば「タグ付け」を保存するテーブルに `todo_id` という外部キーを持たせると、
    存在しない ToDo の `id`（たとえば `999`）を入れようとしたときに
    DB 側がエラーで止めてくれます。テーブル同士の「参照の辻褄が合っている」ことを
    DB に保証させる仕組みだと思ってください。

!!! note "トランザクションとは"
    **トランザクション**は、複数の SQL を **「ぜんぶ成功」か「ぜんぶ取り消し」** の
    どちらかにまとめる仕組みです。第3章で `BEGIN` → 実行 → `SELECT` で確認 →
    `COMMIT` / `ROLLBACK` の流れを体験したときに、すでに使っていました。

    トランザクションが持つ性質は、頭文字を取って **ACID** と呼ばれます。

    - **原子性**（Atomicity）: まとめた SQL は全部成功か、全部取り消しか、のどちらか
    - **一貫性**（Consistency）: 制約違反のまま確定されることはない
    - **独立性**（Isolation）: 同時に動く別のトランザクションの途中経過は見えない
    - **永続性**（Durability）: `COMMIT` した結果は障害が起きても消えない

    この章で実感してほしいのは主に**原子性**です。
    残りの 3 つも「そういう性質がある」程度の紹介に留めます。

## 4.3 準備: 前章のテーブルを確認する

PostgreSQL コンテナが動いていなければ起動し、psql で接続します
（手順は第3章と同じです）。

```bash
docker compose up -d
docker exec -it webapp-training-db psql -U todo -d tododb
```

（ホストに psql が入っているなら `psql -h localhost -p 5432 -U todo -d tododb` でも構いません）

第3章で作った `todos` テーブルが残っているか確認しましょう。

```sql
SELECT id, title, due_on, priority FROM todos ORDER BY id;
```

期待される出力:

```text
 id |     title      |   due_on   | priority 
----+----------------+------------+----------
  1 | 牛乳を買う     |            |        2
  2 | 健康診断の予約 | 2026-08-10 |        1
  3 | 領収書の整理   |            |        2
  4 | 家賃を振り込む | 2026-08-25 |        2
  5 | 車検の見積もり | 2026-09-01 |        2
  6 | 週次の振り返り | 2026-08-09 |        2
  7 | 歯医者の予約   |            |        2
(7 rows)
```

この 7 行が本章の出発点です。
第3章では問4の最後に `id = 2` を `done = FALSE` に戻す手順が必須になっているため、
ここまで順に進めていれば `done = TRUE` の行は `id = 3`（領収書の整理）だけの
はずです。行数が 7 行でない場合は、第3章の SQL で作り直してください。

## 4.4 集約: GROUP BY でまとめて数える

まずは「テーブル全体で何行あるか」を数えるところから。

```sql
SELECT COUNT(*) FROM todos;
```

期待される出力:

```text
 count 
-------
     7
(1 row)
```

`COUNT(*)` のように、**複数行の値を 1 つにまとめる関数**を**集約関数**と呼びます。
他にも `SUM`（合計）/ `AVG`（平均）/ `MAX`（最大）/ `MIN`（最小）があります。
詳しくは[集約関数の公式チュートリアル](https://www.postgresql.org/docs/current/tutorial-agg.html)を参照してください。

### GROUP BY でグループごとに集計する

集約関数だけだと「テーブル全体を 1 つのグループ」として集計します。
[`GROUP BY`](https://www.postgresql.org/docs/current/sql-select.html) を付けると、
指定した列の値が同じ行どうしをグループにまとめ、**グループごとに別々に集計**します。
優先度ごとの件数を数えてみましょう。

```sql
SELECT priority, COUNT(*) AS n
  FROM todos
 GROUP BY priority
 ORDER BY priority;
```

期待される出力:

```text
 priority | n 
----------+---
        1 | 1
        2 | 6
(2 rows)
```

「`priority = 1` が 1 件、`priority = 2` が 6 件」と、さっきの 7 行が
グループごとの件数に集約されました。

ここで大事なルールが 1 つあります。`GROUP BY` を使うクエリで `SELECT` に書いていいのは、
**「`GROUP BY` に書いた列」か「集約関数の中」**のどちらかだけです。
たとえば `title` をそのまま `SELECT` しようとするとエラーになります。

```sql
SELECT title, COUNT(*) FROM todos GROUP BY priority;
```

期待される出力（エラー）:

```text
ERROR:  column "todos.title" must appear in the GROUP BY clause or be used in an aggregate function
LINE 1: SELECT title, COUNT(*) FROM todos GROUP BY priority;
               ^
```

同じ `priority` のグループには複数の `title` が含まれているので、
「そのグループの `title`」は 1 つに決まらない——だから止めてくれる、という理屈です。

### FILTER で条件付きの件数を数える

「期限が設定されている件数」と「未設定の件数」を、1 つのクエリで並べて取りたいときは
`FILTER (WHERE ...)` が便利です。

```sql
SELECT
    COUNT(*) FILTER (WHERE due_on IS NOT NULL) AS with_due,
    COUNT(*) FILTER (WHERE due_on IS NULL)     AS without_due,
    COUNT(*)                                   AS total
FROM todos;
```

期待される出力:

```text
 with_due | without_due | total 
----------+-------------+-------
        4 |           3 |     7
(1 row)
```

`FILTER (WHERE ...)` は「集約関数ごとに集計対象の条件を変える」書き方です。
これを使わないと `COUNT(CASE WHEN due_on IS NOT NULL THEN 1 END)` のように書く必要があり、
条件が増えるほど読みにくくなります。`FILTER` は標準 SQL の書き方で、
PostgreSQL はもちろん対応しているので、こちらを使うのがおすすめです。

## 4.5 JOIN: タグで ToDo を分類する

ここからが本章の山場です。ToDo に「タグ」を付けられるようにして、
複数のテーブルをまたいだ検索（**JOIN**）を体験します。
本格的なテーブル設計は第9章でやりますが、ここでは JOIN の感覚をつかむのが目的です。

### なぜテーブルを分けるのか

1 つの ToDo に複数のタグを付けられて、1 つのタグも複数の ToDo で使い回せる——
これは**多対多（many-to-many）**の関係です。`todos` にタグの列を直接足す方法だと
「タグは 1 つまで」に制限されてしまいます。

そこで、既存の `todos` に次の 2 つのテーブルを足して表現します。

- `tags` … タグそのものの一覧
- `todo_tags` … 「どの ToDo に、どのタグが付いているか」の対応表（**中間テーブル**）

`todos`（既存。抜粋）:

| id | title |
|---:|---|
| 1 | 牛乳を買う |
| 2 | 健康診断の予約 |
| ... | ... |

`todo_tags`（中間テーブル）:

| todo_id | tag_id |
|---:|---:|
| 1 | 1 |
| 2 | 3 |

`tags`:

| id | name |
|---:|---|
| 1 | 家事 |
| 2 | 仕事 |
| 3 | 健康 |

なお、3 つの表で**行の縦の並び位置に対応関係はありません**。
「どの ToDo にどのタグか」の対応は、`todo_tags` の行が持つ値
（`todo_id` と `tag_id` の組）だけが表しています。
「`todos` の `id`」と「`tags` の `id`」の**組**を中間テーブルに持つ、という形です。
この形にしておけば、1 つの ToDo にタグをいくつ付けても、
1 つのタグをいくつの ToDo に付けても対応できます。

### tags と todo_tags を作る

```sql
CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE todo_tags (
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
);
```

期待される出力（2 回とも同じ表示です）:

```text
CREATE TABLE
```

`todo_tags` の定義には、新しい指定が 3 つ出てきました。

- **`REFERENCES todos(id)`** が外部キー制約です。`todo_tags` に、存在しない
  `todo_id` や `tag_id` を挿入できないようにして、参照先が必ず実在することを保証します
- **`ON DELETE CASCADE`** は、参照先（`todos` や `tags`）の行を消したときに、
  対応する `todo_tags` の行も自動で消してくれる設定です。付けなくても外部キー制約は
  働くので「存在しない ToDo を指すタグ付け」が作られることはありませんが、そのぶん
  **タグが付いている ToDo を消そうとすると外部キー違反でエラー**になり、
  先に `todo_tags` の行を消す後片付けが必要になります。`ON DELETE CASCADE` を
  付けておくと、その後片付けを DB が自動でやってくれます
- **`PRIMARY KEY (todo_id, tag_id)`** のように複数列の組を主キーにする（**複合主キー**）と、
  「同じ ToDo に同じタグを二重に付ける」ことを防げます

データを入れましょう。

```sql
INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康');

INSERT INTO todo_tags (todo_id, tag_id) VALUES
    (1, 1),  -- 牛乳を買う → 家事
    (4, 1),  -- 家賃を振り込む → 家事
    (2, 3),  -- 健康診断の予約 → 健康
    (7, 3);  -- 歯医者の予約 → 健康
```

期待される出力（順に）:

```text
INSERT 0 3
INSERT 0 4
```

### INNER JOIN: マッチする行だけを結合する

いよいよ JOIN です。`todo_tags` の各行について、
「`todo_id` に対応する `todos` の行」と「`tag_id` に対応する `tags` の行」を
見つけて横にくっつける、というのが JOIN の動作です。

```sql
SELECT t.id, t.title, g.name AS tag
  FROM todos t
  JOIN todo_tags tt ON tt.todo_id = t.id
  JOIN tags g ON g.id = tt.tag_id
 ORDER BY t.id;
```

期待される出力:

```text
 id |     title      | tag  
----+----------------+------
  1 | 牛乳を買う     | 家事
  2 | 健康診断の予約 | 健康
  4 | 家賃を振り込む | 家事
  7 | 歯医者の予約   | 健康
(4 rows)
```

読み解き方はこうです。

- `FROM todos t` の `t` は**別名（エイリアス）**です。`todos` をこのクエリの中では
  `t` と呼ぶ、という宣言で、長いテーブル名を何度も書かずに済みます
- `JOIN todo_tags tt ON tt.todo_id = t.id` は「`todo_tags` を、
  `todo_id` が `todos` の `id` と等しい行どうしで結合する」という指定です
- 同様に `JOIN tags g ON g.id = tt.tag_id` で、タグの名前もくっつけています

結果が **4 行**なのに注目してください。`todos` は 7 行ありますが、
タグが付いているのは 4 件だけなので、`JOIN`（= `INNER JOIN`）では
**両方のテーブルにマッチする行だけ**が返り、タグなしの ToDo（`id = 3, 5, 6`）は
結果に現れません。

表で見ると、こういうイメージです（`todo_tags` の `(1, 1)` の行を例に）。

| todo_tags | → todos で `id = 1` を探す | → tags で `id = 1` を探す | 結果の行 |
|---|---|---|---|
| `todo_id = 1, tag_id = 1` | 牛乳を買う | 家事 | `1, 牛乳を買う, 家事` |

`todo_id = 3`（領収書の整理）のような行は `todo_tags` に存在しないので、
結合のしようがなく、結果から外れます。

### LEFT JOIN: 左側の行をすべて残す

「タグが付いていない ToDo も含めて、全部の ToDo を一覧したい」こともよくあります。
そのときは **`LEFT JOIN`** を使います。

```sql
SELECT t.id, t.title, g.name AS tag
  FROM todos t
  LEFT JOIN todo_tags tt ON tt.todo_id = t.id
  LEFT JOIN tags g ON g.id = tt.tag_id
 ORDER BY t.id;
```

期待される出力:

```text
 id |     title      | tag  
----+----------------+------
  1 | 牛乳を買う     | 家事
  2 | 健康診断の予約 | 健康
  3 | 領収書の整理   | 
  4 | 家賃を振り込む | 家事
  5 | 車検の見積もり | 
  6 | 週次の振り返り | 
  7 | 歯医者の予約   | 健康
(7 rows)
```

今度は 7 行すべてが返りました。`LEFT JOIN` は
**左側のテーブル（ここでは `todos`）の行を必ずすべて残し**、
マッチする右側の行がなければ右側の列を `NULL`（空欄）で埋めます。

!!! note "JOIN の種類の使い分け"
    - **`INNER JOIN`**（単に `JOIN` と書いても同じ）: 両方にマッチする行だけを返す。
      「タグが付いている ToDo だけ見たい」ときはこちら
    - **`LEFT JOIN`**（正式には `LEFT OUTER JOIN`）: 左側の行をすべて残し、
      マッチがなければ右側を `NULL` で埋める。「タグの有無に関わらず全 ToDo を
      一覧したい」ときはこちら
    - 逆に右側を必ず残す `RIGHT JOIN`、両方を残す `FULL JOIN` もありますが、
      実務で使われるのは `INNER JOIN` と `LEFT JOIN` の 2 つが大半です

    どの JOIN も「結合条件（`ON` の後ろ）にマッチする行の組み合わせを作る」点は共通で、
    **マッチしなかった行をどう扱うか**だけが違います。
    詳しくは[テーブル式（結合）の公式ドキュメント](https://www.postgresql.org/docs/current/queries-table-expressions.html)を参照してください。

### タグを 1 行にまとめる（string_agg）

`LEFT JOIN` の結果のままだと、1 つの ToDo にタグが 2 つ付くと行が 2 行にわかれます。
「1 ToDo = 1 行で、タグはカンマ区切りで並べたい」という形にするには、
`GROUP BY` と集約関数 `string_agg` を組み合わせます。

```sql
SELECT t.id, t.title, COALESCE(string_agg(g.name, ', '), '') AS tags
  FROM todos t
  LEFT JOIN todo_tags tt ON tt.todo_id = t.id
  LEFT JOIN tags g ON g.id = tt.tag_id
 GROUP BY t.id
 ORDER BY t.id;
```

期待される出力:

```text
 id |     title      | tags 
----+----------------+------
  1 | 牛乳を買う     | 家事
  2 | 健康診断の予約 | 健康
  3 | 領収書の整理   | 
  4 | 家賃を振り込む | 家事
  5 | 車検の見積もり | 
  6 | 週次の振り返り | 
  7 | 歯医者の予約   | 健康
(7 rows)
```

- `string_agg(g.name, ', ')` は、グループ内のタグ名を `', '` で連結する集約関数です
- タグが 1 つもない行は `string_agg` の結果が `NULL` になるので、
  `COALESCE(..., '')` で「最初の `NULL` でない値」を取る形にして空文字に置き換えています
- `GROUP BY t.id` だけで `t.title` も `SELECT` できているのは、`id` が `todos` の
  主キーで `title` を一意に決められることを PostgreSQL が理解しているためです
  （他の DB 製品では `GROUP BY t.id, t.title` と全列書く必要がある場合もあります）

## 4.6 トランザクション: まとめて成功、まとめて取り消し

最後にトランザクションです。第3章では「失敗してもやり直せる安全網」として
`BEGIN` → 実行 → `SELECT` で確認 → `COMMIT` / `ROLLBACK` の流れを練習しました。
この章ではもう 1 つの役割、**複数の SQL を「ぜんぶ成功か、ぜんぶ取り消しか」に
まとめる**ことを体験します。

### 2 つの INSERT を 1 つにまとめる

「新しいタグを追加して、同時に ToDo に紐付ける」という操作を考えます。
これは `tags` への `INSERT` と `todo_tags` への `INSERT` の **2 文で 1 つの操作**です。

```sql
BEGIN;
INSERT INTO tags (name) VALUES ('買い物') RETURNING id;
INSERT INTO todo_tags (todo_id, tag_id) VALUES (3, 4);
SELECT t.title, g.name AS tag
  FROM todos t
  JOIN todo_tags tt ON tt.todo_id = t.id
  JOIN tags g ON g.id = tt.tag_id
 WHERE t.id = 3;
COMMIT;
```

期待される出力:

```text
BEGIN
 id 
----
  4
(1 row)

INSERT 0 1
INSERT 0 1
    title     |  tag   
--------------+--------
 領収書の整理 | 買い物
(1 row)

COMMIT
```

`RETURNING id` で採番されたタグの `id`（ここでは `4`）を受け取り、
その番号を続く `todo_tags` への `INSERT` に使っています。
確認の `SELECT` で「領収書の整理」に「買い物」が付いたことを見てから
`COMMIT` で確定しました。

### 失敗したら全部取り消される

では、2 文目が失敗したらどうなるでしょうか。わざと失敗させてみます。
存在しない `todo_id = 999` に紐付けようとして、外部キー違反を起こします。

```sql
BEGIN;
INSERT INTO tags (name) VALUES ('読書') RETURNING id;
INSERT INTO todo_tags (todo_id, tag_id) VALUES (999, 5);  -- 5 は上の RETURNING で返った「読書」の id
SELECT id, name FROM tags WHERE name = '読書';
ROLLBACK;
SELECT id, name FROM tags WHERE name = '読書';
```

期待される出力:

```text
BEGIN
 id 
----
  5
(1 row)

INSERT 0 1
ERROR:  insert or update on table "todo_tags" violates foreign key constraint "todo_tags_todo_id_fkey"
DETAIL:  Key (todo_id)=(999) is not present in table "todos".
ERROR:  current transaction is aborted, commands ignored until end of transaction block
ROLLBACK
 id | name 
----+------
(0 rows)
```

重要なことが 2 つ起きています。

1. `todo_tags` への `INSERT` が外部キー違反で失敗したあと、
   そのトランザクションは**中断（aborted）状態**になり、続けて打った `SELECT` も
   `current transaction is aborted` というエラーで拒否されました。
   こうなったら `ROLLBACK`（または `COMMIT` でも結果はロールバック）で
   終了させるしかありません
2. `ROLLBACK` のあとに `tags` を確認すると、**1 文目の `INSERT` も
   なかったことになっています**（`読書` が 0 行）

これが**原子性**です。トランザクションで囲んでいなければ、
「どの ToDo にも紐付いていない `読書` タグ」だけが中途半端に残るところでした。
囲んでおけば、途中で失敗したときに中途半端な状態ごと取り消せます。
詳しくは[トランザクションの公式チュートリアル](https://www.postgresql.org/docs/current/tutorial-transactions.html)を参照してください。

!!! note "連番はロールバックされない"
    上の例で `読書` に割り当てられた `id = 5` は、ロールバックしても
    **欠番になり、次に `INSERT` するタグは `id = 6`** になります。
    `SERIAL` の連番カウンター（シーケンス）はトランザクションの対象外で、
    「いったん進んだ番号は戻らない」のが仕様です。同時に動く別の人の `INSERT` と
    衝突しないようにするための設計なので、`id` に欠番ができても問題ありません。
    「`id` は連番のまま並んでいるはず」と仮定したコードは書かないようにしましょう。

!!! tip "Web アプリではトランザクションが必須"
    たとえば「ToDo を作って、同時にタグを付ける」ような操作では、
    片方だけ成功してもう片方が失敗すると**データの整合性が壊れます**。
    Python から複数の SQL を投げる場合も、必ずトランザクションで包むのが基本です。
    その実践は [第6章 プレースホルダとトランザクション](06-psycopg-tx.md) で扱います。

## 4.7 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] `COUNT(*)` で全件数を数えられた
- [ ] `GROUP BY` でグループごとの件数を取れた。`GROUP BY` にない列をそのまま
      `SELECT` するとエラーになる理由を説明できる
- [ ] `FILTER (WHERE ...)` で条件付きの件数を 1 クエリで取れた
- [ ] 外部キー制約（`REFERENCES`）の役割を説明できる
- [ ] 中間テーブル（`todo_tags`）で多対多を表現する仕組みを説明できる
- [ ] `INNER JOIN` と `LEFT JOIN` の結果の違い（タグなしの ToDo の出方）を説明できる
- [ ] 複数の SQL を 1 つのトランザクションにまとめ、失敗時に `ROLLBACK` で
      全部取り消されることを確認できた
- [ ] トランザクションが中断状態になったら `ROLLBACK` で終了させることを知っている

## 4.8 つまずきポイント

### GROUP BY にない列を SELECT してしまう

```text
tododb=# SELECT title, COUNT(*) FROM todos GROUP BY priority;
ERROR:  column "todos.title" must appear in the GROUP BY clause or be used in an aggregate function
```

「`title` はグループ（`priority`）ごとに 1 つに決まらない」というエラーです。
`GROUP BY` に書いた列だけを `SELECT` に書くか、集約関数で 1 つにまとめてください。

### 外部キー違反で INSERT できない

```text
ERROR:  insert or update on table "todo_tags" violates foreign key constraint "todo_tags_todo_id_fkey"
DETAIL:  Key (todo_id)=(999) is not present in table "todos".
```

`todo_tags` に入れようとした `todo_id`（や `tag_id`）が、参照先のテーブルに
存在しないというエラーです。`DETAIL` の行に、問題になった値が書かれています。
先に `SELECT id FROM todos;` で実在する `id` を確認してください。

### エラーのあと、何を打ってもエラーになる

```text
ERROR:  current transaction is aborted, commands ignored until end of transaction block
```

トランザクションの中でエラーが起きると、それ以降の SQL は全部このエラーで
拒否されます。「`ROLLBACK;` を打ってもエラーになるのでは？」と思うかもしれませんが、
`ROLLBACK`（と `COMMIT`）だけは受け付けられるので、まず `ROLLBACK;` で
トランザクションを終了させてからやり直してください。

## 4.9 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
すべて psql の中で実行します。本文を最後まで（「買い物」タグの追加まで）
進めた状態が前提です。

### 問1 優先度ごとの「期限あり」の件数

優先度ごとに、**全体の件数**と**期限が設定されている件数**を並べて取る
`SELECT` を書いてください（`GROUP BY` と `FILTER` を使います）。

??? example "解答例"

    ```sql
    SELECT priority,
           COUNT(*)                                   AS total,
           COUNT(*) FILTER (WHERE due_on IS NOT NULL) AS with_due
      FROM todos
     GROUP BY priority
     ORDER BY priority;
    ```

    期待される出力:

    ```text
     priority | total | with_due 
    ----------+-------+----------
            1 |     1 |        1
            2 |     6 |        3
    (2 rows)
    ```

    `COUNT(*)` と `COUNT(*) FILTER (...)` を並べると、「全体」と「条件付き」を
    1 回の集計で比較できます。`priority = 2` の 6 件中、期限ありは 3 件
    （`id = 4, 5, 6`）ということが読み取れます。

### 問2 特定のタグが付いた ToDo だけを取る

「`健康`」タグが付いている ToDo の `id` と `title` を取る `SELECT` を
書いてください。JOIN に `WHERE` で条件を付けます。

??? example "解答例"

    ```sql
    SELECT t.id, t.title
      FROM todos t
      JOIN todo_tags tt ON tt.todo_id = t.id
      JOIN tags g ON g.id = tt.tag_id
     WHERE g.name = '健康'
     ORDER BY t.id;
    ```

    期待される出力:

    ```text
     id |     title      
    ----+----------------
      2 | 健康診断の予約
      7 | 歯医者の予約
    (2 rows)
    ```

    「タグで絞りたい」だけなら、タグなしの ToDo を残す必要がないので
    `INNER JOIN`（単に `JOIN`）で十分です。`WHERE g.name = '健康'` を
    `LEFT JOIN` のクエリに付けると、タグなしの行（`tag` が `NULL`）は
    条件に合わずに除外されて `INNER JOIN` と同じ結果になるので、
    両者の違いが `WHERE` の条件で消えてしまう点に注意してください。

### 問3 トランザクションでタグ追加と紐付けをまとめる

新しいタグ「`勉強`」を追加し、「週次の振り返り」（`id = 6`）に紐付けてください。
**2 つの `INSERT` を 1 つのトランザクションにまとめ**、確認の `SELECT` を
してから `COMMIT` してください。`RETURNING id` で返ってきた番号を
2 つ目の `INSERT` に使います。

??? example "解答例"

    ```sql
    BEGIN;
    INSERT INTO tags (name) VALUES ('勉強') RETURNING id;
    INSERT INTO todo_tags (todo_id, tag_id) VALUES (6, 6);  -- RETURNING の id に合わせる
    SELECT t.title, g.name AS tag
      FROM todos t
      JOIN todo_tags tt ON tt.todo_id = t.id
      JOIN tags g ON g.id = tt.tag_id
     WHERE t.id = 6;
    COMMIT;
    ```

    期待される出力（`id` は本文の手順どおり進めた場合の値です）:

    ```text
    BEGIN
     id 
    ----
      6
    (1 row)

    INSERT 0 1
    INSERT 0 1
         title      | tag  
    ----------------+------
     週次の振り返り | 勉強
    (1 row)

    COMMIT
    ```

    本文の失敗例でロールバックした「`読書`」が `id = 5` を消費しているので、
    `勉強` には `id = 6` が割り当てられます（4.6 の「連番はロールバックされない」
    を参照）。`RETURNING id` の出力を見てから次の `INSERT` に進めば、
    番号を当て推量で書く必要はありません。

### 問4 タグごとの ToDo 件数

タグごとに「そのタグが付いている ToDo の件数」を取る `SELECT` を書いてください。
**どの ToDo にも使われていないタグも 0 件として表示**するのがポイントです。

??? example "解答例"

    ```sql
    SELECT g.name AS tag, COUNT(tt.todo_id) AS n
      FROM tags g
      LEFT JOIN todo_tags tt ON tt.tag_id = g.id
     GROUP BY g.id
     ORDER BY n DESC, g.id;
    ```

    期待される出力（問3 まで済ませた状態の例）:

    ```text
      tag   | n 
    --------+---
     家事   | 2
     健康   | 2
     買い物 | 1
     勉強   | 1
     仕事   | 0
    (5 rows)
    ```

    「タグを全部残す」ので、今度は `tags` を左側に置いた `LEFT JOIN` です。
    `COUNT(*)` ではなく `COUNT(tt.todo_id)` と列を指定しているのは、
    `COUNT(列名)` が **`NULL` を数えない**からです。使われていない「`仕事`」タグの
    行は `tt.todo_id` が `NULL` なので、正しく `0` と数えられます
    （`COUNT(*)` にすると `1` になってしまうので注意）。

### 問5 後片付け（任意）

この章で作った `tags` と `todo_tags` は練習用なので、消してしまって構いません
（次章以降は `todos` だけを使います）。**`todos` は残したまま**、2 つのテーブルを
`DROP TABLE` で消し、`\dt` で確認してください。
なお、消さずに残しておいても以降の章には影響しません。

??? example "解答例"

    ```sql
    DROP TABLE todo_tags;
    DROP TABLE tags;
    ```

    ```text
    \dt
    ```

    期待される出力（順に）:

    ```text
    DROP TABLE
    DROP TABLE
    ```

    ```text
           List of relations
     Schema | Name  | Type  | Owner 
    --------+-------+-------+-------
     public | todos | table | todo
    (1 row)
    ```

    外部キーで `todo_tags` が `tags` を参照しているため、消す順番は
    `todo_tags` → `tags` の順になります（先に `tags` を消そうとすると
    「参照されています」というエラーになります）。
    `\dt` の一覧に `todos` だけが残っていれば OK です。

## まとめ

- **集約関数**（`COUNT` / `SUM` / `AVG` / `MAX` / `MIN`）は複数行を 1 つにまとめる。
  `GROUP BY` を付けるとグループごとに集計できる。`SELECT` に書いていいのは
  「`GROUP BY` の列」か「集約関数の中」だけ
- `FILTER (WHERE ...)` で「条件付きの件数」を 1 クエリで取れる
- **外部キー**（`REFERENCES`）は参照先の実在を DB が保証する制約。
  多対多は両側の `id` を持つ**中間テーブル**で表現する
- **JOIN** は結合条件にマッチする行の組み合わせを作る操作。`INNER JOIN` は
  マッチした行だけ、`LEFT JOIN` は左側の行を全部残して右側を `NULL` で埋める
- **トランザクション**は複数の SQL を「ぜんぶ成功か、ぜんぶ取り消しか」にまとめる
  （原子性）。エラーで中断状態になったら `ROLLBACK` で終了させる。
  連番（シーケンス）はロールバックされず欠番になる

ここまでで PostgreSQL のおさらいは終わりです。`todos` テーブルは消さずに残しておいてください。
次は [第5章 psycopg入門 接続と基本のCRUD](05-psycopg-basics.md) で、
**ここで書いた SQL を Python から実行する**入口に立ちます。
