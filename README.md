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

1. 第0章 環境構築
2. 第1章 Pythonのおさらい
3. 第2章 PostgreSQLのおさらい
4. 第3章 PythonとDBをつなぐ
5. 第4章 ToDoアプリの設計
6. 第5章 データアクセス層を作る
7. 第6章 Web APIを作る
8. 第7章 画面を作る
9. 第8章 仕上げと公開
10. 付録A SQLチートシート / 付録B 用語集
