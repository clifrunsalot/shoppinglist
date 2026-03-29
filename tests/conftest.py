from pathlib import Path

import pytest

from app.db import db
from app.main import create_app


@pytest.fixture
def app(tmp_path: Path):
    test_app = create_app(
        {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'test.sqlite'}",
        }
    )

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()