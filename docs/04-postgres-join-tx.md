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

`GROUP BY priority` は「`priority` の値が同じ行をひとつのグループにまとめる」という指定です。`COUNT(*)` のような**集約関数**（複数行の値をひとつにまとめる関数）は、`GROUP BY` を書かなければ**テーブル全体を1つのグループ**として集計し、`GROUP BY priority` を付けると**優先度ごとに別々のグループ**として集計します。`SELECT` に書いていい列は「集約関数の中の列」か「`GROUP BY` に書いた列」のどちらかだけです。`title` のような列をそのまま `SELECT` しようとするとエラーになりますが、これは同じ `priority` のグループに複数の `title` が含まれてしまい、どれを返すべきか一意に決まらないからです。集約関数には他にも `SUM` / `AVG` / `MAX` / `MIN` などがあります。詳しくは[集約関数の公式チュートリアル](https://www.postgresql.org/docs/current/tutorial-agg.html)を参照してください。

未完了の件数だけを数える:

```sql
SELECT
    COUNT(*) FILTER (WHERE done = FALSE) AS open_count,
    COUNT(*) FILTER (WHERE done = TRUE)  AS done_count,
    COUNT(*)                             AS total
FROM todos;
```

`FILTER (WHERE ...)` は「1つのクエリの中で、集約関数ごとに集計対象の条件を変えたい」ときのための書き方です。これを使わずに同じ結果を出そうとすると `COUNT(CASE WHEN done = FALSE THEN 1 END)` のように書く必要があり、条件が増えるほど読みにくくなります。`FILTER` は PostgreSQL に標準で入っている書き方で、`CASE WHEN` を使うより読みやすくおすすめです。

## 4.2 JOIN を ToDo に絡める

ToDo を「タグ付け」できるようにしてみましょう。
本格的な設計は第9章でやりますが、JOIN の感覚を取り戻すために
試しに書いてみます。

1つの ToDo に複数のタグを付けられて、1つのタグも複数の ToDo で使い回せる——これは**多対多（many-to-many）**の関係です。`todos` に直接タグの列を足す方法だと「タグは1つまで」に制限されてしまうので、代わりに両方の `id` を組で持つ**中間テーブル**（`todo_tags`）を挟みます。

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

!!! note "外部キー制約と複合主キー"
    - `REFERENCES todos(id)` は**外部キー制約**です。存在しない `todo_id` や `tag_id` を `todo_tags` に挿入できないようにして、参照先が必ず実在することを保証します（[制約の公式ドキュメント](https://www.postgresql.org/docs/current/ddl-constraints.html)）。
    - `ON DELETE CASCADE` は、参照先（`todos` や `tags`）の行が消えたときに、対応する `todo_tags` の行も自動で消してくれる設定です。付けないと「存在しない ToDo を指すタグ付け」がゴミとして残ってしまいます。
    - `PRIMARY KEY (todo_id, tag_id)` のように複数列を組み合わせて主キーにする（**複合主キー**）と、「同じ ToDo に同じタグを二重に付ける」ことを防げます。

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
- 1 行の ToDo に複数のタグを並べるには `string_agg` で文字列をくっつけます（これも `COUNT` と同じ集約関数の一種です）。
- 値が NULL になる場合に備えて `COALESCE(..., '')` で空文字に置き換えています。
- `GROUP BY t.id` だけで `t.title` も一緒に `SELECT` できているのは、`id` が `todos` の主キーで `title` を一意に決められる（**関数従属**）ことを PostgreSQL が理解しているためです。他の DB 製品ではこの緩和がなく、`GROUP BY t.id, t.title` のように全列を書く必要がある場合もあります。

!!! note "JOIN の種類がなぜ複数あるか"
    - **`INNER JOIN`**（単に `JOIN` と書いても同じ）は、**両方のテーブルにマッチする行だけ**を返します。もしこのクエリを `INNER JOIN` で書くと、タグが1つも付いていない ToDo は結果から消えてしまいます。
    - **`LEFT JOIN`**（正式には `LEFT OUTER JOIN`）は、**左側のテーブル（ここでは `todos`）の行を必ずすべて残し**、マッチする右側の行がなければ右側の列を `NULL` で埋めます。「タグの有無に関わらず全 ToDo を一覧したい」という今回の要件には、こちらが必要です。
    - 逆に右側を必ず残す `RIGHT JOIN`、両方を残す `FULL JOIN` もありますが、実務で使うのは大半が `INNER JOIN` と `LEFT JOIN` です。どの JOIN も「結合条件（`ON` の後ろ）にマッチする行の組み合わせを作る」点は共通で、マッチしなかった行をどう扱うかだけが違います。詳しくは[テーブル式（結合）の公式ドキュメント](https://www.postgresql.org/docs/current/queries-table-expressions.html)を参照してください。

## 4.3 トランザクションを意識する

DB の世界では、複数の SQL を **「ぜんぶ成功」か「ぜんぶ取り消し」** にまとめる仕組みがあります。これがトランザクションです。

```sql
BEGIN;
INSERT INTO tags (name) VALUES ('買い物') RETURNING id;
-- 上で得た id を使って
INSERT INTO todo_tags (todo_id, tag_id) VALUES (1, 4);
COMMIT;
```

この「ぜんぶ成功かぜんぶ取り消しか」という性質を**原子性（atomicity）**と呼びます。上の例で、`tags` への `INSERT` は成功したのに、続く `todo_tags` への `INSERT` が何かの理由（エラー、接続断など）で失敗したとします。トランザクションで囲んでいなければ、「存在するけれど、どの ToDo にも紐付いていないタグ」が中途半端に残ってしまいます。`BEGIN` 〜 `COMMIT` で囲んでおけば、途中で失敗したときにその中途半端な状態ごと取り消せます。詳しくは[トランザクションの公式チュートリアル](https://www.postgresql.org/docs/current/tutorial-transactions.html)を参照してください。

途中で `ROLLBACK;` すれば、`BEGIN` 以降の変更はすべてなかったことになります。

!!! tip "Web アプリではトランザクションが必須"
    たとえば「ToDoを作って、同時にタグを付ける」ような操作では、
    片方だけ成功してもう片方が失敗すると **データの整合性が壊れます**。
    Python から複数の SQL を投げる場合、必ずトランザクションで包むのが基本。
    （第6章で [psycopg のトランザクション制御](https://www.psycopg.org/psycopg3/docs/basic/transactions.html) を扱います）

## 4.4 ビュー（軽く復習）

頻繁に使う `SELECT` 文に名前を付けて再利用できる仕組みです。同じ条件の `SELECT` をあちこちのコードにコピペしていると、条件を直したくなったときに直し忘れが起きがちですが、[ビュー](https://www.postgresql.org/docs/current/sql-createview.html)としてひとまとめにしておけば修正箇所は1か所で済みます。

```sql
-- 期限が今日以前で、完了していない ToDo を「やるべきリスト」として保存
CREATE VIEW v_due_today AS
SELECT id, title, due_on, priority
  FROM todos
 WHERE done = FALSE
   AND (due_on IS NULL OR due_on <= CURRENT_DATE);

SELECT * FROM v_due_today ORDER BY priority;
```

ビュー自体は **データを持たず**、参照されるたびに `SELECT` を実行します。そのため元のテーブル（ここでは `todos`）が更新されれば、ビューを見るたびに常に最新の結果が返ります（結果をキャッシュとして持つ「マテリアライズドビュー」という別の仕組みもありますが、本研修では扱いません）。

## 4.5 サブクエリ（軽く復習）

`SELECT` 文の中に `SELECT` を埋め込めます。ビューが「名前を付けて何度も使い回す」ためのものだとすると、[サブクエリ](https://www.postgresql.org/docs/current/functions-subquery.html)は「その場限りの一時的な計算結果」をその場で使うためのものです。

```sql
-- 平均優先度より大事な ToDo（数値が小さいほど優先度が高いので「<」）
SELECT id, title, priority
  FROM todos
 WHERE priority < (SELECT AVG(priority) FROM todos);
```

スカラサブクエリ（1 行 1 列だけを返すもの）は、単一の値と同じように比較演算子（`<` や `=` など）と組み合わせて使えます。複数行を返すサブクエリなら `IN` や `EXISTS` と組み合わせるのが定番ですが、本研修では深入りしません。

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
