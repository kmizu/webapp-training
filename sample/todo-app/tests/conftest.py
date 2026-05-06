import psycopg
import pytest
from psycopg.rows import dict_row

from app.config import settings


@pytest.fixture
def conn():
    """各テストごとに独立した接続を渡す。テスト後にロールバック。"""
    with psycopg.connect(settings.dsn, row_factory=dict_row, autocommit=False) as c:
        try:
            yield c
        finally:
            c.rollback()
