# 第2章 Pythonのおさらい② with・モジュール・pytest

前章に続いて Python の復習です。
この章では「**実装するときに毎日使う**」3 つを扱います。

- 例外処理と `with` 文
- モジュールとパッケージ
- pytest の基本

## 2.1 例外処理

DB 接続に失敗する、SQL がおかしい、入力がおかしい——いろいろ起きます。
Python はこうした「想定外の事態」を **例外（exception）** として表現します。
例外を何もせず放置すると、その場でプログラムが止まってしまいます
（Web アプリなら、ユーザーには真っ白なエラー画面が返ります）。
`try` で「例外が起きるかもしれない処理」を囲み、`except` で「起きたときにどうするか」を
書いておくことで、プログラムを止めずに次の一手を打てるようになります。
詳しくは公式チュートリアルの[エラーと例外](https://docs.python.org/3/tutorial/errors.html)にまとまっています。
まずは `try / except / finally` を最低限知っておきます。

```python
try:
    n = int(input("数字を入れて: "))
except ValueError:
    print("数字じゃないやんか")
finally:
    print("ここは何があっても通る")
```

`finally` ブロックは、例外が起きても起きなくても必ず実行されます。
「ファイルを閉じる」「ロックを解放する」といった後始末を書くのに向いていますが、
ファイルや DB 接続の後始末に限っては、次に説明する `with` 文を使うほうが
書き忘れの心配がなく安全です。

複数の例外をまとめて拾うこともできます。

```python
try:
    risky()
except (ValueError, KeyError) as e:
    print(f"想定内のエラー: {e}")
except Exception as e:
    print(f"想定外: {e}")
    raise  # 再送して上に投げる
```

`except` は上から順に照合されるので、**より具体的な例外を先に、
`Exception` のような広い例外は最後に**置きます。逆順にすると、広い方が先に
マッチしてしまい、具体的な `except` 節が永遠に使われなくなります。
`as e` で例外オブジェクトを変数に束縛すると、そのエラーメッセージや属性を使って
詳しい情報を出せます。何もしない `raise` は、いま捕まえた例外を握りつぶさずに
スタックトレースごとそのまま上へ投げ直す書き方です。

例外を **にぎりつぶさない** のが鉄則です。`except Exception: pass` は
「**バグを隠した**」と同じ意味になります。少なくともログを残しましょう。
本格的にログを残すときは `print` ではなく標準の
[logging](https://docs.python.org/3/library/logging.html) モジュールを使うと、
ログレベルや出力先を後から柔軟に変えられます（第17章で扱います）。

## 2.2 `with` 文（コンテキストマネージャ）

ファイルを開いたら閉じる、DB に接続したら閉じる、ロックを取ったら離す——
こういう **「最後に必ず後始末をしたい処理」** には `with` を使います。

`with` の後ろに置けるオブジェクトを **コンテキストマネージャ** と呼びます。
「ブロックに入るときの処理」と「ブロックを抜けるときの処理」をセットで持つ仕組みで、
抜けるときの処理は途中で例外が起きても必ず呼ばれます。つまり `with` は、
`try / finally` で後始末を書くパターンを短く・書き忘れなく表現するための構文です。
仕組みの詳細は[公式ドキュメントの `with` 文の説明](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement)、
自作したい場合は[contextlib](https://docs.python.org/3/library/contextlib.html)を参照してください。

```python
# 旧来のやり方（閉じ忘れの危険）
f = open("notes.txt")
data = f.read()
f.close()

# with を使った正しいやり方
with open("notes.txt") as f:
    data = f.read()
# ↑ ブロックを抜けると自動で f.close() が呼ばれる
```

「旧来のやり方」の何が危険かというと、`f.read()` の途中で例外が起きると
`f.close()` の行にたどり着けず、ファイルが開いたままになってしまう点です。
DB 接続で同じことをすると、接続が解放されないまま残り続け、やがて
「接続数の上限に達して新しい接続が作れない」といった実害につながります。

[`psycopg`](https://www.psycopg.org/psycopg3/docs/) の接続も `with` で書きます（第5章で詳しく扱います）。

```python
with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        print(cur.fetchone())
# ブロックを抜けるとカーソルも接続も自動で閉じる
```

外側の `with` が接続を、内側の `with` がカーソルを管理しています。
このように `with` は入れ子にでき、内側で例外が起きても内側・外側どちらの
後始末も正しく実行されます。`with A as a, B as b:` のように 2 つ以上を
1 行にまとめる書き方もよく使います（意味は入れ子の `with` と同じで、
インデントが 1 段減るぶん読みやすくなります）。

## 2.3 モジュールとパッケージ

1 つのファイルに全部書いていくと、すぐに数百〜数千行になって
「どこに何が書いてあるか分からない」状態になります。
ファイルが増えてきたら **役割ごとにファイルを分割** します。
分割しておけば、変更したい箇所を見つけやすくなり、テストも書きやすくなります。
分割した Python ファイルを「モジュール」、モジュールをまとめたフォルダを
「パッケージ」と呼びます。詳しくは公式チュートリアルの
[モジュール](https://docs.python.org/3/tutorial/modules.html)を参照してください。

```text
app/
├── __init__.py     # 「ここはパッケージです」と示す（中身は空でOK）
├── main.py         # アプリの起動点
├── db.py           # DB接続の関数
└── models.py       # データクラスの定義
```

`__init__.py` は中身が空でも構いません。このファイルがあることで、
Python はそのフォルダを「ただのフォルダ」ではなく「import できるパッケージ」
として扱えるようになります。

`main.py` から他のファイルを使うとき:

```python
from app.db import get_connection
from app.models import Todo
```

`app.db` のように **パッケージ名から書き始める import** を絶対importと呼びます。
ファイルを移動してもこの書き方なら意味が変わりにくいので、迷ったら絶対importを
使うのが無難です。

実行は **モジュール指定** で行うのが安全です。

```bash
uv run python -m app.main
```

!!! note "なぜ -m か"
    `python app/main.py` だと相対 import がうまくいかない場合があります。
    `-m` を使うと「パッケージとして」起動できるので、import の挙動が安定します。
    ざっくり言うと、`-m app.main` は `app` パッケージを起点に `main` モジュールを
    実行してくれと Python に伝える書き方で、`app` 以下の import が常に同じ基準で
    解決されるようになります。

## 2.4 pytest の基本

コードを書くたびに手で動作確認するのは手間ですし、後から機能を追加したときに
以前動いていた部分を壊してしまっても気づきにくくなります。期待する動作を
あらかじめテストとして書いておけば、変更のたびに自動で再確認でき、
安心してコードを直せるようになります。このテキストでは
[pytest](https://docs.pytest.org/en/stable/) を使います。pytest は
「命名規則に従ったファイルと関数」を自動的に見つけて実行してくれるので、
テストファイルは `tests/` ディレクトリに、ファイル名は `test_*.py`、
関数名も `test_*` にします。

```python
# tests/test_math.py
def add(a: int, b: int) -> int:
    return a + b

def test_add_positive():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, -2) == -3
```

`assert 式` は、式が `False` になった時点で `AssertionError` を投げて
失敗を知らせるだけの、Python 標準の仕組みです。pytest はこの `assert` を
そのまま使うだけでよく、専用の比較メソッドを覚える必要がありません。
失敗したときは、比較した値の差分まで見やすく表示してくれます。

実行:

```bash
uv run pytest -v
```

例外が起きることをテストしたい場合:

```python
import pytest

def parse_positive(s: str) -> int:
    n = int(s)
    if n < 0:
        raise ValueError("negative")
    return n

def test_negative_raises():
    with pytest.raises(ValueError):
        parse_positive("-1")
```

`pytest.raises(ValueError)` は、`with` ブロックの中で本当にその例外が
投げられることを確認するためのコンテキストマネージャです。例外が投げられなかった
場合や、別の種類の例外が投げられた場合は、テストの方が失敗してくれます。

!!! tip "fixture（前準備）の考え方"
    複数のテストで共通の前準備（DB 接続など）が必要なときは `@pytest.fixture` を使います。
    第12章のテスト回でしっかり扱うので、ここでは「そういうのがある」ことだけ覚えておけば十分です。
    先取りして見ておきたい場合は
    [pytest公式のfixtureガイド](https://docs.pytest.org/en/stable/how-to/fixtures.html)
    も参考になります。

## やってみよう

1. `app/calc.py` に `def add(a: int, b: int) -> int:` を作る。
2. `tests/test_calc.py` で、正の数・負の数・大きな数の 3 ケースを書く。
3. `pytest -v` で 3 つとも緑になることを確認する。
4. わざと `add` を `a - b` に書き換えて **失敗の出方**を見てみる。

次は [第 3 章 PostgreSQLのおさらい① DDL/DML/SELECT](03-postgres-ddl-dml.md) で、
DB 側のおさらいに入ります。
