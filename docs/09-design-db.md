# 第9章 テーブル設計とマイグレーション

前章で「何を作るか」を決めました。
この章では **DB 側の設計** と、それを **再現可能な形で管理する仕組み**を作ります。

## 9.1 ER 図（テキストで）

いきなり `CREATE TABLE` を書き始めるのではなく、まずテーブル同士の関係を図に起こしておきます。
文章やコードより先に図で整理しておくと、「この関係は実は多対多だから中間テーブルがいる」
「このテーブルにはこの列が要らないのでは」といった設計の見落としに、SQL を書く前の段階で気づけます。
あとから気づいて本番データが入った後に `ALTER TABLE` で作り直すよりずっと安上がりです。

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
`todos` と `tags` を直接つなごうとして、たとえば `todos` に `tag_id` 列を1つ持たせただけだと、
1件の ToDo に複数のタグを付けられません。逆に `tags` 側に `todo_id` を持たせると、
1つのタグを複数の ToDo に使い回せなくなります。間に `todo_id` と `tag_id` の組だけを持つ
`todo_tags` を挟むことで、「どの ToDo にどのタグが付いているか」を行単位で自由に増減できるようになります。

## 9.2 テーブル定義

ER 図で整理した関係を、実際の [`CREATE TABLE`](https://www.postgresql.org/docs/current/sql-createtable.html) 文に落とし込みます。

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

設計のポイント:

- **[`CHECK` 制約](https://www.postgresql.org/docs/current/ddl-constraints.html)** で「タイトルは空NG」「優先度は1-3」を DB レベルで担保。
  アプリのバグで変な値を入れても DB が止めてくれます。
  こうしたチェックを Python 側だけで書いていると、`psql` から直接触ったり、
  将来別の言語のプログラムから書き込んだりしたときにすり抜けてしまいます。
  DB 自身にルールを持たせておけば、どの経路から書き込んでも同じ制約が働きます。
- **`REFERENCES`（[外部キー制約](https://www.postgresql.org/docs/current/ddl-constraints.html)）** は、
  `todo_tags.todo_id` が必ず `todos.id` に実在する値を指すことを DB に保証させる仕組みです。
  この制約がないと、存在しない `todo_id` を指す `todo_tags` 行を誤って作れてしまい、
  あとで `JOIN` したときに「タグの行はあるのに紐づく ToDo がない」といった、
  気づきにくいデータ不整合を生みます。
- **`ON DELETE CASCADE`** で「ToDo を消したら関連する `todo_tags` も消える」ようにします。
  これを付けずに親（`todos`）行を削除しようとすると、外部キー制約そのものが削除をブロックしてエラーになります
  （子の `todo_tags` 行が参照先を失うのを防ぐためです）。`CASCADE` はその代わりに子行もまとめて消す、という指定で、
  これがないと孤児レコードが残ります。
- **`idx_todos_done_due`** は「未完了で期限順に並べる」検索が頻繁なので、
  その複合[インデックス](https://www.postgresql.org/docs/current/indexes.html)を張っています。
  インデックスがないと、この検索のたびにテーブル全体を先頭から舐める「シーケンシャルスキャン」になり、
  行数が増えるほど遅くなります。インデックスを張れば検索は速くなりますが、
  代わりに書き込み時にはインデックス自体の更新コストが増える、というトレードオフがあることも覚えておいてください。

!!! note "なぜ priority は SMALLINT？"
    優先度は 1〜3 の小さな整数なので、4 バイトの `INTEGER` ではなく
    2 バイトの `SMALLINT` で十分です。
    何万件もある場合のサイズ差はばかになりません。

## 9.3 マイグレーション戦略

**マイグレーション**とは、DB のスキーマ（テーブル定義）の変更履歴を、アプリのソースコードと
同じようにバージョン管理する考え方です。`psql` を開いて手元の DB に直接 `ALTER TABLE` を打って
終わりにしてしまうと、「その変更を誰がいつ何のために行ったか」が残らず、チームの他のメンバーの
環境や本番環境に同じ変更を再現するのも「あのとき打ったコマンド、正確には何だったっけ」と
記憶頼みになってしまいます。変更内容を SQL ファイルとして残しておけば、Git の履歴として追跡でき、
新しい環境でもファイルを順番に適用するだけで同じスキーマを再現できます。

スキーマ変更を **連番付きの SQL ファイル**で管理します。
今回は Alembic などのツールを使わず、手書きの最小実装でやります。

```text
migrations/
├── 001_init.sql
├── 002_seed.sql
└── ...
```

`app.cli init-db` を実行すると、`migrations/` 以下の SQL を **連番順に**実行する仕組みにします。**いつどのファイルまで適用したか**を記録するテーブル `schema_versions` を別に持ちます。

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

適用履歴をわざわざ記録しておく一番の理由は、**同じマイグレーションを何度実行しても安全にする
（[冪等](https://developer.mozilla.org/ja/docs/Glossary/Idempotent)にする）**ためです。
この記録がないと、`init-db` を2回実行しただけで「`todos` はもう存在します」というエラーで
止まってしまったり、`INSERT` 文を含む `002_seed.sql` が二重に実行されてサンプルデータが
重複したりします。「実行済みかどうか」を DB 自身に覚えさせておくことで、`init-db` は
デプロイのたびに何回呼び出しても、未適用のファイルだけを追加で当ててくれる安全な操作になります。

!!! warning "適用済みのファイルは書き換えない"
    一度チームに配布したり本番環境に適用したりしたマイグレーションファイルは、
    あとから中身を書き換えないでください。`schema_versions` は「このバージョン名のファイルは
    実行済み」という記録しか持っておらず、ファイルの中身が変わったこと自体は検知できません。
    テーブル定義を直したくなったら、既存ファイルを編集するのではなく
    `003_xxx.sql` のように**新しいファイルを追加**します（末尾の「やってみよう」で実際にやります）。

!!! tip "実務では Alembic / Flyway を使う"
    本研修では学習目的でシンプルなスクリプトを書きますが、
    実務では **Alembic（Python）** や **Flyway（言語非依存）** など
    実績のあるマイグレーションツールを使ってください。
    こうしたツールは、今回自作した「連番 SQL を順番に適用する」だけの仕組みに加えて、
    変更を巻き戻す **ロールバック（down マイグレーション）**や、
    アプリのモデル定義との差分から SQL を自動生成する機能なども備えています。

## 9.4 マイグレーション SQL ファイル

`migrations/001_init.sql`:

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

`migrations/002_seed.sql`（動作確認用のサンプルデータ）:

```sql
INSERT INTO todos (title, due_on, priority) VALUES
    ('牛乳を買う',          CURRENT_DATE + 1, 2),
    ('健康診断の予約',      CURRENT_DATE + 2, 1),
    ('過去の領収書を整理',  NULL,             3),
    ('家賃を振り込む',      CURRENT_DATE + 18, 1);

INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康')
ON CONFLICT DO NOTHING;
```

!!! note "`ON CONFLICT DO NOTHING` も安全策のひとつ"
    `schema_versions` の仕組みのおかげで、`002_seed.sql` が `init-db` 経由で二重に実行される
    ことはありません。ただ、動作確認のために `psql` からこのファイルを直接流し込む人もいるかもしれません。
    `tags` への `INSERT` に `ON CONFLICT DO NOTHING` を付けておくと、そういう場合でも
    `name` の `UNIQUE` 制約違反でエラーにならず、既に同じ名前の行があれば黙ってスキップしてくれます。

## 9.5 マイグレーションスクリプト（cli.py）

`uv run python -m app.cli init-db` で初期スキーマを入れられるようにします。
やっていることは 9.3 で説明した「未適用のファイルだけ順番に当てる」を、そのまま Python にしただけです。

```python
# app/cli.py
import argparse
from pathlib import Path

from .db import connection

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def init_db() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_versions (
                    version    TEXT        PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT version FROM schema_versions")
            applied = {row["version"] for row in cur.fetchall()}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in applied:
                print(f"  skip  {version} (already applied)")
                continue
            print(f"apply  {version}")
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_versions (version) VALUES (%s)",
                    (version,),
                )


def reset_db() -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DROP TABLE IF EXISTS todo_tags;
            DROP TABLE IF EXISTS tags;
            DROP TABLE IF EXISTS todos;
            DROP TABLE IF EXISTS schema_versions;
            """
        )
    print("reset done")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="マイグレーションを適用する")
    sub.add_parser("reset-db", help="ぜんぶ消す（怖い）")
    args = parser.parse_args()
    if args.cmd == "init-db":
        init_db()
    elif args.cmd == "reset-db":
        reset_db()


if __name__ == "__main__":
    main()
```

`init_db()` の流れを順番に追うと次のようになります。

1. `schema_versions` テーブルを（なければ）作る。ここに `IF NOT EXISTS` が付いているのも、
   このテーブル自体の作成をふくめて `init-db` を何度実行しても失敗させないためです。
2. すでに記録されているバージョン名をぜんぶ読み出して `applied` に集める。
3. `migrations/` 内の `*.sql` ファイルを `sorted()` で**ファイル名順**に処理し、
   `applied` に入っているものは `skip` して読み飛ばし、入っていないものだけ実行して
   `schema_versions` に追加する。

ファイル名を `001_`、`002_` のように**ゼロ埋めの連番**にしているのは、この `sorted()` が
文字列としての並び替えだからです（ゼロ埋めしないと `10_xxx.sql` が `2_xxx.sql` より先に
来てしまいます）。バージョンの識別子には `path.stem`（拡張子を除いたファイル名。たとえば
`"001_init"`）をそのまま使い、`schema_versions.version` の主キーと突き合わせています。

こうして「適用済みならスキップする」を徹底しているおかげで、`init_db()` は開発中に何度呼んでも、
デプロイのたびに CI から呼んでも、そのとき未適用のファイルだけを追加で当ててくれる安全な操作になります。

対して `reset_db()` は、`DROP TABLE IF EXISTS` で関連テーブルを問答無用で全部消すだけの実装です。
`schema_versions` への記録が残っていても一緒に消えてしまうので、次に `init-db` を実行すると
`001` からすべて再適用されます。`main()` のヘルプ文で「ぜんぶ消す（怖い）」と釘を刺しているとおり、
開発中にスキーマをまっさらに戻したいときだけ使う劇薬コマンドです。

## 9.6 動かしてみる

`sample/todo-app/` で:

```bash
docker compose up -d   # （まだなら）リポジトリのルートで実行
cd sample/todo-app
uv sync
uv run python -m app.cli init-db
```

`psql` でテーブルが入ったか確認:

```bash
docker exec -it webapp-training-db psql -U todo -d tododb -c '\dt'
```

`todos`、`tags`、`todo_tags`、`schema_versions` の 4 つが見えれば成功です。

## やってみよう

1. **`migrations/003_add_memo.sql`** を作って、`todos` に `memo TEXT` を追加する
   `ALTER TABLE` を書く。`init-db` で適用されることを確認する。
2. `schema_versions` テーブルを `psql` で見て、適用された 3 行が記録されていることを確認する。
3. `reset-db` を実行してから `init-db` で全部やり直してみる。

次は [第 10 章 ドメインモデルとリポジトリ（Read系）](10-data-read.md) で、
**この設計を Python のコードに落とし込んでいきます**。
