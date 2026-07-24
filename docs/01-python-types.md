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
これを「[仮想環境](https://docs.python.org/3/library/venv.html)」と呼びます。
仮想環境を使わずライブラリをシステムの Python に直接インストールしていくと、
プロジェクト A では `httpx 1.0` が必要なのにプロジェクト B は `httpx 0.27`
でないと動かない、といった**バージョンの衝突**が起きがちです。プロジェクトごとに
仮想環境を分けておけば、そもそもこの衝突を起こさずに済みます（第0章の復習です）。

[uv](https://docs.astral.sh/uv/) を使う場合、`pyproject.toml` のあるディレクトリで `uv sync` を実行すれば、
自動的に `.venv/` が作られて必要なライブラリが入ります。

```bash
uv sync                 # 通常の依存関係を入れる
uv add httpx            # 新しいライブラリを追加
uv run python app.py    # 仮想環境内の python で実行
```

`uv sync` は `pyproject.toml` に書かれた依存関係を読んで `.venv/` を最新の状態に
そろえるコマンド、`uv add` は新しいライブラリを `pyproject.toml` に追記してから
インストールするコマンドです。どちらも裏では標準の venv の仕組みを使っているので、
`uv` が仮想環境そのものを独自に発明しているわけではなく、面倒な操作をまとめて
やってくれている、とイメージしておけば十分です。

!!! tip "仮想環境を意識する一行"
    シェルのプロンプトに `(.venv)` のような表示が出ていれば中に入っている状態。
    `uv run` を使えば毎回意識しなくても勝手に中で動きます。

## 1.2 型ヒント（type hints）

Python は動的型付けですが、**ヒントとして型を書ける**仕組みがあります
（[typing モジュール](https://docs.python.org/3/library/typing.html)、
仕様は [PEP 484](https://peps.python.org/pep-0484/) で定義されています）。
**実行時にチェックされない**ので「ただの注釈」ですが、エディタの補完と
静的解析が劇的に良くなります。型ヒントがないと、エディタは「この引数に何を
渡せばいいか」「この戻り値からどんなメソッドが呼べるか」を推測するしかありません。
型ヒントがあれば、エディタはそれを手がかりに正確な補完やジャンプを出せますし、
関数を呼ぶ側もいちいち実装を読みに行かずにシグネチャだけで使い方を判断できます。
関数のシグネチャ自体が最小限のドキュメントになる、とイメージすると分かりやすいです。

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

`str | None` は「`str` か、値がないことを表す `None` のどちらか」という意味です。
これは以前からある `typing.Optional[str]` と**まったく同じ意味**で、書き方が違うだけです。
Python 3.10 で `X | Y` という合体型（union）の記法が言語に組み込まれ、
`from typing import Optional` を import しなくても素の記法で書けるようになりました。
このテキストは Python 3.12+ を前提にしているので、以降は基本的に `T | None` の
書き方で統一します。他人のコードやライブラリのドキュメントで `Optional[T]` を
見かけたときは、`T | None` と同じものだと読み替えてください。

コレクション型は組み込みの `list` / `dict` / `tuple` をそのまま使えます。

```python
def average(scores: list[float]) -> float:
    return sum(scores) / len(scores)

def index_by_name(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r["name"]: r for r in rows}
```

`list[float]` のように **中身の型まで指定** できるのがポイントです。
単に `list` とだけ書くと「リストであること」しかわかりませんが、`list[float]`
なら「`float` が並んだリスト」だと伝わるので、受け取った側も安心して要素を扱えます。

!!! warning "型ヒントは強制ではない"
    型ヒントを書いても Python は実行時にエラーを出しません。
    嘘の型を書いても動いてしまいます。
    `mypy` や `pyright`（VS Code の Pylance）と一緒に使って初めて意味が出ます。

## 1.3 dataclass

`dataclass` は **「データを持つだけのクラス」** を簡潔に書くための仕組みです
（[公式ドキュメント](https://docs.python.org/3/library/dataclasses.html)）。
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
`@dataclass` を付けなければ、この3つのメソッドは自分の手で書く必要があります。
`__init__` は各フィールドを `self.xxx = xxx` と代入していくだけの単純な繰り返し、
`__repr__` は `print()` したときに見やすい文字列を組み立てる処理、`__eq__` は
全フィールドを1つずつ比較する処理です。どれも定型的で、しかも「フィールドを
1つ追加したのに `__eq__` の比較を直し忘れる」といった事故が起きやすいコードなので、
`dataclass` に任せてしまうほうが安全です。

```python
t = Todo(id=1, title="牛乳を買う")
print(t)
# Todo(id=1, title='牛乳を買う', done=False, due_on=None)

t2 = Todo(id=1, title="牛乳を買う")
print(t == t2)  # True（中身が同じだから等しい）
```

`__eq__` を自分で定義しない普通のクラスでは、`t == t2` は「同じオブジェクトかどうか」
（メモリ上で同一かどうか）で判定されるため、フィールドの中身が同じでも `False` に
なってしまいます。`dataclass` が生成する `__eq__` はフィールドの値どうしを比較するので、
「中身が同じなら等しい」という直感的な挙動になります。

!!! tip "frozen=True で「変更できない」値にする"
    `@dataclass(frozen=True)` を使うと、属性の代入が禁止された **イミュータブル**
    なクラスになります。値オブジェクトを作るときに便利です。
    書き換えができないぶん「どこかで勝手に値が変わっていた」というバグを防げますし、
    デフォルトの `eq=True` と組み合わせれば辞書のキーや `set` の要素としても使えるようになります。

## やってみよう

次の `Todo` クラスを完成させて、`tests/test_todo.py` で 2 つ以上のテストを通してください。
（pytest の使い方は次章で扱います）

```python
# 仕様
# - 期限が「今日より前」なら is_overdue() が True を返す
# - done が True なら（期限が過ぎていても）is_overdue() は False
# - title が空文字なら ValueError を投げる
```

!!! note "なぜ ValueError を投げるのか"
    「不正な値が渡された」ことを呼び出し側に伝える方法はいろいろありますが、
    Python では組み込みの `ValueError` を使うのが慣習です。実際、`int("abc")`
    のような標準ライブラリの関数も、値としておかしい入力を受け取ると
    `ValueError` を投げます。この慣習に乗っておくと、呼び出し側は
    `except ValueError:` でピンポイントに失敗を捕まえられますし、他の開発者も
    コードを読んだだけで「ここで弾かれることがある」と予想できます（詳しくは
    [例外処理のチュートリアル](https://docs.python.org/3/tutorial/errors.html)）。
    独自の例外クラスを定義する選択肢もありますが、このテキストでは
    基本的に `ValueError` で統一します。

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

!!! tip "`__post_init__` とは"
    `dataclass` は `__init__` を自動生成してくれる一方で、「値を受け取ったら
    チェックしたい」というカスタムのロジックを挟む隙間がありません。
    そこで用意されているのが `__post_init__` で、自動生成された `__init__` が
    フィールドへの代入を終えた**直後に**自動で呼ばれるメソッドです。
    ここでバリデーションをしたり、他のフィールドから計算した値を追加で
    セットしたりします。

書けたら次の [第 2 章 Pythonおさらい② with・モジュール・pytest](02-python-context.md) に進みましょう。
