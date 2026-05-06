# 付録B 用語集

研修で出てくる用語を、**この研修の文脈での意味**で簡潔に書きます。
厳密な定義より「ぱっと思い出せる」を優先しています。

## A〜Z

**API（Application Programming Interface）**
: プログラムの境界。本研修では「HTTP で呼ばれるサーバー側の窓口」を指す。`/api/todos` がそれ。

**CASCADE**
: 親が消えたら子も連鎖的に消す。`ON DELETE CASCADE` は ToDo を消したら関連する `todo_tags` も自動で消える設定。

**CHECK 制約**
: テーブルのカラムが守るべき条件。`CHECK (priority BETWEEN 1 AND 3)` で「1〜3 以外は入れさせない」。

**CRUD**
: Create / Read / Update / Delete。データに対する 4 つの基本操作。

**CSRF（クロスサイトリクエストフォージェリ）**
: ログイン中のユーザーをだまして、本人の意図しない操作（送金など）を実行させる攻撃。

**DDL / DML**
: Data Definition Language（`CREATE TABLE` などスキーマ操作）/ Data Manipulation Language（`SELECT/INSERT/UPDATE/DELETE` などデータ操作）。

**dataclass**
: Python 標準の「データを持つだけのクラス」を簡潔に書く仕組み。`@dataclass` を付けて使う。

**DSN（Data Source Name）**
: DB の接続情報を 1 行にまとめた文字列。`host=... port=... dbname=...`。

**ER 図**
: Entity-Relationship Diagram。テーブル間の関係を図示したもの。

**FastAPI**
: Python の Web フレームワーク。型ヒントを活用した API 構築が得意。

**GIL**
: Global Interpreter Lock。Python は基本 1 プロセスで CPU を 1 スレッドぶんしか使わない仕組み。研修では深追いしない。

**htmx**
: HTML 属性に `hx-*` を書くだけで Ajax できる軽量ライブラリ。サーバーは HTML を返すだけ。

**HTTP**
: Web の通信プロトコル。リクエスト（メソッド + パス + ヘッダ + ボディ）とレスポンス（ステータス + ヘッダ + ボディ）でやりとり。

**JOIN**
: 複数テーブルを **結合**して 1 つの結果に。`INNER` / `LEFT` / `RIGHT` / `FULL OUTER` などの種類がある。

**LIMIT / OFFSET**
: SQL の取得行数制限と、何行目から取るかの指定。ページング基礎。

**Migration（マイグレーション）**
: DB スキーマの変更を **連番付きの SQL** で管理し、再現可能にする仕組み。

**N+1 問題**
: 1 件取ったあと、関連する子を **1 件ごとに別クエリ**で取ってしまう典型的な性能問題。`IN`/`ANY` でまとめて取ると解消できる。

**ORM**
: Object-Relational Mapper。SQL を書かずにオブジェクト操作で DB を扱う仕組み。本研修では使わない。

**PATCH / PUT**
: HTTP のメソッド。PATCH は部分更新、PUT は丸ごと差し替え。

**psycopg**
: Python から PostgreSQL を扱うドライバ。本研修ではバージョン 3 を使う。

**Pydantic**
: 型ヒントベースのバリデーションライブラリ。FastAPI と組み合わせて使う。

**REST**
: HTTP の使い方の流儀のひとつ。リソースに対する CRUD をメソッドで表現する考え方。

**Repository パターン**
: 「DB アクセスをまとめる層」を作って、他の層から SQL を直接呼ばない設計。

**Schema（スキーマ）**
: 「形」。文脈で意味が変わる。DB 文脈ではテーブル定義、API 文脈では入出力 JSON の形。

**SERIAL**
: PostgreSQL の **自動採番カラム** を作るショートカット。実体は `INTEGER` + シーケンス。

**SQL インジェクション**
: ユーザー入力を SQL に直接結合してしまうことで起きる攻撃。**プレースホルダ（`%s`）を必ず使う**ことで防ぐ。

**Stack Trace（スタックトレース）**
: 例外が発生したときに出る、関数呼び出しの履歴。バグ調査の最初の一手。

**TIMESTAMPTZ**
: タイムゾーン付きのタイムスタンプ。複数地域で使う可能性があるなら基本これ。

**Trigger（トリガー）**
: テーブルに対する INSERT/UPDATE/DELETE をきっかけに自動実行される SQL。本研修では使わない。

**uv**
: 高速な Python パッケージマネージャ。`pip` の代わりに使う。

**View（ビュー）**
: SELECT の結果に名前を付けたもの。実体のデータは持たず、参照のたびに計算される。

**WAL**
: Write-Ahead Log。PostgreSQL の耐久性を支える仕組み。「先にログを書く、本体はあとから」。本研修では深追いしない。

**WSGI / ASGI**
: Python の Web サーバーとアプリの境界仕様。FastAPI は ASGI、Flask は WSGI。

## 五十音

**インデックス**
: SQL の検索を速くするためのデータ構造。`CREATE INDEX` で作る。WHERE と ORDER BY の組み合わせに合わせて貼ると効く。

**正規化**
: 重複を減らすようにテーブルを分割していく考え方。第 1〜第 3 正規形あたりまでが実用ライン。

**ソート**
: 並べ替え。SQL では `ORDER BY`。

**トランザクション**
: 複数の SQL を「ぜんぶ成功」か「ぜんぶ失敗」にまとめる仕組み。`BEGIN; ... COMMIT;` または `ROLLBACK;`。

**バインディング / プレースホルダ**
: 値を SQL に直接入れず、`%s`（psycopg）や `?`（一部のドライバ）で書いて値を別に渡す方式。SQL インジェクション対策の基本。

**ホットリロード**
: コードを変更したら自動でサーバーが再起動する仕組み。`uvicorn --reload`。

**マイグレーション**（再掲）
: DB スキーマの変更を再現可能な形で管理すること。

**ロールバック**
: トランザクションの取り消し。`ROLLBACK;`。
