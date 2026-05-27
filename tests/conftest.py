from threading import Thread
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app.db import db
from app.main import create_app
from app.models import AppSetting, AuditLog, DefaultCategoryTemplate, DefaultItemTemplate, DefaultStoreTemplate, Household, HouseholdInvite, HouseholdMember, Item, Store, User


@pytest.fixture(scope="session")
def app():
    test_app = create_app(
        {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            # Disable pool-level reset_on_return.  After a session commits and is then
            # closed, SQLAlchemy's default 'rollback' reset would issue ROLLBACK to
            # SQLite when no transaction is active, causing an OperationalError that
            # invalidates the StaticPool connection and loses the entire in-memory DB.
            'SQLALCHEMY_ENGINE_OPTIONS': {'pool_reset_on_return': None},
        }
    )

    # Create schema once for the whole session.
    with test_app.app_context():
        db.create_all()

    yield test_app

    # Drop schema at the end of the session.
    with test_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def create_user(app):
    def _create_user(email, password='password123!', *, admin=False, approved=True, active=True, theme_preference=None):
        with app.app_context():
            normalized_email = email.strip().lower() if email else None
            existing = User.query.filter_by(email=normalized_email).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            user = User()
            user.email = normalized_email
            user.is_admin = admin
            user.is_approved = approved
            user.is_active = active
            user.theme_preference = theme_preference
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
        from urllib.parse import urlencode
        # Get CSRF token from cookie
        client.get('/login')  # Always GET the form page before POST
        _csrf_cookie = client.get_cookie('_csrf_token')
        csrf_token = _csrf_cookie.value if _csrf_cookie else None
        form_data = {'email': email, 'password': password}
        headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
        return client.post(
            '/login',
            data=urlencode(form_data),
            follow_redirects=follow_redirects,
            content_type='application/x-www-form-urlencoded',
            headers=headers,
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
    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    _csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = _csrf_cookie.value if _csrf_cookie else None
    form_data = {'email': admin_user['email'], 'password': admin_user['password']}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)
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
        with app.app_context():
            created_categories = []
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
def create_household(app):
    def _create_household(owner_user_id, *, role='owner'):
        with app.app_context():
            household = Household()
            db.session.add(household)
            db.session.flush()
            member = HouseholdMember(
                household_id=household.id,
                user_id=owner_user_id,
                role=role,
                notifications_enabled=True,
            )
            db.session.add(member)
            db.session.commit()
            return {'household_id': household.id, 'member_id': member.id}

    return _create_household


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


@pytest.fixture(autouse=True)
def clean_db_between_tests(app):
    """Clear all data tables after each test to prevent state leaking between tests."""
    yield
    with app.app_context():
        db.session.rollback()
        Item.query.delete()
        Store.query.delete()
        AuditLog.query.delete()
        DefaultItemTemplate.query.delete()
        DefaultStoreTemplate.query.delete()
        DefaultCategoryTemplate.query.delete()
        AppSetting.query.delete()
        HouseholdInvite.query.delete()
        HouseholdMember.query.delete()
        Household.query.delete()
        User.query.delete()
        db.session.commit()
