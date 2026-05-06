# 第3章 PostgreSQLのおさらい① DDL/DML/SELECT

PostgreSQL の復習です。前回までの講義でひととおり扱った内容を、
**ToDo アプリで実際に使う部分だけ**に絞って総ざらいします。

接続は第0章の通りで、`docker compose up -d` してから:

```bash
psql -h localhost -p 5432 -U todo -d tododb
# あるいは
docker exec -it webapp-training-db psql -U todo -d tododb
```

## 3.1 テーブルを作る（DDL）

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

## 3.2 行を増やす（INSERT）

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

## 3.3 行を読む（SELECT）

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

## 3.4 行を変える（UPDATE）/ 消す（DELETE）

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

トランザクションそのものは次章で詳しく扱います。

## 3.5 後片付け

ここで作った練習用テーブルは、**第9章でちゃんと設計しなおします**。
一旦消しておきましょう。

```sql
DROP TABLE IF EXISTS todos;
```

## やってみよう

`psql` で次のことをやってみましょう。

1. `todos` テーブルを作って、少なくとも 5 行を `INSERT` する。
2. 「完了していない、期限が 7 日以内」の ToDo を `SELECT` する。
3. ID=2 の優先度を 1 に `UPDATE` する。
4. 期限が NULL の ToDo を `DELETE` する。

次は [第 4 章 PostgreSQLのおさらい② JOIN・集約・トランザクション](04-postgres-join-tx.md) で、
複数テーブルやデータ整合性の話を扱います。
