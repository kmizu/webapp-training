# 第17章 設定・ログ・例外ハンドリング

第16章までで、ブラウザから ToDo を作って、切り替えて、消せるアプリが
完成しました。この章はその**仕上げ**です。やることは 3 つあります。

1 つ目は、第13章から少しずつ育ててきた `app/main.py` に残りの部品
（ログ設定・リクエストログのミドルウェア・全体例外ハンドラ）を追加し、
**完成版と完全一致**させること。これで `mytodo/` の全ファイルが
完成版と一致します。

2 つ目は、これまでの章で予告してきた話の回収です。第0章の
「パスワード直書きは本番ではNG」、第10章の「ログレベルや `.env`
ファイルは第17章で」、第14章の「`validate_due_on` の組み込みは
第17章で」という 3 つの予告に、ここで答えます。

3 つ目は、外部に公開するときの**セキュリティの最低ライン**の確認です。
どれも、自分ひとりで動かしている間は気づきにくいけれど、他人や
本番環境が触れた瞬間に効いてくる話です。

## 17.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- `.env` ファイルを作り、`uvicorn --env-file` で設定を読み込んで
  起動できる
- `logging` のレベルの仕組み（`INFO` 以上だけ出る、など）を
  説明できる
- `@app.middleware("http")` と `@app.exception_handler(Exception)` が
  それぞれ何をするか説明できる
- `mytodo/app/main.py` を完成させ、`diff` が完成版と**差分なし**
  になることを確認できる
- 起動中のサーバーのターミナルにリクエストログが 1 行ずつ出ることを
  確認できる
- `services.py` の `validate_due_on` が完成版のルーターから
  呼ばれていない理由と、組み込む場合の手順を説明できる
- 公開前のセキュリティチェックリストの各項目の理由を説明できる

**所要時間の目安: 60 分**

!!! info "前提となる状態"
    - 第16章末時点の `mytodo/` がある（ブラウザで一覧・絞り込み・
      追加・切替・削除が動き、第15章の `diff` 答え合わせ済み）
    - 第0章の Docker の PostgreSQL が起動している
      （`docker compose up -d`）
    - シードデータが入った状態である（この章の動作確認で
      初期状態に戻します）

## 17.2 前提知識

コードに入る前に、この章の鍵になる概念を 4 つ押さえておきます。

!!! note "環境変数とは"
    **環境変数**は、OS がプロセスに渡す名前つきの値の仕組みです。
    ターミナルで `LOG_LEVEL=DEBUG uv run ...` のようにコマンドの
    前に書くと、そのコマンドから起動したプログラムの中で
    `os.getenv("LOG_LEVEL")` が `"DEBUG"` を返します。
    プログラムの外側から値を差し込めるので、**コードを書き換えずに
    動作を変えられる**のが特徴です。第10章で写経した
    `app/config.py` の `os.getenv("DB_HOST", "localhost")` は、
    まさにこの仕組みで DB の接続先を読んでいます。

!!! note "設定をコードに埋め込まない理由"
    理由は 2 つあります。1 つは、**環境ごとに設定だけを
    切り替えたい**からです。DB のホスト名やパスワードは開発・
    テスト・本番で違うのが普通なので、同じコードのまま起動時の
    環境変数だけ差し替えられると楽です。もう 1 つは、パスワードや
    API キーのような**秘密情報をコードに書かないため**です。
    コードは Git で管理して共有するものですが、秘密情報が紛れ込むと
    共有した相手全員に秘密が渡ってしまいます。一度 Git にコミット
    すると、あとから消しても履歴には残り続け、すでに `clone`
    された分は取り消せません。だから秘密情報はコードではなく
    環境変数経由で渡し、その受け皿である `.env` ファイル自体も
    Git に入れない、という運用が定石です。

!!! note "ログとは"
    **ログ**は、プログラムが「いつ・何が起きたか」を残す記録です。
    これまで `print` でデバッグしてきましたが、`print` はその場で
    コンソールに文字を出すだけで、**重要度による絞り込み**も
    **出力先の切り替え**もできません。Python 標準の
    [`logging`](https://docs.python.org/3/library/logging.html)
    を使うと、メッセージに DEBUG / INFO / WARNING / ERROR /
    CRITICAL という**重要度（レベル）**を付けられます。
    レベルには `DEBUG < INFO < WARNING < ERROR < CRITICAL` という
    順序があり、出力の設定で「このレベル以上だけ出す」を決めます。
    普段は `INFO` で落ち着いた量だけ見て、調査のときだけ
    `DEBUG` に下げて詳細を見る、という切り替えが設定 1 つで
    できます。本番運用では、サーバーを止めずに原因を調べる
    唯一の手がかりがログなので、ほぼ必須の道具です。

!!! note "例外ハンドリングの方針"
    第14章では、エラーの種類に応じて `HTTPException` で 404 を
    返したり、Pydantic が自動で 422 を返したりする仕組みを
    作りました。これらは**想定したエラー**です。問題は、バグや
    DB 停止のような**想定外の例外**です。何も対策しないと、
    Python のスタックトレース（ファイルパス、関数名、ときには
    実行中の SQL 文まで）がそのままレスポンスに出てしまうことが
    あり、攻撃者にとって「次に何を狙えばいいか」のヒントに
    なります。そこで方針はこう決めます。**スタックトレースは
    サーバー側のログに残し、クライアントへの応答には詳細を
    出さない**。調査に必要な情報は手元に全部残しつつ、外には
    「内部エラーが起きた」という事実だけを返す、という使い分けです。

## 17.3 `.env` ファイルで設定を管理する

まず設定まわりの現在地を確認します。第10章で写経した
`app/config.py` は、DB の接続先や `LOG_LEVEL` を環境変数から読む
`Settings` クラスで、モジュール末尾の `settings = Settings()` で
**起動時に 1 回だけ**環境変数を読み込みます。以降は
`from .config import settings` でアプリのどこからでも同じ
インスタンスを参照し、`settings.dsn` や `settings.log_level` の
ようにプロパティとして取り出します。

デフォルト値（`localhost`・`todo` / `todo` など）は第0章の
Docker の PostgreSQL に合わせた**練習用の値**なので、研修中は
環境変数を何も設定しなくても動いてきました。ここでは、この
環境変数をまとめて書いておく **`.env` ファイル**を作ります。

### `.env.example` を写経する

`.env` は秘密情報を含むので Git に入れません。その代わり、
「どの変数が必要か」を伝えるための見本ファイル `.env.example`
を用意するのが習わしです。完成版にも
`sample/todo-app/.env.example` があるので、同じものを作ります。

`mytodo/.env.example` を作成して、次の内容を書き写してください。

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tododb
DB_USER=todo
DB_PASSWORD=todo
LOG_LEVEL=INFO
```

各行が `名前=値` の 1 組です。完成版では見本にも練習用の
デフォルト値がそのまま入っていますが、実務では `.env.example`
に本物のパスワードは書きません（17.9 で触れます）。

### `.env` を作って起動時に読み込む

見本をコピーして `.env` を作ります。`mytodo/` の中で実行して
ください。

```bash
cp .env.example .env
```

期待される出力: なし（コピーが成功すれば何も表示されません）

`uvicorn` に `--env-file` オプションを付けると、指定したファイルの
中身を環境変数として読み込んでからアプリを起動してくれます。
試しに起動してみましょう（すぐ `Ctrl+C` で止めて構いません）。

```bash
uv run uvicorn app.main:app --env-file .env
```

期待される出力（先頭付近。パスやプロセス番号は環境によって
変わります）:

```text
INFO:     Loading environment from '.env'
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

先頭の `Loading environment from '.env'` が、ファイルを読み込んだ
印です。いまは `.env` の中身がデフォルト値と同じなので動作は
変わりませんが、たとえば本番ではこのファイルの `DB_HOST` や
`DB_PASSWORD` だけを本番用に書き換えて起動します。コードは
一行も変えません。

確認できたら `Ctrl+C` で止めてください。

!!! warning "`.env` を編集したら起動し直す"
    `settings = Settings()` が環境変数を読むのは**アプリ起動時の
    1 回だけ**です。`.env` を編集しても、動いているサーバーには
    反映されません。`--reload` 付きでも `.env` の変更は監視対象外
    なので、編集したら `Ctrl+C` で止めてから起動し直してください。

## 17.4 `main.py` にログ設定とリクエストログを追加する

ここから `main.py` の仕上げです。第15章末時点の `main.py` は
pages ルーターと静的ファイルの組み込みまででした。ここに
3 つの部品を追加します。追加する部分を順に見たあと、17.6 で
**追記後の全文**を掲載して丸ごと上書きしてもらいます。

1 つ目はログの土台です。

```python
import logging

from .config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("todo-app")
```

- `logging.basicConfig(...)` …… アプリ全体のログ出力の土台
  （フォーマットと最低レベル）を**起動時に一度だけ**設定します。
  `level=settings.log_level` で、17.3 の `.env`（または環境変数
  `LOG_LEVEL`）の値がそのまま最低レベルになります。
  `level` に指定したレベル**以上**のログだけが出力されるので、
  デフォルトの `INFO` では `logger.debug(...)` は表示されず、
  `WARNING` にすると `INFO` 以下はすべて消えます。
- `format="%(asctime)s %(levelname)s %(name)s - %(message)s"` ……
  1 行の書式です。時刻・レベル・ロガー名・メッセージの順に
  並びます。
- `logging.getLogger("todo-app")` …… このアプリ専用のロガーを
  名前つきで作ります。名前を付けておくと、ログの出どころが
  一目でわかり、あとからモジュールごとにレベルを変えたくなった
  ときにも対応できます。

2 つ目はリクエストログのミドルウェアです。

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response
```

**ミドルウェア**は、すべてのリクエストがエンドポイントに届く
前後に挟まる共通処理です。`@app.middleware("http")` を付けた
関数が全リクエストに対して自動で呼ばれます。`call_next(request)`
が「本来の処理（エンドポイント）を呼ぶ」という意味で、その
前後に処理を書けます。ここでは後側に `logger.info(...)` を
書いたので、**全リクエストについて、メソッド・パス・
ステータスコードが INFO で 1 行ずつ**ログに残ります。
エンドポイントを新しく追加しても、この 1 箇所のおかげで
自動的にログが出るのがミドルウェアの強みです。

!!! tip "ログにパスワードや個人情報を出さない"
    ありがちな事故です。フォームの中身をそのまま
    `logger.info(...)` してしまうと、パスワードや個人情報が
    ログに残ります。ログはコードよりも保存期間が長く、外部の
    集約サービスに転送されることも多いので、うっかり書き込むと
    気づかないまま長期間残ってしまいます。このアプリが出すのは
    メソッド・パス・ステータスコードだけで、リクエストの中身
    （タイトルなどの入力値）は出していません。

## 17.5 `main.py` に全体例外ハンドラを追加する

3 つ目は、想定外の例外をまとめて受け止める**フォールバック
ハンドラ**です。

```python
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def fallback_handler(request: Request, exc: Exception):
    logger.exception("unhandled error: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )
```

`@app.exception_handler(Exception)` は、Python の組み込み例外を
含めて**ありとあらゆる例外**を拾う、最後の砦のハンドラです
（[FastAPI公式: エラーハンドリング](https://fastapi.tiangolo.com/tutorial/handling-errors/)）。
個別の `try/except` を書き忘れた場所があっても、ここで必ず
捕まって定型のレスポンスに変換されます。

中身は 17.2 の方針そのものです。

- `logger.exception(...)` …… `logger.error(...)` と違い、
  **呼ばれた時点のスタックトレースを自動でログに埋め込みます**。
  サーバー側の記録には原因調査に必要な情報が全部残ります。
- `JSONResponse(status_code=500, content={"detail": "internal server error"})`
  …… クライアントへは定型文だけを返します。ファイルパスや
  SQL 文は一切出ません。

なお、第14章の `HTTPException`（404 など）や、Pydantic の
バリデーションによる 422 は、FastAPI がこのハンドラより先に
処理するので、**これまでどおり 404 や 422 のまま返ります**。
このハンドラが拾うのは、本当に想定外の例外だけです
（17.7 で実際に確認します）。

## 17.6 `main.py` の全文と答え合わせ

17.4 と 17.5 の部品を追加すると、import 行も変わるため一部分
だけの書き換えでは収まりません。`mytodo/app/main.py` を、
次の内容で**丸ごと上書き**してください（第15章末の内容に、
ログ設定・ミドルウェア・例外ハンドラとその import を足した
ものです）。

```python
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import pages, todos


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("todo-app")


app = FastAPI(title="ToDo App", version="0.1.0")

_BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")

app.include_router(pages.router)
app.include_router(todos.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(Exception)
async def fallback_handler(request: Request, exc: Exception):
    logger.exception("unhandled error: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )
```

これが完成版の `main.py` とまったく同じ内容です。
`diff` で答え合わせします（**リポジトリのルート**で実行して
ください）。

```bash
diff -u mytodo/app/main.py sample/todo-app/app/main.py
```

期待される出力: なし（**何も表示されなければ一致**です。差分が
出たら写経ミスなので、表示された行を見比べて写し直してください）

これで `mytodo/` の全ファイルが完成版と一致しました。

## 17.7 動作確認: ログが出ること

追加した 2 つの仕組みを動かして確かめます。まず DB を初期状態に
戻します。`mytodo/` の中で実行してください。

```bash
uv run python -m app.cli reset-db
uv run python -m app.cli init-db
```

期待される出力:

```text
reset done
```

```text
apply  001_init
apply  002_seed
```

サーバーを起動します。今度は `--env-file .env` 付きです。

```bash
uv run uvicorn app.main:app --reload --env-file .env
```

期待される出力の末尾に `INFO:     Application startup complete.`
と出れば起動成功です。**別のターミナル**を開いて、次の curl を
実行してください。

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/api/todos
```

期待される出力:

```text
HTTP 200
```

ここで uvicorn を動かしているターミナルを見てください。
uvicorn 自身のアクセスログのほかに、今回追加したロガーからの
行が出ているはずです。

期待される出力（uvicorn 側のターミナル。時刻は実行ごとに
変わります）:

```text
2026-08-16 08:40:00,331 INFO todo-app - GET /api/todos -> 200
```

`basicConfig` で指定した書式（時刻・レベル・ロガー名・
メッセージ）どおりの行です。ブラウザで `http://127.0.0.1:8000/`
を開いて操作しても、同じ形式の行が 1 リクエストごとに
増えていきます。

次に、17.5 で「404 はこれまでどおり返る」と説明した点を確認します。

```bash
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/todos/999
```

期待される出力:

```text
{"detail":"todo not found"}
HTTP 404
```

例外ハンドラを追加したあとも、存在しない ToDo への 404 は
第14章と同じ応答のままです。uvicorn 側のログにも
`INFO todo-app - GET /api/todos/999 -> 404` と残り、ミドルウェアが
エラーの応答も漏れなく記録していることがわかります。

確認が終わったら、uvicorn を動かしているターミナルで `Ctrl+C`
を押してサーバーを止めてください。

## 17.8 `validate_due_on` の組み込み方

第14章で写経した `app/services.py` の `validate_due_on` について、
予告どおり組み込み方を説明します。まず実態の確認からです。
完成版の `sample/todo-app/app/routers/todos.py` は `services` を
import して**いません**。つまり `validate_due_on` は、完成版の
どのエンドポイントからも呼ばれていません。

なぜこうなっているかというと、第14章で説明したとおり
`services.py` は「業務ルールを置く場所」を先に用意するための
写経で、完成版はその土台の状態で固定してあるからです。
組み込みまで完成版に含めてしまうと、第14章時点の CRUD の説明と
コードがずれてしまいます。そこで組み込みはこの章の
**やってみよう（17.12 問1）**で自分の手で試す形にしてあり、
ここでは手順の解説にとどめます。

組み込む場所は、ルーターがリポジトリを呼ぶ**直前**です。
`routers/todos.py` の `create_todo` を例にすると、まず import を
1 行足します。

```python
from .. import repositories as repo
from .. import services          # 追加
```

そして `create_todo` の先頭で判定し、`False` が返ってきたら
`HTTPException` で 400 を返します。

```python
def create_todo(payload: TodoCreate, conn: Conn):
    ok, message = services.validate_due_on(payload.due_on)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    todo = repo.create_todo(
        # ...（以下は元のまま）
```

`validate_due_on` 自身は HTTP のことを何も知らない普通の関数で、
「許すかどうか」と「メッセージ」だけを返します。それを 400 という
HTTP の応答に翻訳するのはルーターの仕事、という分担です。
この形なら、第14章のやってみようで試したように CLI やテストから
直接呼んでも同じ判定を再利用できます。

更新系の `patch_todo` にも組み込むなら、`fields` に `due_on` が
含まれるときだけ同じ判定を挟みます（送られていない＝変更しない
場合は判定しない、という意味です）。

```python
def patch_todo(todo_id: int, payload: TodoPatch, conn: Conn):
    fields = payload.model_dump(exclude_unset=True)
    if "due_on" in fields:
        ok, message = services.validate_due_on(fields["due_on"])
        if not ok:
            raise HTTPException(status_code=400, detail=message)
    # ...（以下は元のまま）
```

実際に組み込んで curl で確かめ、あとで完成版の状態に戻すところ
までが 17.12 の問1 です。

## 17.9 セキュリティの最低ライン

外部に公開する前のチェックリストとして、この章の内容とも
重複する部分をまとめておきます。

- **パスワードをコードに直書きしない** …… 第0章で「本番では
  こんなパスワードは絶対NG」と予告した話の答えが、この章の
  `config.py` + `.env` の仕組みです。コードにあるのは
  `os.getenv(...)` だけで、実際の値は環境変数（`.env`）側に
  あります。`todo / todo` はあくまで研修用の Docker
  （`webapp-training-db` コンテナ）に合わせた練習用の値で、
  本番では使いません。
- **`.env` をコミットしない** …… この研修リポジトリでは
  `mytodo/` 全体が `.gitignore` 済みなので誤ってコミット
  されることはありませんが、自分のプロジェクトを Git 管理する
  ときは `.gitignore` に `.env` を書いてください。
  リポジトリのルートで次のコマンドを実行すると、無視対象に
  なっているか確認できます。

  ```bash
  git check-ignore mytodo/.env
  ```

  期待される出力（無視対象ならパスがそのまま表示されます）:

  ```text
  mytodo/.env
  ```

- **`.env.example` に本物の値を入れない** …… 見本ファイルには
  変数名とダミーの値だけを書きます。完成版の `.env.example`
  に練習用の値が入っているのは、写経してそのまま動くことを
  優先した教材ならではの例外です。「とりあえず動くように」と
  ダミー値のまま本番にデプロイする事故はよくあるので、実務では
  値の欄は空か、明らかにダミーとわかる書き方に統一します。
- **本番にデバッグ情報を出さない** …… 17.5 のフォールバック
  ハンドラで、想定外の例外が起きてもスタックトレースは
  クライアントに出さなくなりました。同じ理由で、開発用の
  `--reload` も本番では外します（第18章で扱います）。
- **SQL は必ずプレースホルダ** …… 第6章で扱った通り、文字列
  連結で SQL を組み立てると SQL インジェクションを許して
  しまいます。このアプリの `repositories.py` はすべて
  プレースホルダ（`%s`）経由です。
- **HTML への埋め込みは Jinja2 の自動エスケープ任せ** ……
  第15章で確認した通り、`{{ }}` は自動でエスケープされます。
  `| safe` フィルタはその解除なので、ユーザー入力には
  使わないでください。
- **依存ライブラリをこまめに更新する** …… `uv sync --upgrade`
  で更新する習慣をつけます。使っているライブラリに脆弱性が
  見つかることは珍しくなく、更新を怠るほど「もう直っている
  はずの穴」が開いたままになります。

## 17.10 チェックポイント

この章の内容を、次の問いに自分の言葉で答えられるか確認して
ください。

- [ ] `.env` と `.env.example` の役割の違いと、`.env` を Git に
      入れない理由を説明できる
- [ ] `uvicorn --env-file .env` が何をしているか説明できる
- [ ] `.env` を編集したあと起動し直さなければならない理由を
      説明できる
- [ ] `logging` のレベルの順序と、「`level` に指定したレベル以上
      だけが出る」仕組みを説明できる
- [ ] `@app.middleware("http")` の `call_next` の前後で、それぞれ
      どのタイミングの処理になるか説明できる
- [ ] `@app.exception_handler(Exception)` が返すレスポンスに
      スタックトレースを含めない理由を説明できる
- [ ] `logger.exception(...)` と `logger.error(...)` の違いを
      説明できる
- [ ] 404 や 422 がフォールバックハンドラ追加後も変わらない理由を
      説明できる
- [ ] `mytodo/app/main.py` の `diff` が完成版と差分なしになった
- [ ] uvicorn のターミナルに `INFO todo-app - ...` のリクエスト
      ログが出ることを確認した
- [ ] `validate_due_on` を組み込む場所（リポジトリ呼び出しの直前）
      と、ルーター側で 400 に翻訳する分担を説明できる

## 17.11 つまずきポイント

### `.env` を作ったのに設定が反映されない

`--env-file .env` を付けずに起動していませんか。このオプション
なしでは `.env` は読み込まれず、`config.py` のデフォルト値が
使われます。起動時の先頭に `Loading environment from '.env'` が
出ているか確認してください。オプションを付けているのに反映
されない場合は、`.env` を作った場所が `mytodo/` 直下か、
起動し直したか（17.3 の warning）を確認してください。

### リクエストログ（`INFO todo-app - ...`）が出ない

`LOG_LEVEL` が `WARNING` など `INFO` より上になっていると、
INFO の行は表示されません。`.env` の `LOG_LEVEL=INFO` を確認し、
起動し直してください。uvicorn 自身のアクセスログ
（`INFO:     127.0.0.1:... - "GET ..." 200 OK`）は別のロガーが
出しているので、これが出ていても `todo-app` の行がなければ
レベル設定を疑います。

### `diff` で差分が出る

`+` と `-` の行を見比べてください。多いのは、17.4〜17.5 の
ブロックの追加し忘れ、import 行（`Request`・`JSONResponse`・
`settings`）の更新し忘れ、空白や空行の違いです。どうしても
そろわなければ、完成版をそのままコピーして構いません
（リポジトリのルートで
`cp sample/todo-app/app/main.py mytodo/app/main.py`）。

### 500 のときブラウザにエラーの詳細が出ない

それが正しい動作です。17.5 より前は素の Traceback が
そのまま出ていましたが、フォールバックハンドラを追加した
いまは `{"detail": "internal server error"}` だけが返ります。
原因を調べたいときは、uvicorn を動かしているターミナルの
ログ（`logger.exception` が残したスタックトレース）を見ます。

## 17.12 やってみよう

解答例は折りたたんであるので、まず自分で考えてから見比べて
ください。

### 問1 `validate_due_on` を組み込んで試す

17.8 の手順どおり `routers/todos.py` の `create_todo` に
`validate_due_on` を組み込み、50 年以上先の期限を API 経由で
送ると 400 が返ること、通常の期限なら従来どおり 201 で作れる
ことを確認してください。確認が終わったら、ファイルを完成版の
状態に戻します。

??? example "解答例"

    `mytodo/app/routers/todos.py` の import に 1 行追加します。

    ```python
    from .. import repositories as repo
    from .. import services          # 追加
    ```

    `create_todo` の先頭に判定を追加します。

    ```python
    def create_todo(payload: TodoCreate, conn: Conn):
        ok, message = services.validate_due_on(payload.due_on)
        if not ok:
            raise HTTPException(status_code=400, detail=message)
        todo = repo.create_todo(
            conn,
            title=payload.title,
            due_on=payload.due_on,
            priority=payload.priority,
            tag_names=payload.tags,
        )
        return TodoOut.model_validate(todo)
    ```

    サーバーを起動して（`--reload` 付きなら自動で再起動されます）、
    50 年以上先の期限を送ります。

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/todos \
      -H 'content-type: application/json' \
      -d '{"title":"遠い未来のタスク","due_on":"2099-01-01"}'
    ```

    期待される出力:

    ```text
    {"detail":"期限がだいぶ未来すぎます"}
    HTTP 400
    ```

    `validate_due_on` が返したメッセージが、そのまま 400 の
    `detail` になっています。通常の期限なら従来どおり作れます。

    ```bash
    curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/todos \
      -H 'content-type: application/json' \
      -d '{"title":"近いタスク","due_on":"2026-12-31"}'
    ```

    期待される出力:

    ```text
    HTTP 201
    ```

    確認が終わったら元に戻します。`mytodo/` は Git 管理されてい
    ないので `git checkout` では戻せません。**完成版のファイルで
    上書きコピー**するのが確実です。リポジトリのルートで実行
    してください。

    ```bash
    cp sample/todo-app/app/routers/todos.py mytodo/app/routers/todos.py
    diff -u mytodo/app/routers/todos.py sample/todo-app/app/routers/todos.py
    ```

    期待される出力: なし（`diff` に何も表示されなければ、完成版と
    一致した元の状態に戻っています）

    試しに作った「近いタスク」は DB に残っているので、
    `reset-db` と `init-db` で掃除しておきましょう。

### 問2 `LOG_LEVEL` でログの量を変える

`LOG_LEVEL=WARNING` で起動すると、17.7 で見えていた
`INFO todo-app - ...` のリクエストログがどうなるか観察して
ください。観察したら元に戻します。

??? example "解答例"

    環境変数は `.env` より直接指定が優先されるので、コマンドの
    先頭に書くだけで試せます。

    ```bash
    LOG_LEVEL=WARNING uv run uvicorn app.main:app --env-file .env
    ```

    期待される出力（起動時の先頭付近）:

    ```text
    INFO:     Loading environment from '.env'
    INFO:     Started server process [12345]
    ...
    ```

    別のターミナルで `curl http://127.0.0.1:8000/api/todos` を
    実行すると、uvicorn 自身のアクセスログ
    （`INFO:     127.0.0.1:... - "GET /api/todos HTTP/1.1" 200 OK`）
    は出ますが、`INFO todo-app - GET /api/todos -> 200` の行は
    **出ません**。`basicConfig(level=...)` の最低レベルが
    `WARNING` に上がり、INFO のログが捨てられたためです。
    レベル 1 つでログの量を絞れることが確認できました。

    確認したら `Ctrl+C` で止め、いつもの
    `uv run uvicorn app.main:app --reload --env-file .env`
    （`.env` の `LOG_LEVEL=INFO` が効く）で起動し直してください。

### 問3 わざと 500 を起こしてフォールバックハンドラを見る

DB を一時的に止めて想定外の例外を起こし、17.5 の
フォールバックハンドラの働きを確認してください。レスポンスに
スタックトレースが**含まれていない**こと、uvicorn 側のログには
スタックトレースが**残っている**こと、の 2 点がポイントです。
見終わったら DB を起動し直します。

??? example "解答例"

    サーバーを起動したまま、別のターミナル（リポジトリのルート）
    で Docker の PostgreSQL を止めます。

    ```bash
    docker compose stop db
    ```

    期待される出力:

    ```text
    [+] Stopping 1/1
     ✔ Container webapp-training-db  Stopped
    ```

    API を叩きます（接続のタイムアウト待ちで、応答まで数秒
    かかることがあります）。

    ```bash
    curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/api/todos
    ```

    期待される出力:

    ```text
    {"detail":"internal server error"}
    HTTP 500
    ```

    接続エラーという想定外の例外が、フォールバックハンドラで
    定型の 500 に変換されました。レスポンスにファイルパスや
    SQL 文は含まれていません。一方 uvicorn を動かしている
    ターミナルには、`ERROR todo-app - unhandled error: GET /api/todos`
    に続いて `logger.exception` が埋め込んだスタックトレース
    （`psycopg.OperationalError` などの接続エラー）が残っている
    はずです。「サーバー側の記録には全部残す、クライアントには
    詳細を出さない」という 17.2 の方針どおりの動きです。

    見終わったら DB を起動し直します。

    ```bash
    docker compose up -d
    ```

    期待される出力:

    ```text
    [+] Running 1/1
     ✔ Container webapp-training-db  Started
    ```

    数秒待ってからもう一度 `curl` すると 200 に戻ります
    （コネクションプールが自動で再接続します）。

## まとめ

- 設定は **環境変数**で渡し、受け皿の `.env` は Git に入れない。
  見本の `.env.example` には本物の値を書かない。
  `uvicorn --env-file .env` で起動時に読み込める
- `config.py` の `settings` は起動時に 1 回だけ環境変数を読む。
  `.env` を変えたら起動し直す
- `logging.basicConfig(level=settings.log_level, ...)` がログの
  土台。`level` 以上のログだけが出るので、レベル 1 つで量を
  切り替えられる
- `@app.middleware("http")` は全リクエストの前後に挟まる共通
  処理。これでメソッド・パス・ステータスコードが 1 行ずつ残る
- `@app.exception_handler(Exception)` は想定外の例外の最後の砦。
  **スタックトレースはログに残し、レスポンスには詳細を出さない**。
  404 や 422 はこれまでどおり
- `services.py` の業務ルールは、ルーター側で呼んで 400 に
  翻訳して使う。完成版では土台の状態で固定してあり、組み込みは
  やってみようで試した
- この章で `main.py` が完成版と一致し、`mytodo/` の全ファイルが
  完成版とそろった

これで ToDo アプリは完成です。
次は [第18章 公開先と最終課題](18-deploy.md) で、
**どこにデプロイするか**と、研修全体の**総仕上げ課題**を扱います。
