from datetime import date

from app import repositories as repo


def test_create_and_get(conn):
    todo = repo.create_todo(conn, title="テスト用", priority=1)
    assert todo.id > 0
    fetched = repo.get_todo(conn, todo.id)
    assert fetched is not None
    assert fetched.title == "テスト用"
    assert fetched.priority == 1
    assert fetched.done is False


def test_filter_open_done(conn):
    a = repo.create_todo(conn, title="やること")
    b = repo.create_todo(conn, title="完了済")
    repo.toggle_done(conn, b.id)

    open_ids = {t.id for t in repo.list_todos(conn, filter_="open")}
    done_ids = {t.id for t in repo.list_todos(conn, filter_="done")}

    assert a.id in open_ids
    assert b.id in done_ids
    assert a.id not in done_ids


def test_search_with_q(conn):
    repo.create_todo(conn, title="ミーティングの議事録")
    repo.create_todo(conn, title="家賃を振り込む")
    found = repo.list_todos(conn, q="議事")
    titles = [t.title for t in found]
    assert "ミーティングの議事録" in titles
    assert "家賃を振り込む" not in titles


def test_update_can_clear_due_on(conn):
    t = repo.create_todo(conn, title="期限あり", due_on=date(2026, 5, 30))
    updated = repo.update_todo(conn, t.id, due_on=None)
    assert updated is not None
    assert updated.due_on is None


def test_update_partial_keeps_other_fields(conn):
    t = repo.create_todo(conn, title="部分更新", priority=2, due_on=date(2026, 6, 1))
    updated = repo.update_todo(conn, t.id, title="変更後")
    assert updated is not None
    assert updated.title == "変更後"
    assert updated.priority == 2
    assert updated.due_on == date(2026, 6, 1)


def test_tags_attach_and_list(conn):
    t = repo.create_todo(conn, title="ジム", tag_names=["健康", "週次"])
    fetched = repo.get_todo(conn, t.id)
    assert fetched is not None
    names = sorted(g.name for g in fetched.tags)
    assert names == ["健康", "週次"]


def test_replace_tags_overrides_existing(conn):
    t = repo.create_todo(conn, title="タグ差し替え", tag_names=["A", "B"])
    repo.replace_tags(conn, t.id, ["C"])
    fetched = repo.get_todo(conn, t.id)
    assert fetched is not None
    assert [g.name for g in fetched.tags] == ["C"]


def test_delete_cascades_tags(conn):
    t = repo.create_todo(conn, title="削除予定", tag_names=["仕事"])
    assert repo.delete_todo(conn, t.id) is True
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM todo_tags WHERE todo_id = %s", (t.id,))
        assert cur.fetchone()["n"] == 0


def test_get_unknown_returns_none(conn):
    assert repo.get_todo(conn, 9999999) is None


def test_toggle_unknown_returns_none(conn):
    assert repo.toggle_done(conn, 9999999) is None
