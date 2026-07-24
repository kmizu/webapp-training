# 付録B 用語集

研修で出てくる用語を、**この研修の文脈での意味**で簡潔に書きます。
厳密な定義より「ぱっと思い出せる」を優先しています。

## A〜Z

**API（Application Programming Interface）**
: プログラムの境界。本研修では「HTTP で呼ばれるサーバー側の窓口」を指す。`/api/todos` がそれ。

**CASCADE**
: 親が消えたら子も連鎖的に消す。`ON DELETE CASCADE` は ToDo を消したら関連する `todo_tags` も自動で消える設定。これを付けないと、親を消しても子だけが残る「孤立データ」が発生してしまう。詳しくは[公式ドキュメント](https://www.postgresql.org/docs/current/ddl-constraints.html)を参照。

**CHECK 制約**
: テーブルのカラムが守るべき条件。`CHECK (priority BETWEEN 1 AND 3)` で「1〜3 以外は入れさせない」。アプリ側のバリデーションだけに頼ると抜け漏れが起きるため、DB 側でも最後の砦として弾く。詳しくは[公式ドキュメント](https://www.postgresql.org/docs/current/ddl-constraints.html)を参照。

**CRUD**
: Create / Read / Update / Delete。データに対する 4 つの基本操作。多くの操作をこの 4 種類に当てはめて考えられるので、API 設計や画面設計の見通しを立てやすくなる。

**CSRF（クロスサイトリクエストフォージェリ）**
: ログイン中のユーザーをだまして、本人の意図しない操作（送金など）を実行させる攻撃。詳しくは[公式ドキュメント](https://developer.mozilla.org/ja/docs/Web/Security/Attacks/CSRF)を参照。

**DDL / DML**
: Data Definition Language（`CREATE TABLE` などスキーマ操作）/ Data Manipulation Language（`SELECT/INSERT/UPDATE/DELETE` などデータ操作）。普段のアプリコードで書くのはほぼ DML で、DDL はマイグレーションなど別の場面で使う、と分けて覚えると混同しにくい。詳しくは DDL は[公式ドキュメント](https://www.postgresql.org/docs/current/ddl.html)、DML は[公式ドキュメント](https://www.postgresql.org/docs/current/dml.html)を参照。

**dataclass**
: Python 標準の「データを持つだけのクラス」を簡潔に書く仕組み。`@dataclass` を付けて使う。`__init__` や `__repr__` を手で書く手間を省くために使う。詳しくは[公式ドキュメント](https://docs.python.org/3/library/dataclasses.html)を参照。

**DSN（Data Source Name）**
: DB の接続情報を 1 行にまとめた文字列。`host=... port=... dbname=...`。接続情報をコードに直書きせず、環境変数などで 1 つの値として渡せるようにするために使う。

**ER 図**
: Entity-Relationship Diagram。テーブル間の関係を図示したもの。テーブルを作る前に関係性を図で確認しておくと、あとからの手戻りを減らせる。

**FastAPI**
: Python の Web フレームワーク。型ヒントを活用した API 構築が得意。型ヒントから入力チェックや API ドキュメントが自動生成されるので、手書きのバリデーションコードを減らせる。詳しくは[公式ドキュメント](https://fastapi.tiangolo.com/)を参照。

**GIL**
: Global Interpreter Lock。Python は基本 1 プロセスで CPU を 1 スレッドぶんしか使わない仕組み。研修では深追いしない。

**htmx**
: HTML 属性に `hx-*` を書くだけで Ajax できる軽量ライブラリ。サーバーは HTML を返すだけ。JS をほとんど書かずに動的な UI を作れるため、SPA 用フレームワークを持ち込まずに済むのが利点。詳しくは[公式ドキュメント](https://htmx.org/docs/)を参照。

**HTTP**
: Web の通信プロトコル。リクエスト（メソッド + パス + ヘッダ + ボディ）とレスポンス（ステータス + ヘッダ + ボディ）でやりとり。ブラウザも API クライアントも同じ土台の上で通信できるようにする、Web 共通のルール。詳しくは[公式ドキュメント](https://developer.mozilla.org/ja/docs/Web/HTTP/Methods)を参照。

**JOIN**
: 複数テーブルを **結合**して 1 つの結果に。`INNER` / `LEFT` / `RIGHT` / `FULL OUTER` などの種類がある。正規化でテーブルを分けた分だけ、必要なときに JOIN で結果を 1 つにまとめ直す必要がある。詳しくは[公式ドキュメント](https://www.postgresql.org/docs/current/queries-table-expressions.html)を参照。

**LIMIT / OFFSET**
: SQL の取得行数制限と、何行目から取るかの指定。ページング基礎。

**Migration（マイグレーション）**
: DB スキーマの変更を **連番付きの SQL** で管理し、再現可能にする仕組み。手作業でスキーマを変えると環境ごとに差異が生まれるため、変更履歴をコードとして残して揃える。

**N+1 問題**
: 1 件取ったあと、関連する子を **1 件ごとに別クエリ**で取ってしまう典型的な性能問題。`IN`/`ANY` でまとめて取ると解消できる。

**ORM**
: Object-Relational Mapper。SQL を書かずにオブジェクト操作で DB を扱う仕組み。本研修では使わない。実務では SQL を書く手間を減らす目的で使われることが多いが、本研修では SQL そのものの理解を優先するためあえて使わない。

**PATCH / PUT**
: HTTP のメソッド。PATCH は部分更新、PUT は丸ごと差し替え。全部を送り直すのが面倒な場面（一部の項目だけ変えたいときなど）のために PATCH が使い分けられる。

**psycopg**
: Python から PostgreSQL を扱うドライバ。本研修ではバージョン 3 を使う。Python は PostgreSQL と直接会話できないため、間を取り持つこのドライバが必要になる。詳しくは[公式ドキュメント](https://www.psycopg.org/psycopg3/docs/)を参照。

**Pydantic**
: 型ヒントベースのバリデーションライブラリ。FastAPI と組み合わせて使う。不正な形のデータが処理の奥まで入り込む前に、入口でまとめて弾くために使う。詳しくは[公式ドキュメント](https://docs.pydantic.dev/latest/)を参照。

**REST**
: HTTP の使い方の流儀のひとつ。リソースに対する CRUD をメソッドで表現する考え方。設計の流儀を揃えることで、初めて見る API でもだいたいの使い方を予測しやすくなる。

**Repository パターン**
: 「DB アクセスをまとめる層」を作って、他の層から SQL を直接呼ばない設計。SQL が散らばらないので、テストの際に DB アクセス部分だけ差し替えやすくなる。

**Schema（スキーマ）**
: 「形」。文脈で意味が変わる。DB 文脈ではテーブル定義、API 文脈では入出力 JSON の形。同じ単語がどちらの文脈かを意識して読み分けないと混乱しやすいので注意。

**SERIAL**
: PostgreSQL の **自動採番カラム** を作るショートカット。実体は `INTEGER` + シーケンス。主キーの値を自分で採番・管理する手間をなくすために使う。

**SQL インジェクション**
: ユーザー入力を SQL に直接結合してしまうことで起きる攻撃。**プレースホルダ（`%s`）を必ず使う**ことで防ぐ。

**Stack Trace（スタックトレース）**
: 例外が発生したときに出る、関数呼び出しの履歴。バグ調査の最初の一手。

**TIMESTAMPTZ**
: タイムゾーン付きのタイムスタンプ。複数地域で使う可能性があるなら基本これ。

**Trigger（トリガー）**
: テーブルに対する INSERT/UPDATE/DELETE をきっかけに自動実行される SQL。本研修では使わない。ルールを DB 側に隠さずアプリのコードで見える形にしておきたいため、本研修ではあえて避けている。

**uv**
: 高速な Python パッケージマネージャ。`pip` の代わりに使う。依存関係のインストールや環境構築を速くして、待ち時間のストレスを減らすために使う。

**View（ビュー）**
: SELECT の結果に名前を付けたもの。実体のデータは持たず、参照のたびに計算される。複雑な SELECT を毎回書き直さずに済むよう、よく使う問い合わせに名前を付けて使い回すために使う。

**WAL**
: Write-Ahead Log。PostgreSQL の耐久性を支える仕組み。「先にログを書く、本体はあとから」。本研修では深追いしない。

**WSGI / ASGI**
: Python の Web サーバーとアプリの境界仕様。FastAPI は ASGI、Flask は WSGI。ASGI は非同期処理を前提にしているため、WSGI では苦手だった同時接続の多い処理に強い。

## 五十音

**インデックス**
: SQL の検索を速くするためのデータ構造。`CREATE INDEX` で作る。WHERE と ORDER BY の組み合わせに合わせて貼ると効く。詳しくは[公式ドキュメント](https://www.postgresql.org/docs/current/indexes.html)を参照。

**正規化**
: 重複を減らすようにテーブルを分割していく考え方。第 1〜第 3 正規形あたりまでが実用ライン。重複を放置すると、更新時に一部だけ直し忘れてデータ不整合が起きやすくなる。

**ソート**
: 並べ替え。SQL では `ORDER BY`。

**トランザクション**
: 複数の SQL を「ぜんぶ成功」か「ぜんぶ失敗」にまとめる仕組み。`BEGIN; ... COMMIT;` または `ROLLBACK;`。詳しくは[公式ドキュメント](https://www.postgresql.org/docs/current/tutorial-transactions.html)を参照。

**バインディング / プレースホルダ**
: 値を SQL に直接入れず、`%s`（psycopg）や `?`（一部のドライバ）で書いて値を別に渡す方式。SQL インジェクション対策の基本。

**ホットリロード**
: コードを変更したら自動でサーバーが再起動する仕組み。`uvicorn --reload`。毎回手動でサーバーを再起動する手間をなくし、開発のリズムを崩さないために使う。

**マイグレーション**（再掲）
: DB スキーマの変更を再現可能な形で管理すること。

**ロールバック**
: トランザクションの取り消し。`ROLLBACK;`。処理の途中でエラーが起きたときに、中途半端な状態のままデータが残るのを防ぐために使う。
