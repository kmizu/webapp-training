# 第17章 設定・ログ・例外ハンドリング

ここまでで、ブラウザから ToDo を作って、編集して、消せる状態になっています。
この章は **「他人が触っても壊れない」** 状態にするための地味だけど大事な仕上げ。

- 設定を環境変数にまとめる
- `logging` で記録する
- 例外を集約して 5xx のスタックトレースを漏らさない
- セキュリティの最低ライン

公開先の選択肢と最終課題は次章です。

## 17.1 設定オブジェクト

ハードコードしない、バージョン管理に入れない。これは原則。

`app/config.py` を作ると見通しがよくなります。

```python
# app/config.py
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "tododb")
    db_user: str = os.getenv("DB_USER", "todo")
    db_password: str = os.getenv("DB_PASSWORD", "todo")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password}"
        )


settings = Settings()
```

`db.py` 側でこれを使うように差し替えます。

```python
# app/db.py
from .config import settings

# 既存の build_dsn() の代わりに settings.dsn を使う
```

## 17.2 ログを整える

`print` でデバッグするのはやめて、`logging` を使います。

```python
# app/main.py（追記）
import logging
from .config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("todo-app")


@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response
```

これで全リクエストが INFO で 1 行ずつ流れるようになります。
詳しく見たいときだけ `LOG_LEVEL=DEBUG` で起動します。

!!! tip "ログにパスワードや個人情報を出さない"
    ありがちな事故です。フォームの中身をそのまま `logger.info(payload)` してしまうと、
    パスワードや個人情報がログに残ります。**「何が来たか」を記録する場合は
    必ずフィルタを書く**こと。

## 17.3 例外ハンドリングと 5xx の隠蔽

開発中は良くても、外に出すなら **「内部実装が漏れない」**ように整えます。

```python
# app/main.py（追記）
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def fallback_handler(request, exc):
    logger.exception("unhandled error: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )
```

スタックトレースは **ログに残し**、レスポンスには **詳細を出さない**。
これは情報漏洩防止の基本です。

特定の例外を 4xx に変換する例:

```python
import psycopg.errors as pgerr


@app.exception_handler(pgerr.UniqueViolation)
async def unique_violation_handler(_request, exc: pgerr.UniqueViolation):
    return JSONResponse(
        status_code=409,
        content={"detail": "重複エラー"},
    )


@app.exception_handler(pgerr.CheckViolation)
async def check_violation_handler(_request, exc: pgerr.CheckViolation):
    return JSONResponse(
        status_code=400,
        content={"detail": "値の制約違反"},
    )
```

## 17.4 入力バリデーションをもう一段固める

すでに Pydantic でカラムの長さ・範囲を見ていますが、
**業務ルール**は services 層で見ます。

```python
# app/services.py
from datetime import date


def validate_due_on(due_on: date | None) -> tuple[bool, str | None]:
    """過去日も許す方針だが、極端な未来は不審なのでブロック。"""
    if due_on is None:
        return True, None
    if (due_on - date.today()).days > 365 * 50:
        return False, "期限がだいぶ未来すぎます"
    return True, None
```

「過去日に期限を設定するのは OK か？」のような **ビジネスの判断** は、
SQL や Pydantic ではなく services にまとめておくと、後から変えやすくなります。

## 17.5 セキュリティの最低ライン

- **SQL は必ずプレースホルダ**（第6章で扱った通り）
- **HTML への埋め込みは Jinja2 が自動エスケープ**してくれる（`safe` フィルタを軽率に使わない）
- **CSRF**: 今回は単一ユーザー前提なので簡略化していますが、複数ユーザーに広げる場合は CSRF トークンが必要
- **依存ライブラリのアップデート**: `uv sync --upgrade` でこまめに更新する習慣
- **本番のパスワードは Git に入れない**: `.env` を `.gitignore` に入れているのを再確認
- **`.env.example` に値は入れない**: 名前だけ書く。例値はダミーであっても本番に流れることがある

## 17.6 ヘルスチェック

外に出すなら、稼働確認用のエンドポイントを 1 つ用意しておきます。

```python
@app.get("/health")
def health(conn: Conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"ok": True}
```

監視ツールがこれを定期的に叩いて、応答が 200 でなくなったらアラートを上げる、
という使い方が一般的です。

## やってみよう

1. `LOG_LEVEL=DEBUG` で起動して、ログがどう変わるか観察する。
2. `/api/todos` で **わざと 500 を起こす**（たとえば repository の中で `1/0` する）
   ことで、`fallback_handler` が動く様子を見る。レスポンスにスタックトレースが
   含まれていないことを確認する。
3. `psycopg.errors.UniqueViolation` を起こせる状況を作って（同じ名前のタグを直接 INSERT）、
   API 経由で 409 が返ることを確認する。

次は [第 18 章 公開先と最終課題](18-deploy.md) で、
**どこにデプロイするか**と、研修全体の **総仕上げ課題**を扱います。
