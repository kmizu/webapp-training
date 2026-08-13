# 第9章 テーブル設計とマイグレーション

第8章で「何を作るか」を紙の上で決めました。
この章では、その要件を **DB のテーブル構造**に落とし込み、
定義を **SQL ファイルとして管理する仕組み（マイグレーション）**を作ります。
ここで作る `mytodo/migrations/` が、写経パート最初の成果物です。

## 9.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- 正規化の基本的な考え方（「同じ事実を 1 か所にだけ持つ」）を説明できる
- 多対多の関係を中間テーブルで表現する理由を説明できる
- マイグレーションとは何か、なぜ SQL をファイルで管理するのかを説明できる
- `mytodo/migrations/001_init.sql` と `002_seed.sql` を作成し、
  `tododb` に適用してテーブルと初期データが入った状態にする

**所要時間の目安: 90 分**

この章で実際に手を動かすのは、SQL ファイルを 2 本作って `psql` で流し込む作業です。
その前に、設計の考え方とマイグレーションの概念をしっかり押さえます。

## 9.2 前提知識

テーブル設計に入る前に、2 つの概念を押さえておきます。

!!! note "正規化の初歩"
    **正規化**とは、データの重複や矛盾が起きにくいように、
    テーブルをルールに沿って分割していく設計手法です。
    難しい理論はさておき、入門としては次の 1 文で十分です。

    **同じ事実は、1 か所にだけ書く。**

    たとえば「タグ名」を `todos` テーブルの列にカンマ区切りで持つ設計を考えてみます。

    ```text
    id | title        | tags
    ---+--------------+----------
     1 | 牛乳を買う   | 家事,買い物
     2 | 健康診断の予約 | 健康
    ```

    一見手軽ですが、この設計はすぐに破綻します。

    - 「`家事` タグの付いた ToDo 一覧」が `LIKE '%家事%'` 頼みになり、
      `'家事'` と `'家事（週末）'` のような似た名前を区別できない
    - タグ名を「家事」から「買い物・家事」に変えたいとき、
      その文字列を含む行を全部書き換える必要がある（更新漏れで矛盾が生まれる）
    - ToDo を消すと、その ToDo にしか使われていなかったタグの存在自体が消える

    そこで「タグそのもの」は `tags` テーブルに 1 回だけ書き、
    「どの ToDo にどのタグが付いているか」は `todo_tags` テーブルに書く、
    という 3 テーブルに分けます（第4章で実際に手を動かした構成です）。
    こうすると、タグ名の変更は `tags` の 1 行を更新するだけで済み、
    集約や JOIN も普通の SQL で書けます。

    正規化には「第1正規形」「第2正規形」……という段階がありますが、
    研修で扱うのはこのレベルまでです。
    「同じ値をあちこちにコピーしていないか」「1 つのセルに複数の値を詰めていないか」
    という 2 つの問いを立てられれば十分です。

!!! note "マイグレーションとは（なぜ SQL をファイルで管理するのか）"
    **マイグレーション**とは、DB のスキーマ（テーブル定義）の作成・変更を、
    **連番付きの SQL ファイル**として残し、順番に適用していくやり方です。

    `psql` を開いて手元の DB に直接 `CREATE TABLE` や `ALTER TABLE` を打って
    終わりにしてしまうと、次の問題が起きます。

    - 「いつ・誰が・何のために」その変更をしたかが残らない
    - 別の環境（チームメンバーの PC、本番サーバー）で同じ状態を再現しようとしたとき、
      「あのとき打ったコマンド、正確には何だったっけ」と記憶頼みになる
    - アプリのコードと DB の構造が、どの組み合わせで動くのか追跡できない

    変更内容を SQL ファイルにして Git で管理すれば、これらが全部解決します。
    新しい環境ではファイルを番号順に流し込むだけで同じスキーマを再現でき、
    変更の履歴はコミットログとして残ります。

    ```text
    migrations/
    ├── 001_init.sql   # テーブル定義
    ├── 002_seed.sql   # 初期データ
    └── 003_xxx.sql    # あとからの変更は新しい番号で追加
    ```

    !!! tip "実務では Alembic / Flyway を使う"
        本研修では学習目的で `psql` に手で流し込む最小のやり方を取りますが、
        実務では **Alembic（Python）** や **Flyway（言語非依存）** など
        実績のあるマイグレーションツールを使います。
        これらは「どこまで適用したか」の記録や、変更を巻き戻す
        **ロールバック（down マイグレーション）**の仕組みを備えています。
        なお完成版の `sample/todo-app/` には、連番 SQL を順に適用する
        小さなランナー `app/cli.py`（`uv run python -m app.cli init-db`）が
        付いています。これは DB 接続モジュール（`app/db.py`）が必要なので、
        写経は第10章で `db.py` を作ってから行います。

## 9.3 テーブル設計: ER 図で関係を整理する

いきなり `CREATE TABLE` を書き始めるのではなく、まずテーブル同士の関係を図に起こします。
文章やコードより先に図で整理しておくと、「この関係は実は多対多だから中間テーブルがいる」
「このテーブルにはこの列が要らないのでは」といった設計の見落としに、SQL を書く前の段階で気づけます。
あとから気づいて、データが入った後に `ALTER TABLE` で作り直すよりずっと安上がりです。

第8章で決めた要件（ToDo にタグを 0 個以上付けられる）を図にすると、こうなります。

```text
[todos]              [todo_tags]            [tags]
 id   PK   ─────┐    todo_id  PK,FK ──┐     id    PK
 title          ├──→                   │     name  UNIQUE
 done           │    tag_id   PK,FK ──┘
 due_on         │
 priority       │
 created_at     │
 updated_at     │
                ↑（多対多）
```

図中の `PK`（Primary Key、主キー）は「その行を一意に特定する列」、
`FK`（Foreign Key、外部キー）は「別テーブルの主キーを指す列」を表す略記です。

「多対多」は中間テーブル（`todo_tags`）で表現するのが定石です。
`todos` と `tags` を直接つなごうとして、たとえば `todos` に `tag_id` 列を 1 つ持たせただけだと、
1 件の ToDo に複数のタグを付けられません。逆に `tags` 側に `todo_id` を持たせると、
1 つのタグを複数の ToDo に使い回せなくなります。間に `todo_id` と `tag_id` の組だけを持つ
`todo_tags` を挟むことで、「どの ToDo にどのタグが付いているか」を行単位で自由に増減できるようになります。
この仕組みは第4章で JOIN と一緒に体験済みです。

設計のポイントとして、完成版では第3〜4章の練習用テーブルより制約を強めています。

- **[`CHECK` 制約](https://www.postgresql.org/docs/current/ddl-constraints.html)** で
  「タイトルは空 NG」「優先度は 1〜3」を DB レベルで担保します。
  こうしたチェックを Python 側だけで書いていると、`psql` から直接触ったり、
  将来別のプログラムから書き込んだりしたときにすり抜けてしまいます。
  DB 自身にルールを持たせておけば、どの経路から書き込んでも同じ制約が働きます
  （実際に制約違反が弾かれるところは、章末の「やってみよう」で確かめます）。
- **`ON DELETE CASCADE`**（第4章で扱いました）は、ToDo を消したときに
  関連する `todo_tags` の行も自動で消す設定です。これがないと、
  タグの付いた ToDo を消そうとするたびに外部キー違反でエラーになります。
- **`idx_todos_done_due`** は「未完了で期限順に並べる」という、
  このアプリで一番頻繁な検索（第8章の画面設計の一覧そのもの）のための
  複合[インデックス](https://www.postgresql.org/docs/current/indexes.html)です。
  インデックスがないと、この検索のたびにテーブル全体を先頭から舐める
  「シーケンシャルスキャン」になり、行数が増えるほど遅くなります。
  インデックスを張れば検索は速くなりますが、代わりに書き込み時には
  インデックス自体の更新コストが増える、というトレードオフがあります。

!!! note "なぜ priority は SMALLINT？"
    優先度は 1〜3 の小さな整数なので、4 バイトの `INTEGER` ではなく
    2 バイトの `SMALLINT` で十分です。
    何万件もある場合のサイズ差はばかになりません。

## 9.4 マイグレーションファイルを作る

いよいよ写経です。第8章で作った `mytodo/` の下に `migrations/` ディレクトリを作り、
SQL ファイルを 2 つ作成します。リポジトリのルートで次を実行してください。

```bash
mkdir mytodo/migrations
```

成功すると何も表示されません。

### 001_init.sql（テーブル定義）

`mytodo/migrations/001_init.sql` を新規作成し、次を**自分の手で**打ち込んでください
（コピー＆ペーストではなく。写経の約束は第8章で確認したとおりです）。

```sql
CREATE TABLE todos (
    id          SERIAL      PRIMARY KEY,
    title       TEXT        NOT NULL CHECK (length(title) > 0),
    done        BOOLEAN     NOT NULL DEFAULT FALSE,
    due_on      DATE,
    priority    SMALLINT    NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_todos_done_due ON todos (done, due_on);

CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT   UNIQUE NOT NULL CHECK (length(name) > 0)
);

CREATE TABLE todo_tags (
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
);
```

書き終わったら、完成版と差分がないことを確認します。

```bash
diff -u mytodo/migrations/001_init.sql sample/todo-app/migrations/001_init.sql
```

何も表示されなければ完成版と一致しています（差分なしがゴールです）。

`todo_tags` の外部キーが `INTEGER` になっているのは、参照先の `SERIAL` の実体が
`INTEGER` だからです。`todos` より先に `todo_tags` を作ると
「参照先のテーブルがありません」というエラーになるので、
**作成は参照される側（`todos`、`tags`）が先、中間テーブルが後**の順番になっています。

### 002_seed.sql（初期データ）

続けて `mytodo/migrations/002_seed.sql` を作成し、次を打ち込んでください。
動作確認用のサンプルデータを入れるファイルです。

```sql
INSERT INTO todos (title, due_on, priority) VALUES
    ('牛乳を買う',          CURRENT_DATE + 1, 2),
    ('健康診断の予約',      CURRENT_DATE + 2, 1),
    ('過去の領収書を整理',  NULL,             3),
    ('家賃を振り込む',      CURRENT_DATE + 18, 1);

INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康')
ON CONFLICT DO NOTHING;

INSERT INTO todo_tags (todo_id, tag_id)
SELECT t.id, g.id
  FROM todos t
  JOIN tags  g ON g.name = '家事'
 WHERE t.title = '牛乳を買う'
ON CONFLICT DO NOTHING;

INSERT INTO todo_tags (todo_id, tag_id)
SELECT t.id, g.id
  FROM todos t
  JOIN tags  g ON g.name = '健康'
 WHERE t.title = '健康診断の予約'
ON CONFLICT DO NOTHING;
```

```bash
diff -u mytodo/migrations/002_seed.sql sample/todo-app/migrations/002_seed.sql
```

こちらも何も表示されなければ一致です。

`todo_tags` への `INSERT` は、第4章のように番号を直接書く（`VALUES (1, 1)`）のではなく、
**`INSERT INTO ... SELECT`** の形で「タイトルとタグ名から id を引いて挿入」しています。
マイグレーションとして何度も作り直すことを考えると、連番の id を前提にした
固定値より、こちらのほうが安全です。

!!! note "ON CONFLICT DO NOTHING は安全策"
    `tags` と `todo_tags` への `INSERT` には `ON CONFLICT DO NOTHING` が付いています。
    うっかりこのファイルを 2 回流し込んだときでも、
    `name` の `UNIQUE` 制約や `todo_tags` の複合主キーに引っかかって
    エラーで止まることがなく、既存の行は黙ってスキップされます。
    （`todos` のほうは重複して入ってしまうので、やはり「2 回流さない」ことが
    大前提です。詳しくは 9.8 のつまずきポイントを参照してください。）

!!! warning "適用済みのファイルは書き換えない"
    いったん環境に適用したマイグレーションファイルを、あとから書き換えてはいけません。
    「ファイルの中身を直しても、すでに適用済みの DB には反映されない」という
    静かな不整合のもとになります。テーブル定義を直したくなったら、
    既存ファイルを編集するのではなく `003_xxx.sql` のように
    **新しい番号のファイルを追加**します（章末の「やってみよう」で実際にやります）。

ファイル名を `001_`、`002_` のように**ゼロ埋めの連番**にしているのは、
ファイル名順に並べたときに適用順と一致させるためです。
ゼロ埋めしないと `10_xxx.sql` が `2_xxx.sql` より先に来てしまいます。

## 9.5 練習用テーブルを片付ける（先に必ずやる）

ここで **1 つだけ先に片付けておくもの** があります。

第3〜4章で、あなたの `tododb` には練習用の `todos`（7 行）、`tags`、`todo_tags`
というテーブルが入っているはずです。これらは名前こそ同じですが、
**今回作るものとは別物**（`CHECK` 制約やインデックスがありません）です。
このまま `001_init.sql` を流し込むと、こうなります。

```text
psql:mytodo/migrations/001_init.sql:9: ERROR:  relation "todos" already exists
```

「テーブルはもうあるよ」と言われて、新しい定義は作られません。
そこで、練習用テーブルはここで**消してしまいます**。
第3〜4章の練習データはこの後の章では使いません。

まず今の状態を確認します。

```text
\dt
```

期待される出力（第3〜4章までの練習をすべてやった場合）:

```text
         List of relations
 Schema |   Name    | Type  | Owner 
--------+-----------+-------+-------
 public | tags      | table | todo
 public | todo_tags | table | todo
 public | todos     | table | todo
(3 rows)
```

次の SQL を実行して、練習用テーブルを削除してください
（外部キーで参照されている `todo_tags` から先に消す順番です）。

```sql
DROP TABLE todo_tags;
DROP TABLE tags;
DROP TABLE todos;
```

期待される出力:

```text
DROP TABLE
DROP TABLE
DROP TABLE
```

なお、第4章の問5（任意の後片付け問題）で `tags` と `todo_tags` を
すでに消している人は、最初の 2 行で
`ERROR: table "todo_tags" does not exist` のようなエラーが出ますが問題ありません。
`todos` さえ消えれば OK です（エラーを避けたい場合は、
`DROP TABLE IF EXISTS todo_tags;` のように `IF EXISTS` を付けてください）。

もう一度 `\dt` を実行して `Did not find any relations.` と出れば、
まっさらな状態に戻っています。

!!! warning "DROP TABLE は取り消せない"
    `DROP TABLE` はデータごと消え、ロールバックもできません
    （トランザクションの外で実行した場合）。**練習用の 3 テーブルだけ**を
    消しているか、実行前に必ず `\dt` で名前を確認してください。

## 9.6 マイグレーションを適用する

いよいよ `mytodo/migrations/` の SQL を `tododb` に流し込みます。
ファイルの中身をそのまま実行する `psql -f` を使います。
リポジトリのルートで実行してください。

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb -f mytodo/migrations/001_init.sql
    ```

=== "Docker 経由の場合"

    ```bash
    docker exec -i webapp-training-db psql -U todo -d tododb < mytodo/migrations/001_init.sql
    ```

期待される出力（どちらの方法でも同じです）:

```text
CREATE TABLE
CREATE INDEX
CREATE TABLE
CREATE TABLE
```

4 つの文（`CREATE TABLE` × 3 と `CREATE INDEX` × 1）が順番に実行されたことがわかります。
続けて `002_seed.sql` も流し込みます。

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb -f mytodo/migrations/002_seed.sql
    ```

=== "Docker 経由の場合"

    ```bash
    docker exec -i webapp-training-db psql -U todo -d tododb < mytodo/migrations/002_seed.sql
    ```

期待される出力:

```text
INSERT 0 4
INSERT 0 3
INSERT 0 1
INSERT 0 1
```

`INSERT 0 4` は「4 行挿入された」という意味です。
`todos` に 4 行、`tags` に 3 行、`todo_tags` に 1 行ずつ、計 4 回の挿入が成功しました。

ここからは psql に接続して（第3章と同じ手順です）、中身を確認します。

```text
\dt
```

期待される出力:

```text
         List of relations
 Schema |   Name    | Type  | Owner 
--------+-----------+-------+-------
 public | tags      | table | todo
 public | todo_tags | table | todo
 public | todos     | table | todo
(3 rows)
```

名前は 9.5 で消す前と同じですが、中身は**新しい定義**です。
`\d todos` で制約が付いていることを確認しましょう。

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
    "idx_todos_done_due" btree (done, due_on)
Check constraints:
    "todos_priority_check" CHECK (priority >= 1 AND priority <= 3)
    "todos_title_check" CHECK (length(title) > 0)
Referenced by:
    TABLE "todo_tags" CONSTRAINT "todo_tags_todo_id_fkey" FOREIGN KEY (todo_id) REFERENCES todos(id) ON DELETE CASCADE
```

`Indexes:` に `idx_todos_done_due`、`Check constraints:` に 2 つの `CHECK` が
見えていれば、第3章で作った練習用テーブルとは別物の、新しい定義だと確認できます。

なお、`CHECK (priority BETWEEN 1 AND 3)` と書いた制約は、
`\d` では `CHECK (priority >= 1 AND priority <= 3)` と表示されます。
`BETWEEN` は内部で `>=` と `<=` の組み合わせに書き換えられて保持されるためで、
意味はまったく同じです。

最後に、入ったデータを見てみます。

```sql
SELECT id, title, done, priority FROM todos ORDER BY id;
```

期待される出力:

```text
 id |       title        | done | priority 
----+--------------------+------+----------
  1 | 牛乳を買う         | f    |        2
  2 | 健康診断の予約     | f    |        1
  3 | 過去の領収書を整理 | f    |        3
  4 | 家賃を振り込む     | f    |        1
(4 rows)
```

（期限の `due_on` は `CURRENT_DATE` 基準で入るため、流し込んだ日付によって値が変わります。
ここでは日付の列を除いて表示しています。）

タグの紐付けも、第4章で覚えた JOIN で確認できます。

```sql
SELECT t.title, g.name AS tag
  FROM todo_tags tt
  JOIN todos t ON t.id = tt.todo_id
  JOIN tags  g ON g.id = tt.tag_id
 ORDER BY tt.todo_id;
```

期待される出力:

```text
     title      | tag  
----------------+------
 牛乳を買う     | 家事
 健康診断の予約 | 健康
(2 rows)
```

これで、このアプリの DB 側の土台ができました。
第10章以降は、このテーブルに Python からアクセスするコードを書いていきます。

## 9.7 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認してください。

- [ ] 正規化の基本（同じ事実は 1 か所にだけ書く）を、カンマ区切りタグの例で説明できる
- [ ] 多対多を中間テーブルで表現する理由を説明できる
- [ ] マイグレーションとは何か、なぜ SQL をファイルで管理するのかを説明できる
- [ ] `mytodo/migrations/001_init.sql` と `002_seed.sql` を作成し、
      `diff` で完成版との一致を確認した
- [ ] 練習用テーブルを `DROP TABLE` で削除してから、2 つのマイグレーションを適用した
- [ ] `\d todos` で `CHECK` 制約と `idx_todos_done_due` が見えることを確認した

## 9.8 つまずきポイント

### `ERROR: relation "todos" already exists`

9.5 の片付けを飛ばして `001_init.sql` を流したときのエラーです。

```text
psql:mytodo/migrations/001_init.sql:9: ERROR:  relation "todos" already exists
CREATE INDEX
psql:mytodo/migrations/001_init.sql:16: ERROR:  relation "tags" already exists
psql:mytodo/migrations/001_init.sql:22: ERROR:  relation "todo_tags" already exists
```

対処は 9.5 どおり、練習用の 3 テーブルを `DROP TABLE` してから流し直すだけです。

ここで注意したいのが、2 行目の `CREATE INDEX` が**成功してしまう**ことです。
練習用の `todos` にも `done` と `due_on` 列があるため、インデックスだけは
古いテーブルの上に作られてしまいます。`psql -f` は途中でエラーが出ても
デフォルトでは最後まで実行を続けるので、**エラーの有無は終了コードや最後の行ではなく、
出力をすべて読んで判断する**癖を付けてください。

### `psql: error: mytodo/migrations/001_init.sql: No such file or directory`

`psql -f` に渡すパスは、**コマンドを実行した場所からの相対パス**です。
この章のコマンドはリポジトリのルートで実行する前提なので、
`mytodo/` の中や `migrations/` の中に移動したまま実行するとこのエラーになります。
リポジトリのルートに戻るか、実際の場所に合わせてパスを直してください。

### Docker 経由でファイルを流し込めない

`docker exec` にファイルを読ませるときは、コンテナの中からは
ホストの `mytodo/` が見えないため、`<` で標準入力に流し込む形にします。
このときオプションは `-it` ではなく **`-i` だけ**にしてください
（`-t` が付いているとリダイレクトが正しく働きません）。

```bash
docker exec -i webapp-training-db psql -U todo -d tododb < mytodo/migrations/001_init.sql
```

### 002_seed.sql を 2 回流してしまった

`tags` と `todo_tags` は `ON CONFLICT DO NOTHING` のおかげで増えませんが、
`todos` にはそのおまじないがないため、**同じ 4 件が重複して入ります**
（合計 8 行になります）。練習のうちは気にせず進めても構いませんが、
きれいにしたければ `TRUNCATE todos, tags, todo_tags;` で空にしてから
`002_seed.sql` を流し直してください。

「適用済みかどうか」を DB に記録して、未適用のファイルだけを当てる
仕組みまで作り込むと、完成版の `app/cli.py`（第10章以降で写経します）や、
実務の Alembic / Flyway になります。

## 9.9 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べてください。

### 問1 003_add_memo.sql を書いて適用する

ToDo に「メモ」（任意の補足説明）を持たせたくなりました。
`mytodo/migrations/003_add_memo.sql` を新規作成し、
`todos` に `memo TEXT` 列（`NULL` 可、既存行は `NULL` のまま）を追加する
`ALTER TABLE` を書いて、適用してください。
既存の `001_init.sql` は**書き換えない**のがルールです。

??? example "解答例"

    `mytodo/migrations/003_add_memo.sql`:

    ```sql
    ALTER TABLE todos ADD COLUMN memo TEXT;
    ```

    適用（リポジトリのルートで）:

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb -f mytodo/migrations/003_add_memo.sql
    ```

    期待される出力:

    ```text
    ALTER TABLE
    ```

    `\d todos` で `memo | text` の行が増えていれば成功です。
    既存ファイルを編集せず新しい番号で追加する、という
    マイグレーションの基本の流れそのものです。

### 問2 正規化されていない設計を直す

ある人が「ToDo の担当者」を管理するために、
`todos` に `assignees TEXT` 列を追加して、
`'佐藤, 鈴木'` のようにカンマ区切りで名前を入れる設計にしました。
この設計の問題点を 2 つ以上挙げ、正規化するとしたら
どんなテーブル構成にするか説明してください。

??? example "解答例"

    問題点の例:

    - 「鈴木さんの担当タスク一覧」を取るのに `LIKE '%鈴木%'` 頼みになり、
      同姓同名や表記ゆれ（`'鈴木'` と `'鈴木 '`）を正しく扱えない
    - 担当者の名前を変更したいとき、その人を含む行をすべて書き換える必要がある
    - 担当者そのものの情報（メールアドレスなど）を持つ場所がない

    正規化すると、タグと同じ多対多の構造になります。

    ```text
    users (id, name, ...)            … 担当者そのもの
    todo_assignees (todo_id, user_id) … 中間テーブル
    ```

    「同じ事実（担当者の名前）は `users` に 1 回だけ書き、
    対応関係は中間テーブルに持つ」という、
    `tags` / `todo_tags` とまったく同じパターンです。

### 問3 CHECK 制約が本当に効いているか確かめる

9.3 で「DB 自身にルールを持たせる」と説明しました。
実際に、制約に違反する `INSERT` を 2 つ（タイトルが空文字のもの、
優先度が `9` のもの）を `psql` で実行して、
それぞれどんなエラーになるか確かめてください。

??? example "解答例"

    ```sql
    INSERT INTO todos (title) VALUES ('');
    ```

    期待される出力:

    ```text
    ERROR:  new row for relation "todos" violates check constraint "todos_title_check"
    DETAIL:  Failing row contains (5, , f, null, 2, 2026-08-14 00:21:33.164587+09, 2026-08-14 00:21:33.164587+09).
    ```

    ```sql
    INSERT INTO todos (title, priority) VALUES ('テスト', 9);
    ```

    期待される出力:

    ```text
    ERROR:  new row for relation "todos" violates check constraint "todos_priority_check"
    DETAIL:  Failing row contains (6, テスト, f, null, 9, 2026-08-14 00:21:33.207399+09, 2026-08-14 00:21:33.207399+09).
    ```

    （`DETAIL:` 行の id とタイムスタンプは実行環境によって変わります。）

    どちらも DB が挿入を拒否しています。
    `psql` から直接打ったこの経路でも制約が働く——これが、
    ルールを Python 側ではなく DB に持たせることの効果です。

## まとめ

- 正規化の基本は **「同じ事実は 1 か所にだけ書く」**。
  カンマ区切りの詰め込みは、検索・更新・整合性のすべてで破綻する
- 多対多は **中間テーブル**（`todo_tags`）で表現する
- **マイグレーション** = スキーマの作成・変更を連番 SQL ファイルで管理し、
  順番に適用するやり方。再現性と変更履歴のためにファイルで管理する
- 適用済みのマイグレーションファイルは書き換えず、変更は **新しい番号のファイル**で追加する
- 第3〜4章の練習用テーブルは同名で衝突するため、
  `DROP TABLE` で片付けてから `mytodo/migrations/` を適用した

次は [第10章 ドメインモデルとリポジトリ（Read系）](10-data-read.md) で、
いよいよ Python のコードを書き始めます。
この章で作ったテーブルから、psycopg（第5〜7章）を使ってデータを読み出します。
