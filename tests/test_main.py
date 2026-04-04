from decimal import Decimal

import app.main as main_module
import pytest

from app.db import db
from app.main import parse_price
from app.models import AppSetting, AuditLog, Item, Store, User


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (None, Decimal('0.00')),
        ('', Decimal('0.00')),
        ('abc', Decimal('0.00')),
        (-1, Decimal('0.00')),
        ('2.345', Decimal('2.35')),
    ],
)
def test_parse_price_handles_invalid_and_rounding(value, expected):
    assert parse_price(value) == expected


def test_login_page_renders_for_guests(client):
    response = client.get('/login')

    assert response.status_code == 200
    assert b'Sign in to your grocery list' in response.data
    assert b'Request Access' in response.data
    assert b'Show' in response.data


def test_signup_creates_pending_user(client, app):
    response = client.post('/signup', data={'email': 'pending@example.com'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'Your signup request has been submitted for approval.' in response.data

    with app.app_context():
        user = User.query.filter_by(email='pending@example.com').first()
        assert user is not None
        assert user.is_approved is False
        assert user.is_active is True


def test_pending_user_cannot_login(client, create_user):
    user = create_user('pending@example.com', approved=False)

    response = client.post('/login', data={'email': user['email'], 'password': user['password']})

    assert response.status_code == 200
    assert b'account pending approval' in response.data


def test_inactive_user_cannot_login(client, create_user):
    user = create_user('inactive@example.com', active=False)

    response = client.post('/login', data={'email': user['email'], 'password': user['password']})

    assert response.status_code == 200
    assert b'account is inactive' in response.data


def test_login_rejects_invalid_credentials(client, create_user):
    user = create_user('owner@example.com')

    response = client.post(
        '/login',
        data={
            'email': user['email'],
            'password': 'wrong-password',
        },
    )

    assert response.status_code == 200
    assert b'invalid email or password' in response.data


def test_index_redirects_to_login_when_unauthenticated(client):
    response = client.get('/')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login?next=/')


def test_api_requires_authentication_json_401(client):
    response = client.get('/api/items')

    assert response.status_code == 401
    assert response.get_json() == {'error': 'authentication required'}


def test_items_api_creates_and_lists_items(auth_client):
    response = auth_client.post(
        '/api/items',
        json={
            'name': '  Apples  ',
            'quantity': 3,
            'unit': 'lb',
            'category': 'Produce',
            'price': '2.345',
        },
    )

    assert response.status_code == 201
    assert response.get_json() == {
        'id': 1,
        'name': 'Apples',
        'quantity': 3,
        'unit': 'lb',
        'category': 'Produce',
        'sort_order': 10,
        'store_id': None,
        'price': 2.35,
        'checked': False,
        'created_at': response.get_json()['created_at'],
    }
    assert response.get_json()['created_at'] is not None

    list_response = auth_client.get('/api/items')

    assert list_response.status_code == 200
    assert list_response.get_json() == [response.get_json()]


def test_items_api_rejects_missing_name(auth_client):
    response = auth_client.post('/api/items', json={'name': '   '})

    assert response.status_code == 400
    assert response.get_json() == {'error': 'name is required'}


def test_items_api_rejects_non_json_requests(auth_client):
    response = auth_client.post('/api/items', data='name=Apples', content_type='application/x-www-form-urlencoded')

    assert response.status_code == 415
    assert response.get_json() == {'error': 'request must be JSON'}


def test_items_api_rejects_invalid_store_reference(auth_client):
    response = auth_client.post(
        '/api/items',
        json={
            'name': 'Apples',
            'store_id': 999,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'store_id must reference an existing store'}


def test_items_api_rejects_invalid_quantity_on_update(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('3.99'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(
        f'/api/items/{item_id}',
        json={
            'quantity': 'not-a-number',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'quantity must be a finite number'}


def test_items_api_rejects_blank_name_on_update(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('3.99'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(
        f'/api/items/{item_id}',
        json={
            'name': '   ',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'name is required'}


def test_items_api_updates_fields_and_normalizes_negative_price(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('3.99'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(
        f'/api/items/{item_id}',
        json={
            'checked': True,
            'quantity': 2,
            'price': -10,
            'category': 'Dairy',
        },
    )

    assert response.status_code == 200
    assert response.get_json()['checked'] is True
    assert response.get_json()['quantity'] == 2
    assert response.get_json()['category'] == 'Dairy'
    assert response.get_json()['price'] == 0.0


def test_items_api_deletes_item(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Bread', price=Decimal('1.25'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.delete(f'/api/items/{item_id}')

    assert response.status_code == 204

    with app.app_context():
        assert db.session.get(Item, item_id) is None


def test_user_cannot_access_another_users_item(auth_client, auth_user, create_user, app):
    other_user = create_user('other@example.com')

    with app.app_context():
        item = Item(name='Secret Milk', price=Decimal('3.99'), user_id=other_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(
        f'/api/items/{item_id}',
        json={'checked': True},
    )

    assert response.status_code == 404

    list_response = auth_client.get('/api/items')
    assert list_response.status_code == 200
    assert list_response.get_json() == []


def test_stores_api_prevents_duplicate_names(auth_client):
    first_response = auth_client.post('/api/stores', json={'name': 'Corner Market'})
    duplicate_response = auth_client.post('/api/stores', json={'name': 'Corner Market'})

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.get_json() == {'error': 'Store already exists'}


def test_stores_api_allows_same_name_for_different_users(create_user, app):
    first_user = create_user('first@example.com')
    second_user = create_user('second@example.com')

    first_client = app.test_client()
    login_response = first_client.post('/login', data={'email': first_user['email'], 'password': first_user['password']})
    assert login_response.status_code == 302
    first_create = first_client.post('/api/stores', json={'name': 'Corner Market'})
    assert first_create.status_code == 201

    second_client = app.test_client()
    second_login = second_client.post('/login', data={'email': second_user['email'], 'password': second_user['password']})
    assert second_login.status_code == 302
    second_create = second_client.post('/api/stores', json={'name': 'Corner Market'})

    assert second_create.status_code == 201


def test_stores_api_rejects_non_json_requests(auth_client):
    response = auth_client.post('/api/stores', data='name=Corner Market', content_type='application/x-www-form-urlencoded')

    assert response.status_code == 415
    assert response.get_json() == {'error': 'request must be JSON'}


def test_security_headers_are_set_on_html_responses(auth_client):
    response = auth_client.get('/')

    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'same-origin'


def test_deleting_store_clears_store_id_from_items(auth_client, auth_user, app):
    with app.app_context():
        store = Store(name='Neighborhood Grocer', user_id=auth_user['id'])
        db.session.add(store)
        db.session.flush()
        item = Item(name='Eggs', store_id=store.id, price=Decimal('4.50'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        store_id = store.id
        item_id = item.id

    response = auth_client.delete(f'/api/stores/{store_id}')

    assert response.status_code == 204

    with app.app_context():
        refreshed_item = db.session.get(Item, item_id)
        assert refreshed_item is not None
        assert refreshed_item.store_id is None


def test_logout_clears_session_and_redirects_to_login(auth_client):
    response = auth_client.post('/logout')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

    redirected = auth_client.get('/api/items')
    assert redirected.status_code == 401
    assert redirected.get_json() == {'error': 'authentication required'}


def test_theme_preference_endpoint_updates_current_user(auth_client, auth_user, app):
    response = auth_client.patch('/api/preferences/theme', json={'theme': 'ocean'})

    assert response.status_code == 200
    assert response.get_json() == {'theme': 'ocean'}

    with app.app_context():
        user = db.session.get(User, auth_user['id'])
        assert user.theme_preference == 'ocean'


def test_user_can_change_own_password(auth_client, auth_user, app):
    response = auth_client.patch(
        '/api/account/password',
        json={
            'current_password': auth_user['password'],
            'new_password': 'new-password-456',
            'confirmation_password': 'new-password-456',
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {'message': 'password updated'}

    with app.app_context():
        user = db.session.get(User, auth_user['id'])
        assert user.check_password('new-password-456') is True
        assert user.check_password(auth_user['password']) is False
        assert AuditLog.query.filter_by(action='user.password_changed_self', target_id=user.id).count() == 1

    old_password_client = app.test_client()
    old_password_response = old_password_client.post('/login', data={'email': auth_user['email'], 'password': auth_user['password']})
    assert old_password_response.status_code == 200
    assert b'invalid email or password' in old_password_response.data

    new_password_client = app.test_client()
    new_password_response = new_password_client.post('/login', data={'email': auth_user['email'], 'password': 'new-password-456'})
    assert new_password_response.status_code == 302


def test_password_change_rejects_wrong_current_password(auth_client, auth_user):
    response = auth_client.patch(
        '/api/account/password',
        json={
            'current_password': 'wrong-password',
            'new_password': 'new-password-456',
            'confirmation_password': 'new-password-456',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'current password is incorrect'}


def test_password_change_rejects_mismatched_confirmation(auth_client, auth_user):
    response = auth_client.patch(
        '/api/account/password',
        json={
            'current_password': auth_user['password'],
            'new_password': 'new-password-456',
            'confirmation_password': 'different-password',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'new password confirmation does not match'}


def test_password_change_rejects_short_password(auth_client, auth_user):
    response = auth_client.patch(
        '/api/account/password',
        json={
            'current_password': auth_user['password'],
            'new_password': 'short',
            'confirmation_password': 'short',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'new password must be at least 8 characters long'}


def test_admin_dashboard_requires_admin(auth_client):
    response = auth_client.get('/admin')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_admin_can_approve_signup_and_clone_defaults(monkeypatch, admin_client, create_user, create_default_templates, app):
    create_default_templates()
    pending_user = create_user('newuser@example.com', approved=False)
    monkeypatch.setattr(main_module, 'generate_temporary_password', lambda length=12: 'TempPass234')

    response = admin_client.post(f"/admin/users/{pending_user['id']}/approve", follow_redirects=True)

    assert response.status_code == 200
    assert b'Temporary password for newuser@example.com:' in response.data
    assert b'TempPass234' in response.data

    with app.app_context():
        user = db.session.get(User, pending_user['id'])
        items = Item.query.filter_by(user_id=user.id).all()
        stores = Store.query.filter_by(user_id=user.id).all()
        assert user.is_approved is True
        assert user.is_active is True
        assert len(stores) == 1
        assert len(items) == 1
        assert stores[0].template_store_id is not None
        assert items[0].template_item_id is not None
        assert AuditLog.query.filter_by(action='user.approved', target_id=user.id).count() == 1

    fresh_client = app.test_client()
    login_response = fresh_client.post('/login', data={'email': 'newuser@example.com', 'password': 'TempPass234'})
    assert login_response.status_code == 302


def test_admin_can_generate_temporary_password_for_existing_user(monkeypatch, admin_client, create_user, app):
    user = create_user('resetme@example.com')
    monkeypatch.setattr(main_module, 'generate_temporary_password', lambda length=12: 'ResetPass234')

    response = admin_client.post(f"/admin/users/{user['id']}/reset-password", follow_redirects=True)

    assert response.status_code == 200
    assert b'Temporary password for resetme@example.com:' in response.data
    assert b'ResetPass234' in response.data

    fresh_client = app.test_client()
    login_response = fresh_client.post('/login', data={'email': 'resetme@example.com', 'password': 'ResetPass234'})
    assert login_response.status_code == 302


def test_admin_can_change_default_theme(admin_client, app):
    response = admin_client.post('/admin/settings/theme', data={'theme': 'berry'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'Default theme updated.' in response.data

    with app.app_context():
        setting = AppSetting.query.filter_by(key='default_theme').first()
        assert setting is not None
        assert setting.value == 'berry'


def test_create_user_cli_creates_user_and_copies_defaults(app, create_default_templates):
    create_default_templates()
    runner = app.test_cli_runner()

    result = runner.invoke(args=['create-user', 'owner@example.com', '--password', 'password123!'])

    assert result.exit_code == 0
    assert 'Created user owner@example.com' in result.output

    with app.app_context():
        created_user = User.query.filter_by(email='owner@example.com').first()
        assert created_user is not None
        assert created_user.is_approved is True
        assert Item.query.filter_by(user_id=created_user.id).count() == 1
        assert Store.query.filter_by(user_id=created_user.id).count() == 1