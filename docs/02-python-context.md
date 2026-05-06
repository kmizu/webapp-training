# 第2章 Pythonのおさらい② with・モジュール・pytest

前章に続いて Python の復習です。
この章では「**実装するときに毎日使う**」3 つを扱います。

- 例外処理と `with` 文
- モジュールとパッケージ
- pytest の基本

## 2.1 例外処理

DB 接続に失敗する、SQL がおかしい、入力がおかしい——いろいろ起きます。
`try / except / finally` を最低限知っておきます。

```python
try:
    n = int(input("数字を入れて: "))
except ValueError:
    print("数字じゃないやんか")
finally:
    print("ここは何があっても通る")
```

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

例外を **にぎりつぶさない** のが鉄則です。`except Exception: pass` は
「**バグを隠した**」と同じ意味になります。少なくともログを残しましょう。

## 2.2 `with` 文（コンテキストマネージャ）

ファイルを開いたら閉じる、DB に接続したら閉じる、ロックを取ったら離す——
こういう **「最後に必ず後始末をしたい処理」** には `with` を使います。

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

`psycopg` の接続も `with` で書きます（第5章で詳しく扱います）。

```python
with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        print(cur.fetchone())
# ブロックを抜けるとカーソルも接続も自動で閉じる
```

`with A as a, B as b:` のように 2 つ以上を 1 行にまとめる書き方もよく使います。

## 2.3 モジュールとパッケージ

ファイルが増えてきたら **役割ごとにファイルを分割** します。
分割した Python ファイルを「モジュール」、フォルダにまとめたものを「パッケージ」と呼びます。

```text
app/
├── __init__.py     # 「ここはパッケージです」と示す（中身は空でOK）
├── main.py         # アプリの起動点
├── db.py           # DB接続の関数
└── models.py       # データクラスの定義
```

`main.py` から他のファイルを使うとき:

```python
from app.db import get_connection
from app.models import Todo
```

実行は **モジュール指定** で行うのが安全です。

```bash
uv run python -m app.main
```

!!! note "なぜ -m か"
    `python app/main.py` だと相対 import がうまくいかない場合があります。
    `-m` を使うと「パッケージとして」起動できるので、import の挙動が安定します。

## 2.4 pytest の基本

このテキストでは pytest を使います。テストファイルは `tests/` ディレクトリに、
ファイル名は `test_*.py`、関数名も `test_*` にします。

```python
# tests/test_math.py
def add(a: int, b: int) -> int:
    return a + b

def test_add_positive():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, -2) == -3
```

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

!!! tip "fixture（前準備）の考え方"
    複数のテストで共通の前準備（DB 接続など）が必要なときは `@pytest.fixture` を使います。
    第12章のテスト回でしっかり扱うので、ここでは「そういうのがある」ことだけ覚えておけば十分です。

## やってみよう

1. `app/calc.py` に `def add(a: int, b: int) -> int:` を作る。
2. `tests/test_calc.py` で、正の数・負の数・大きな数の 3 ケースを書く。
3. `pytest -v` で 3 つとも緑になることを確認する。
4. わざと `add` を `a - b` に書き換えて **失敗の出方**を見てみる。

次は [第 3 章 PostgreSQLのおさらい① DDL/DML/SELECT](03-postgres-ddl-dml.md) で、
DB 側のおさらいに入ります。
