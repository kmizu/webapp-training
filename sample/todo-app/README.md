# sample/todo-app

研修テキストの完成形コードです。`docs/` の各章で書き上げる内容と
ほぼ同じものが揃っています。テキストを進めるなかで「動くコード」を
参照したいとき、ここを覗いてください。

## 動かす

```bash
# 1. PostgreSQL を立てる（リポジトリのルートで）
cd ../..
docker compose up -d
cd sample/todo-app

# 2. 依存を入れる
uv sync

# 3. スキーマと初期データを入れる
uv run python -m app.cli init-db

# 4. 起動
uv run uvicorn app.main:app --reload
```

ブラウザで http://127.0.0.1:8000/ を開いてください。

## 構成

```text
app/
├── __init__.py
├── main.py            FastAPI 起動点・ミドルウェア
├── config.py          設定（環境変数）
├── db.py              接続プール
├── models.py          ドメインモデル（dataclass）
├── schemas.py         Pydantic スキーマ
├── repositories.py    SQL を投げる層
├── services.py        業務ロジック（軽く）
├── cli.py             init-db / reset-db
├── routers/
│   ├── __init__.py
│   ├── pages.py       GET / と htmx 用エンドポイント
│   └── todos.py       /api/todos の CRUD
├── templates/         Jinja2
└── static/            CSS
migrations/
├── 001_init.sql
└── 002_seed.sql
tests/
├── conftest.py
├── test_repositories.py
└── test_api.py
```

## テスト

```bash
uv run pytest -v
```

PostgreSQL が立ち上がっていることを前提にしています。
