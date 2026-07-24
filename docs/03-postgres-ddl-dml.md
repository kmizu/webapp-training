# 第3章 PostgreSQLのおさらい① DDL/DML/SELECT

PostgreSQL の復習です。前回までの講義でひととおり扱った内容を、
**ToDo アプリで実際に使う部分だけ**に絞って総ざらいします。

SQL は大きく分けると、「テーブルの形」を定義する **DDL**（[Data Definition Language](https://www.postgresql.org/docs/current/ddl.html)）と、
「テーブルの中身」を操作する **DML**（[Data Manipulation Language](https://www.postgresql.org/docs/current/dml.html)）の2種類に分かれます。
`CREATE TABLE` / `ALTER TABLE` / `DROP TABLE` が DDL、`INSERT` / `SELECT` / `UPDATE` / `DELETE` が DML です。
どちらを書いているのかを意識しておくと、「今は器を作っているのか、中身をいじっているのか」が整理でき、
エラーメッセージや権限まわり（誰がテーブルを作れるか、誰がデータを触れるか）の話も理解しやすくなります。

接続は第0章の通りで、`docker compose up -d` してから:

```bash
psql -h localhost -p 5432 -U todo -d tododb
# あるいは
docker exec -it webapp-training-db psql -U todo -d tododb
```

## 3.1 テーブルを作る（DDL）

ToDo を保存するテーブルを作ってみます。[`CREATE TABLE`](https://www.postgresql.org/docs/current/sql-createtable.html) 文で、
カラム名・型・制約をまとめて宣言します。

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

- **`SERIAL`** は「自動採番される INTEGER」のショートカット。内部では専用の連番カウンター（シーケンス）が
  作られ、`INSERT` で値を省略すると自動で次の番号が割り当てられます。自分で「今の最大値+1」を計算する
  ようなコードを書かずに済み、複数人が同時に `INSERT` しても番号が衝突しません。
  新しめの PostgreSQL では `GENERATED ALWAYS AS IDENTITY` を推奨することもありますが、研修ではわかりやすい `SERIAL` を使います。
- **`TIMESTAMPTZ`** は「タイムゾーン付き時刻」。日付だけなら `DATE`、時刻まで含めるなら `TIMESTAMPTZ` が無難。
  タイムゾーンを持たない `TIMESTAMP` もありますが、サーバーとクライアントで時刻の解釈が食い違って
  ズレる事故が起きやすいので、この研修では「時刻を保存するなら基本 `TIMESTAMPTZ`」と覚えておけば十分です。
- **`NOT NULL`** と **`DEFAULT`** は両方書くのが基本。`NOT NULL` は「このカラムは空にしてはいけない」という
  [制約](https://www.postgresql.org/docs/current/ddl-constraints.html)で、`title` を入れ忘れた `INSERT` を DB 側がエラーで
  止めてくれます。アプリ側のバリデーションだけに頼ると、バグや別経路からの書き込みで空データが紛れ込むことが
  あるため、DB にも「最後の砦」として制約を持たせておくと安心です。`DEFAULT` があれば、そのカラムを
  `INSERT` のときに省略でき、`NOT NULL` と組み合わせても値を確実に埋められます。もっと複雑な条件
  （「優先度は1〜3の範囲」など）を課したい場合は `CHECK` 制約を使います。ここではまだ登場しませんが、
  第9章でちゃんとしたテーブル定義を作るときに使います。
- 主キーは `PRIMARY KEY`、行を一意に決めるカラムを必ずひとつ用意します。主キーには自動的に一意性を
  保証するインデックスが張られるので、`WHERE id = ...` の検索や、後述する `UPDATE` / `DELETE` で
  「狙った1行だけ」を確実に指定するための土台になります。

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

`INSERT INTO todos (title, ...)` のように**カラム名を明示している**のがポイントです。
カラムを省略して `INSERT INTO todos VALUES (...)` と書くこともできますが、その場合はテーブル定義の列順どおりに
値を並べる必要があり、あとで誰かがカラムを増やしたり順番を変えたりしたときに値がズレて壊れます。
少し長くなっても、カラム名を明示するほうが事故が少なく安全です。

複数行をまとめて:

```sql
INSERT INTO todos (title, due_on) VALUES
    ('家賃を振り込む', '2026-05-25'),
    ('車検の見積もり', '2026-06-01'),
    ('週次の振り返り', '2026-05-09');
```

こうして1文にまとめると、`INSERT` を3回発行するよりサーバーとの通信回数が減り、まとめて入れたい件数が
多いほど効いてきます。

`RETURNING` を付けると、**今入れた行のカラム**を取り出せます。
あとで Python から呼び出すとき、生成された `id` を取りたいときに便利。
`RETURNING` がないと「`INSERT` した直後にもう一度 `SELECT` して `id` を取得する」ような書き方をしがちですが、
それだと2回のクエリの間に別の行が挿入されて、狙った行を取り違えるおそれがあります。
`RETURNING` なら `INSERT` と同じ1回のクエリで結果が返るので、この手の事故を避けられます。

```sql
INSERT INTO todos (title) VALUES ('テスト') RETURNING id, created_at;
```

## 3.3 行を読む（SELECT）

最初は素直に。[`SELECT`](https://www.postgresql.org/docs/current/sql-select.html) 文自体はおさらい済みのはずなので、
ここでは ToDo アプリでよく使う書き方を中心に見ていきます。

```sql
SELECT * FROM todos;
SELECT id, title, done FROM todos WHERE done = FALSE;
SELECT * FROM todos ORDER BY due_on NULLS LAST, priority;
```

`psql` で自分の目で確認するだけなら `SELECT *`（全カラム）で構いませんが、アプリのコードから呼ぶ `SELECT` では
**必要なカラムだけを明示する**のが基本です。`SELECT *` のままだと、あとでカラムを追加したときに意図せず
余分なデータまで取ってきたり、コードがどのカラムに依存しているのか読み取りにくくなったりします。

`ORDER BY due_on NULLS LAST` の `NULLS LAST` は「期限未設定（`NULL`）の ToDo を並び替えの最後に回す」指定です。
PostgreSQL は昇順 (`ASC`) だと `NULL` を最後に、降順 (`DESC`) だと最初に置くのがデフォルトの挙動ですが、
「期限が近い順、未設定は後回し」という自然な並びを明示したいときは、こうして書いておくと意図が伝わります。

`LIKE` での部分一致、`IN` での複数一致:

```sql
SELECT * FROM todos WHERE title LIKE '%振%';
SELECT * FROM todos WHERE priority IN (1, 2);
```

`LIKE` の `%` は「任意の0文字以上」にマッチするワイルドカードです（1文字だけにマッチさせたいなら `_`）。
`IN (1, 2)` は `priority = 1 OR priority = 2` の短縮形で、比較したい値が増えるほど `IN` のほうが読みやすくなります。

NULL の扱いは要注意です。**`= NULL` は使えません**。

```sql
-- 期限が設定されていない ToDo
SELECT * FROM todos WHERE due_on IS NULL;

-- 設定されている ToDo
SELECT * FROM todos WHERE due_on IS NOT NULL;
```

!!! note "なぜ `= NULL` が使えないのか"
    `NULL` は「値がない」という特別な状態であって、他の値と等しいかどうかを比較できる普通の値ではありません。
    `due_on = NULL` は `TRUE` にも `FALSE` にもならず、常に「不明（UNKNOWN）」という第三の結果になります。
    `WHERE` 句は「不明」と判定された行を結果に含めないため、`= NULL` では意図した行が絶対に取れません。
    だから専用の `IS NULL` / `IS NOT NULL` を使う必要があります。

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

`UPDATE` と `DELETE` はどちらも `WHERE` で指定した行**だけ**に効きます。裏を返せば、`WHERE` を書き忘れると
テーブルの**全行**が対象になります。`SELECT` で `WHERE` を忘れても「見えるだけ」で実害はありませんが、
`UPDATE` / `DELETE` で `WHERE` を忘れると実データが書き換わったり消えたりするので、`SELECT` 以上に慎重に扱ってください。

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

ここでのポイントは、`psql` は何もしなければ**1文ごとに即座に確定（オートコミット）**することです。
`BEGIN` を打った瞬間から、その後の変更は `COMMIT`（確定）するか `ROLLBACK`（取り消し）するかを自分で選べる
状態になるので、「とりあえず `BEGIN` してから触る」だけで、間違いに気づいたときにやり直せる安全網になります。
[トランザクション](https://www.postgresql.org/docs/current/tutorial-transactions.html)の詳しい仕組みは次章で扱います。

## 3.5 後片付け

ここで作った練習用テーブルは、**第9章でちゃんと設計しなおします**。
一旦消しておきましょう。

```sql
DROP TABLE IF EXISTS todos;
```

`IF EXISTS` を付けておくと、**そのテーブルが存在しない場合でもエラーにならず、何もせず正常終了**します。
付けない `DROP TABLE todos;` は、テーブルがすでに無いときにエラーで止まってしまいます。何度実行しても
安全にしておきたいスクリプト（今回のような練習用のリセットや、後の章で扱うマイグレーション）では、
`IF EXISTS` を付けておくのが定石です。

## やってみよう

`psql` で次のことをやってみましょう。

1. `todos` テーブルを作って、少なくとも 5 行を `INSERT` する。
2. 「完了していない、期限が 7 日以内」の ToDo を `SELECT` する。
3. ID=2 の優先度を 1 に `UPDATE` する。
4. 期限が NULL の ToDo を `DELETE` する。

次は [第 4 章 PostgreSQLのおさらい② JOIN・集約・トランザクション](04-postgres-join-tx.md) で、
複数テーブルやデータ整合性の話を扱います。
