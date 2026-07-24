# 第17章 設定・ログ・例外ハンドリング

ここまでで、ブラウザから ToDo を作って、編集して、消せる状態になっています。
この章は **「他人が触っても壊れない」** 状態にするための地味だけど大事な仕上げ。

- 設定を環境変数にまとめる
- `logging` で記録する
- 例外を集約して 5xx のスタックトレースを漏らさない
- セキュリティの最低ライン

共通しているのは、**自分ひとりで動かしている間は気づきにくいが、
他人や本番環境が触れた瞬間に効いてくる**という点です。

公開先の選択肢と最終課題は次章です。

## 17.1 設定オブジェクト

ハードコードしない、バージョン管理に入れない。これは原則。

**環境変数にする理由は大きく 2 つ**あります。1 つは、同じコードのまま開発・テスト・
本番で設定だけを切り替えられること。DB のホスト名やパスワードは環境ごとに違うのが
普通なので、コードを書き換えずに起動時の環境変数だけ差し替えられると楽です。
もう 1 つは、パスワードや API キーのような**秘密情報をコードに書かないため**です。
一度 Git にコミットすると、あとから消しても履歴には残り続け、すでに `clone` された
分は取り消せません。第7章では `build_dsn()` という関数でこれを仮に実装しましたが、
ここでは `app/config.py` に**設定専用のオブジェクト**としてまとめ直します。

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

[dataclasses](https://docs.python.org/3/library/dataclasses.html) の `frozen=True` は
第1章で見た通り、一度作った値をあとから書き換えられなくする指定です。設定値は
アプリの動作中にコロコロ変わってほしくないので、ここでも同じ理由で付けています。
`os.getenv("DB_HOST", "localhost")` の第 2 引数は、その環境変数が**設定されていない
ときのフォールバック値**です。ローカル開発では便利ですが、本番では `DB_PASSWORD` の
ようなフォールバックにだけは頼らず、必ず環境変数を明示的に設定してください
（デフォルト値の `"todo"` はあくまで研修用の docker-compose に合わせた仮の値です）。
最後の `settings = Settings()` で、モジュールが最初に読み込まれたタイミングで
**1 回だけ**環境変数を読み込み、以降は `from .config import settings` として
アプリのどこからでも同じインスタンスを参照します。

`db.py` 側でこれを使うように差し替えます。

```python
# app/db.py
from .config import settings

# 既存の build_dsn() の代わりに settings.dsn を使う
```

## 17.2 ログを整える

`print` でデバッグするのはやめて、[`logging`](https://docs.python.org/3/library/logging.html)
を使います。第2章で少し触れた通り、`print` はその場でコンソールに文字を出すだけで、
**重要度による絞り込み**も**出力先の切り替え**もできません。`logging` を使うと、
メッセージに DEBUG／INFO／WARNING／ERROR／CRITICAL という**重要度（レベル）**を
付けられるので、「普段は落ち着いたログだけ見たいけど、調査のときだけ詳細も見たい」を
設定 1 つで切り替えられます。出力先もコンソールだけでなくファイルや外部の集約基盤に
差し替えられるので、本番運用ではほぼ必須の道具です。

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

`logging.basicConfig(level=settings.log_level, ...)` は、アプリ全体のログ出力の土台
（フォーマットと最低レベル）を**起動時に一度だけ**設定します。レベルには
`DEBUG < INFO < WARNING < ERROR < CRITICAL` という順序があり、`level` に指定した
レベル**以上**のログだけが実際に出力される仕組みです。デフォルトの `INFO` で起動すると
`logger.debug(...)` は表示されず、`LOG_LEVEL=DEBUG` にすると全部見えるようになります。
`logging.getLogger("todo-app")` のように名前を付けておくと、ログの出どころ（どのアプリ・
モジュールから出た行か）が一目でわかり、あとからモジュールごとにレベルを変えたくなった
ときにも対応できます。

これで全リクエストが INFO で 1 行ずつ流れるようになります。
詳しく見たいときだけ `LOG_LEVEL=DEBUG` で起動します。

!!! tip "ログにパスワードや個人情報を出さない"
    ありがちな事故です。フォームの中身をそのまま `logger.info(payload)` してしまうと、
    パスワードや個人情報がログに残ります。**「何が来たか」を記録する場合は
    必ずフィルタを書く**こと。ログはコードよりも保存期間が長く、外部の集約サービスに
    転送されることも多いので、うっかり書き込むと**気づかないまま長期間残ってしまう**
    リスクがあります。

## 17.3 例外ハンドリングと 5xx の隠蔽

開発中は良くても、外に出すなら **「内部実装が漏れない」**ように整えます。
何もハンドラを書かないと、想定外の例外が起きたときに Python のスタックトレース
（ファイルパス、関数名、ときには実行中の SQL 文まで）がそのままレスポンスに
出てしまうことがあります。これは攻撃者にとって**「次に何を狙えばいいか」の
ヒント**になってしまうので、外部公開するアプリでは必ず塞いでおきたいポイントです。
FastAPI では [`@app.exception_handler`](https://fastapi.tiangolo.com/tutorial/handling-errors/)
を使うと、特定の例外クラスが発生したときのレスポンスをアプリ全体でまとめて
定義できます。

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

`@app.exception_handler(Exception)` は、Python の組み込み例外を含めて**ありとあらゆる
例外**を拾う、最後の砦のハンドラです。個別の `try/except` を書き忘れた場所があっても、
ここで必ず捕まって定型のレスポンスに変換されます。中の `logger.exception(...)` は
`logger.error(...)` と違い、**呼ばれた時点のスタックトレースを自動でログに埋め込みます**
（`except` ブロックの中で呼ぶのが前提です）。これで「サーバー側の記録には全部残す、
クライアントへの応答には何も出さない」という使い分けができます。

スタックトレースは **ログに残し**、レスポンスには **詳細を出さない**。
これは情報漏洩防止の基本です。

すべてを 500 で返すのではなく、**原因によって 4xx（クライアント側の問題）と
5xx（サーバー側の問題）を使い分ける**と、呼び出す側（フロントエンドや API 利用者）が
「リクエストを直せば直るのか」「時間を置いて再試行すべきか」を判断しやすくなります
（[HTTP ステータスコード](https://developer.mozilla.org/ja/docs/Web/HTTP/Status) の
一覧も参照）。第6章で見た `psycopg.errors.UniqueViolation` や `CheckViolation` は、
そのままだと `Exception` 扱いで 500 になってしまいますが、専用のハンドラを追加すれば
意味のある 4xx として返せます。個々の `repositories.py` の関数で毎回 `try/except` する
のではなく、こうして**アプリ全体で 1 箇所に集約**しておくと、新しいエンドポイントを
追加したときにも自動的に同じ変換が効きます。

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

すでに [Pydantic](https://docs.pydantic.dev/latest/) でカラムの長さ・範囲を見ていますが
（第14章の `Field(min_length=1, max_length=200)` や `Field(ge=1, le=3)` など）、
**業務ルール**は services 層で見ます。1 か所にまとめない理由は、Pydantic が得意なのは
「型や長さ・範囲が正しいか」という**データの形**のチェックで、「このアプリのルールとして
許すかどうか」という**意味の判断**とは性質が違うからです。後者は仕様変更で基準が
変わることがありますし、HTTP 経由のリクエスト以外（CLI やバッチ処理、テストから直接
呼ぶ場合など）からも同じ判断を再利用したいことがあります。Pydantic のスキーマだけに
業務ルールを書いてしまうと、API を経由しない呼び出しではそのチェックがすり抜けて
しまいます。

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
実際にエンドポイントで使うときは、`create_todo` などのルーターの中でこの関数を呼び、
`False` が返ってきたら `HTTPException(status_code=400, detail=message)` を投げる、
という形で組み込みます。

ちなみに `title` の長さや `priority` の範囲は、Pydantic だけでなく DB 側の `CHECK`
制約（第9章のテーブル定義）でも二重にチェックされています。これは手抜きの重複では
なく、**アプリのコードにバグがあっても DB が最後の砦として守ってくれる**ようにする
ための、意図した重複です。一方 `due_on` の「50年以上先はブロック」のような基準は、
データの整合性というより運用上の判断なので、`CHECK` 制約にはせず services 層にだけ
置いています。層ごとに向き不向きがあるので、**どのルールをどの層に置くか**を意識して
設計するのがポイントです。

## 17.5 セキュリティの最低ライン

ここまでの内容と重複する部分もありますが、外部公開する前のチェックリストとして
最後にまとめておきます。

- **SQL は必ずプレースホルダ**（第6章で扱った通り）。文字列連結で SQL を組み立てると、
  入力値がそのまま SQL の一部として解釈されてしまう SQL インジェクションを許して
  しまいます。
- **HTML への埋め込みは Jinja2 が自動エスケープ**してくれる（`safe` フィルタを軽率に
  使わない）。ユーザーが入力した文字列に `<script>` タグなどが含まれていても、
  エスケープなしで出力すると他の利用者のブラウザ上でスクリプトが実行されてしまいます
  （[XSS](https://developer.mozilla.org/ja/docs/Web/Security/Attacks/XSS)、第15章でも
  触れた通り）。`safe` フィルタはこの自動エスケープを解除する指定なので、本当に安全だと
  確信できる値以外には使わないでください。
- **[CSRF](https://developer.mozilla.org/ja/docs/Web/Security/Attacks/CSRF)**:
  今回は単一ユーザー前提なので簡略化していますが、複数ユーザーに広げる場合は CSRF
  トークンが必要です。悪意あるサイトが、ログイン中のユーザーのブラウザ経由で
  意図しないリクエストを送らせる攻撃で、Cookie ベースの認証を使うアプリほど注意が
  必要になります。
- **依存ライブラリのアップデート**: `uv sync --upgrade` でこまめに更新する習慣を
  つける。使っているライブラリに脆弱性が見つかることは珍しくなく、更新を怠るほど
  「もう直っているはずの穴」が長く開いたままになります。
- **本番のパスワードは Git に入れない**: `.env` を `.gitignore` に入れているのを
  再確認する。17.1 で見た通り、一度コミットすると、あとから消しても履歴には残り
  続けます。
- **`.env.example` に値は入れない**: 名前だけ書く。例値はダミーであっても本番に
  流れることがある。「とりあえず動くように」とダミー値をコピーしたまま本番に
  デプロイしてしまう事故はよくあるので、値の欄は空にするか、明らかにダミーと
  わかる書き方に統一しておきます。

## 17.6 ヘルスチェック

外に出すなら、稼働確認用のエンドポイントを 1 つ用意しておきます。
「プロセスが起動しているか」と「実際にリクエストをさばけるか」は別の問題です。
アプリのプロセス自体は生きていても、DB に接続できていなければユーザーからは
「動いていない」のと同じです。だからこの `/health` は、ただ `{"ok": True}` を
返すだけでなく、**実際に DB へ 1 回問い合わせて**からレスポンスを返すように
してあります。

```python
@app.get("/health")
def health(conn: Conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"ok": True}
```

監視ツールがこれを定期的に叩いて、応答が 200 でなくなったらアラートを上げる、
という使い方が一般的です。ロードバランサやコンテナのオーケストレーションツール
（Docker のヘルスチェックや、複数台構成のロードバランサなど）も同じ仕組みを使い、
`/health` が失敗したインスタンスを**自動的にトラフィックの振り分け先から外す**、
といった判断に利用します。なお `/health` のレスポンスには、DB のバージョンや接続
情報のような内部情報を含めないようにしましょう。17.3 で見た「5xx で内部実装を
漏らさない」のと同じ考え方で、稼働確認用のエンドポイントであっても**必要以上の
情報を外に出さない**のが原則です。

## やってみよう

1. `LOG_LEVEL=DEBUG` で起動して、ログがどう変わるか観察する。
2. `/api/todos` で **わざと 500 を起こす**（たとえば repository の中で `1/0` する）
   ことで、`fallback_handler` が動く様子を見る。レスポンスにスタックトレースが
   含まれていないことを確認する。
3. `psycopg.errors.UniqueViolation` を起こせる状況を作って（同じ名前のタグを直接 INSERT）、
   API 経由で 409 が返ることを確認する。

次は [第 18 章 公開先と最終課題](18-deploy.md) で、
**どこにデプロイするか**と、研修全体の **総仕上げ課題**を扱います。
