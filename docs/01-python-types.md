# 第1章 Pythonのおさらい① 型ヒントとdataclass

第0章で環境が整ったので、ここから Python の準備運動です。
この章と次章では、入門書にはあまり載っていないけれど**実用コードでは当たり前に使われる**
2 つの仕組み —— **型ヒント** と **dataclass** —— を扱います。

どちらも「書いたことがない」前提で、**なぜ使うのか** から説明します。
この章で書くコードはすべて練習用です。リポジトリのルートに `practice/` ディレクトリを
作り、その中にファイルを置いて進めてください。

## 1.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- 関数に型ヒントを付けて書ける
- `list[float]` や `str | None` といった表記の意味がわかる
- `@dataclass` で「データを持つだけのクラス」を作れる
- 型ヒントが実行時にはチェック**されない**ことを理解している

**所要時間の目安: 45〜60 分**

## 1.2 前提知識: 実用コードではなぜ型を書くのか

Python には、変数や引数の「型」を宣言しなくても動く、という特徴があります。
入門書の段階ではそれで十分ですが、実用コード（数百行を超える、他人と共有するコード）では、
型を書くことが事実上の標準になっています。まずその背景を押さえましょう。

!!! note "動的型付けとは"
    Python は**動的型付け**の言語です。変数の型は実行してみるまで確定せず、
    同じ変数に `int` を入れたあと `str` を入れ直してもエラーになりません。

    柔軟で書きやすい反面、「この関数の引数には何を渡せばいいのか」が
    **コードを読むだけではわからない**という弱点があります。
    関数の中身を読んで初めて「ああ、ここでは `int` を想定しているのか」とわかるわけです。

!!! note "型ヒントとは"
    **型ヒント**（type hints）は、「この引数は `int`」「この戻り値は `str`」という
    **注釈**をコードに書き添える仕組みです（[PEP 484](https://peps.python.org/pep-0484/) で導入されました）。

    重要なのは、**Python 本体は型ヒントを実行時にチェックしない**ことです。
    嘘の型を書いてもプログラムは普通に動きます。あくまで「人とツールのための注釈」です。

!!! note "静的チェックとは"
    型ヒントだけではただのコメントですが、**静的解析ツール**と組み合わせると威力を発揮します。
    静的解析とは、プログラムを**実行せずに**コードを解析して問題を見つけることです。

    第0章でエディタに入れた **Pylance**（VS Code / Cursor の拡張機能）がその代表で、
    「`int` を渡すはずの引数に `str` を渡している」といった矛盾を、
    書いている最中に赤い波線で教えてくれます。コマンドラインで動かす `mypy` や
    `pyright` も同じ役割のツールです。

実用コードで型を書く理由は、ひとことでいえば **「読み手（未来の自分を含む）とツールに、
コードの意図を伝えるため」** です。具体的には次のような効果があります。

- **補完が効く**: エディタが型を手がかりに、使えるメソッドや属性を正確に候補として出せる
- **シグネチャがドキュメントになる**: 関数の中身を読まなくても、何を渡して何が返るかがわかる
- **バグを実行前に見つけられる**: 静的解析が型の食い違いを指摘してくれる
- **ツールが型を解釈してくれる**: 第13章で使う FastAPI は、型ヒントを読んで
  リクエストの検証や API ドキュメントの生成を自動でやってくれます（型ヒントが
  「ただの注釈」ではなくフレームワークへの入力になる例です）

「動かせばわかる」と思うかもしれませんが、Web アプリのように
「動かすまでの準備が重い」プログラムでは、**書いた瞬間に教えてもらえる**のと
**動かして初めて気づく**のとでは、開発速度がまったく違います。
この研修でも以降のすべてのコードに型ヒントを付けていきます。

## 1.3 型ヒントの基本

まずは書き方を見ます。`practice/types_basic.py` を作って、次を写してください。

```python
def add(a: int, b: int) -> int:
    return a + b


def greet(name: str) -> None:
    print(f"hello, {name}")


print(add(2, 3))
greet("alice")
```

引数名の後ろの `: int` が「この引数は `int`」、
`-> int` が「この関数は `int` を返す」という注釈です。
`greet` の `-> None` は「返り値がない（`return` で値を返さない）」ことを表します。

実行してみましょう。リポジトリのルートで次を打ちます。

```bash
uv run python practice/types_basic.py
```

期待される出力:

```text
5
hello, alice
```

型ヒントを付けても、**実行結果は何も変わりません**。あくまで注釈だからです。

では、注釈に嘘をつくとどうなるでしょうか。`practice/types_lie.py` を作って試します。

```python
def add(a: int, b: int) -> int:
    return a + b


print(add("2", "3"))  # int を渡すはずの引数に str を渡している
```

```bash
uv run python practice/types_lie.py
```

期待される出力:

```text
23
```

エラーにはなりません。`"2" + "3"` は文字列の連結として普通に実行され、`23` が表示されます。
`-> int` と書いたのに `str` が返ってきていますが、Python は何も文句を言いません。

!!! warning "型ヒントは強制ではない"
    上の例のとおり、型ヒントを書いても Python は実行時にエラーを出しません。
    型ヒントを「安全装置」として機能させるには、Pylance のような静的解析ツールが必要です。
    エディタでこのファイルを開くと、`add("2", "3")` の行に波線が付くはずです。
    それが静的チェックです。

## 1.4 よく使う型ヒント

実用コードで頻繁に使う表記を 3 つ紹介します。
`practice/types_collections.py` を作って写してください。

```python
def average(scores: list[float]) -> float:
    return sum(scores) / len(scores)


def find_user(user_id: int) -> str | None:
    if user_id == 1:
        return "alice"
    return None


print(average([80.0, 90.0, 100.0]))
print(find_user(1))
print(find_user(999))
```

```bash
uv run python practice/types_collections.py
```

期待される出力:

```text
90.0
alice
None
```

ひとつずつ見ます。

- **`list[float]`**: 「`float` が並んだリスト」。`list` とだけ書くと
  「リストであること」しか伝わりませんが、中身の型まで指定できるのがポイントです。
  `dict[str, int]`（キーが `str`、値が `int` の辞書）なども同じ要領です
- **`str | None`**: 「`str` か、値がないことを表す `None` のどちらか」。
  `find_user` のように「見つからなければ `None` を返す」関数で必須の表現です。
  以前は `typing.Optional[str]` と書くしかありませんでしたが、Python 3.10 から
  この `|` の記法が使えるようになりました。このテキストは Python 3.12+ を前提に
  しているので、以降は `T | None` の書き方で統一します。他人のコードで
  `Optional[T]` を見かけたら、同じ意味だと読み替えてください
- **戻り値が `str | None` の関数を使う側**: `find_user(1)` の戻り値に対して
  いきなり `.upper()` などを呼ぶと、Pylance が「`None` かもしれないのに危ない」と
  警告してくれます。こういう指摘こそ、型ヒントを書く最大の見返りです

## 1.5 dataclass

次は **dataclass** です。これは **「データを持つだけのクラス」を簡潔に書くための仕組み**
（[公式ドキュメント](https://docs.python.org/3/library/dataclasses.html)）で、
型ヒントとセットで使われます。

この研修で作る ToDo アプリでは、「1 件の ToDo」を Python のオブジェクトとして
DB との間でやり取りします。その受け皿にするのが dataclass です。
`practice/todo_dataclass.py` を作って写してください。

```python
from dataclasses import dataclass
from datetime import date


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    due_on: date | None = None


t = Todo(id=1, title="牛乳を買う", due_on=date(2026, 8, 10))
print(t)

t2 = Todo(id=1, title="牛乳を買う", due_on=date(2026, 8, 10))
print(t == t2)

t.done = True
print(t)
```

```bash
uv run python practice/todo_dataclass.py
```

期待される出力:

```text
Todo(id=1, title='牛乳を買う', done=False, due_on=datetime.date(2026, 8, 10))
True
Todo(id=1, title='牛乳を買う', done=True, due_on=datetime.date(2026, 8, 10))
```

見どころは 3 つあります。

- **クラスの中身がフィールドの列挙だけ** で済んでいる。`done = False` のように
  書いたものは「省略したときのデフォルト値」です
- **`print` で中身が読める**。`Todo(id=1, title='牛乳を買う', ...)` と
  全部のフィールドが表示されました
- **`==` が中身どうしの比較になる**。`t` と `t2` は別々に作ったオブジェクトですが、
  フィールドの値が同じなので `True` になりました

`@dataclass` を付けると、`__init__`（初期化）、`__repr__`（`print` 用の文字列化）、
`__eq__`（`==` の比較）という 3 つのメソッドが**自動生成**されるのが理由です。
`@dataclass` なしで同じことをしようとすると、この 3 つを自分で書く必要があります。
`__init__` は各フィールドを `self.xxx = xxx` と代入していくだけの単純な繰り返し、
`__eq__` は全フィールドを 1 つずつ比較する処理です。どれも定型的で、しかも
「フィールドを 1 つ追加したのに `__eq__` の比較を直し忘れる」といった事故が
起きやすいコードなので、自動生成に任せるほうが安全です。

!!! tip "なぜ「中身が同じなら等しい」が特別なのか"
    `__eq__` を自分で定義しない普通のクラスでは、`==` は「メモリ上で同一の
    オブジェクトかどうか」で判定されます。その場合、フィールドの中身が同じでも
    別々に作れば `False` になってしまいます。dataclass が生成する `__eq__` は
    フィールドの値どうしを比較するので、「中身が同じなら等しい」という
    直感的な挙動になります。

!!! tip "frozen=True で「変更できない」値にする"
    `@dataclass(frozen=True)` と書くと、作成後のフィールドへの代入が禁止された
    **イミュータブル**（変更不可）なクラスになります。
    「どこかで勝手に値が書き換わっていた」というバグを防げるので、
    金額や日付のような「値」を表すクラスに向いています。

## 1.6 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] 型ヒントつきの関数を書いて、`uv run python` で実行できた
- [ ] 型ヒントに嘘をついてもエラーにならないことを、自分のコードで確認した
- [ ] `list[float]`・`str | None` の意味を説明できる
- [ ] `@dataclass` でクラスを作り、`print` と `==` の結果を確認できた
- [ ] エディタで型の矛盾（`int` の引数に `str` を渡す等）に波線が付くことを確認した

## 1.7 つまずきポイント

### 「型ヒントを付けたのにエラーが出ない」は正常です

1.3 で試したとおり、`add("2", "3")` はエラーにならず `23` が返ります。
型ヒントは実行時にチェックされないので、**実行で確かめても型の間違いは見つかりません**。
エディタの波線（Pylance）や、`mypy` / `pyright` などの静的解析ツールで確認するもの、
と理解しておきましょう。

### `@dataclass` を付け忘れた

`@dataclass` を付け忘れると、`__init__` が自動生成されないため、
インスタンスを作った時点で次のエラーになります。

```text
TypeError: Todo() takes no arguments
```

「クラスを定義したのに引数を渡せない」と言われたら、まず `@dataclass` の有無を
確認してください。同様に、`from dataclasses import dataclass` を忘れると
`NameError: name 'dataclass' is not defined` になります。

### デフォルト値に `[]` を書くとエラーになる

リストを持つフィールドに、次のようにデフォルト値 `[]` を書くとエラーになります。

```python
@dataclass
class Box:
    items: list[str] = []  # これはダメ
```

```text
ValueError: mutable default <class 'list'> for field items is not allowed: use default_factory
```

`[]` のようなミュータブル（変更可能）な値をデフォルトにすると、
**全インスタンスで同じリストを共有してしまう**事故が起きるため、
dataclass 側で禁止されています。メッセージの指示どおり `field(default_factory=list)`
を使うのが正解です。「インスタンスを作るたびに新しい `list()` を作って初期値にする」
という意味になります。

```python
from dataclasses import dataclass, field


@dataclass
class Box:
    items: list[str] = field(default_factory=list)
```

## 1.8 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。

### 問1 型ヒントを付ける

次の仕様の関数 `repeat` を書いて、`practice/q1.py` に保存し、実行してください。

- 引数: `text`（文字列）、`times`（整数）
- 戻り値: `text` を `times` 回繰り返した文字列
- `repeat("ab", 3)` の結果を `print` する

??? example "解答例"

    ```python
    def repeat(text: str, times: int) -> str:
        return text * times


    print(repeat("ab", 3))
    ```

    ```bash
    uv run python practice/q1.py
    ```

    期待される出力:

    ```text
    ababab
    ```

    文字列は `*` で繰り返せます（文法の復習ではなく、型ヒントの付け方が本題です）。
    試しに `repeat(3, "ab")` のように引数を逆にして実行してみてください。
    今度は `3 * "ab"`（整数 × 文字列）として解釈され、エラーにならず
    同じ `ababab` が返ってきます。型を間違えているのに結果まで正しく見える、
    という最もたちの悪いパターンです。エディタでは波線が付きます。

### 問2 dataclass を作る

次の仕様の `Member` クラスを dataclass で作り、`practice/q2.py` に保存して実行してください。

- フィールド: `name`（`str`）、`age`（`int`）、`email`（`str | None`、デフォルト `None`）
- 「`name="alice"`, `age=30`, `email="alice@example.com"`」のインスタンスを 2 つ作り、
  `==` で比較して `print` する
- さらに `email` を省略した別のインスタンスを作って `print` する

??? example "解答例"

    ```python
    from dataclasses import dataclass


    @dataclass
    class Member:
        name: str
        age: int
        email: str | None = None


    m1 = Member(name="alice", age=30, email="alice@example.com")
    m2 = Member(name="alice", age=30, email="alice@example.com")
    m3 = Member(name="bob", age=25)

    print(m1)
    print(m1 == m2)
    print(m1 == m3)
    ```

    ```bash
    uv run python practice/q2.py
    ```

    期待される出力:

    ```text
    Member(name='alice', age=30, email='alice@example.com')
    True
    False
    ```

    `m1 == m2` が `True` になるのは、dataclass が生成する `__eq__` が
    フィールドの値どうしを比較してくれるからでしたね。

### 問3 メソッドを持つ dataclass

1.5 の `Todo` に次の 2 つを追加して、`practice/q3.py` に保存して実行してください。

- フィールドのチェック: `title` が空文字なら `ValueError` を投げる
- メソッド `is_overdue(today)`: 「期限切れか」を判定する
    - `done` が `True` なら（期限が過ぎていても）`False`
    - `due_on` が `None` なら `False`
    - `due_on` が `today` より前なら `True`

??? example "解答例"

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
            if self.title == "":
                raise ValueError("title は空にできません")

        def is_overdue(self, today: date) -> bool:
            if self.done or self.due_on is None:
                return False
            return self.due_on < today


    today = date(2026, 8, 8)
    t1 = Todo(id=1, title="牛乳を買う", due_on=date(2026, 8, 1))
    t2 = Todo(id=2, title="健康診断の予約", done=True, due_on=date(2026, 8, 1))
    t3 = Todo(id=3, title="領収書の整理")

    print(t1.is_overdue(today))  # 期限切れ → True
    print(t2.is_overdue(today))  # 完了済み → False
    print(t3.is_overdue(today))  # 期限なし → False

    try:
        Todo(id=4, title="")
    except ValueError as e:
        print(f"ValueError: {e}")
    ```

    ```bash
    uv run python practice/q3.py
    ```

    期待される出力:

    ```text
    True
    False
    False
    ValueError: title は空にできません
    ```

    `__post_init__` は、dataclass が自動生成する `__init__` がフィールドへの代入を
    終えた**直後に自動で呼ばれる**メソッドです。ここにバリデーション（値の検査）を
    書いておくと、「`title` が空の ToDo」という不正なオブジェクトが
    そもそも作れなくなります。

    !!! note "なぜ ValueError を投げるのか"
        「不正な値が渡された」ことを伝えるには、Python では組み込みの `ValueError`
        を使うのが慣習です。実際、`int("abc")` のような標準の変換関数も、値として
        おかしい入力には `ValueError` を投げます。この慣習に乗っておくと、
        呼び出し側は `except ValueError:` でピンポイントに失敗を捕まえられます。

## まとめ

- **型ヒント**は「人とツールのための注釈」。実行時にはチェックされないが、
  エディタの補完と静的解析（Pylance など）が劇的に良くなる
- `-> int` が戻り値、`: int` が引数の型。`list[float]` や `str | None` で
  中身や「値がないかもしれない」ことまで表現できる
- **dataclass** は「データを持つだけのクラス」を書く仕組み。
  `@dataclass` を付けるだけで `__init__`・`__repr__`・`__eq__` が自動生成される
- dataclass のデフォルト値に `[]` は書けない。`field(default_factory=list)` を使う
- 型ヒントと dataclass は、このあと DB の行を受け取る型（第5章以降）や
  FastAPI のリクエスト/レスポンスの型（第13章）でそのまま使います

次は [第2章 Pythonのおさらい② with・モジュール・pytest](02-python-context.md) で、
ファイルの後始末を任せる `with` 文、コードのファイル分割、テスト自動化の pytest を扱います。
