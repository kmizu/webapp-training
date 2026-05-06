# 第2章 PostgreSQLのおさらい

前回までの講義で、`SELECT` / `INSERT` / `UPDATE` / `DELETE` / `JOIN` /
`GROUP BY` / ビュー / サブクエリ / 関数までひととおり扱いました。

この章では、**ToDo アプリで実際に使う部分だけ**に絞って総ざらいします。
新しい構文の紹介は最小限です。手元の `psql` で実行しながら読んでください。

接続は第0章の通りで、`docker compose up -d` してから:

```bash
psql -h localhost -p 5432 -U todo -d tododb
# あるいは
docker exec -it webapp-training-db psql -U todo -d tododb
```

## 2.1 テーブルを作る（DDL）

ToDo を保存するテーブルを作ってみます。

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

ポイント:

- **`SERIAL`** は「自動採番される INTEGER」のショートカット。新しめの PostgreSQL では `GENERATED ALWAYS AS IDENTITY` を推奨することもありますが、研修ではわかりやすい `SERIAL` を使います。
- **`TIMESTAMPTZ`** は「タイムゾーン付き時刻」。日付だけなら `DATE`、時刻まで含めるなら `TIMESTAMPTZ` が無難。
- **`NOT NULL`** と **`DEFAULT`** は両方書くのが基本。デフォルト値があれば `INSERT` のときに省略できます。
- 主キーは `PRIMARY KEY`、行を一意に決めるカラムを必ずひとつ用意します。

確認:

```sql
\d todos        -- テーブルの構造を見る
\dt             -- テーブル一覧
```

## 2.2 行を増やす（INSERT）

```sql
INSERT INTO todos (title) VALUES ('牛乳を買う');
INSERT INTO todos (title, due_on, priority) VALUES ('健康診断の予約', '2026-05-08', 1);
INSERT INTO todos (title, done) VALUES ('過去の領収書を捨てる', TRUE);
```

複数行をまとめて:

```sql
INSERT INTO todos (title, due_on) VALUES
    ('家賃を振り込む', '2026-05-25'),
    ('車検の見積もり', '2026-06-01'),
    ('週次の振り返り', '2026-05-09');
```

`RETURNING` を付けると、**今入れた行のカラム**を取り出せます。
あとで Python から呼び出すとき、生成された `id` を取りたいときに便利。

```sql
INSERT INTO todos (title) VALUES ('テスト') RETURNING id, created_at;
```

## 2.3 行を読む（SELECT）

最初は素直に。

```sql
SELECT * FROM todos;
SELECT id, title, done FROM todos WHERE done = FALSE;
SELECT * FROM todos ORDER BY due_on NULLS LAST, priority;
```

`LIKE` での部分一致、`IN` での複数一致:

```sql
SELECT * FROM todos WHERE title LIKE '%振%';
SELECT * FROM todos WHERE priority IN (1, 2);
```

NULL の扱いは要注意です。**`= NULL` は使えません**。

```sql
-- 期限が設定されていない ToDo
SELECT * FROM todos WHERE due_on IS NULL;

-- 設定されている ToDo
SELECT * FROM todos WHERE due_on IS NOT NULL;
```

## 2.4 行を変える（UPDATE）/ 消す（DELETE）

```sql
-- ID=1 を完了にする
UPDATE todos
   SET done = TRUE,
       updated_at = now()
 WHERE id = 1;

-- 完了済みを全部消す（こわい）
DELETE FROM todos WHERE done = TRUE;
```

!!! danger "WHERE を忘れると全行に効く"
    `UPDATE todos SET done = TRUE;` は **全行が完了になります**。
    `psql` で本番 DB を触るときは、まず `BEGIN;` してから操作して、
    結果を `SELECT` で確認してから `COMMIT;` する習慣を付けましょう。

```sql
BEGIN;
UPDATE todos SET done = TRUE WHERE id = 1;
SELECT id, title, done FROM todos WHERE id = 1;  -- 確認
COMMIT;   -- 確定
-- やっぱりやめる場合は ROLLBACK;
```

## 2.5 集約と GROUP BY

優先度ごとの件数を見てみます。

```sql
SELECT priority, COUNT(*) AS n
  FROM todos
 GROUP BY priority
 ORDER BY priority;
```

未完了の件数だけを数える:

```sql
SELECT
    COUNT(*) FILTER (WHERE done = FALSE) AS open_count,
    COUNT(*) FILTER (WHERE done = TRUE)  AS done_count,
    COUNT(*)                             AS total
FROM todos;
```

`FILTER (WHERE ...)` は PostgreSQL に標準で入っている書き方で、
`CASE WHEN` を使うより読みやすくおすすめです。

## 2.6 JOIN を ToDo に絡める

ToDo を「タグ付け」できるようにしてみましょう。
これは第4章で実際に設計しますが、JOIN の感覚を取り戻すために
試しに書いてみます。

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
    (1, 1),  -- 牛乳 → 家事
    (2, 3);  -- 健康診断 → 健康
```

ToDo にタグを並べる JOIN:

```sql
SELECT t.id, t.title, COALESCE(string_agg(g.name, ', '), '') AS tags
  FROM todos t
  LEFT JOIN todo_tags tt ON tt.todo_id = t.id
  LEFT JOIN tags      g  ON g.id = tt.tag_id
 GROUP BY t.id
 ORDER BY t.id;
```

ポイント:

- ToDo にタグが **付いていない場合も表示したい**ので **`LEFT JOIN`** を使います。
- 1 行の ToDo に複数のタグを並べるには `string_agg` で文字列をくっつけます。
- 値が NULL になる場合に備えて `COALESCE(..., '')` で空文字に置き換えています。

## 2.7 トランザクションを意識する

DB の世界では、複数の SQL を **「ぜんぶ成功」か「ぜんぶ取り消し」** にまとめる仕組みがあります。これがトランザクションです。

```sql
BEGIN;
INSERT INTO tags (name) VALUES ('買い物') RETURNING id;
-- 上で得た id を使って
INSERT INTO todo_tags (todo_id, tag_id) VALUES (1, 4);
COMMIT;
```

途中で `ROLLBACK;` すれば、`BEGIN` 以降の変更はすべてなかったことになります。

!!! tip "Web アプリではトランザクションが必須"
    たとえば「ToDoを作って、同時にタグを付ける」ような操作では、
    片方だけ成功してもう片方が失敗すると **データの整合性が壊れます**。
    Python から複数の SQL を投げる場合、必ずトランザクションで包むのが基本。

## 2.8 ビューとサブクエリ（軽く復習）

前回までで扱った内容なのでざっと。

```sql
-- 期限が今日以前で、完了していない ToDo を「やるべきリスト」として保存
CREATE VIEW v_due_today AS
SELECT id, title, due_on, priority
  FROM todos
 WHERE done = FALSE
   AND due_on <= CURRENT_DATE;

SELECT * FROM v_due_today ORDER BY priority;
```

サブクエリの例（平均優先度より大事な ToDo）:

```sql
SELECT id, title, priority
  FROM todos
 WHERE priority < (SELECT AVG(priority) FROM todos);
```

## 2.9 後片付け

ここで作った練習用テーブルは、第4章でちゃんと設計しなおします。
一旦消しておきましょう。

```sql
DROP VIEW IF EXISTS v_due_today;
DROP TABLE IF EXISTS todo_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS todos;
```

## やってみよう

`psql` で次のことをやってみましょう。

1. `todos` テーブルに少なくとも 5 行を `INSERT` する。
2. 「完了していない、期限が 7 日以内」の ToDo を `SELECT` する。
3. 「優先度ごとの未完了件数」を `GROUP BY` で出す。
4. `BEGIN` → `UPDATE` → `SELECT` で確認 → `ROLLBACK` を試して、
   ロールバック後にデータが元に戻っていることを確認する。

次は [第 3 章 PythonとDBをつなぐ](03-connect-db.md) で、
**ここで書いた SQL を Python から実行する**方法を学びます。
