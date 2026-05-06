# 第1章 Pythonのおさらい

このテキストでは、Python の **すべて** を扱うわけではありません。
ToDo アプリを作るうえで **これは必ず使う** という機能だけ、ここでまとめて確認します。

すでに身についている内容ならざっと流し読みでかまいません。
**型ヒント**と**データクラス**と**`with` 文**は、後の章で何度も出てきます。

## 1.1 仮想環境

Python は **プロジェクトごとに専用のライブラリ環境** を作るのが基本です。
これを「仮想環境」と呼びます。

`uv` を使う場合、`pyproject.toml` のあるディレクトリで `uv sync` を実行すれば、
自動的に `.venv/` という仮想環境が作られ、必要なライブラリが入ります。

```bash
uv sync                 # 通常の依存関係を入れる
uv add httpx            # 新しいライブラリを追加
uv run python app.py    # 仮想環境内の python を使って実行
```

!!! tip "仮想環境を意識する一行"
    シェルのプロンプトに `(.venv)` のような表示が出ていれば「中に入っている」状態です。
    `uv run` を使えばこれを意識しなくても勝手に中で動きます。

## 1.2 型ヒント（type hints）

Python は動的型付けですが、**ヒントとして型を書ける**仕組みがあります。
**実行時にチェックされない**ので「ただの注釈」ですが、エディタの補完と
静的解析が劇的に良くなります。

```python
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> None:
    print(f"hello, {name}")
```

頻繁に使うのはこのあたりです。

```python
from typing import Optional

def find_user(user_id: int) -> Optional[str]:
    """見つからなければ None を返す。"""
    if user_id == 1:
        return "alice"
    return None

# Python 3.10 以降は Optional[T] を T | None と書ける
def find_user2(user_id: int) -> str | None:
    ...
```

コレクション型は組み込みの `list` / `dict` / `tuple` をそのまま使えます。

```python
def average(scores: list[float]) -> float:
    return sum(scores) / len(scores)

def index_by_name(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r["name"]: r for r in rows}
```

!!! warning "型ヒントは強制ではない"
    型ヒントを書いても Python は実行時にエラーを出しません。
    嘘の型を書いても動いてしまいます。**`mypy` や `pyright` のような静的解析**
    と一緒に使って初めて意味が出ます。
    研修では VS Code の Pylance に任せます。

## 1.3 dataclass

`dataclass` は **「データを持つだけのクラス」** を簡潔に書くための仕組みです。
ToDo を表す型を、こう書けます。

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    due_on: date | None = None
```

これだけで `__init__`、`__repr__`、`__eq__` が自動生成されます。

```python
t = Todo(id=1, title="牛乳を買う")
print(t)
# Todo(id=1, title='牛乳を買う', done=False, due_on=None)

t2 = Todo(id=1, title="牛乳を買う")
print(t == t2)  # True（中身が同じだから等しい）
```

!!! tip "frozen=True で「変更できない」値にする"
    `@dataclass(frozen=True)` を使うと、属性の代入が禁止された **イミュータブル**
    なクラスになります。値オブジェクトを作るときに便利です。

## 1.4 例外処理

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

## 1.5 `with` 文（コンテキストマネージャ）

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

`psycopg` の接続も `with` で書きます（第3章で詳しく扱います）。

```python
with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        print(cur.fetchone())
# ブロックを抜けるとカーソルも接続も自動で閉じる
```

## 1.6 モジュールとパッケージ

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

## 1.7 簡単なテスト

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

第 5 章でデータアクセス層を作ったときに、ここで書いたパターンが
そのまま生きてきます。

## やってみよう

次の `Todo` クラスを完成させて、`tests/test_todo.py` で 2 つ以上のテストを通してください。

```python
# 仕様
# - 期限が「今日より前」なら is_overdue() が True を返す
# - done が True なら（期限が過ぎていても）is_overdue() は False
# - title が空文字なら ValueError を投げる
```

ヒント:

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    due_on: date | None = None

    def __post_init__(self) -> None:
        # title が空ならここで弾く
        ...

    def is_overdue(self, today: date) -> bool:
        # 仕様に従って書く
        ...
```

書けたら次の [第 2 章 PostgreSQLのおさらい](02-postgres-recap.md) に進みましょう。
