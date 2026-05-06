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
