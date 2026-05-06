# 第8章 仕上げと公開

ここまでで、ブラウザから ToDo を作って、編集して、消せる状態になっています。
最後に、**「他人が触っても壊れない・落ちない・ログが追える」** ようにする
仕上げを入れます。

## 8.1 設定を環境変数にまとめる

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

def build_dsn() -> str:
    return settings.dsn
```

## 8.2 ログを整える

`print` でデバッグするのはやめて、`logging` を使います。

```python
# app/main.py（追記）
import logging
from .config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


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

## 8.3 入力バリデーションをもう一段固める

すでに Pydantic でカラムの長さ・範囲を見ていますが、
**業務ルール**は services 層で見ます。

```python
# app/services.py
from datetime import date

from .models import Todo


def can_set_due_on(due_on: date | None) -> tuple[bool, str | None]:
    """過去日も許す方針だが、極端な未来は不審なのでブロック。"""
    if due_on is None:
        return True, None
    if (due_on - date.today()).days > 365 * 50:
        return False, "期限がだいぶ未来すぎます"
    return True, None
```

「過去日に期限を設定するのは OK か？」のような **ビジネスの判断** は、
SQL や Pydantic ではなく services にまとめておくと、後から変えやすくなります。

## 8.4 例外ハンドリングと 5xx の隠蔽

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

## 8.5 セキュリティの最低ライン

- **SQL は必ずプレースホルダ**（第3章で扱った通り）
- **HTML への埋め込みは Jinja2 が自動エスケープ**してくれる（`safe` フィルタを軽率に使わない）
- **CSRF**: 今回は単一ユーザー前提なので簡略化していますが、複数ユーザーに広げる場合は CSRF トークンが必要
- **依存ライブラリのアップデート**: `uv sync --upgrade` でこまめに更新する習慣
- **本番のパスワードは Git に入れない**: `.env` を `.gitignore` に入れているのを再確認

## 8.6 公開先の選択肢

「自分だけが触る」のか「インターネットに出す」のかで、選ぶ場所が変わります。

| 用途 | 候補 | 一言 |
|---|---|---|
| 自分の PC だけ | そのまま `uvicorn` | 一番気楽 |
| 家庭内 LAN | `--host 0.0.0.0` で起動 | 同じ Wi-Fi の端末から触れる |
| 個人で軽く外に出したい | [Fly.io](https://fly.io/) / [Render](https://render.com/) | 無料枠あり |
| 自由度が欲しい | VPS（さくら / Vultr / DigitalOcean） | ssh と nginx の知識が要る |
| 仕事で使う | クラウド（AWS / GCP / Azure） | 本研修の範囲外 |

外に出す場合は最低限:

1. **HTTPS** にする（[Caddy](https://caddyserver.com/) なら自動）
2. **PostgreSQL は別ホスト**にする（同じコンテナで永続化しない）
3. **バックアップを取る**（`pg_dump` を cron で）

## 8.7 動作確認チェックリスト

完成形を平井さんに渡すときに、このチェックを通しておくと安心です。

- [ ] `docker compose up -d` で DB が起動する
- [ ] `uv run python -m app.cli init-db` でテーブルが作られる
- [ ] `uv run uvicorn app.main:app --reload` で起動する
- [ ] `http://127.0.0.1:8000/` でリストが見える
- [ ] 追加・完了切替・削除がそれぞれ動く
- [ ] フィルタ（全/未/完）と検索が動く
- [ ] `http://127.0.0.1:8000/docs` で Swagger UI が表示される
- [ ] `uv run pytest -v` がぜんぶ緑

## 8.8 これから先のお題

研修としてはここまでですが、続けるなら次のテーマがおすすめです。

1. **複数ユーザー対応**: 認証・認可、ToDo を所有するユーザー、CSRF 対策
2. **マイグレーションの本格化**: Alembic を導入する
3. **コネクションプールの本気運用**: 監視（接続数・スロークエリ）、再接続
4. **CI**: GitHub Actions で `pytest` と `ruff` を回す
5. **デプロイ**: Fly.io か Render に上げて URL を共有してみる
6. **観測**: 構造化ログ（JSON）と Sentry のエラー送信
7. **大量データへの耐性**: 100 万件入れてみて、`EXPLAIN ANALYZE` で見直す

## やってみよう（最終課題）

ここまでで覚えた範囲で、**「自分が欲しい機能」を1つだけ追加** してみてください。
たとえば、

- ToDo に **メモ（複数行）** を持たせる
- ToDo を **CSV にエクスポート**する画面を付ける
- **完了済みは別タブ** に隠す
- **期限が今日のもの**にバッジを付ける

設計（テーブル変更がいるか） → マイグレーション → リポジトリ → API → 画面、
の順で **薄く 1 周** すれば、研修で扱った内容のほとんどを使うはずです。

おつかれさまでした。
あとは [付録A SQLチートシート](appendix-sql.md) と [付録B 用語集](appendix-glossary.md)
に困ったときに戻ってきてください。
