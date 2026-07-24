# 第0章 環境構築

実装に入る前に、開発環境を整えます。
ここでつまずくと後がつらいので、**ひとつずつ確認しながら**進めましょう。

このテキストでは Windows / macOS / Linux のいずれでも同じように動くよう、
**Docker で [PostgreSQL](https://www.postgresql.org/docs/current/) を立ち上げる**手順を採用します。
すでに PostgreSQL を入れている人はそれを使ってもかまいません。

Docker は「アプリが動くのに必要な環境（OS の一部・ライブラリのバージョンなど）ごと箱詰めにして、
どのマシンでも同じように動かす」仕組みです。ホストに直接 PostgreSQL をインストールすると、
バージョンや設定が人によって微妙に違って「自分の環境だけ動かない」の原因になりがちですが、
Docker を使えば全員が同じバージョンの PostgreSQL を、ホスト環境を汚さずに使い回せます。

## ゴール

このページが終わったときに、次のことができる状態を目指します。

- [x] `python --version` で 3.12 以上が出る
- [x] `uv --version` でバージョンが出る
- [x] `docker compose up -d` で PostgreSQL が立ち上がる
- [x] `psql` でデータベースに接続できる
- [x] エディタで Python ファイルを保存すると保存できる（あたりまえですが）

## 1. Python 3.12 を用意する

すでに Python が入っているなら `python --version` を確認してください。
3.12 未満なら次のいずれかで入れます。

=== "uv で入れる（推奨）"

    `uv` をインストールすれば、Python 自体も `uv` で入れられます。
    まずは [公式の手順](https://docs.astral.sh/uv/getting-started/installation/) を見て `uv` をインストールしてください。

    ```bash
    # macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    入ったら Python を入れます。

    ```bash
    uv python install 3.12
    uv python list   # 入っているバージョンを確認
    ```

=== "公式インストーラ"

    [python.org](https://www.python.org/downloads/) から 3.12 系をダウンロードしてインストールします。
    Windows なら "Add python.exe to PATH" にチェックを入れるのを忘れずに。

確認:

```bash
python --version
# Python 3.12.x （以上であればOK）
```

!!! note "なぜ uv なのか"
    `pip` でも問題なく動きますが、`uv` は **インストールが速く、依存関係の解決が壊れにくい**
    ため、研修では `uv` を採用します。慣れている `pip` を使いたい場合は、
    `uv pip install ...` のように互換コマンドも使えます。
    `uv` は Rust 製のツールで、これまで `pip`（インストール）・`venv`（仮想環境）・`pyenv`（バージョン管理）
    のように複数のツールに分かれていた役割を1つにまとめています。詳しくは
    [公式ドキュメント](https://docs.astral.sh/uv/) を参照してください。

## 2. uv で仮想環境とパッケージを管理する

Python の**仮想環境**（[venv](https://docs.python.org/3/library/venv.html)）は、プロジェクトごとに
独立した Python 環境を用意する仕組みです。仮想環境を使わずライブラリをシステムの Python に直接
インストールしていくと、別のプロジェクトが必要とするバージョンとぶつかって壊れる、といった事故が
起きやすくなります。`uv` を使うと、この仮想環境の作成とライブラリのインストールをまとめて面倒みてくれます。

このリポジトリには `pyproject.toml`（このプロジェクトが使うパッケージとそのバージョンをまとめて書いておく設定ファイル）
が置いてあります。リポジトリのルートで次を実行してください。

```bash
uv sync --group docs
```

これで `.venv/` という仮想環境が作られ、テキストをローカルで表示するための
ライブラリ（[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)）が入ります。

## 3. Docker で PostgreSQL を起動する

Docker Desktop（Windows / macOS）または Docker Engine（Linux）が入っていることを確認してください。
このリポジトリのルートには `docker-compose.yml` が置いてあります。これは「どのイメージを」
「どんな環境変数で」「どのポートで」起動するかをまとめて書いておく設定ファイルで、
[Docker Compose](https://docs.docker.com/compose/) がこれを読んで PostgreSQL コンテナを立ち上げます。
`docker run` の長いオプションを毎回打つ代わりに、このファイルさえあれば誰でも同じ環境を再現できます。

```bash
docker compose up -d
```

`-d` は detached（バックグラウンド）で起動するオプションです。付けないとターミナルがログ表示に
占有され続けるので、基本的には付けておくと使いやすいです。

うまく立ち上がったか確認:

```bash
docker compose ps
# STATUS が "Up" になっていればOK
```

接続情報は次のとおりです。

| 項目 | 値 |
|---|---|
| ホスト | `localhost` |
| ポート | `5432` |
| データベース | `tododb` |
| ユーザー | `todo` |
| パスワード | `todo` |

この5つの値は、このあとの章で Python から PostgreSQL に接続するときにそのまま使います。
パスワードだけでなく、ホスト・ポート・データベース名・ユーザー名もまとめて「接続情報」として
どこかにメモしておくと、あとで接続エラーが出たときに確認しやすくなります。

!!! warning "本番ではこんなパスワードは絶対NG"
    研修用なのでわかりやすさ優先で `todo / todo` にしています。
    実務では絶対にこのままにしないでください。
    第8章で「環境変数で上書きする」やり方を扱います。

## 4. psql で接続してみる

`psql` は PostgreSQL 純正の CLI です。**ここがいちばん大事**で、
アプリがおかしくなったときの最後の頼みの綱はだいたい `psql` です。
Python のコードを介さずに直接 SQL を打てるので、「アプリのバグなのか、そもそも DB に
入っているデータがおかしいのか」を切り分けるときに欠かせません。

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb
    # パスワードを聞かれたら todo
    ```

=== "コンテナの中で psql を使う"

    ホストに `psql` を入れたくない人向け:

    ```bash
    docker exec -it webapp-training-db psql -U todo -d tododb
    ```

接続できたら次を試してみましょう。

```sql
SELECT version();
\dt           -- テーブル一覧（まだ空）
\q            -- 抜ける
```

`\` から始まる `\dt` や `\q` は **SQL ではなく psql 独自のメタコマンド**（ショートカット）です。
一方 `SELECT version();` はふつうの SQL 文で、Python のコードから実行するのもこれと同じものです。
どちらが SQL でどちらが psql の機能なのかを区別しておくと、後の章でエラーメッセージを読むときに迷いません。

## 5. エディタの準備

エディタは普段使っているものでかまいません。
おすすめは VS Code か Cursor で、最低でも次の拡張機能を入れておくとラクです。

- **Python**（Microsoft）
- **Pylance**（型チェック）
- **Ruff**（自動フォーマット + 静的解析）
- **PostgreSQL**（任意。SQL ファイルのシンタックスハイライト）

Pylance は、コードに書いた[型ヒント](https://docs.python.org/3/library/typing.html)をもとに
「`int` を渡すはずの引数に `str` を渡している」といった矛盾を、実行する前にエディタ上で
教えてくれます。Ruff は [PEP 8](https://peps.python.org/pep-0008/) に沿ったスタイルへの自動整形と、
未使用の import のようなよくあるミスの検出を、1つの高速なツールでまとめて行ってくれます。

`.vscode/settings.json` の例:

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "ruff.organizeImports": true
}
```

## やってみよう

1. `python --version` と `uv --version` の出力をメモしておく。
2. `docker compose up -d` のあと、`docker compose logs db` でログを眺めて
   どんなメッセージが出るか見てみる。
3. `psql` で接続して、次の SQL を順に実行する。

    ```sql
    CREATE TABLE hello (id SERIAL PRIMARY KEY, msg TEXT NOT NULL);
    INSERT INTO hello (msg) VALUES ('はじめての行');
    SELECT * FROM hello;
    DROP TABLE hello;
    ```

これで環境構築は終わりです。
次は [第 1 章 Pythonのおさらい① 型ヒントとdataclass](01-python-types.md) から、
**研修で使う Python の機能を 2 章に分けて**確認します。
