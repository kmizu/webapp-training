# 第18章 公開先と最終課題

研修の最終章です。
**どこに置くか**の選択肢と、研修全体を踏まえた **総仕上げの課題**を扱います。

## 18.1 公開先の選択肢

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
4. **環境変数を本番値に差し替える**（`DB_PASSWORD` など）

## 18.2 LAN 公開の試し方

ちょっと触る程度なら、まず家庭内 LAN で十分です。

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

スマホで `http://<PCのローカルIP>:8000/` を開くと触れます。
PC の IP アドレスは:

```bash
# Linux / macOS
ip addr show | grep inet
# Windows (PowerShell)
ipconfig
```

！ ファイアウォールでブロックされていることがあります。
研修目的なら一時的に通してもいいですが、**作業が終わったら戻す**こと。

## 18.3 簡単なコンテナ化（参考）

将来 Fly.io などにデプロイする想定なら、Dockerfile を作っておくのが便利です。
（研修必須ではありません）

```dockerfile
# Dockerfile（例）
FROM python:3.12-slim

ENV UV_LINK_MODE=copy
RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY migrations ./migrations

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 18.4 動作確認チェックリスト

完成形を平井さんに渡すときに、このチェックを通しておくと安心です。

- [ ] `docker compose up -d` で DB が起動する
- [ ] `uv run python -m app.cli init-db` でテーブルが作られる
- [ ] `uv run uvicorn app.main:app --reload` で起動する
- [ ] `http://127.0.0.1:8000/` でリストが見える
- [ ] 追加・完了切替・削除がそれぞれ動く
- [ ] フィルタ（全/未/完）と検索が動く
- [ ] `http://127.0.0.1:8000/docs` で Swagger UI が表示される
- [ ] `uv run pytest -v` がぜんぶ緑

## 18.5 これから先のお題

研修としてはここまでですが、続けるなら次のテーマがおすすめです。

1. **複数ユーザー対応**: 認証・認可、ToDo を所有するユーザー、CSRF 対策
2. **マイグレーションの本格化**: Alembic を導入する
3. **コネクションプールの本気運用**: 監視（接続数・スロークエリ）、再接続
4. **CI**: GitHub Actions で `pytest` と `ruff` を回す
5. **デプロイ**: Fly.io か Render に上げて URL を共有してみる
6. **観測**: 構造化ログ（JSON）と Sentry のエラー送信
7. **大量データへの耐性**: 100 万件入れてみて、`EXPLAIN ANALYZE` で見直す

## 18.6 最終課題

研修の総仕上げです。
ここまで覚えた範囲で、**「自分が欲しい機能」を 1 つだけ追加** してみてください。

たとえば:

- ToDo に **メモ（複数行）** を持たせる
- ToDo を **CSV にエクスポート**する画面を付ける
- **完了済みは別タブ** に隠す
- **期限が今日のもの**にバッジを付ける
- **タグ別の件数**をフッタに表示

進め方の目安:

1. **設計**: テーブル変更が要るか、API はどうなるか、画面はどう見えるか
2. **マイグレーション**: 必要なら `migrations/00X_xxx.sql` を追加して `init-db`
3. **リポジトリ**: SQL を書いて、テストを書く
4. **API**: スキーマを更新して、ルーターに足し、テストを書く
5. **画面**: テンプレートと CSS を更新する
6. **動作確認**: チェックリストを通す

「**薄く 1 周**」すれば、研修で扱った内容のほとんどを使うはずです。
余裕があれば、**コミットを機能ごとに分けて、PR の説明文を書く**ところまでやると、
そのまま実務の流れになります。

## 18.7 振り返り

研修おつかれさまでした。

ここまでで触れた主なテーマを並べると:

- Python の型ヒント・dataclass・with・モジュール
- pytest の基本
- PostgreSQL の DDL/DML/JOIN/集約/トランザクション
- psycopg v3 の接続、プレースホルダ、トランザクション、プール
- 設計（要件・画面・API・テーブル・マイグレーション）
- Repository パターン
- FastAPI と依存性注入
- Pydantic でのバリデーション
- Jinja2 + htmx の軽量UI
- 設定・ログ・例外ハンドリング・セキュリティ

ほとんどが「**実務でも同じ顔ぶれで出てくる**」道具です。
あとは作るものが変わるだけ。

困ったら [付録A SQLチートシート](appendix-sql.md) と
[付録B 用語集](appendix-glossary.md) を覗いてください。
