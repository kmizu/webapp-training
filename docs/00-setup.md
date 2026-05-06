# 第0章 環境構築

実装に入る前に、開発環境を整えます。
ここでつまずくと後がつらいので、**ひとつずつ確認しながら**進めましょう。

このテキストでは Windows / macOS / Linux のいずれでも同じように動くよう、
**Docker で PostgreSQL を立ち上げる**手順を採用します。
すでに PostgreSQL を入れている人はそれを使ってもかまいません。

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

## 2. uv で仮想環境とパッケージを管理する

このリポジトリには `pyproject.toml` が置いてあります。
リポジトリのルートで次を実行してください。

```bash
uv sync --group docs
```

これで `.venv/` という仮想環境が作られ、テキストをローカルで表示するための
ライブラリ（MkDocs Material）が入ります。

## 3. Docker で PostgreSQL を起動する

Docker Desktop（Windows / macOS）または Docker Engine（Linux）が入っていることを確認してください。
このリポジトリのルートには `docker-compose.yml` が置いてあります。

```bash
docker compose up -d
```

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

!!! warning "本番ではこんなパスワードは絶対NG"
    研修用なのでわかりやすさ優先で `todo / todo` にしています。
    実務では絶対にこのままにしないでください。
    第8章で「環境変数で上書きする」やり方を扱います。

## 4. psql で接続してみる

`psql` は PostgreSQL 純正の CLI です。**ここがいちばん大事**で、
アプリがおかしくなったときの最後の頼みの綱はだいたい `psql` です。

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

## 5. エディタの準備

エディタは普段使っているものでかまいません。
おすすめは VS Code か Cursor で、最低でも次の拡張機能を入れておくとラクです。

- **Python**（Microsoft）
- **Pylance**（型チェック）
- **Ruff**（自動フォーマット + 静的解析）
- **PostgreSQL**（任意。SQL ファイルのシンタックスハイライト）

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
