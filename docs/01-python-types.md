# 第1章 Pythonのおさらい① 型ヒントとdataclass

ここからは Python の復習です。
**1 章 = 1 回のセッション**で読み切れる量にしてあります。
すでに身についている部分はざっと流し読みでかまいません。

この章で扱うのは次の 3 つです。

- 仮想環境（uv）
- 型ヒント
- dataclass

## 1.1 仮想環境

Python は **プロジェクトごとに専用のライブラリ環境** を作るのが基本で、
これを「仮想環境」と呼びます。

`uv` を使う場合、`pyproject.toml` のあるディレクトリで `uv sync` を実行すれば、
自動的に `.venv/` が作られて必要なライブラリが入ります。

```bash
uv sync                 # 通常の依存関係を入れる
uv add httpx            # 新しいライブラリを追加
uv run python app.py    # 仮想環境内の python で実行
```

!!! tip "仮想環境を意識する一行"
    シェルのプロンプトに `(.venv)` のような表示が出ていれば中に入っている状態。
    `uv run` を使えば毎回意識しなくても勝手に中で動きます。

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
# Python 3.10 以降は Optional[T] を T | None と書ける
def find_user(user_id: int) -> str | None:
    if user_id == 1:
        return "alice"
    return None
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
    嘘の型を書いても動いてしまいます。
    `mypy` や `pyright`（VS Code の Pylance）と一緒に使って初めて意味が出ます。

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

## やってみよう

次の `Todo` クラスを完成させて、`tests/test_todo.py` で 2 つ以上のテストを通してください。
（pytest の使い方は次章で扱います）

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

書けたら次の [第 2 章 Pythonおさらい② with・モジュール・pytest](02-python-context.md) に進みましょう。
