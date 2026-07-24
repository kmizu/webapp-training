# 付録A SQLチートシート

研修で使う/思い出す SQL を 1 ページにまとめました。
**PostgreSQL 16** を前提にしています。

## A.1 接続と確認

```bash
psql -h localhost -p 5432 -U todo -d tododb
docker exec -it webapp-training-db psql -U todo -d tododb
```

`psql` 内コマンド:

```text
\l            データベース一覧
\dt           テーブル一覧
\d todos      テーブルの定義を表示
\du           ユーザー一覧
\x            縦表示の切り替え
\q            終了
```

## A.2 DDL（テーブル作成・変更）

参考: [DDL（テーブル定義）](https://www.postgresql.org/docs/current/ddl.html)

```sql
CREATE TABLE name (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    due_on      DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE name ADD COLUMN memo TEXT;
ALTER TABLE name DROP COLUMN memo;
ALTER TABLE name RENAME COLUMN done TO is_done;
ALTER TABLE name ADD CONSTRAINT chk_pri CHECK (priority BETWEEN 1 AND 3);

DROP TABLE name;
DROP TABLE IF EXISTS name;
```

`DROP TABLE` や `ALTER TABLE` は本番データに直接効くので、事前にバックアップを取ってから実行しましょう。

インデックス:

```sql
CREATE INDEX idx_name_col ON name (col);
CREATE UNIQUE INDEX idx_name_unique ON name (col);
DROP INDEX idx_name_col;
```

## A.3 DML（データ操作）

参考: [DML（データ操作）](https://www.postgresql.org/docs/current/dml.html)

```sql
-- 追加
INSERT INTO todos (title) VALUES ('test');
INSERT INTO todos (title, due_on) VALUES ('a', '2026-05-30'), ('b', NULL);
INSERT INTO todos (title) VALUES ('c') RETURNING id, created_at;

-- 更新
UPDATE todos SET done = TRUE WHERE id = 1;
UPDATE todos SET priority = priority - 1 WHERE done = FALSE;

-- 削除
DELETE FROM todos WHERE id = 1;
DELETE FROM todos WHERE done = TRUE;

-- ON CONFLICT（UPSERT）
INSERT INTO tags (name) VALUES ('家事')
ON CONFLICT (name) DO NOTHING;

INSERT INTO tags (name) VALUES ('家事')
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name;
```

`UPDATE` / `DELETE` は `WHERE` を書き忘れると全行が対象になります。実行前に同じ条件で `SELECT` して対象行を確認する癖をつけましょう。

## A.4 SELECT の基本

参考: [SELECT 文](https://www.postgresql.org/docs/current/sql-select.html)

```sql
SELECT * FROM todos;
SELECT id, title FROM todos;
SELECT id AS todo_id, title FROM todos;

SELECT * FROM todos WHERE done = FALSE;
SELECT * FROM todos WHERE due_on IS NULL;
SELECT * FROM todos WHERE due_on IS NOT NULL;
SELECT * FROM todos WHERE due_on BETWEEN '2026-05-01' AND '2026-05-31';
SELECT * FROM todos WHERE title LIKE '%議事%';
SELECT * FROM todos WHERE title ILIKE '%hello%';   -- 大文字小文字無視
SELECT * FROM todos WHERE priority IN (1, 2);
SELECT * FROM todos WHERE id = ANY(ARRAY[1, 2, 3]);

SELECT * FROM todos
 ORDER BY due_on NULLS LAST, priority ASC, id DESC
 LIMIT 50 OFFSET 100;

SELECT DISTINCT priority FROM todos;
```

## A.5 集約

参考: [集約関数入門](https://www.postgresql.org/docs/current/tutorial-agg.html)

```sql
SELECT COUNT(*) FROM todos;
SELECT COUNT(*) FILTER (WHERE done = FALSE) FROM todos;
SELECT priority, COUNT(*) FROM todos GROUP BY priority;
SELECT priority, COUNT(*) FROM todos GROUP BY priority HAVING COUNT(*) > 3;
SELECT AVG(priority) FROM todos;
SELECT MAX(due_on), MIN(due_on) FROM todos;
SELECT string_agg(title, ', ') FROM todos WHERE done = FALSE;
```

`GROUP BY` していない列を `SELECT` に含めると `column must appear in the GROUP BY clause` エラーになります。

## A.6 JOIN

参考: [テーブル式（JOIN）](https://www.postgresql.org/docs/current/queries-table-expressions.html)

```sql
-- INNER JOIN（両方にあるものだけ）
SELECT t.*, g.name
  FROM todos t
  JOIN todo_tags tt ON tt.todo_id = t.id
  JOIN tags g       ON g.id = tt.tag_id;

-- LEFT JOIN（左にあるものは全部）
SELECT t.*, g.name
  FROM todos t
  LEFT JOIN todo_tags tt ON tt.todo_id = t.id
  LEFT JOIN tags g       ON g.id = tt.tag_id;

-- 自己結合
SELECT a.title, b.title
  FROM todos a, todos b
 WHERE a.id <> b.id AND a.priority = b.priority;
```

カンマ区切りで複数テーブルを並べる書き方は `WHERE` 条件を書き忘れると全組み合わせ（直積）になるので、基本は `JOIN ... ON` を使いましょう。

## A.7 サブクエリ

参考: [サブクエリ式](https://www.postgresql.org/docs/current/functions-subquery.html)

```sql
-- スカラサブクエリ（1行1列）
SELECT *
  FROM todos
 WHERE priority < (SELECT AVG(priority) FROM todos);

-- IN サブクエリ
SELECT *
  FROM todos
 WHERE id IN (SELECT todo_id FROM todo_tags WHERE tag_id = 1);

-- 相関サブクエリ
SELECT t.id,
       t.title,
       (SELECT COUNT(*) FROM todo_tags tt WHERE tt.todo_id = t.id) AS tag_count
  FROM todos t;

-- WITH（共通テーブル式）
WITH urgent AS (
    SELECT * FROM todos WHERE priority = 1 AND done = FALSE
)
SELECT COUNT(*) FROM urgent;
```

スカラサブクエリが複数行を返すと `more than one row returned by a subquery` エラーになります。

## A.8 ビュー

参考: [CREATE VIEW](https://www.postgresql.org/docs/current/sql-createview.html)

```sql
CREATE VIEW v_open_todos AS
SELECT id, title, due_on, priority
  FROM todos
 WHERE done = FALSE;

SELECT * FROM v_open_todos ORDER BY due_on NULLS LAST;

DROP VIEW v_open_todos;
```

## A.9 トランザクション

参考: [トランザクション入門](https://www.postgresql.org/docs/current/tutorial-transactions.html)

```sql
BEGIN;
UPDATE todos SET done = TRUE WHERE id = 1;
SELECT id, done FROM todos WHERE id = 1;
COMMIT;
-- もしくは
ROLLBACK;

-- セーブポイント
BEGIN;
INSERT INTO todos (title) VALUES ('a');
SAVEPOINT s1;
INSERT INTO todos (title) VALUES ('b');
ROLLBACK TO SAVEPOINT s1;   -- b だけ取り消し
COMMIT;
```

`BEGIN` したまま `COMMIT`/`ROLLBACK` を忘れると、トランザクションが開いたままになり他のクエリをロックし続けることがあります。

## A.10 関数（よく使うもの）

```sql
-- 文字列
LENGTH(title), CHAR_LENGTH(title)
LOWER(title), UPPER(title)
REPLACE(title, '旧', '新')
SUBSTRING(title FROM 1 FOR 5)
title || ' (重要)'           -- 連結

-- 数値
ABS(x), ROUND(x, 2), CEIL(x), FLOOR(x), MOD(x, 3)

-- 日付
CURRENT_DATE, CURRENT_TIME, CURRENT_TIMESTAMP, now()
date_trunc('day', updated_at)
EXTRACT(DOW FROM CURRENT_DATE)
CURRENT_DATE - INTERVAL '7 days'

-- NULL の扱い
COALESCE(due_on, CURRENT_DATE + 30)
NULLIF(value, '')           -- 空文字なら NULL
```

## A.11 トラブルシュート

| 症状 | チェックポイント |
|---|---|
| `relation "todos" does not exist` | テーブル作成済み？ `\dt` で確認 |
| `current transaction is aborted` | `ROLLBACK;` で抜ける |
| `null value in column "x" violates not-null constraint` | DEFAULT を入れるか、`INSERT` で値を渡す |
| `duplicate key value violates unique constraint` | UNIQUE 制約に引っかかった、`ON CONFLICT` を検討 |
| `foreign key violation` | 親レコードがない、`ON DELETE CASCADE` を検討 |

## A.12 性能の最初のひと押し

参考: [EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html)

```sql
EXPLAIN SELECT * FROM todos WHERE done = FALSE ORDER BY due_on;
EXPLAIN ANALYZE SELECT * FROM todos WHERE done = FALSE ORDER BY due_on;
```

`EXPLAIN ANALYZE` は **実際に実行して** プランと時間を出します。
インデックスが使われているか確認するときの一手目です。

```sql
-- WHERE と ORDER BY のセットに対応する複合インデックス
CREATE INDEX idx_todos_done_due ON todos (done, due_on);
```
