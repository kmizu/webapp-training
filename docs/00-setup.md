# 第0章 環境構築

実装に入る前に、開発環境を整えます。
この章は全章の土台です。ここで構築する **PostgreSQL（Docker コンテナ）** と **Python 環境（uv）** を、
このあとのすべての章で使い続けます。ここでつまずくと後がつらいので、
**ひとつずつ確認しながら**進めましょう。

## 0.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- Docker で PostgreSQL 16 が起動し、`psql` で接続できる
- uv で Python 3.12 以上とこのリポジトリの依存パッケージがインストールされている
- エディタで Python ファイルを編集できる

**所要時間の目安: 60〜90 分**（Docker や uv のインストールを含む。回線速度によって前後します）

## 0.2 前提知識

この章では「ツールの使い方」だけでなく、ツールが**何をしてくれているのか**も説明します。
あとの章でエラーが出たときに原因を切り分ける土台になるので、軽く目を通してから進めてください。

!!! note "コンテナと Docker とは"
    **コンテナ**は、「アプリが動くのに必要なもの（プログラム本体・ライブラリ・設定）をひとまとめにした箱」です。
    **Docker** は、その箱を作ったり動かしたりするためのツールです。

    ホストの OS に直接 PostgreSQL をインストールすると、バージョンや設定が人によって微妙に違い、
    「自分の環境だけ動かない」の原因になりがちです。Docker を使えば、全員が**まったく同じ
    PostgreSQL 16** を、ホスト環境を汚さずに動かせます。箱ごと捨てれば痕跡も残りません。

!!! note "ポートとは"
    **ポート**は、1 台のマシンの中で動いている複数のサービスを番号で区別する仕組みです。
    「`localhost` の **5432 番**に接続する」といえば、それは PostgreSQL への接続、という具合です。

    PostgreSQL の標準ポートは **5432** です。この章では、Docker コンテナの中の PostgreSQL（5432）を
    ホストの 5432 につなぎます。もしホストに別の PostgreSQL がすでに動いていると、
    同じ番号を取り合って**ポート競合**のエラーになります（対処法は「つまずきポイント」を参照）。

!!! note "仮想環境とは"
    Python の**仮想環境**は、プロジェクトごとに独立した Python の実行環境（専用の Python と
    ライブラリ置き場）を作る仕組みです。

    仮想環境を使わず、ライブラリをシステムの Python に直接インストールしていくと、
    「プロジェクト A は requests 2.28 が必要」「プロジェクト B は 2.32 が必要」のように
    バージョンがぶつかって、どちらかが壊れます。プロジェクトごとに部屋を分けるのが仮想環境で、
    このリポジトリでは `.venv/` というディレクトリがその部屋になります。

!!! note "uv と pip の違い"
    **pip** は Python 標準のパッケージインストーラです。**uv** はその高速な代替ツールで、
    次のような特徴があります。

    - インストールが圧倒的に速い
    - 依存関係の解決が厳密で、壊れにくい
    - パッケージ管理（pip）・仮想環境の作成（venv）・Python 本体のバージョン管理（pyenv）を
      1 つのツールでまかなえる

    この研修では uv を使います。pip でも同じことはできますが、手順が増えるので統一しています。

## 0.3 Docker を用意する

まず Docker をインストールします。

- Windows / macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/) をインストール
- Linux: [Docker Engine](https://docs.docker.com/engine/install/) をインストール
  （ディストリビューションごとの手順に従ってください）

インストールできたら、Docker が動いているかを確認します。
Windows / macOS は Docker Desktop を起動してから、次のコマンドを実行してください。

```bash
docker version
```

期待される出力（バージョン番号は環境によって異なります）:

```text
Client:
 Version:           27.x.x
 ...
Server: Docker Desktop x.x.x
 Engine:
  Version:          27.x.x
  ...
```

「Client」と「Server」の両方が表示されれば OK です。
なお Linux（Docker Engine）では Server の行は `Server: Docker Engine - Community` のように表示されます。
`Cannot connect to the Docker daemon` のようなエラーが出た場合は Docker が起動していないので、
Docker Desktop を起動してからやり直してください（詳しくは「つまずきポイント」）。

## 0.4 uv と Python 3.12 を用意する

次に uv をインストールします。[公式の手順](https://docs.astral.sh/uv/getting-started/installation/)に
沿って進めてください。

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    期待される出力:

    ```text
    downloading uv 0.x.x x86_64-unknown-linux-gnu
    no checksums to verify
    installing to /home/<ユーザー名>/.local/bin
      uv
      uvx
    everything's installed!
    ```

=== "Windows（PowerShell）"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

    期待される出力:

    ```text
    Downloading uv 0.x.x
    Installing to C:\Users\<ユーザー名>\.local\bin
      uv.exe
      uvx.exe
    everything's installed!
    ```

インストール後、**ターミナルを開き直して**確認します。これは、コマンドを探す場所のリスト
（**PATH**）に uv のインストール先が追加されたことを、起動中のターミナルに認識させるためです。

```bash
uv --version
```

期待される出力:

```text
uv 0.x.x (xxxxxxxx xxxx-xx-xx)
```

`uv: command not found` と言われた場合は「つまずきポイント」を参照してください。

uv が入ったら、Python 3.12 を uv 経由でインストールします。

```bash
uv python install 3.12
```

期待される出力:

```text
Installed Python 3.12.x in x.xxs
 + cpython-3.12.x-<プラットフォーム>
```

Python の動作確認は、次の 0.5 で仮想環境を作ってから行います。
`uv python install` は `python` コマンドを直接使えるようにするものではないため、
この時点で `python --version` を打っても反応がない（別の Python が応答する）場合があります。

!!! note "すでに Python が入っている場合"
    3.12 以上ならそのまま使ってかまいません。3.11 以下しかない場合は、
    上記の `uv python install 3.12` で追加してください。
    複数の Python が同居していても、uv がプロジェクトごとに適切なものを選んでくれます。

## 0.5 依存パッケージをインストールする

このリポジトリのルートには `pyproject.toml` があり、このプロジェクトが使うパッケージが
宣言されています。リポジトリのルートに移動して、次を実行してください。

```bash
uv sync --group docs
```

期待される出力（所要時間のみ環境によって異なります。パッケージ数は `uv.lock` で固定です）:

```text
Using CPython 3.12.x interpreter at: /home/<ユーザー名>/.local/share/uv/python/...
Creating virtual environment at: .venv
Resolved 30 packages in xxxms
Prepared 29 packages in x.xxs
Installed 29 packages in xxms
 + mkdocs==1.6.x
 + mkdocs-material==9.5.x
 ...
```

これで `.venv/` という仮想環境が作られ、テキストをローカルで表示するためのライブラリ
（[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)）が入りました。

ここで Python のバージョンを確認しておきましょう。仮想環境の中の Python を実行するので、
`uv run` 経由で打ちます。

```bash
uv run python --version
```

期待される出力:

```text
Python 3.12.x
```

この研修では、Python のバージョン確認は常にこの `uv run python --version` で行います。

動作確認として、このテキストをローカルでプレビューしてみましょう。

```bash
uv run mkdocs serve
```

期待される出力:

```text
INFO    -  Building documentation...
INFO    -  Documentation built in x.xx seconds
INFO    -  [xx:xx:xx] Watching paths for changes: ...
INFO    -  [xx:xx:xx] Serving on http://127.0.0.1:8000/
```

ブラウザで <http://127.0.0.1:8000/> を開き、このページが表示されれば OK です。
確認できたら `Ctrl` + `C` で停止してください。

!!! tip "uv run とは"
    `uv run <コマンド>` は「このプロジェクトの仮想環境（`.venv/`）の中でコマンドを実行する」
    という意味です。仮想環境を手動で有効化（`source .venv/bin/activate` など）しなくても、
    `uv run` 経由なら常に正しい環境で実行できます。この研修では基本的にこの形でコマンドを実行します。

## 0.6 PostgreSQL を起動する

リポジトリのルートには `docker-compose.yml` があります。これは「どのイメージ
（コンテナのもとになる設計図のようなもの）を、どんな環境変数で、どのポートで起動するか」を
まとめた設定ファイルで、
[Docker Compose](https://docs.docker.com/compose/) がこれを読んで PostgreSQL コンテナを立ち上げます。
`docker run` の長いオプションを毎回打つ代わりに、このファイルさえあれば誰でも同じ環境を再現できます。

リポジトリのルートで次を実行してください（初回は PostgreSQL のイメージをダウンロードするため
数分かかることがあります）。

```bash
docker compose up -d
```

期待される出力:

```text
[+] Running 2/2
 ✔ Network webapp-training_default  Created
 ✔ Container webapp-training-db     Started
```

`-d` は detached（バックグラウンド）で起動するオプションです。付けないとターミナルが
ログ表示に占有され続けるので、基本的には付けておきます。

起動できたか確認します。

```bash
docker compose ps
```

期待される出力:

```text
NAME                 IMAGE         STATUS                   PORTS
webapp-training-db   postgres:16   Up xx seconds (healthy)   0.0.0.0:5432->5432/tcp, ...
```

`STATUS` が `Up`（しばらくすると `(healthy)` が付きます）になっていれば OK です。
`PORTS` 列の `...` は IPv6 向けの表示（`:::5432->5432/tcp`）を省略したもので、気にしなくて大丈夫です。

接続情報は次のとおりです。

| 項目 | 値 |
|---|---|
| ホスト | `localhost` |
| ポート | `5432` |
| データベース | `tododb` |
| ユーザー | `todo` |
| パスワード | `todo` |

この 5 つの値は、このあとの章で Python から PostgreSQL に接続するときにそのまま使います。
まとめて「接続情報」としてメモしておくと、あとで接続エラーが出たときに確認しやすくなります。

!!! warning "本番ではこんなパスワードは絶対NG"
    研修用なのでわかりやすさ優先で `todo / todo` にしています。
    実務では絶対にこのままにしないでください。
    第17章で「環境変数で設定を外に出す」やり方を扱います。

## 0.7 psql で接続してみる

`psql` は PostgreSQL 純正のコマンドラインクライアントです。
Python のコードを介さずに直接 SQL を打てるので、「アプリのバグなのか、そもそも DB の
データがおかしいのか」を切り分けるときの最後の頼みの綱になります。

=== "ホストに psql が入っている場合"

    ```bash
    psql -h localhost -p 5432 -U todo -d tododb
    ```

    パスワードを聞かれたら `todo` と入力します（入力中は画面に何も表示されません）。

=== "コンテナの中で psql を使う（ホストに入れたくない場合）"

    ```bash
    docker exec -it webapp-training-db psql -U todo -d tododb
    ```

    コンテナの中には `psql` が最初から入っているので、この方法ならホストへの
    インストールは不要です。

期待される出力:

```text
psql (16.x)
Type "help" for help.

tododb=#
```

`tododb=#` というプロンプトが出れば接続成功です。次を順に試してみましょう。

```sql
SELECT version();
```

期待される出力:

```text
                                                version
--------------------------------------------------------------------------------------------------------
 PostgreSQL 16.x (...) on x86_64-pc-linux-gnu, compiled by gcc ...
(1 row)
```

```text
\dt
```

期待される出力:

```text
Did not find any relations.
```

テーブルがまだ 1 つもないので、この表示で正解です。最後に `\q` で抜けます。

```text
\q
```

!!! note "SQL と psql のメタコマンドの区別"
    `\` から始まる `\dt` や `\q` は **SQL ではなく psql 独自のメタコマンド**（ショートカット）です。
    一方 `SELECT version();` はふつうの SQL 文で、Python のコードから実行するのもこれと同じものです。
    どちらが SQL でどちらが psql の機能なのかを区別しておくと、後の章でエラーメッセージを
    読むときに迷いません。

## 0.8 エディタの準備

エディタは普段使っているものでかまいません。
おすすめは VS Code か Cursor で、最低でも次の拡張機能を入れておくとラクです。

- **Python**（Microsoft）
- **Pylance**（型チェック）
- **Ruff**（自動フォーマット + 静的解析）
- **PostgreSQL**（任意。SQL ファイルのシンタックスハイライト）

Pylance は、コードに書いた型ヒントをもとに「`int` を渡すはずの引数に `str` を渡している」
といった矛盾を、実行する前にエディタ上で教えてくれます。Ruff はスタイルの自動整形と、
未使用の import のようなよくあるミスの検出をまとめて行ってくれます。
型ヒントについては第1章で扱います。

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

## 0.9 チェックポイント

ここまでの作業が全部できているか、自分で確認しましょう。
すべてにチェックが付けば環境構築は完了です。

- [ ] `docker version` で Client と Server の両方が表示される
- [ ] `uv --version` でバージョンが表示される
- [ ] `uv run python --version` で 3.12 以上が表示される
- [ ] `docker compose ps` の STATUS が `Up`（または `Up ... (healthy)`）になっている
- [ ] `psql` で `SELECT version();` が実行できる
- [ ] `uv run mkdocs serve` でテキストがブラウザに表示される

どれか 1 つでも欠けていると後の章で必ずつまずくので、次に進む前に解消してください。

## 0.10 つまずきポイント

### Docker が起動していない

`docker compose up -d` で次のようなエラーが出る:

```text
Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
Is the docker daemon running?
```

Docker の本体（デーモン）が動いていません。

- Windows / macOS: **Docker Desktop を起動**して、クジラのアイコンが
  「Docker Desktop is running」になるのを待ってから再実行
- Linux: `sudo systemctl start docker` でデーモンを起動

### ポート 5432 が競合する

```text
Error response from daemon: Bind for 0.0.0.0:5432 failed: port is already allocated
```

ホストの 5432 番ポートを、すでに動いている別の PostgreSQL（以前インストールしたものなど）が
使っています。対処は次のどちらかです。

1. 既存の PostgreSQL を停止する（不要ならアンインストールでもよい）
2. `docker-compose.yml` の `ports` を `"5433:5432"` に変えて、ホスト側は 5433 で受ける。
   この場合、以降の章の接続情報のポートもすべて `5433` に読み替えてください

### `uv: command not found` と言われる

uv のインストール直後に多い症状です。インストーラは `~/.local/bin`（Windows は別の場所）に
uv を置きますが、そのパスが現在のシェルにまだ読み込まれていないのが原因です。

1. ターミナルを**すべて閉じて開き直す**（多くの場合これで直ります）
2. それでもダメなら、インストール時のメッセージに従って `source $HOME/.local/bin/env` を
   実行するか、その行を `~/.bashrc` / `~/.zshrc` に追記する

### 権限エラーが出る（Linux）

```text
permission denied while trying to connect to the Docker daemon socket
```

Linux では、Docker を使えるのはデフォルトで root と `docker` グループのユーザーのみです。
自分を `docker` グループに追加してください。

```bash
sudo usermod -aG docker $USER
```

実行後、**一度ログアウトして再ログイン**すれば `sudo` なしで `docker` コマンドが使えます。

!!! warning "sudo でごまかさない"
    `sudo docker compose up -d` のように sudo で実行する手もありますが、
    root 所有のファイルが作業ディレクトリに混ざって後のトラブルのもとになります。
    グループ追加で根本的に解決しましょう。

## 0.11 やってみよう

### 問1 ログを読んでみる

`docker compose logs db` を実行して、PostgreSQL の起動ログを眺めてみましょう。
その中から `database system is ready to accept connections` という行を探してください。
この行が出ていれば、PostgreSQL が接続を受け付ける準備ができた証拠です。

??? example "解答例"

    ```bash
    docker compose logs db
    ```

    期待される出力（抜粋）:

    ```text
    webapp-training-db  | ... LOG:  database system was shut down at ...
    webapp-training-db  | ... LOG:  database system is ready to accept connections
    ```

    大量に流れるログの中から「準備完了」の 1 行を見つける練習です。
    ログは「エラーが出たときだけ読むもの」ではなく、正常時がどう見えるかを
    知っておくと異常に気づきやすくなります。

### 問2 はじめての SQL

`psql` で接続して、次の SQL を順に実行してみましょう。実行ごとに結果を確認してください。

```sql
CREATE TABLE hello (id SERIAL PRIMARY KEY, msg TEXT NOT NULL);
INSERT INTO hello (msg) VALUES ('はじめての行');
SELECT * FROM hello;
DROP TABLE hello;
```

??? example "解答例"

    ```text
    tododb=# CREATE TABLE hello (id SERIAL PRIMARY KEY, msg TEXT NOT NULL);
    CREATE TABLE
    tododb=# INSERT INTO hello (msg) VALUES ('はじめての行');
    INSERT 0 1
    tododb=# SELECT * FROM hello;
     id |      msg
    ----+----------------
      1 | はじめての行
    (1 row)
    tododb=# DROP TABLE hello;
    DROP TABLE
    ```

    各文が何をしているかは第3章で詳しくやります。ここでは
    「psql で SQL を打てば、すぐ結果が返ってくる」という体験ができれば十分です。

### 問3 コンテナを止めてもデータは残るか？

問2 の `DROP TABLE hello;` を実行する**前**に試してください。

1. `CREATE TABLE` と `INSERT` まで実行する
2. いったん `\q` で抜け、`docker compose down` でコンテナを停止・削除する
3. `docker compose up -d` で起動し直し、再度 `psql` で接続して `SELECT * FROM hello;` を実行する

コンテナは作り直されたのに、データは残っているはずです。なぜでしょうか？

??? example "解答例"

    残っていれば正解です。理由は `docker-compose.yml` のこの部分です。

    ```yaml
    volumes:
      - pgdata:/var/lib/postgresql/data
    ```

    PostgreSQL のデータファイルは **named volume**（`pgdata`）という、
    コンテナの外側の保存領域に置かれています。`docker compose down` で
    コンテナ自体は削除されても、volume は残るため、起動し直せばデータが戻ってきます。

    「コンテナは使い捨て、データは volume に」というのが Docker の基本設計です。
    本当にデータごと消したいときは `docker compose down -v`（volume も削除）を使います。

    確認が終わったら、`DROP TABLE hello;` で後片付けをしておきましょう。

## まとめ

- **Docker** は「環境ごと箱詰めしたコンテナ」を動かす仕組み。これで全員が同じ PostgreSQL 16 を使える
- **ポート**はサービスの窓口番号。PostgreSQL は 5432 番で待ち受ける
- **uv** は pip の高速な代替。仮想環境の作成（`uv sync`）からコマンド実行（`uv run`）まで面倒を見てくれる
- **psql** は DB を直接覗く道具。アプリの調子が悪いときの切り分けに必須
- コンテナを消しても **named volume** にデータは残る

環境はこれで完成です。次は [第1章 Pythonのおさらい① 型ヒントとdataclass](01-python-types.md) で、
この研修で使う Python の機能を確認します。
