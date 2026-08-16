# 付録A SQLチートシート

第3章・第4章で使った SQL を、構文別にいつでも引ける形でまとめました。
**PostgreSQL 16** を前提にしています。

## この付録の使い方

- 各項目は「構文 → 実行例 → 期待される出力」の順で並んでいます。
  psql で `tododb` に接続し（A.1 参照）、実行例をそのままコピペして試せます
- 実行例のデータは、第3章で作った `todos` テーブル（7 行、
  `done = TRUE` は `id = 3`「領収書の整理」のみ）と、
  第4章で作った `tags` / `todo_tags` が前提です。
  第3章・第4章の手順どおりに進めていれば、出力もそのまま再現します
- 変更系の例（`INSERT` / `UPDATE` / `DELETE` / DDL）を実行すると前提状態が変わり、
  後続の例の出力（行数や件数）と一致しなくなります。変更系の例には
  「後片付け」の手順を付けてあるので、試したあとは必ず元に戻してください。
  参照系の例（`SELECT`、集約、JOIN）は何度実行しても状態は変わりません
- `id` や時刻など、実行ごとに変わる値は「実行ごとに変わります」と注記しています
- Python から同じ SQL を実行する方法（`%s` プレースホルダなど）は
  [第5章 psycopg入門 接続と基本のCRUD](05-psycopg-basics.md) を参照してください

## A.1 psql の起動と確認

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb
    ```

=== "コンテナの中で psql を使う"

    ```bash
    docker exec -it webapp-training-db psql -U todo -d tododb
    ```

期待される出力（バージョンの数字は多少変わることがあります）:

```text
psql (16.x)
Type "help" for help.

tododb=#
```

最後の行の `tododb=#` が psql のプロンプトです。
ここに SQL を打ち込んで Enter を押すと実行されます。

よく使う psql のメタコマンド（SQL ではなく psql 独自のショートカットです）:

| コマンド | 意味 |
|---|---|
| `\dt` | テーブルの一覧を表示する |
| `\d テーブル名` | テーブルの構造（列・型・制約）を表示する |
| `\q` | psql を終了する |

実行例:

```text
\dt
```

期待される出力（第4章まで進めた状態）:

```text
           List of relations
 Schema |   Name    | Type  | Owner 
--------+-----------+-------+-------
 public | tags      | table | todo
 public | todo_tags | table | todo
 public | todos     | table | todo
(3 rows)
```

SQL は**セミコロン（`;`）を打って Enter した時点**で実行されます。
忘れるとプロンプトが `tododb=#` から `tododb-#` に変わって待ち状態になるので、
`;` を打ち足すか `Ctrl` + `C` でキャンセルしてください。

## A.2 テーブルを作る・変える・消す（DDL）

### CREATE TABLE: テーブルを作る

構文:

```sql
CREATE TABLE テーブル名 (
    列名 型 制約,
    ...
);
```

実行例（第3章で作った `todos` テーブル）:

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

主な型と制約:

| 書き方 | 意味 |
|---|---|
| `TEXT` / `SMALLINT` / `DATE` / `BOOLEAN` / `TIMESTAMPTZ` | 文字列 / 小さな整数 / 日付 / 真偽値 / タイムゾーン付き日時 |
| `SERIAL PRIMARY KEY` | 自動採番される整数を主キーにする |
| `NOT NULL` | 空（`NULL`）を許さない |
| `UNIQUE` | 同じ値を 2 回入れられない（重複禁止） |
| `DEFAULT 値` | `INSERT` で省略されたときに自動で入る値 |
| `REFERENCES テーブル名(列名)` | 外部キー。参照先に実在する値しか入らない（A.7 参照） |

### ALTER TABLE: あとから列を足す・消す

構文:

```sql
ALTER TABLE テーブル名 ADD COLUMN 列名 型;
ALTER TABLE テーブル名 DROP COLUMN 列名;
```

実行例（練習用のテーブルで試す場合）:

```sql
CREATE TABLE practice_notes (
    id   SERIAL PRIMARY KEY,
    body TEXT NOT NULL
);
ALTER TABLE practice_notes ADD COLUMN memo TEXT;
ALTER TABLE practice_notes DROP COLUMN memo;
```

期待される出力（順に）:

```text
CREATE TABLE
ALTER TABLE
ALTER TABLE
```

### DROP TABLE: テーブルを消す

構文:

```sql
DROP TABLE テーブル名;
DROP TABLE IF EXISTS テーブル名;
```

実行例:

```sql
DROP TABLE practice_notes;
```

期待される出力:

```text
DROP TABLE
```

存在しないテーブルに `DROP TABLE` を実行するとエラーになります。
`IF EXISTS` を付けると、対象がなくても `NOTICE` が出るだけでエラーにならないため、
何度実行しても安全なスクリプトにできます。

```sql
DROP TABLE IF EXISTS practice_notes;
```

期待される出力（`practice_notes` が存在しない場合）:

```text
NOTICE:  table "practice_notes" does not exist, skipping
DROP TABLE
```

!!! danger "DDL は取り消せないと思っておく"
    `DROP TABLE` はテーブルごと全行を消します。
    `ALTER TABLE ... DROP COLUMN` も列の中身ごと消えます。
    練習用のデータベース以外で実行するときは、事前にバックアップを取りましょう。

## A.3 行を追加する（INSERT）

構文:

```sql
INSERT INTO テーブル名 (列名, ...) VALUES (値, ...);
INSERT INTO テーブル名 (列名, ...) VALUES (値, ...), (値, ...), ...;
INSERT INTO テーブル名 (列名, ...) VALUES (値, ...) RETURNING 列名, ...;
```

実行例（順に: 1 行、複数行、`RETURNING` 付き）:

```sql
INSERT INTO todos (title) VALUES ('牛乳を買う');
INSERT INTO todos (title, due_on) VALUES
    ('家賃を振り込む', '2026-08-25'),
    ('車検の見積もり', '2026-09-01'),
    ('週次の振り返り', '2026-08-09');
INSERT INTO todos (title) VALUES ('歯医者の予約') RETURNING id, created_at;
```

期待される出力（順に。`id` と時刻は実行ごとに変わります）:

```text
INSERT 0 1
INSERT 0 3
 id |          created_at           
----+-------------------------------
  7 | 2026-08-09 01:56:06.835046+09
(1 row)

INSERT 0 1
```

- `INSERT 0 1` の最後の数字は「追加された行数」です
- 指定しなかった列には `DEFAULT` の値が入り、`DEFAULT` もなければ `NULL` になります
- `RETURNING` を付けると、自動採番された `id` などを 1 回の文で受け取れます
- 文字列は**シングルクォート**（`'`）で囲みます。ダブルクォート（`"`）は
  テーブル名や列名を囲む記号なので、文字列に使うとエラーになります（A.9 参照）

!!! note "前提状態でこの例を試す場合"
    上の出力例は、第3章の手順を最初から実行したときのものです。
    すでに 7 行入った `todos` に対してこの例を実行すると、新しい行には
    `id = 8` 以降が採番され、同名の行が二重に登録されます。
    試したあとは、次の手順で元に戻してください。

    ```sql
    BEGIN;
    DELETE FROM todos WHERE id > 7;
    SELECT COUNT(*) AS n FROM todos;
    COMMIT;
    ```

    期待される出力:

    ```text
    BEGIN
    DELETE 5
     n 
    ---
     7
    (1 row)

    COMMIT
    ```

## A.4 行を読む（SELECT）

### 基本形と WHERE

構文:

```sql
SELECT 列名, ... FROM テーブル名;
SELECT 列名, ... FROM テーブル名 WHERE 条件;
```

実行例（未完了の ToDo だけを取る）:

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

条件を複数つなげるときは `AND`（両方満たす）/ `OR`（どちらか満たす）を使います。

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

### ORDER BY: 並び替える

構文:

```sql
SELECT 列名, ... FROM テーブル名 ORDER BY 列名 [ASC | DESC] [NULLS FIRST | NULLS LAST], ...;
```

実行例（期限が近い順、期限未設定は最後）:

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

並び順はデフォルトで昇順（`ASC`）です。逆順にしたいときは `DESC` を付けます。

実行例（優先度の大きい順。同じ優先度どうしは `id` 順）:

```sql
SELECT id, title, priority FROM todos ORDER BY priority DESC, id;
```

期待される出力:

```text
 id |     title      | priority 
----+----------------+----------
  1 | 牛乳を買う     |        2
  3 | 領収書の整理   |        2
  4 | 家賃を振り込む |        2
  5 | 車検の見積もり |        2
  6 | 週次の振り返り |        2
  7 | 歯医者の予約   |        2
  2 | 健康診断の予約 |        1
(7 rows)
```

### LIMIT / OFFSET: 件数を絞る

この構文は第3〜4章では使っていませんが、アプリのページネーション
（「1 ページ 20 件ずつ表示」など）でよく使うため収録しています。

構文:

```sql
SELECT 列名, ... FROM テーブル名 ORDER BY 列名 LIMIT 件数;
SELECT 列名, ... FROM テーブル名 ORDER BY 列名 LIMIT 件数 OFFSET 飛ばす件数;
```

実行例（期限が近い順に先頭 3 件）:

```sql
SELECT id, title, due_on FROM todos ORDER BY due_on NULLS LAST LIMIT 3;
```

期待される出力:

```text
 id |     title      |   due_on   
----+----------------+------------
  6 | 週次の振り返り | 2026-08-09
  2 | 健康診断の予約 | 2026-08-10
  4 | 家賃を振り込む | 2026-08-25
(3 rows)
```

`OFFSET` を付けると先頭から指定件数を飛ばします。

```sql
SELECT id, title, due_on FROM todos ORDER BY due_on NULLS LAST LIMIT 3 OFFSET 3;
```

期待される出力:

```text
 id |     title      |   due_on   
----+----------------+------------
  5 | 車検の見積もり | 2026-09-01
  1 | 牛乳を買う     | 
  3 | 領収書の整理   | 
(3 rows)
```

`LIMIT` は `ORDER BY` とセットで使うのが基本です。
`ORDER BY` がないと「どの 3 件が返るか」は決まっていません。

### LIKE / IN: あいまいな条件・複数の候補

構文:

```sql
SELECT 列名, ... FROM テーブル名 WHERE 列名 LIKE 'パターン';
SELECT 列名, ... FROM テーブル名 WHERE 列名 IN (値, 値, ...);
```

実行例（順に: 「振」を含む `title`、`priority` が 1 か 2）:

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

`%` は「任意の 0 文字以上」、`_` は「ちょうど 1 文字」にマッチするワイルドカードです。

### IS NULL / IS NOT NULL: NULL の判定

構文:

```sql
SELECT 列名, ... FROM テーブル名 WHERE 列名 IS NULL;
SELECT 列名, ... FROM テーブル名 WHERE 列名 IS NOT NULL;
```

実行例（期限が未設定の行）:

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

逆に、期限が設定されている行だけを取るのが `IS NOT NULL` です。

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

!!! note "`= NULL` ではなく `IS NULL`"
    `NULL` は「値がない」という特別な状態なので、`=` で比較できません。
    `due_on = NULL` と書くとエラーにもならず**常に 0 行**が返る、
    気づきにくいミスになります。`NULL` の判定は必ず `IS NULL` / `IS NOT NULL` を
    使ってください。

### 日付の条件: current_date

「今日から 7 日以内」という条件は、`current_date`（今日の日付）に
整数を足して書けます（第3章の「やってみよう」問3 で使用）。

実行例（未完了で、期限が今日から 7 日以内の ToDo を期限が近い順に）:

```sql
SELECT id, title, due_on FROM todos
 WHERE done = FALSE AND due_on <= current_date + 7
 ORDER BY due_on;
```

期待される出力（2026-08-16 に実行した例。実行日によって結果は変わります）:

```text
 id |     title      |   due_on   
----+----------------+------------
  6 | 週次の振り返り | 2026-08-09
  2 | 健康診断の予約 | 2026-08-10
(2 rows)
```

期限が `NULL` の行は比較できないため、自動的に除かれます。

## A.5 行を更新・消す（UPDATE / DELETE）

構文:

```sql
UPDATE テーブル名 SET 列名 = 値, ... WHERE 条件;
DELETE FROM テーブル名 WHERE 条件;
```

実行例（`id = 1` を完了にする。確認してから確定する安全な手順）:

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

- `UPDATE 1` は「1 行が更新された」の意味です。
  想定外の件数（0 行や多数）なら `WHERE` の条件が違うサインです
- 「違うな」と思ったら `COMMIT` の代わりに `ROLLBACK;` で取り消せます
  （A.8 参照）

!!! note "試したあとは元に戻す"
    この例を `COMMIT` まで実行すると、`id = 1` が `done = TRUE` のまま残り、
    後続の例の出力と一致しなくなります
    （直後の DELETE 例が `DELETE 2` になります）。
    試したあとは、次の手順で元に戻してください。

    ```sql
    BEGIN;
    UPDATE todos SET done = FALSE, updated_at = now() WHERE id = 1;
    SELECT id, title, done FROM todos WHERE id = 1;
    COMMIT;
    ```

    期待される出力:

    ```text
    BEGIN
    UPDATE 1
     id |   title    | done 
    ----+------------+------
      1 | 牛乳を買う | f
    (1 row)

    COMMIT
    ```

実行例（完了済みの行を消し、取り消してみる）:

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
DELETE 1
 id | title | done 
----+-------+------
(0 rows)

ROLLBACK
 id |    title     | done 
----+--------------+------
  3 | 領収書の整理 | t
(1 row)
```

!!! danger "WHERE を忘れると全行に効く"
    `UPDATE todos SET done = TRUE;` は全行が完了になり、
    `DELETE FROM todos;` は全行が消えます。
    実行後の `UPDATE 7` のような件数表示は毎回必ず目で確認し、
    本番の DB では `BEGIN;` → 実行 → `SELECT` で確認 → `COMMIT;` の
    手順を習慣にしてください。

## A.6 集約: まとめて数える（COUNT / GROUP BY）

### COUNT: 件数を数える

構文:

```sql
SELECT COUNT(*) FROM テーブル名;
```

実行例:

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

`COUNT` のような、複数行を 1 つの値にまとめる関数を**集約関数**と呼びます。
他にも `SUM`（合計）/ `AVG`（平均）/ `MAX`（最大）/ `MIN`（最小）があります。

```sql
SELECT MIN(due_on), MAX(due_on), AVG(priority) FROM todos;
```

期待される出力:

```text
    min     |    max     |        avg         
------------+------------+--------------------
 2026-08-09 | 2026-09-01 | 1.8571428571428571
(1 row)
```

### GROUP BY: グループごとに集計する

構文:

```sql
SELECT 列名, COUNT(*) FROM テーブル名 GROUP BY 列名;
```

実行例（優先度ごとの件数）:

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

`GROUP BY` を使うクエリで `SELECT` に書いていいのは、
**「`GROUP BY` に書いた列」か「集約関数の中」**だけです。
それ以外の列を書くとエラーになります。

```sql
SELECT title, COUNT(*) FROM todos GROUP BY priority;
```

期待される出力（エラー）:

```text
ERROR:  column "todos.title" must appear in the GROUP BY clause or be used in an aggregate function
```

### FILTER: 条件付きの件数を数える

構文:

```sql
SELECT COUNT(*) FILTER (WHERE 条件) FROM テーブル名;
```

実行例（期限あり・なし・全体の件数を 1 クエリで）:

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

なお、`COUNT(列名)` は **`NULL` を数えません**。
「`NULL` でない値がいくつあるか」を数えたいときに使えます（4.9 の問4 参照）。

## A.7 JOIN: 複数のテーブルをまたぐ

### 前提: tags と todo_tags

第4章で作った多対多のテーブルです。`REFERENCES` が外部キー制約、
`ON DELETE CASCADE` は「参照先の行が消えたら、この行も自動で消す」設定です。

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

INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康');
INSERT INTO todo_tags (todo_id, tag_id) VALUES
    (1, 1),  -- 牛乳を買う → 家事
    (4, 1),  -- 家賃を振り込む → 家事
    (2, 3),  -- 健康診断の予約 → 健康
    (7, 3);  -- 歯医者の予約 → 健康
```

### INNER JOIN: マッチする行だけ

構文:

```sql
SELECT ...
  FROM テーブルA 別名
  JOIN テーブルB 別名 ON 結合条件;
```

実行例（タグが付いている ToDo とタグ名の一覧）:

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

`JOIN`（= `INNER JOIN`）は**両方のテーブルにマッチする行だけ**を返すので、
タグなしの ToDo（`id = 3, 5, 6`）は結果に現れません。

### LEFT JOIN: 左側の行をすべて残す

構文:

```sql
SELECT ...
  FROM テーブルA 別名
  LEFT JOIN テーブルB 別名 ON 結合条件;
```

実行例（タグの有無に関わらず全 ToDo を一覧）:

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

`LEFT JOIN` は左側のテーブルの行をすべて残し、
マッチする右側の行がなければ右側の列を `NULL`（空欄）で埋めます。

逆に右側を必ず残す `RIGHT JOIN`、両方を残す `FULL JOIN` もありますが、
実務で使われるのは `INNER JOIN` と `LEFT JOIN` の 2 つが大半です。
本研修でもこの 2 つだけを扱います。

### string_agg: グループ内の値を 1 行に連結する

`GROUP BY` と集約関数 `string_agg` を組み合わせると、
「1 ToDo = 1 行で、タグはカンマ区切り」の形にできます。

構文:

```sql
SELECT 列名, string_agg(連結する列名, '区切り文字')
  FROM テーブル名
 GROUP BY 列名;
```

実行例:

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

`COALESCE(a, b)` は「`a` が `NULL` なら `b`」を返す関数です。
タグが 1 つもない行の `NULL` を空文字に置き換えています。

## A.8 トランザクション: まとめて成功、まとめて取り消し

構文:

```sql
BEGIN;
-- ここに複数の SQL
COMMIT;    -- ぜんぶ確定
-- もしくは
ROLLBACK;  -- ぜんぶ取り消し
```

実行例（タグの追加と紐付けを 1 つにまとめる）:

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

期待される出力（`RETURNING` の `id` は実行ごとに変わります。
返ってきた番号を 2 つ目の `INSERT` に使います）:

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

!!! note "試したあとは元に戻す"
    この例を `COMMIT` まで実行すると、「買い物」タグと紐付けが残り、
    A.7 の例の出力と一致しなくなります。試したあとは、次の手順で元に戻してください
    （`tag_id = 4` の部分は、`RETURNING` で返ってきた番号に合わせます）。

    ```sql
    BEGIN;
    DELETE FROM todo_tags WHERE todo_id = 3 AND tag_id = 4;
    DELETE FROM tags WHERE name = '買い物';
    COMMIT;
    ```

    期待される出力:

    ```text
    BEGIN
    DELETE 1
    DELETE 1
    COMMIT
    ```

途中で失敗した場合の実行例（存在しない `todo_id = 999` に紐付けようとして
外部キー違反を起こす）:

```sql
BEGIN;
INSERT INTO tags (name) VALUES ('読書') RETURNING id;
INSERT INTO todo_tags (todo_id, tag_id) VALUES (999, 5);
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
ROLLBACK
 id | name 
----+------
(0 rows)
```

- トランザクション内でエラーが起きると、それ以降の SQL は
  `current transaction is aborted` というエラーで拒否されます。
  `ROLLBACK;`（または `COMMIT;`）でいったん終了させてからやり直してください
- `ROLLBACK` すると 1 文目の `INSERT` もなかったことになります（**原子性**）
- `SERIAL` の連番はロールバックされず欠番になります。
  「`id` は連番のまま並んでいるはず」と仮定したコードは書かないようにしましょう

## A.9 よくあるエラー

| エラーメッセージ | 原因と対処 |
|---|---|
| `column "牛乳" does not exist` | 文字列をダブルクォートで囲んでいる。シングルクォート `'...'` に直す |
| `column "todos.title" must appear in the GROUP BY clause` | `GROUP BY` にない列をそのまま `SELECT` した。`GROUP BY` に書いた列か集約関数だけにする |
| `violates foreign key constraint` | 参照先に存在しない値を入れようとした。`DETAIL` 行の値を確認する |
| `current transaction is aborted` | トランザクション内でエラーが起きたあと。`ROLLBACK;` で終了させてからやり直す |
| プロンプトが `tododb-#` に変わったまま | セミコロン忘れ。`;` を打ち足すか `Ctrl` + `C` でキャンセル |

この付録でカバーしていない構文（ビュー、インデックス、サブクエリなど）が
必要になったら、[PostgreSQL の公式ドキュメント](https://www.postgresql.org/docs/current/)を参照してください。
