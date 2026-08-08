# 第2章 Pythonのおさらい② with・モジュール・pytest

第1章に続いて、Python の準備運動です。
この章では「**実用コードでは毎日使うのに、入門書では後回しになりがち**」な 3 つを扱います。

- **with 文**: ファイルや DB 接続の「後始末」を自動でやってくれる構文
- **モジュール分割**: 1 つのファイルに全部書かず、役割ごとにファイルを分ける方法
- **pytest**: テストを自動化するための定番ツール

どれも「書いたことがない」前提で、**なぜ使うのか** から説明します。
この章でも、書くコードはすべてリポジトリルート直下の `practice/` ディレクトリに置いて進めてください。

## 2.1 この章でやること

この章が終わったときに、次のことができる状態を目指します。

- `with` 文を使って、ファイルを閉じ忘れないコードが書ける
- 処理を複数の Python ファイルに分割し、`import` でつないで実行できる
- pytest でテストを書き、`uv run --with pytest pytest` で実行して結果を読める
- テストが**失敗したときの出力**を見て、どこが期待と違ったか判断できる

**所要時間の目安: 60〜90 分**

## 2.2 前提知識: 「後始末」と「テストの自動化」

本章のテーマである with 文と pytest は、どちらも「やらなくても一応動くけれど、
やらないと後で痛い目に遭う」類の仕組みです。まず背景となる考え方を 2 つ押さえましょう。

!!! note "リソースと後始末"
    プログラムがファイルを開いたり DB に接続したりするとき、OS や DB サーバから
    **リソース**（資源）を借りています。リソースは無限ではありません。
    借りたまま返さない（= ファイルを閉じない、接続を切断しない）でいると、
    いずれ「これ以上ファイルを開けない」「これ以上接続できない」という状態になり、
    プログラム全体が動かなくなります。

    この「使い終わったら必ず返す」処理を **後始末** と呼びます。
    ファイルなら `close()`、DB 接続なら接続のクローズがそれにあたります。
    後始末は、処理の途中でエラーが起きたときも含めて **必ず** 必要です。
    これが難しいのは、「エラーが起きたとき用の後始末」を人間が書き忘れるからです。
    with 文は、この書き忘れを仕組みで防ぎます。

!!! note "テストの自動化とは"
    コードを書いたら「本当に期待どおり動くか」を確かめる必要があります。
    小さなプログラムなら、実行して目で見る手動確認でも間に合います。
    しかし実用コードでは、**機能を追加するたびに、以前動いていた部分まで全部
    手動で確認し直す**ことになり、すぐに破綻します。

    そこで、「こう入力したらこう返るはず」という期待を **コードとして** 書き残しておき、
    コマンドひとつで何度でも再実行できるようにします。これがテストの自動化です。
    テストがあれば、変更のたびに「前まで動いていたものが壊れていないか」を
    機械に確認させられるので、安心してコードを直し続けられます。

## 2.3 with 文: 後始末を自動化する

ファイルを開いて読むだけのコードでも、後始末（`close()`）が必要です。
まず「with を使わないやり方」と「with を使うやり方」を見比べます。

```python
# with を使わないやり方（閉じ忘れの危険がある）
f = open("practice/notes.txt")
data = f.read()
f.close()

# with を使うやり方
with open("practice/notes.txt") as f:
    data = f.read()
# ← ブロックを抜けた時点で、自動的に f.close() が呼ばれる
```

`with ... as f:` のブロックを抜けると、Python が自動で `f.close()` を呼んでくれます。
大事なのは、**ブロックの途中で例外が起きても、後始末だけは必ず実行される**ことです。
「使わないやり方」では、`f.read()` の行で例外が起きると `f.close()` にたどり着けず、
ファイルが開いたまま残ってしまいます。

実際に動かしてみましょう。まず読む対象のファイル `practice/notes.txt` を作ります。

```text
牛乳を買う
健康診断の予約
領収書の整理
```

次に `practice/with_file.py` を作って、次を写してください。

```python
with open("practice/notes.txt") as f:
    for line in f:
        print(line.strip())

print(f.closed)
```

最後の `print(f.closed)` は、「ブロックを抜けたあと、本当にファイルが閉じているか」を
確かめるための確認コードです。`closed` はファイルが閉じていれば `True` になる属性です。

リポジトリのルートで実行します。

```bash
uv run python practice/with_file.py
```

期待される出力:

```text
牛乳を買う
健康診断の予約
領収書の整理
True
```

最後の行が `True` なので、with ブロックを抜けた時点でファイルが閉じられたことが
確認できました。`close()` をどこにも書いていないのに、です。

!!! note "open のパスは「どこから実行するか」が基準"
    `open("practice/notes.txt")` のパスは、**コマンドを実行した場所**（今なら
    リポジトリのルート）からの相対パスとして解釈されます。
    `practice/` の中に `cd` してから実行すると、今度は `practice/practice/notes.txt`
    を探しに行って `FileNotFoundError` になります。この研修では、実行は常に
    リポジトリのルートで行う、と決めて進めます。

`with` の後ろに置けるものを **コンテキストマネージャ** と呼びます。
「ブロックに入るときの処理」と「ブロックを抜けるときの処理」をセットで持つ仕組みで、
ファイル以外にも DB 接続・ロックなど「後始末が必要なもの」が軒並み対応しています。
この研修でも、第5章以降で扱う psycopg（PostgreSQL ドライバ）の接続は
`with` で書くのが基本形です。

```python
# 第5章で詳しく扱います。今は雰囲気だけ
with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
# ブロックを抜けると、カーソルも接続も自動で閉じる
```

このように `with` は入れ子にもでき、内側で例外が起きても内側・外側どちらの
後始末も正しく実行されます。

## 2.4 モジュール分割: 複数ファイルで書く

1 つのファイルに全部書いていくと、すぐに数百〜数千行になって
「どこに何が書いてあるか分からない」状態になります。
実用コードでは、**役割ごとにファイルを分け**、必要なものを `import` で
読み込んで組み合わせます。この「分けた Python ファイル 1 つ 1 つ」を
**モジュール** と呼びます。

試しに、計算用の関数を別ファイルに切り出してみましょう。
`practice/calc.py` を作ります。

```python
def add(a: int, b: int) -> int:
    return a + b


def div(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("0 で割ることはできません")
    return a / b
```

`div` で `raise ValueError(...)` としているのは、「不正な値が渡された」ことを
呼び出し側に伝えるためです（第1章の `__post_init__` でも同じことをしましたね）。
この関数は、あとで pytest の練習でも使います。

次に、それを使う側の `practice/use_calc.py` を作ります。

```python
from calc import add, div

print(add(2, 3))
print(div(10, 4))
```

`from calc import add, div` は、「`calc.py`（拡張子を除いて `calc`）という
モジュールから、`add` と `div` を持ってくる」という意味です。
ポイントは、**import する側とされる側を同じディレクトリに置く**ことです。
Python は、実行したファイルと同じフォルダの中から `calc.py` を探します。

```bash
uv run python practice/use_calc.py
```

期待される出力:

```text
5
2.5
```

ファイルが 2 つに分かれましたが、使う側は `import` するだけで何も変わりません。
「計算は `calc.py`、実行の入口は `use_calc.py`」という役割分担ができました。

!!! note "分割すると何がうれしいのか"
    - **探しやすい**: 「計算ロジックを直したい」とき、開くファイルがすぐ決まる
    - **テストしやすい**: 2.5 でやるように、関数単位でテストを書ける
    - **再利用できる**: 別のプログラムからも `import` して使い回せる

ファイルがさらに増えてきたら、フォルダを分けて **パッケージ**（モジュールを
まとめたフォルダ）にします。第10章で作る ToDo アプリ `mytodo/` も
このパッケージ構成になります。ここでは「ファイルを分けて `import` でつなぐ」
という基本が分かれば十分です。

## 2.5 pytest: テストを自動化する

### テストファイルを書く

2.4 で作った `add` と `div` が「本当に正しく動くか」を、コードで確認してみましょう。
このテキストではテストツールに [pytest](https://docs.pytest.org/en/stable/) を使います。

pytest は **命名規則に従ったファイルと関数を自動で見つけて実行**してくれます。
覚えるのは 2 つだけです。

- ファイル名は `test_` で始める（例: `test_calc.py`）
- テストの関数名も `test_` で始める（例: `test_add`）

`practice/test_calc.py` を作って、次を写してください。

```python
import pytest

from calc import add, div


def test_add():
    assert add(2, 3) == 5


def test_div():
    assert div(10, 4) == 2.5


def test_div_zero():
    with pytest.raises(ValueError):
        div(1, 0)
```

見どころは 3 つあります。

- **`assert 式`** は、式が `False` になった時点でテスト失敗を知らせる、
  Python 標準の仕組みです。pytest はこの `assert` をそのまま使うだけでよく、
  専用の比較メソッドを覚える必要がありません
- **テストファイルはテスト対象と同じディレクトリ**に置きます。
  `practice/` に置くので、`from calc import ...` がそのまま通ります
- **`pytest.raises(ValueError)`** は、「`with` ブロックの中で本当に
  その例外が投げられること」を確認するための仕組みです（中身はまさに
  コンテキストマネージャです）。例外が投げられなかったり、別の種類の例外が
  投げられたりした場合は、テストのほうが失敗します

### 実行する

このリポジトリの環境には pytest は入っていないので、**実行のたびに一時的に
用意する**形で動かします。

```bash
uv run --with pytest pytest practice/test_calc.py
```

期待される出力:

```text
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/mizushima/repo/webapp-training
configfile: pyproject.toml
collected 3 items

practice/test_calc.py ...                                                [100%]

============================== 3 passed in 0.01s ===============================
```

末尾の **`3 passed`** が「3 個のテストがすべて成功した」ことを表します。
`...` の 1 個 1 個がテスト 1 件に対応しています（`-v` オプションを付けると、
各テストの名前と結果が 1 行ずつ表示されます）。

!!! note "uv run --with pytest とは"
    `--with pytest` は「この実行の間だけ、pytest を環境に追加してから動かす」
    という uv の機能です。プロジェクトの `pyproject.toml` を書き換えずに済むので、
    練習用にちょうどよい形です。
    なお、第12章で ToDo アプリ本体にテストを書くときは、開発用の依存として
    プロジェクトに登録する方法（`uv add --group dev pytest`）を使います。

### 失敗の出方を見る

テストは **失敗したときのほうが情報量が多い** ので、わざと失敗させてみます。
`test_add` の期待値を間違えて `6` に書き換えてください。

```python
def test_add():
    assert add(2, 3) == 6  # わざと間違えた
```

```bash
uv run --with pytest pytest practice/test_calc.py
```

期待される出力（抜粋）:

```text
practice/test_calc.py F..                                                [100%]

=================================== FAILURES ===================================
___________________________________ test_add ___________________________________

    def test_add():
>       assert add(2, 3) == 6
E       assert 5 == 6
E        +  where 5 = add(2, 3)

practice/test_calc.py:7: AssertionError
=========================== short test summary info ============================
FAILED practice/test_calc.py::test_add - assert 5 == 6
========================= 1 failed, 2 passed in 0.02s ==========================
```

読み方:

- `F..` は「1 件目が失敗（Fail）、残り 2 件は成功」
- `E       assert 5 == 6` で、「実際には `5` だったのに `6` と期待していた」
  と、**比較した値の中身まで**教えてくれます。pytest の `assert` だけで
  十分な理由がこれです
- 最終行の `1 failed, 2 passed` がサマリです

確認できたら、期待値を `5` に戻して `3 passed` に直しておきましょう。
この「壊して→直して緑に戻す」流れを自分の手で一度やっておくと、
本番でテストが赤くなったときに慌てずに済みます。

!!! tip "fixture（前準備）の考え方"
    複数のテストで共通の前準備（DB 接続など）が必要なときは `@pytest.fixture`
    を使います。第12章でしっかり扱うので、ここでは「そういうのがある」ことだけ
    覚えておけば十分です。

## 2.6 チェックポイント

ここまでの内容が身についているか、自分で確認しましょう。

- [ ] `with open(...)` でファイルを読み、ブロックを抜けたあと `closed` が `True` になることを確認した
- [ ] 後始末が必要な処理で、なぜ手で `close()` を書くより `with` が安全なのか説明できる
- [ ] 関数を別ファイル（モジュール）に切り出して、`import` して実行できた
- [ ] `test_*.py` に `test_*` 関数を書いて、`uv run --with pytest pytest` で `3 passed` を確認した
- [ ] わざと失敗させて、`E assert 5 == 6` のような差分表示を読めた

## 2.7 つまずきポイント

### `uv run pytest` で実行できない（または変な pytest が動く）

このリポジトリの `pyproject.toml` には pytest が登録されていません。
そのため `--with` なしで `uv run pytest ...` とすると、環境によっては
「コマンドが見つからない」エラーになったり、プロジェクトとは無関係の
pytest が拾われて動いてしまったりします。
本章のとおり、**`uv run --with pytest pytest` の形で実行する**のが確実です。

### `collected 0 items` と言われる

```text
collected 0 items

============================ no tests ran in 0.00s =============================
```

テストが 1 件も見つかっていません。命名規則を確認してください。

- ファイル名が `test_calc.py` ではなく `check_calc.py` や `calc_test.py` になっていないか
- 関数名が `test_add` ではなく `check_add` など `test_` で始まっていないか

pytest が自動で探すのは、**`test_` で始まるファイルの中の、`test_` で始まる関数**
だけです。

### `ModuleNotFoundError: No module named 'calc'`

```text
    from calc import add, div
E   ModuleNotFoundError: No module named 'calc'
```

`import` したいモジュール（`calc.py`）が、テストファイル（`test_calc.py`）と
同じディレクトリにありません。pytest は「テストファイルのあるフォルダ」から
import を探すので、`calc.py` と `test_calc.py` は**両方とも `practice/` に
置く**ようにしてください。

### `ValueError: I/O operation on closed file`

```python
with open("practice/notes.txt") as f:
    pass

print(f.read())  # ← ブロックの外
```

```text
ValueError: I/O operation on closed file.
```

with ブロックを抜けたあとに、閉じられたファイルを操作しようとしています。
読み書きは**必ず with ブロックの内側**（インデント 1 段深い側）で済ませるか、
2.3 の例のようにブロックの中で `data = f.read()` と変数に取り出してから
ブロックを抜けてください。

## 2.8 やってみよう

解答例は折りたたんであるので、まずは自分で書いてから見比べてください。
すべて `practice/` にファイルを作り、実行はリポジトリのルートで行います。

### 問1 with 文で書き込み・読み込み

次の仕様のプログラムを `practice/q1.py` に書いて、実行してください。

- 「牛乳を買う」「健康診断の予約」「領収書の整理」の 3 行を、
  `with` を使って `practice/q1_memo.txt` に書き込む（開くモードは `"w"`）
- 続けて別の `with` ブロックで読み込み、内容を `print` する
- 最後に、読み込み側のファイルが閉じていること（`closed` が `True`）を
  `print` して確かめる

??? example "解答例"

    ```python
    lines = ["牛乳を買う", "健康診断の予約", "領収書の整理"]

    with open("practice/q1_memo.txt", "w") as f:
        for line in lines:
            f.write(line + "\n")

    with open("practice/q1_memo.txt") as f:
        content = f.read()

    print(content, end="")
    print(f.closed)
    ```

    ```bash
    uv run python practice/q1.py
    ```

    期待される出力:

    ```text
    牛乳を買う
    健康診断の予約
    領収書の整理
    True
    ```

    `f.write(...)` では改行が自動で付かないので、行ごとに `"\n"` を足しています。
    2 つ目の `with` で読み込み側のファイルを開き直しており、
    `content = f.read()` で中身を変数に取り出してからブロックを抜けているので、
    抜けたあとも `print` できています。最後の `True` は、読み込み側の `f` が
    ブロックを抜けた時点で閉じられた印です。

### 問2 モジュールに分割する

文字列を加工する関数群を `practice/q2_textutil.py`、
それを使うプログラムを `practice/q2_main.py` に分けて書き、
`q2_main.py` を実行してください。

- `q2_textutil.py` に作る関数:
    - `count_chars(text)`: 文字数を返す
    - `shout(text)`: 大文字にして末尾に `!` を付けて返す
    - `first_char(text)`: 先頭の 1 文字を返す。空文字なら `ValueError` を投げる
- `q2_main.py` では 3 つの関数を `import` し、`"hello"` に対する結果を
  それぞれ `print` する

??? example "解答例"

    `practice/q2_textutil.py`:

    ```python
    def count_chars(text: str) -> int:
        return len(text)


    def shout(text: str) -> str:
        return text.upper() + "!"


    def first_char(text: str) -> str:
        if text == "":
            raise ValueError("空文字には先頭の文字がありません")
        return text[0]
    ```

    `practice/q2_main.py`:

    ```python
    from q2_textutil import count_chars, first_char, shout

    print(count_chars("hello"))
    print(shout("hello"))
    print(first_char("hello"))
    ```

    ```bash
    uv run python practice/q2_main.py
    ```

    期待される出力:

    ```text
    5
    HELLO!
    h
    ```

    「関数を置くファイル」と「実行の入口」が分かれました。
    実行するのはあくまで `q2_main.py` のほうで、`q2_textutil.py` は
    `import` されるだけ（直接実行しない）という関係に注意してください。

### 問3 問2の関数にテストを書く

問2で作った 3 つの関数に対して、次の 4 件のテストを
`practice/test_textutil.py` に書いて、pytest で実行してください。

- `count_chars("hello")` が `5` を返す
- `shout("hello")` が `"HELLO!"` を返す
- `first_char("hello")` が `"h"` を返す
- `first_char("")` が `ValueError` を投げる（`pytest.raises` を使う）

??? example "解答例"

    ```python
    import pytest

    from q2_textutil import count_chars, first_char, shout


    def test_count_chars():
        assert count_chars("hello") == 5


    def test_shout():
        assert shout("hello") == "HELLO!"


    def test_first_char():
        assert first_char("hello") == "h"


    def test_first_char_empty():
        with pytest.raises(ValueError):
            first_char("")
    ```

    ```bash
    uv run --with pytest pytest practice/test_textutil.py
    ```

    期待される出力:

    ```text
    practice/test_textutil.py ....                                           [100%]

    ============================== 4 passed in 0.01s ===============================
    ```

    `....` が 4 件分の成功です。
    例外のテストは「投げられること自体が正しい動作」なので、
    `pytest.raises` のブロック内で呼び出す形になる点だけが通常のテストと
    違います。
    試しに `first_char` の `raise` の行を消して実行してみてください。
    `test_first_char_empty` が失敗し、「例外が投げられなかった」ことを
    pytest が教えてくれます。

## まとめ

- **with 文**は「後始末つきのブロック」。ファイルや DB 接続を使ったら、
  例外が起きても必ず閉じられる。`close()` の書き忘れを仕組みで防げる
- **モジュール分割**は、役割ごとにファイルを分けて `import` でつなぐこと。
  テストしたい関数を別ファイルに切り出しておくと、テストが書きやすくなる
- **pytest** は `test_*.py` の `test_*` 関数を自動で見つけて実行する。
  実行は `uv run --with pytest pytest practice/xxx.py`。結果は末尾の
  `N passed` / `N failed` で読む
- テストが失敗したときは、`assert 実際 == 期待` の差分表示を見て
  どこが食い違ったかを判断する。`pytest.raises` で「例外が投げられること」も
  テストできる

次は [第3章 PostgreSQLのおさらい① DDL/DML/SELECT](03-postgres-ddl-dml.md) で、
DB 側のおさらいに入ります。
