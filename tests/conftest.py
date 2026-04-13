from threading import Thread
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app.db import db
from app.main import create_app
from app.models import DefaultCategoryTemplate, DefaultItemTemplate, DefaultStoreTemplate, User


@pytest.fixture
def app(tmp_path: Path):
    test_app = create_app(
        {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'test.sqlite'}",
        }
    )

    with test_app.app_context():
        db.create_all()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def create_user(app):
    def _create_user(email, password='password123!', *, admin=False, approved=True, active=True, theme_preference=None):
        with app.app_context():
            user = User(
                email=email.strip().lower(),
                is_admin=admin,
                is_approved=approved,
                is_active=active,
                theme_preference=theme_preference,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return {
                'id': user.id,
                'email': user.email,
                'password': password,
                'is_admin': user.is_admin,
                'is_approved': user.is_approved,
                'is_active': user.is_active,
            }

    return _create_user


@pytest.fixture
def login(client):
    def _login(email, password, *, follow_redirects=False):
        return client.post(
            '/login',
            data={
                'email': email,
                'password': password,
            },
            follow_redirects=follow_redirects,
        )

    return _login


@pytest.fixture
def auth_user(create_user):
    return create_user('user@example.com')


@pytest.fixture
def auth_client(client, auth_user, login):
    response = login(auth_user['email'], auth_user['password'])
    assert response.status_code == 302
    return client


@pytest.fixture
def admin_user(create_user):
    return create_user('admin@example.com', admin=True)


@pytest.fixture
def admin_client(app, admin_user):
    client = app.test_client()
    response = client.post('/login', data={'email': admin_user['email'], 'password': admin_user['password']})
    assert response.status_code == 302
    return client


@pytest.fixture
def create_default_templates(app):
    def _create_default_templates():
        with app.app_context():
            category = DefaultCategoryTemplate(name='Produce')
            db.session.add(category)
            db.session.flush()
            store = DefaultStoreTemplate(name='Warehouse Club', sort_order=10)
            db.session.add(store)
            db.session.flush()
            item = DefaultItemTemplate(
                name='Apples',
                quantity=3,
                unit='lb',
                category='Produce',
                sort_order=20,
                store_template_id=store.id,
            )
            db.session.add(item)
            db.session.commit()
            return {
                'category_id': category.id,
                'store_id': store.id,
                'item_id': item.id,
            }

    return _create_default_templates


@pytest.fixture
def create_default_categories(app):
    def _create_default_categories(*names):
        created_categories = []
        with app.app_context():
            for name in names:
                category = DefaultCategoryTemplate(name=name)
                db.session.add(category)
                created_categories.append(category)
            db.session.commit()
            return [
                {
                    'id': category.id,
                    'name': category.name,
                }
                for category in created_categories
            ]

    return _create_default_categories


@pytest.fixture
def live_server(app):
    server = make_server('127.0.0.1', 0, app)
    server_thread = Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server_thread.join(timeout=5)


@pytest.fixture
def browser_page():
    sync_api = pytest.importorskip('playwright.sync_api')

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        try:
            yield page
        finally:
            context.close()
            browser.close()