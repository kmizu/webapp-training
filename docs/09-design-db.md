# 第9章 テーブル設計とマイグレーション

前章で「何を作るか」を決めました。
この章では **DB 側の設計** と、それを **再現可能な形で管理する仕組み**を作ります。

## 9.1 ER 図（テキストで）

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

「多対多」は中間テーブル（`todo_tags`）で表現するのが定石です。

## 9.2 テーブル定義

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

- **`CHECK` 制約** で「タイトルは空NG」「優先度は1-3」を DB レベルで担保。
  アプリのバグで変な値を入れても DB が止めてくれます。
- **`ON DELETE CASCADE`** で「ToDo を消したら関連する `todo_tags` も消える」ようにします。
  これがないと孤児レコードが残ります。
- **`idx_todos_done_due`** は「未完了で期限順に並べる」検索が頻繁なので、
  その複合インデックスを張っています。

!!! note "なぜ priority は SMALLINT？"
    優先度は 1〜3 の小さな整数なので、4 バイトの `INTEGER` ではなく
    2 バイトの `SMALLINT` で十分です。
    何万件もある場合のサイズ差はばかになりません。

## 9.3 マイグレーション戦略

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

!!! tip "実務では Alembic / Flyway を使う"
    本研修では学習目的でシンプルなスクリプトを書きますが、
    実務では **Alembic（Python）** や **Flyway（言語非依存）** など
    実績のあるマイグレーションツールを使ってください。

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

## 9.5 マイグレーションスクリプト（cli.py）

`uv run python -m app.cli init-db` で初期スキーマを入れられるようにします。

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
