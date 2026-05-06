# 第4章 PostgreSQLのおさらい② JOIN・集約・トランザクション

前章のテーブル単体の操作に続いて、**複数テーブル**と**データ整合性**の話に進みます。

この章で再確認するもの:

- 集約（`GROUP BY` と `FILTER`）
- 多対多と JOIN
- トランザクション
- ビューとサブクエリ（軽く）

## 4.1 集約と GROUP BY

優先度ごとの件数を見てみます。
（前章の `todos` テーブルが残っていない場合は、軽く作り直してから試してください）

```sql
CREATE TABLE todos (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    due_on      DATE,
    priority    SMALLINT NOT NULL DEFAULT 2
);

INSERT INTO todos (title, priority, done) VALUES
    ('a', 1, FALSE), ('b', 2, FALSE), ('c', 2, TRUE),
    ('d', 3, FALSE), ('e', 1, TRUE);
```

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

## 4.2 JOIN を ToDo に絡める

ToDo を「タグ付け」できるようにしてみましょう。
本格的な設計は第9章でやりますが、JOIN の感覚を取り戻すために
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
    (1, 1),  -- a → 家事
    (2, 3);  -- b → 健康
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

## 4.3 トランザクションを意識する

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
    （第6章で psycopg のトランザクション制御を扱います）

## 4.4 ビュー（軽く復習）

頻繁に使う `SELECT` 文に名前を付けて再利用できる仕組みです。

```sql
-- 期限が今日以前で、完了していない ToDo を「やるべきリスト」として保存
CREATE VIEW v_due_today AS
SELECT id, title, due_on, priority
  FROM todos
 WHERE done = FALSE
   AND (due_on IS NULL OR due_on <= CURRENT_DATE);

SELECT * FROM v_due_today ORDER BY priority;
```

ビュー自体は **データを持たず**、参照されるたびに `SELECT` を実行します。

## 4.5 サブクエリ（軽く復習）

`SELECT` 文の中に `SELECT` を埋め込めます。

```sql
-- 平均優先度より大事な ToDo（数値が小さいほど優先度が高いので「<」）
SELECT id, title, priority
  FROM todos
 WHERE priority < (SELECT AVG(priority) FROM todos);
```

スカラサブクエリ（1 行 1 列を返すもの）は比較演算子と組み合わせて使えます。

## 4.6 後片付け

```sql
DROP VIEW IF EXISTS v_due_today;
DROP TABLE IF EXISTS todo_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS todos;
```

## やってみよう

`psql` で次のことをやってみましょう。

1. 「優先度ごとの未完了件数」を `GROUP BY` と `FILTER` で出す。
2. `BEGIN` → `UPDATE` → `SELECT` で確認 → `ROLLBACK` を試して、
   ロールバック後にデータが元に戻っていることを確認する。
3. `LEFT JOIN` と `INNER JOIN` で結果がどう変わるかを比べる
   （タグなしの ToDo の出方に注目）。

ここまでで PostgreSQL のおさらいは終わりです。
次は [第 5 章 psycopg入門 接続と基本のCRUD](05-psycopg-basics.md) で、
**ここで書いた SQL を Python から実行する**入口に立ちます。
