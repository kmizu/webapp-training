# Python + PostgreSQL ToDoアプリ研修

平井さん向けの研修テキストとサンプルコードのリポジトリ。

- 公開先: https://kmizu.github.io/webapp-training/
- テキスト: `docs/`（MkDocs Material）
- サンプル/完成版: `sample/todo-app/`

## ローカルでテキストをプレビュー

```bash
# uv のインストールは公式手順を参照: https://docs.astral.sh/uv/
uv sync --group docs
uv run mkdocs serve
# http://127.0.0.1:8000/ を開く
```

## サンプルアプリを動かす

```bash
cd sample/todo-app
docker compose up -d        # PostgreSQL 起動
uv sync
uv run python -m app.cli init-db     # スキーマ作成
uv run uvicorn app.main:app --reload # http://127.0.0.1:8000/
```

詳細はテキストの「第0章 環境構築」から順に進めてください。

## 章立て

| Part | 章 |
|---|---|
| 1 復習 | 第0章 環境構築 / 第1〜2章 Pythonおさらい / 第3〜4章 PostgreSQLおさらい |
| 2 PythonとDB | 第5章 psycopg入門 / 第6章 プレースホルダとトランザクション / 第7章 プール |
| 3 設計 | 第8章 要件・画面・API設計 / 第9章 テーブル・マイグレーション |
| 4 データ層 | 第10章 Read系 / 第11章 Write系とタグ / 第12章 テスト |
| 5 Web API | 第13章 FastAPI入門 / 第14章 CRUD実装＋テスト |
| 6 画面 | 第15章 Jinja2 / 第16章 htmx |
| 7 仕上げ | 第17章 設定・ログ・例外 / 第18章 公開先と最終課題 |
| 付録 | A SQLチートシート / B 用語集 |
