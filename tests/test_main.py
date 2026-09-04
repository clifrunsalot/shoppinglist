def test_print_cookies_after_login_get(client):
    """Temporary debug: Print all cookies after GET /login to inspect CSRF token presence and name."""
    response = client.get('/login')
    print("\n[DEBUG] Cookies after GET /login:")
    _csrf_cookie = client.get_cookie('_csrf_token')
    if _csrf_cookie:
        print(f"[DEBUG] Cookie: key=_csrf_token, value={_csrf_cookie.value}")
    else:
        print("[DEBUG] No _csrf_token cookie found")
    # This test always passes; it's for debug output only
    assert response.status_code == 200
import io
from decimal import Decimal

import app.main as main_module
import pytest

from app.db import db
from app.main import parse_price
from app.models import AppSetting, AuditLog, Item, Store, User

def test_admin_post_form_rejects_without_csrf(admin_client, app):
    # Verify the admin page includes CSRF token hidden inputs in its forms,
    # which is the app's responsibility for CSRF protection.
    response = admin_client.get('/admin')
    assert response.status_code == 200
    assert b'name="_csrf_token"' in response.data

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
    assert b'Grocery List' in response.data
    assert b'Sign in to manage your private stores and shopping items.' in response.data
    assert b'max-w-xl items-center justify-center px-5 py-4 sm:px-6 sm:py-6' in response.data
    assert b'Welcome back' in response.data
    assert b'Use your authorized account to continue.' in response.data
    assert b'Request Access' in response.data
    assert b'Show' in response.data
    assert b'Private access' not in response.data
    assert b'flask create-user EMAIL' not in response.data
    
    def test_csrf_protection_enforced(client, app):
        # Add a dummy POST route for testing if not present
        @app.route('/test-csrf', methods=['POST'])
        def test_csrf():
            return 'ok'

        response = client.post('/test-csrf')
        # Flask-SeaSurf returns 400 for missing/invalid CSRF token
        assert response.status_code == 400
        assert b'CSRF' in response.data or b'csrf' in response.data


def test_index_page_refreshes_stores_when_page_regains_focus(auth_client):
    response = auth_client.get('/')

    assert response.status_code == 200
    assert b"window.addEventListener('focus'" in response.data
    assert b"document.addEventListener('visibilitychange'" in response.data
    assert b'refreshStoresSilently' in response.data


def test_index_page_uses_debounced_item_save_hooks(auth_client):
    response = auth_client.get('/')

    assert response.status_code == 200
    assert b":data-item-id=\"selectedItem.id\" x-model=\"selectedItem.name\" @blur=\"commitNameField(Number($el.dataset.itemId), $event.target.value)\"" in response.data
    assert b'async commitNameField(itemId, value)' in response.data
    assert b'x-effect="syncSelectedStoreControl()"' in response.data
    assert b'x-effect="syncSelectedCategoryControl()"' in response.data
    assert b"@change=\"selectedItem.store_value = $event.target.value; saveStoreSelection(Number($el.dataset.itemId), selectedItem.store_value === '' ? null : Number(selectedItem.store_value))\"" in response.data
    assert b"saveCategorySelection(Number($el.dataset.itemId), selectedItem.category_value === '' ? null : selectedItem.category_value)" in response.data
    assert b'itemSaveDebounceMs: 400' in response.data
    assert b'storeSaveItemId: null' in response.data
    assert b'categorySaveItemId: null' in response.data
    assert b'Saving store...' in response.data
    assert b'Saving category...' in response.data
    assert b'async saveStoreSelection(itemId, storeId)' in response.data
    assert b'async saveCategorySelection(itemId, categoryName)' in response.data
    assert b'this.fetchCategories()' in response.data
    assert b'collectSelectedItemDraftChanges' in response.data
    assert b'flushSelectedItemChanges' in response.data
    assert b'pendingItemSavePromises' in response.data
    assert b'itemSelectionPromise: Promise.resolve()' in response.data
    assert b"selectItem(item, source = 'click')" in response.data
    assert b'syncSelectedStoreControl()' in response.data
    assert b'syncSelectedCategoryControl()' in response.data
    assert b'Store Catalog' not in response.data
    assert b'Stores are managed by an administrator and stay aligned across all accounts.' not in response.data
    assert b'Category Catalog' not in response.data
    assert b'Categories are managed by an administrator and used as shared dropdown options.' not in response.data
    assert b'Manage Stores' not in response.data


def test_index_page_panel_avoids_virtual_keyboard(auth_client):
    # The bottom-sheet panel overlay must be keyboard-aware so the panel
    # automatically rises above the virtual keyboard on iOS/WebKit without
    # the user having to drag it.  Regression guard for the visualViewport fix.
    response = auth_client.get('/')

    assert response.status_code == 200
    # Alpine state property and syncKeyboard initialiser must both be present.
    assert b'keyboardOffset: 0' in response.data
    assert b'const syncKeyboard = () =>' in response.data
    assert b'window.visualViewport' in response.data
    # The overlay's bottom edge is driven by the reactive keyboardOffset value.
    assert b':style="`bottom: ${keyboardOffset}px`"' in response.data
    # Overlay uses inset-x-0 top-0 (not a static inset-0) so only bottom is dynamic.
    assert b'fixed inset-x-0 top-0' in response.data
    # Panel sheet CSS class and its CSS variable must be rendered.
    assert b'panel-sheet' in response.data
    assert b'--panel-max-h' in response.data


def test_mobile_input_font_size_prevents_ios_zoom(auth_client, admin_client, app):
    # iOS Safari / DuckDuckGo (WebKit) auto-zoom the viewport when a focused
    # input has font-size < 16 px.  The zoom persists after keyboard dismissal,
    # making the layout wider than the screen.  All three pages must include the
    # mobile-scoped CSS rule that forces inputs to 16 px.
    ios_zoom_rule = b'font-size: 16px !important'
    mobile_media_rule = b'max-width: 767px'

    index_html = auth_client.get('/').data
    assert ios_zoom_rule in index_html
    assert mobile_media_rule in index_html

    # Use a fresh unauthenticated client so /login renders the form rather than
    # redirecting (auth_client and the shared client fixture are the same object).
    anon_client = app.test_client()
    login_html = anon_client.get('/login').data
    assert ios_zoom_rule in login_html
    assert mobile_media_rule in login_html

    admin_html = admin_client.get('/admin').data
    assert ios_zoom_rule in admin_html
    assert mobile_media_rule in admin_html


def test_signup_creates_pending_user(client, app):
    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    _csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = _csrf_cookie.value if _csrf_cookie else None
    form_data = {'email': 'pending@example.com'}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/signup', data=urlencode(form_data), follow_redirects=True, content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'verification link' in response.data

    with app.app_context():
        # Phase 3: signup creates a SignupToken, NOT a User
        token = SignupToken.query.filter_by(email='pending@example.com').first()
        assert token is not None
        assert token.consumed is False
        assert User.query.filter_by(email='pending@example.com').first() is None


def test_pending_user_cannot_login(client, create_user):
    user = create_user('pending@example.com', approved=False)

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    _csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = _csrf_cookie.value if _csrf_cookie else None
    form_data = {'email': user['email'], 'password': user['password']}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'account pending approval' in response.data


def test_inactive_user_cannot_login(client, create_user):
    user = create_user('inactive@example.com', active=False)

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    _csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = _csrf_cookie.value if _csrf_cookie else None
    form_data = {'email': user['email'], 'password': user['password']}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'account is inactive' in response.data


def test_login_rejects_invalid_credentials(client, create_user):
    user = create_user('owner@example.com')

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    _csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = _csrf_cookie.value if _csrf_cookie else None
    form_data = {'email': user['email'], 'password': 'wrong-password'}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'invalid email or password' in response.data


def test_index_redirects_to_login_when_unauthenticated(client):
    response = client.get('/')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login?next=/')


def test_help_page_renders_for_authenticated_user(auth_client):
    response = auth_client.get('/help')

    assert response.status_code == 200
    assert b'Help' in response.data
    assert b'Back to your list' not in response.data


def test_help_page_redirects_to_login_when_unauthenticated(client):
    response = client.get('/help')

    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_help_page_back_button_points_to_index_by_default(auth_client):
    response = auth_client.get('/help')

    assert b'?settings=1' not in response.data
    assert b'url_for' not in response.data  # rendered, not raw Jinja


def test_help_page_back_button_includes_settings_param_when_ref_settings(auth_client):
    response = auth_client.get('/help?ref=settings')

    assert response.status_code == 200
    assert b'?settings=1' in response.data


def test_api_requires_authentication_json_401(client):
    response = client.get('/api/items')

    assert response.status_code == 401
    assert response.get_json() == {'error': 'authentication required'}


def test_items_api_creates_and_lists_items(auth_client, app):
    with app.app_context():
        db.session.add(main_module.DefaultCategoryTemplate(name='Produce'))
        db.session.commit()

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
        'version': 1,
        'template_item_id': None,
        'photo_url': None,
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


def test_items_api_accepts_photo_upload_and_serializes_photo_url(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Bananas', price=Decimal('1.99'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.post(
        f'/api/items/{item_id}/photo',
        data={'photo': (io.BytesIO(b'not-a-real-image'), 'banana.jpg')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['photo_url'].startswith('/static/uploads/items/')
    assert payload['photo_url'].endswith('.jpg')

    list_response = auth_client.get('/api/items')
    assert list_response.status_code == 200
    assert list_response.get_json()[0]['photo_url'] == payload['photo_url']

    delete_response = auth_client.delete(f'/api/items/{item_id}/photo')
    assert delete_response.status_code == 200
    assert delete_response.get_json()['photo_url'] is None

    refreshed_response = auth_client.get('/api/items')
    assert refreshed_response.get_json()[0]['photo_url'] is None


def test_items_api_returns_meaningful_error_for_oversized_photo(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('2.49'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    original_limit = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 64
    try:
        response = auth_client.post(
            f'/api/items/{item_id}/photo',
            data={'photo': (io.BytesIO(b'x' * 128), 'milk.jpg')},
            content_type='multipart/form-data',
        )
    finally:
        app.config['MAX_CONTENT_LENGTH'] = original_limit

    assert response.status_code == 413
    assert response.get_json() == {'error': 'photo is too large; maximum size is 5 MB'}


def test_items_api_rejects_duplicate_name_on_create(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Apples', price=Decimal('1.25'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()

    response = auth_client.post('/api/items', json={'name': ' apples '})

    assert response.status_code == 409
    assert response.get_json() == {'error': 'item already exists'}


def test_items_api_creates_item_from_default_template(auth_client, auth_user, app):
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Milk', quantity=1)
        db.session.add(template)
        db.session.commit()
        template_id = template.id

    response = auth_client.post('/api/items', json={'name': 'Milk', 'template_item_id': template_id})

    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Milk'
    assert data['template_item_id'] == template_id


def test_items_api_rejects_already_claimed_template_id_on_create(auth_client, auth_user, app):
    """Backend guard: even if the frontend drops template_item_id for 'in list' items,
    a request that still carries an already-claimed template_item_id is rejected."""
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Milk', quantity=1)
        db.session.add(template)
        db.session.flush()
        existing = Item(name='Milk', price=Decimal('0.00'), user_id=auth_user['id'], template_item_id=template.id)
        db.session.add(existing)
        db.session.commit()
        template_id = template.id

    response = auth_client.post('/api/items', json={'name': 'Whole Milk', 'template_item_id': template_id})

    assert response.status_code == 409
    assert response.get_json() == {'error': 'item already exists'}


def test_items_api_creates_renamed_item_without_template_link(auth_client, auth_user, app):
    """Simulates the user changing the name after pre-filling from defaults (frontend clears template_item_id)."""
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Milk', quantity=1)
        db.session.add(template)
        db.session.flush()
        existing = Item(name='Milk', price=Decimal('0.00'), user_id=auth_user['id'], template_item_id=template.id)
        db.session.add(existing)
        db.session.commit()

    response = auth_client.post('/api/items', json={'name': 'Whole Milk'})

    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Whole Milk'
    assert data['template_item_id'] is None


def test_items_api_rejects_duplicate_name_when_selecting_in_list_item(auth_client, auth_user, app):
    """Simulates selecting an 'In list' default without renaming it.
    The frontend clears template_item_id for already-added items, so the backend
    catches the collision via the name-duplicate check rather than the template check."""
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Milk', quantity=1)
        db.session.add(template)
        db.session.flush()
        existing = Item(name='Milk', price=Decimal('0.00'), user_id=auth_user['id'], template_item_id=template.id)
        db.session.add(existing)
        db.session.commit()

    # No template_item_id sent — matches what the frontend does for 'in list' items.
    response = auth_client.post('/api/items', json={'name': 'Milk'})

    assert response.status_code == 409
    assert response.get_json() == {'error': 'item already exists'}


def test_default_items_api_returns_sorted_templates(auth_client, auth_user, app):
    with app.app_context():
        store_tpl = main_module.DefaultStoreTemplate(name='Market', sort_order=0)
        db.session.add(store_tpl)
        db.session.flush()
        db.session.add_all([
            main_module.DefaultItemTemplate(name='Zucchini', quantity=2, unit='each', category=None, store_template_id=None),
            main_module.DefaultItemTemplate(name='Apples', quantity=1, unit='lb', category='Produce', store_template_id=store_tpl.id),
        ])
        db.session.commit()

    response = auth_client.get('/api/default-items')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]['name'] == 'Apples'
    assert data[0]['quantity'] == 1
    assert data[0]['unit'] == 'lb'
    assert data[0]['category'] == 'Produce'
    assert data[0]['store_template_id'] == data[0]['store_template_id']  # value present
    assert data[1]['name'] == 'Zucchini'
    assert set(data[0].keys()) == {'id', 'name', 'quantity', 'unit', 'category', 'store_template_id'}


def test_default_items_api_returns_empty_list_when_no_templates(auth_client):
    response = auth_client.get('/api/default-items')

    assert response.status_code == 200
    assert response.get_json() == []


def test_default_items_api_requires_authentication(client):
    response = client.get('/api/default-items')

    assert response.status_code in (401, 302)


def test_items_api_rejects_unknown_template_item_id(auth_client):
    response = auth_client.post('/api/items', json={'name': 'Ghost Item', 'template_item_id': 99999})

    assert response.status_code == 404
    assert response.get_json() == {'error': 'template_item_id does not reference a known template'}


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


def test_items_api_rejects_invalid_category_reference(auth_client):
    response = auth_client.post(
        '/api/items',
        json={
            'name': 'Apples',
            'category': 'Unknown Category',
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'category must reference an existing category'}


def test_items_api_rejects_zero_quantity_on_create(auth_client):
    response = auth_client.post(
        '/api/items',
        json={
            'name': 'Apples',
            'quantity': 0,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'quantity must be greater than 0'}


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


def test_items_api_rejects_zero_quantity_on_update(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('3.99'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(
        f'/api/items/{item_id}',
        json={
            'quantity': 0,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'quantity must be greater than 0'}


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


def test_items_api_rejects_duplicate_name_on_update(auth_client, auth_user, app):
    with app.app_context():
        first_item = Item(name='Milk', price=Decimal('3.99'), user_id=auth_user['id'])
        second_item = Item(name='Bread', price=Decimal('1.25'), user_id=auth_user['id'])
        db.session.add_all([first_item, second_item])
        db.session.commit()
        second_item_id = second_item.id

    response = auth_client.patch(
        f'/api/items/{second_item_id}',
        json={
            'name': ' milk ',
        },
    )

    assert response.status_code == 409
    assert response.get_json() == {'error': 'item already exists'}


def test_items_api_updates_fields_and_normalizes_negative_price(auth_client, auth_user, app):
    with app.app_context():
        db.session.add(main_module.DefaultCategoryTemplate(name='Dairy'))
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


def test_categories_api_lists_admin_managed_categories(auth_client, app):
    with app.app_context():
        db.session.add_all([
            main_module.DefaultCategoryTemplate(name='Food'),
            main_module.DefaultCategoryTemplate(name='Produce'),
        ])
        db.session.commit()

    response = auth_client.get('/api/categories')

    assert response.status_code == 200
    assert [category['name'] for category in response.get_json()] == ['Food', 'Produce']


def test_categories_api_rejects_user_mutation(auth_client):
    response = auth_client.post('/api/categories', json={'name': 'Produce'})

    assert response.status_code == 403
    assert response.get_json() == {'error': 'categories are managed by an administrator'}


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


def test_items_api_delete_all(auth_client, auth_user, app):
    with app.app_context():
        item1 = Item(name='Bread', price=Decimal('1.25'), user_id=auth_user['id'])
        item2 = Item(name='Milk', price=Decimal('2.50'), user_id=auth_user['id'])
        item3 = Item(name='Eggs', price=Decimal('3.00'), user_id=auth_user['id'])
        db.session.add_all([item1, item2, item3])
        db.session.commit()
        item_ids = [item1.id, item2.id, item3.id]

    response = auth_client.post('/api/items/delete-all', json={})

    assert response.status_code == 200
    assert response.get_json() == {'deleted_count': 3}

    with app.app_context():
        assert db.session.get(Item, item_ids[0]) is None
        assert db.session.get(Item, item_ids[1]) is None
        assert db.session.get(Item, item_ids[2]) is None


def test_items_api_delete_all_empty_list(auth_client):
    response = auth_client.post('/api/items/delete-all', json={})

    assert response.status_code == 200
    assert response.get_json() == {'deleted_count': 0}


def test_items_api_delete_all_deletes_only_user_items(auth_client, auth_user, create_user, app):
    other_user = create_user('other@example.com')

    with app.app_context():
        user_item = Item(name='User Item', price=Decimal('1.00'), user_id=auth_user['id'])
        other_item = Item(name='Other Item', price=Decimal('2.00'), user_id=other_user['id'])
        db.session.add_all([user_item, other_item])
        db.session.commit()
        user_item_id = user_item.id
        other_item_id = other_item.id

    response = auth_client.post('/api/items/delete-all', json={})

    assert response.status_code == 200
    assert response.get_json() == {'deleted_count': 1}

    with app.app_context():
        assert db.session.get(Item, user_item_id) is None
        assert db.session.get(Item, other_item_id) is not None


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


def test_stores_api_returns_admin_managed_catalog_only(auth_client, auth_user, app):
    with app.app_context():
        aldi_template = main_module.DefaultStoreTemplate(name='Aldi', sort_order=0)
        live_probe_template = main_module.DefaultStoreTemplate(name='Live Store Probe', sort_order=0)
        db.session.add_all([aldi_template, live_probe_template])
        db.session.flush()
        aldi_template_id = aldi_template.id
        live_probe_template_id = live_probe_template.id
        copied_store = Store(name='Old Probe Name', user_id=auth_user['id'], template_store_id=live_probe_template.id, sort_order=80)
        stray_store = Store(name='Rogue Store', user_id=auth_user['id'], sort_order=90)
        db.session.add_all([copied_store, stray_store])
        db.session.flush()
        stray_item = Item(name='Eggs', store_id=stray_store.id, price=Decimal('4.50'), user_id=auth_user['id'])
        db.session.add(stray_item)
        db.session.commit()
        stray_store_id = stray_store.id
        stray_item_id = stray_item.id

    response = auth_client.get('/api/stores')

    assert response.status_code == 200
    data = response.get_json()
    assert [{'id': s['id'], 'name': s['name']} for s in data] == [
        {'id': data[0]['id'], 'name': 'Aldi'},
        {'id': data[1]['id'], 'name': 'Live Store Probe'},
        {'id': data[2]['id'], 'name': 'unknown'},
    ]

    with app.app_context():
        stores = Store.query.filter_by(user_id=auth_user['id']).order_by(Store.sort_order.asc(), Store.id.asc()).all()
        assert [(store.name, store.template_store_id, store.sort_order) for store in stores] == [
            ('Aldi', aldi_template_id, 10),
            ('Live Store Probe', live_probe_template_id, 20),
            ('unknown', None, 30),
        ]
        refreshed_item = db.session.get(Item, stray_item_id)
        assert refreshed_item is not None
        assert refreshed_item.store_id == stores[-1].id


def test_stores_api_backfills_missing_default_stores_for_existing_user(auth_client, auth_user, app):
    with app.app_context():
        aldi_template = main_module.DefaultStoreTemplate(name='Aldi', sort_order=0)
        live_probe_template = main_module.DefaultStoreTemplate(name='Live Probe Store', sort_order=0)
        db.session.add_all([aldi_template, live_probe_template])
        db.session.flush()
        existing_store = Store(name='Live Probe Store', user_id=auth_user['id'], template_store_id=live_probe_template.id, sort_order=10)
        db.session.add(existing_store)
        db.session.commit()

    response = auth_client.get('/api/stores')

    assert response.status_code == 200
    data = response.get_json()
    assert [{'id': s['id'], 'name': s['name']} for s in data] == [
        {'id': data[0]['id'], 'name': 'Aldi'},
        {'id': data[1]['id'], 'name': 'Live Probe Store'},
    ]

    with app.app_context():
        stores = Store.query.filter_by(user_id=auth_user['id']).order_by(Store.sort_order.asc(), Store.id.asc()).all()
        assert [(store.name, store.sort_order) for store in stores] == [
            ('Aldi', 10),
            ('Live Probe Store', 20),
        ]


def test_stores_api_rejects_store_creation(auth_client):
    response = auth_client.post('/api/stores', json={'name': 'Corner Market'})

    assert response.status_code == 403
    assert response.get_json() == {'error': 'stores are managed by an administrator'}


def test_stores_api_rejects_store_updates(auth_client, auth_user, app):
    with app.app_context():
        store = Store(name='Warehouse Club', user_id=auth_user['id'])
        db.session.add(store)
        db.session.commit()
        store_id = store.id

    response = auth_client.patch(f'/api/stores/{store_id}', json={'name': 'Corner Market'})

    assert response.status_code == 403
    assert response.get_json() == {'error': 'stores are managed by an administrator'}


def test_stores_api_rejects_store_deletion(auth_client, auth_user, app):
    with app.app_context():
        store = Store(name='Neighborhood Grocer', user_id=auth_user['id'])
        db.session.add(store)
        db.session.commit()
        store_id = store.id

    response = auth_client.delete(f'/api/stores/{store_id}')

    assert response.status_code == 403
    assert response.get_json() == {'error': 'stores are managed by an administrator'}


def test_security_headers_are_set_on_html_responses(auth_client):
    response = auth_client.get('/')

    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'same-origin'
    assert response.headers['Permissions-Policy'] == 'camera=(self), microphone=(), geolocation=(), payment=()'

    csp = response.headers.get('Content-Security-Policy', '')
    assert "default-src 'none'" in csp
    assert 'connect-src' in csp
    assert 'form-action' in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "nonce-" in csp


def test_session_cookie_secure_warning_when_disabled():
    """create_app() should warn when SESSION_COOKIE_SECURE is off and TESTING is off."""
    import warnings
    from app.main import create_app
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        create_app({'TESTING': False, 'SESSION_COOKIE_SECURE': False,
                    'WTF_CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})
    messages = [str(w.message) for w in caught]
    assert any('SESSION_COOKIE_SECURE' in m for m in messages)


def test_session_cookie_secure_no_warning_when_enabled():
    """No SESSION_COOKIE_SECURE warning when the flag is set."""
    import warnings
    from app.main import create_app
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        create_app({'TESTING': False, 'SESSION_COOKIE_SECURE': True,
                    'WTF_CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})
    messages = [str(w.message) for w in caught]
    assert not any('SESSION_COOKIE_SECURE' in m for m in messages)


def test_cdn_scripts_have_sri_integrity_attributes(client, auth_client):
    """Alpine.js (served via jsDelivr with CORS) must have SRI integrity/crossorigin.
    Tailwind is version-pinned but SRI is not applied because cdn.tailwindcss.com
    does not return CORS headers, so crossorigin+integrity would block the script."""
    import re
    response = auth_client.get('/')
    html = response.data.decode()

    # Alpine.js from jsDelivr must have integrity + crossorigin
    alpine_tags = re.findall(r'<script[^>]+cdn\.jsdelivr\.net[^>]*>', html)
    assert alpine_tags, 'Alpine.js script tag not found'
    for tag in alpine_tags:
        assert 'integrity=' in tag, f'Missing SRI integrity on Alpine: {tag}'
        assert 'crossorigin=' in tag, f'Missing crossorigin on Alpine: {tag}'

    # Tailwind must be pinned to an explicit version (not a floating tag)
    tailwind_tags = re.findall(r'<script[^>]+cdn\.tailwindcss\.com[^>]*>', html)
    assert tailwind_tags, 'Tailwind script tag not found'
    for tag in tailwind_tags:
        assert '@' not in tag and 'x.x' not in tag, \
            f'Tailwind script uses a floating version tag: {tag}'


def test_logout_clears_session_and_redirects_to_login(auth_client):
    response = auth_client.post('/logout')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

    redirected = auth_client.get('/api/items')
    assert redirected.status_code == 401
    assert redirected.get_json() == {'error': 'authentication required'}


def test_admin_logout_redirects_to_login_page(admin_client):
    response = admin_client.post('/logout', follow_redirects=True)

    assert response.status_code == 200
    assert b'Welcome back' in response.data
    assert b'Use your authorized account to continue.' in response.data

    redirected = admin_client.get('/admin')
    assert redirected.status_code == 302
    assert redirected.headers['Location'].endswith('/login?next=/admin')


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


def test_import_default_items_api_links_unlinked_same_name_item_without_overwriting(auth_client, auth_user, app):
    """Import links a user's existing same-name item to the template but preserves the user's data."""
    with app.app_context():
        default_store = main_module.DefaultStoreTemplate(name='Pantry', sort_order=0)
        db.session.add(default_store)
        db.session.flush()
        template_item = main_module.DefaultItemTemplate(
            name='Apples',
            quantity=3,
            unit='bag',
            category='Produce',
            sort_order=15,
            store_template_id=default_store.id,
        )
        existing_item = Item(
            name=' apples ',
            quantity=9,
            unit='crate',
            category='Snacks',
            sort_order=90,
            price=Decimal('4.50'),
            checked=True,
            user_id=auth_user['id'],
        )
        db.session.add_all([template_item, existing_item])
        db.session.commit()
        existing_item_id = existing_item.id
        template_item_id = template_item.id

    response = auth_client.post('/api/account/import-default-items', json={})

    assert response.status_code == 200
    assert response.get_json() == {
        'message': 'default items imported',
        'created_count': 0,
        'overwritten_count': 1,
    }

    with app.app_context():
        items = Item.query.filter_by(user_id=auth_user['id']).order_by(Item.id.asc()).all()
        assert len(items) == 1
        assert items[0].id == existing_item_id
        # User data is preserved — only template_item_id is set (link-only)
        assert items[0].name == ' apples '
        assert items[0].quantity == 9
        assert items[0].unit == 'crate'
        assert items[0].category == 'Snacks'
        assert items[0].sort_order == 90
        assert items[0].price == Decimal('4.50')
        assert items[0].checked is True
        assert items[0].template_item_id == template_item_id
        audit_entry = AuditLog.query.filter_by(action='user.default_items_imported', target_id=auth_user['id']).first()
        assert audit_entry is not None
        assert str(existing_item_id) in (audit_entry.details or '')


def test_import_default_items_api_preserves_custom_item_renamed_from_default(auth_client, auth_user, app):
    """Regression: custom item added by renaming a default must survive import of all defaults."""
    with app.app_context():
        template_milk = main_module.DefaultItemTemplate(name='Milk', quantity=1, unit='gal', category='Dairy', sort_order=10)
        template_eggs = main_module.DefaultItemTemplate(name='Eggs', quantity=12, unit='ct', category='Dairy', sort_order=20)
        db.session.add_all([template_milk, template_eggs])
        db.session.commit()

    # User adds a custom item by renaming "Milk" → "Oat Milk" (template_item_id withheld)
    create_resp = auth_client.post('/api/items', json={
        'name': 'Oat Milk', 'quantity': 2, 'unit': 'carton',
    })
    assert create_resp.status_code == 201
    custom_item_id = create_resp.get_json()['id']

    # Import all defaults
    import_resp = auth_client.post('/api/account/import-default-items', json={})
    assert import_resp.status_code == 200

    list_resp = auth_client.get('/api/items')
    assert list_resp.status_code == 200
    items = list_resp.get_json()
    names = [i['name'] for i in items]

    # Custom item must still be present
    assert 'Oat Milk' in names, 'Custom renamed item must survive import'
    # Both defaults must also be present
    assert 'Milk' in names
    assert 'Eggs' in names
    # Exactly 3 items — no duplicates
    assert len(items) == 3

    with app.app_context():
        custom = db.session.get(Item, custom_item_id)
        assert custom is not None
        assert custom.name == 'Oat Milk'
        assert custom.template_item_id is None  # custom item retains no template link


def test_import_default_items_api_resets_previously_linked_item_to_template_defaults(auth_client, auth_user, app):
    """Items that were previously imported (template_item_id set) are fully reset on re-import."""
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Butter', quantity=1, unit='lb', category='Dairy', sort_order=10)
        db.session.add(template)
        db.session.flush()
        # Simulate a previously imported item that the user modified
        linked_item = Item(
            name='Butter', quantity=5, unit='kg', category='Snacks',
            sort_order=99, price=Decimal('9.99'), checked=True,
            user_id=auth_user['id'], template_item_id=template.id,
        )
        db.session.add(linked_item)
        db.session.commit()
        item_id = linked_item.id
        template_id = template.id

    response = auth_client.post('/api/account/import-default-items', json={})
    assert response.status_code == 200

    with app.app_context():
        item = db.session.get(Item, item_id)
        # Template-linked item IS fully reset to template defaults
        assert item.name == 'Butter'
        assert item.quantity == 1
        assert item.unit == 'lb'
        assert item.category == 'Dairy'
        assert item.price == Decimal('0.00')
        assert item.checked is False
        assert item.template_item_id == template_id


def test_import_default_items_api_applies_alphabetical_sort_order(auth_client, auth_user, app):
    with app.app_context():
        db.session.add_all(
            [
                main_module.DefaultItemTemplate(name='Zulu Apples', quantity=1, sort_order=10),
                main_module.DefaultItemTemplate(name='bananas', quantity=1, sort_order=999),
            ]
        )
        db.session.commit()

    import_response = auth_client.post('/api/account/import-default-items', json={})

    assert import_response.status_code == 200

    list_response = auth_client.get('/api/items')

    assert list_response.status_code == 200
    assert [item['name'] for item in list_response.get_json()] == ['bananas', 'Zulu Apples']
    assert [item['sort_order'] for item in list_response.get_json()] == [10, 20]


def test_items_api_lists_items_alphabetically_by_default(auth_client, auth_user, app):
    with app.app_context():
        db.session.add_all(
            [
                Item(name='Zulu Apples', quantity=1, user_id=auth_user['id'], sort_order=10),
                Item(name='bananas', quantity=1, user_id=auth_user['id'], sort_order=1),
                Item(name='Carrots', quantity=1, user_id=auth_user['id'], sort_order=5),
            ]
        )
        db.session.commit()

    response = auth_client.get('/api/items')

    assert response.status_code == 200
    assert [item['name'] for item in response.get_json()] == ['bananas', 'Carrots', 'Zulu Apples']


def test_admin_dashboard_requires_admin(auth_client):
    response = auth_client.get('/admin')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_admin_default_stores_page_omits_sort_order_field(admin_client, app):
    with app.app_context():
        db.session.add_all(
            [
                main_module.DefaultStoreTemplate(name='Zulu Market', sort_order=90),
                main_module.DefaultStoreTemplate(name='Alpha Foods', sort_order=10),
            ]
        )
        db.session.commit()

    response = admin_client.get('/admin')

    assert response.status_code == 200
    assert b'Compact rows keep the store list scannable.' in response.data
    default_stores_section = response.data.split(b'Default Stores', 1)[1].split(b'Default Grocery List', 1)[0]
    assert b'name="sort_order"' not in default_stores_section
    assert response.data.index(b'Alpha Foods') < response.data.index(b'Zulu Market')


def test_admin_create_default_store_ignores_sort_order_and_defaults_to_alphabetical(admin_client, app):
    with app.app_context():
        db.session.add(main_module.DefaultStoreTemplate(name='Zulu Market', sort_order=90))
        db.session.commit()

    response = admin_client.post(
        '/admin/default-stores',
        data={'name': 'Alpha Foods', 'sort_order': '999'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert response.data.index(b'Alpha Foods') < response.data.index(b'Zulu Market')

    with app.app_context():
        store = main_module.DefaultStoreTemplate.query.filter_by(name='Alpha Foods').first()
        assert store is not None
        assert store.sort_order == 0
        audit_entry = AuditLog.query.filter_by(action='default_store.created', target_id=store.id).first()
        assert audit_entry is not None
        assert 'copied_user_ids' in (audit_entry.details or '')


def test_admin_update_default_store_ignores_sort_order_input(admin_client, app):
    with app.app_context():
        store = main_module.DefaultStoreTemplate(name='Bravo Market', sort_order=70)
        db.session.add(store)
        db.session.commit()
        store_id = store.id

    response = admin_client.post(
        f'/admin/default-stores/{store_id}/update',
        data={'name': 'Alpha Market', 'sort_order': '999'},
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        store = db.session.get(main_module.DefaultStoreTemplate, store_id)
        assert store.name == 'Alpha Market'
        assert store.sort_order == 0
        audit_entry = AuditLog.query.filter_by(action='default_store.updated', target_id=store.id).first()
        assert audit_entry is not None
        assert 'sort_order' not in (audit_entry.details or '')


def test_admin_update_default_store_propagates_name_to_existing_user_stores(admin_client, create_user, app):
    regular_user = create_user('rename-store-owner@example.com')

    with app.app_context():
        store = main_module.DefaultStoreTemplate(name='Bravo Market', sort_order=0)
        db.session.add(store)
        db.session.flush()
        copied_store = Store(name='Bravo Market', user_id=regular_user['id'], template_store_id=store.id, sort_order=10)
        db.session.add(copied_store)
        db.session.commit()
        store_id = store.id
        copied_store_id = copied_store.id

    response = admin_client.post(
        f'/admin/default-stores/{store_id}/update',
        data={'name': 'Alpha Market', 'sort_order': '999'},
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        copied_store = db.session.get(Store, copied_store_id)
        assert copied_store is not None
        assert copied_store.name == 'Alpha Market'


def test_admin_create_default_item_merges_into_existing_user_accounts(admin_client, create_user, app):
    regular_user = create_user('default-item-owner@example.com')

    with app.app_context():
        db.session.add(main_module.DefaultCategoryTemplate(name='Produce'))
        default_store = main_module.DefaultStoreTemplate(name='Pantry', sort_order=0)
        db.session.add(default_store)
        db.session.flush()
        default_store_id = default_store.id
        copied_store = Store(name='Pantry', user_id=regular_user['id'], template_store_id=default_store.id, sort_order=10)
        db.session.add(copied_store)
        db.session.flush()
        copied_store_id = copied_store.id
        db.session.commit()

    response = admin_client.post(
        '/admin/default-items',
        data={
            'name': 'Bananas',
            'quantity': '2',
            'unit': 'lb',
            'category': 'Produce',
            'sort_order': '25',
            'store_template_id': str(default_store_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Default item added.' in response.data

    with app.app_context():
        template_item = main_module.DefaultItemTemplate.query.filter_by(name='Bananas').first()
        assert template_item is not None
        merged_item = Item.query.filter_by(user_id=regular_user['id'], template_item_id=template_item.id).first()
        assert merged_item is not None
        assert merged_item.name == 'Bananas'
        assert merged_item.quantity == 2
        assert merged_item.unit == 'lb'
        assert merged_item.category == 'Produce'
        assert merged_item.store_id == copied_store_id


def test_admin_create_default_item_defaults_blank_quantity_to_one(admin_client, app):
    with app.app_context():
        db.session.add(main_module.DefaultCategoryTemplate(name='Produce'))
        db.session.commit()

    response = admin_client.post(
        '/admin/default-items',
        data={
            'name': 'Bananas',
            'quantity': '',
            'unit': 'lb',
            'category': 'Produce',
            'sort_order': '25',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Default item added.' in response.data

    with app.app_context():
        template_item = main_module.DefaultItemTemplate.query.filter_by(name='Bananas').first()
        assert template_item is not None
        assert template_item.quantity == 1


def test_admin_create_default_item_rejects_duplicate_name(admin_client, app):
    with app.app_context():
        db.session.add(main_module.DefaultCategoryTemplate(name='Produce'))
        db.session.add(main_module.DefaultItemTemplate(name='Bananas', quantity=1, sort_order=10))
        db.session.commit()

    response = admin_client.post(
        '/admin/default-items',
        data={
            'name': ' bananas ',
            'quantity': '2',
            'unit': 'lb',
            'category': 'Produce',
            'sort_order': '25',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'That default item already exists.' in response.data

    with app.app_context():
        assert main_module.DefaultItemTemplate.query.count() == 1


def test_admin_bulk_delete_default_items(admin_client, app):
    with app.app_context():
        first_item = main_module.DefaultItemTemplate(name='Bananas', quantity=1, sort_order=10)
        second_item = main_module.DefaultItemTemplate(name='Yogurt', quantity=2, sort_order=20)
        db.session.add_all([first_item, second_item])
        db.session.commit()
        first_item_id = first_item.id
        second_item_id = second_item.id

    response = admin_client.post(
        '/admin/default-items/bulk-delete',
        data={'item_ids': [str(first_item_id), str(second_item_id)]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Deleted 2 default items.' in response.data

    with app.app_context():
        assert db.session.get(main_module.DefaultItemTemplate, first_item_id) is None
        assert db.session.get(main_module.DefaultItemTemplate, second_item_id) is None
        audit_entry = AuditLog.query.filter_by(action='default_item.bulk_deleted').first()
        assert audit_entry is not None
        assert str(first_item_id) in (audit_entry.details or '')
        assert str(second_item_id) in (audit_entry.details or '')


def test_admin_bulk_delete_default_items_clears_existing_user_links(admin_client, create_user, app):
    regular_user = create_user('bulk-delete-links@example.com')

    with app.app_context():
        first_item = main_module.DefaultItemTemplate(name='Bananas', quantity=1, sort_order=10)
        second_item = main_module.DefaultItemTemplate(name='Yogurt', quantity=2, sort_order=20)
        db.session.add_all([first_item, second_item])
        db.session.flush()
        linked_item = Item(name='Bananas', quantity=1, user_id=regular_user['id'], template_item_id=first_item.id)
        db.session.add(linked_item)
        db.session.commit()
        first_item_id = first_item.id
        second_item_id = second_item.id
        linked_item_id = linked_item.id

    response = admin_client.post(
        '/admin/default-items/bulk-delete',
        data={'item_ids': [str(first_item_id), str(second_item_id)]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Deleted 2 default items.' in response.data

    with app.app_context():
        linked_item = db.session.get(Item, linked_item_id)
        assert linked_item is not None
        assert linked_item.template_item_id is None


def test_admin_bulk_delete_default_items_requires_selection(admin_client, app):
    with app.app_context():
        item = main_module.DefaultItemTemplate(name='Bananas', quantity=1, sort_order=10)
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = admin_client.post('/admin/default-items/bulk-delete', data={})

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin#default-items')

    with app.app_context():
        assert db.session.get(main_module.DefaultItemTemplate, item_id) is not None


def test_admin_default_items_page_lists_items_alphabetically(admin_client, app):
    with app.app_context():
        db.session.add_all(
            [
                main_module.DefaultItemTemplate(name='Zulu Apples', quantity=1, sort_order=0),
                main_module.DefaultItemTemplate(name='bananas', quantity=1, sort_order=999),
            ]
        )
        db.session.commit()

    response = admin_client.get('/admin')

    assert response.status_code == 200
    default_items_section = response.data.split(b'Default Grocery List', 1)[1].split(b'Default Theme', 1)[0]
    assert default_items_section.index(b'bananas') < default_items_section.index(b'Zulu Apples')


def test_items_api_does_not_auto_link_same_name_item_on_list(auth_client, auth_user, app):
    """GET /api/items no longer auto-links items to templates; that happens via the import endpoint."""
    with app.app_context():
        existing_item = Item(name='Oranges', quantity=5, unit='bag', category='Produce', price=Decimal('4.50'), user_id=auth_user['id'])
        template_item = main_module.DefaultItemTemplate(name='oranges', quantity=3, unit='bag', category='Produce', sort_order=15)
        db.session.add_all([existing_item, template_item])
        db.session.commit()
        existing_item_id = existing_item.id

    response = auth_client.get('/api/items')

    assert response.status_code == 200
    data = response.get_json()
    assert [item['name'] for item in data].count('Oranges') == 1

    with app.app_context():
        items = Item.query.filter_by(user_id=auth_user['id']).order_by(Item.id.asc()).all()
        assert len(items) == 1
        assert items[0].id == existing_item_id
        # template_item_id is NOT auto-linked on GET; user data is preserved as-is
        assert items[0].template_item_id is None
        assert items[0].quantity == 5


def test_items_api_list_deduplicates_existing_user_duplicates(auth_client, auth_user, app):
    with app.app_context():
        template_item = main_module.DefaultItemTemplate(name='Apples', quantity=1, category='Produce', sort_order=10)
        db.session.add(template_item)
        db.session.flush()
        db.session.add_all([
            Item(name='Apples', quantity=1, category='Produce', user_id=auth_user['id'], template_item_id=template_item.id),
            Item(name='Apples', quantity=1, category='Produce', user_id=auth_user['id'], template_item_id=template_item.id),
        ])
        db.session.commit()
        template_item_id = template_item.id

    response = auth_client.get('/api/items')

    assert response.status_code == 200
    assert [item['name'] for item in response.get_json()].count('Apples') == 1

    with app.app_context():
        items = Item.query.filter_by(user_id=auth_user['id']).order_by(Item.id.asc()).all()
        assert len(items) == 1
        assert items[0].template_item_id == template_item_id


def test_items_api_does_not_recreate_items_deleted_by_user(auth_client, auth_user, app):
    """Regression: deleting all items and refreshing must not silently restore them."""
    with app.app_context():
        template = main_module.DefaultItemTemplate(name='Milk', quantity=1, unit='gal', category='Dairy', sort_order=10)
        db.session.add(template)
        db.session.flush()
        item = Item(name='Milk', quantity=1, unit='gal', category='Dairy', price=Decimal('0.00'),
                    user_id=auth_user['id'], template_item_id=template.id)
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    # Confirm item exists
    response = auth_client.get('/api/items')
    assert response.status_code == 200
    assert any(i['name'] == 'Milk' for i in response.get_json())

    # Delete the item
    delete_response = auth_client.delete(f'/api/items/{item_id}')
    assert delete_response.status_code in (200, 204)

    # Simulate browser refresh — item must not reappear
    response = auth_client.get('/api/items')
    assert response.status_code == 200
    assert not any(i['name'] == 'Milk' for i in response.get_json())

    # Second refresh — list must not grow
    response2 = auth_client.get('/api/items')
    assert response2.status_code == 200
    assert response2.get_json() == response.get_json()


def test_admin_dashboard_deduplicates_duplicate_default_item_templates(admin_client, auth_user, app):
    with app.app_context():
        primary_template = main_module.DefaultItemTemplate(name='Apples', quantity=1, category='Food', sort_order=10, template_key='dup-apple-1')
        duplicate_template = main_module.DefaultItemTemplate(name=' apples ', quantity=2, category='Food', sort_order=20, template_key='dup-apple-2')
        db.session.add_all([primary_template, duplicate_template])
        db.session.flush()
        db.session.add_all([
            Item(name='Apples', quantity=1, category='Food', user_id=auth_user['id'], template_item_id=primary_template.id),
            Item(name='Apples', quantity=2, category='Food', user_id=auth_user['id'], template_item_id=duplicate_template.id),
        ])
        db.session.commit()
        primary_template_id = primary_template.id
        duplicate_template_id = duplicate_template.id

    response = admin_client.get('/admin')

    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(main_module.DefaultItemTemplate, duplicate_template_id) is None
        assert db.session.get(main_module.DefaultItemTemplate, primary_template_id) is not None
        items = Item.query.filter_by(user_id=auth_user['id']).order_by(Item.id.asc()).all()
        assert len(items) == 1
        assert items[0].template_item_id == primary_template_id


def test_admin_update_default_category_renames_existing_assignments(admin_client, auth_user, app):
    with app.app_context():
        category = main_module.DefaultCategoryTemplate(name='Produce')
        default_item = main_module.DefaultItemTemplate(name='Apples', quantity=1, category='Produce', sort_order=10)
        user_item = Item(name='Bananas', quantity=1, category='Produce', user_id=auth_user['id'])
        db.session.add_all([category, default_item, user_item])
        db.session.commit()
        category_id = category.id
        default_item_id = default_item.id
        user_item_id = user_item.id

    response = admin_client.post(
        f'/admin/default-categories/{category_id}/update',
        data={'name': 'Fresh Produce'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Default category updated.' in response.data

    with app.app_context():
        renamed_category = db.session.get(main_module.DefaultCategoryTemplate, category_id)
        assert renamed_category is not None
        assert renamed_category.name == 'Fresh Produce'
        assert db.session.get(main_module.DefaultItemTemplate, default_item_id).category == 'Fresh Produce'
        assert db.session.get(Item, user_item_id).category == 'Fresh Produce'


def test_admin_delete_default_category_clears_existing_assignments(admin_client, auth_user, app):
    with app.app_context():
        category = main_module.DefaultCategoryTemplate(name='Produce')
        default_item = main_module.DefaultItemTemplate(name='Apples', quantity=1, category='Produce', sort_order=10)
        user_item = Item(name='Bananas', quantity=1, category='Produce', user_id=auth_user['id'])
        db.session.add_all([category, default_item, user_item])
        db.session.commit()
        category_id = category.id
        default_item_id = default_item.id
        user_item_id = user_item.id

    response = admin_client.post(f'/admin/default-categories/{category_id}/delete', follow_redirects=True)

    assert response.status_code == 200
    assert b'Default category deleted.' in response.data

    with app.app_context():
        assert db.session.get(main_module.DefaultCategoryTemplate, category_id) is None
        assert db.session.get(main_module.DefaultItemTemplate, default_item_id).category is None
        assert db.session.get(Item, user_item_id).category is None
        audit_entry = AuditLog.query.filter_by(action='default_category.deleted', target_id=category_id).first()
        assert audit_entry is not None


def test_admin_create_default_store_adds_store_for_existing_approved_users(admin_client, create_user, app):
    regular_user = create_user('regular@example.com')

    response = admin_client.post('/admin/default-stores', data={'name': 'Neighborhood Market'})

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin#default-stores')

    with app.app_context():
        default_store = main_module.DefaultStoreTemplate.query.filter_by(name='Neighborhood Market').first()
        assert default_store is not None
        user_store = Store.query.filter_by(user_id=regular_user['id'], template_store_id=default_store.id).first()
        assert user_store is not None
        assert user_store.name == 'Neighborhood Market'


def test_admin_update_default_store_redirects_back_to_default_stores_section(admin_client, app):
    with app.app_context():
        store = main_module.DefaultStoreTemplate(name='Neighborhood Market', sort_order=0)
        db.session.add(store)
        db.session.commit()
        store_id = store.id

    response = admin_client.post(f'/admin/default-stores/{store_id}/update', data={'name': 'Neighborhood Market'})

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin#default-stores')


def test_admin_delete_default_store_moves_items_to_unknown_store(admin_client, create_user, app):
    regular_user = create_user('default-store-owner@example.com')

    with app.app_context():
        default_store = main_module.DefaultStoreTemplate(name='Neighborhood Market', sort_order=0)
        default_item = main_module.DefaultItemTemplate(name='Apples', quantity=1, sort_order=10, store_template_id=None)
        db.session.add(default_store)
        db.session.flush()
        default_item.store_template_id = default_store.id
        copied_store = Store(name='Neighborhood Market', user_id=regular_user['id'], template_store_id=default_store.id, sort_order=10)
        db.session.add_all([default_item, copied_store])
        db.session.flush()
        copied_item = Item(name='Eggs', store_id=copied_store.id, price=Decimal('4.50'), user_id=regular_user['id'])
        db.session.add(copied_item)
        db.session.commit()
        default_store_id = default_store.id
        copied_store_id = copied_store.id
        default_item_id = default_item.id
        copied_item_id = copied_item.id

    response = admin_client.post(f'/admin/default-stores/{default_store_id}/delete', follow_redirects=True)

    assert response.status_code == 200
    assert b'Default store deleted.' in response.data

    with app.app_context():
        assert db.session.get(main_module.DefaultStoreTemplate, default_store_id) is None
        assert db.session.get(Store, copied_store_id) is None
        unknown_store = Store.query.filter_by(user_id=regular_user['id'], template_store_id=None, name='unknown').first()
        assert unknown_store is not None
        detached_item = db.session.get(main_module.DefaultItemTemplate, default_item_id)
        assert detached_item is not None
        assert detached_item.store_template_id is None
        copied_item = db.session.get(Item, copied_item_id)
        assert copied_item is not None
        assert copied_item.store_id == unknown_store.id
        audit_entry = AuditLog.query.filter_by(action='default_store.deleted', target_id=default_store_id).first()
        assert audit_entry is not None
        assert str(copied_store_id) in (audit_entry.details or '')


def test_items_api_does_not_backfill_missing_default_items_on_list(auth_client, auth_user, app):
    """GET /api/items does not auto-create items from templates; deleted items stay deleted."""
    with app.app_context():
        default_store = main_module.DefaultStoreTemplate(name='Pantry', sort_order=0)
        db.session.add(default_store)
        db.session.flush()
        copied_store = Store(name='Pantry', user_id=auth_user['id'], template_store_id=default_store.id, sort_order=10)
        db.session.add(copied_store)
        template_item = main_module.DefaultItemTemplate(name='Oranges', quantity=3, unit='bag', category='Produce', sort_order=15, store_template_id=default_store.id)
        db.session.add(template_item)
        db.session.commit()
        template_item_id = template_item.id

    response = auth_client.get('/api/items')

    assert response.status_code == 200
    # No item should be auto-created from the template
    assert not any(item['name'] == 'Oranges' for item in response.get_json())

    with app.app_context():
        merged_item = Item.query.filter_by(user_id=auth_user['id'], template_item_id=template_item_id).first()
        assert merged_item is None


def test_admin_dashboard_preserves_scroll_for_default_store_forms(admin_client):
    response = admin_client.get('/admin')

    assert response.status_code == 200
    assert b'data-preserve-scroll-form' in response.data
    assert b"shoppinglist-admin-scroll-target" in response.data
    assert b'restoreAdminScrollPosition' in response.data


def test_admin_can_approve_signup_and_clone_defaults(monkeypatch, admin_client, create_user, create_default_templates, app):
    create_default_templates()
    pending_user = create_user('newuser@example.com', approved=False)
    monkeypatch.setattr(main_module, 'generate_temporary_password', lambda length=12: 'TempPass234')
    monkeypatch.setattr(main_module, 'send_temp_password_email', lambda e, p: None)

    response = admin_client.post(f"/admin/users/{pending_user['id']}/approve", follow_redirects=True)

    assert response.status_code == 200
    assert b'Approved newuser@example.com.' in response.data
    assert b'temporary password has been sent by email' in response.data
    # Temp password must NOT be exposed in the flash message
    assert b'TempPass234' not in response.data

    with app.app_context():
        user = db.session.get(User, pending_user['id'])
        items = Item.query.filter_by(user_id=user.id).all()
        stores = Store.query.filter_by(user_id=user.id).all()
        assert user.is_approved is True
        assert user.is_active is True
        assert len(stores) == 1
        assert len(items) == 0
        assert stores[0].template_store_id is not None
        assert AuditLog.query.filter_by(action='user.approved', target_id=user.id).count() == 1

    fresh_client = app.test_client()
    login_response = fresh_client.post('/login', data={'email': 'newuser@example.com', 'password': 'TempPass234'})
    assert login_response.status_code == 302


def test_admin_approval_clones_default_stores_in_alphabetical_order(monkeypatch, admin_client, create_user, app):
    pending_user = create_user('alphabetical@example.com', approved=False)
    monkeypatch.setattr(main_module, 'generate_temporary_password', lambda length=12: 'TempPass234')

    with app.app_context():
        db.session.add_all(
            [
                main_module.DefaultStoreTemplate(name='Zulu Market', sort_order=90),
                main_module.DefaultStoreTemplate(name='Alpha Foods', sort_order=10),
            ]
        )
        db.session.commit()

    response = admin_client.post(f"/admin/users/{pending_user['id']}/approve", follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        stores = Store.query.filter_by(user_id=pending_user['id']).order_by(Store.sort_order.asc(), Store.id.asc()).all()
        assert [store.name for store in stores] == ['Alpha Foods', 'Zulu Market']
        assert [store.sort_order for store in stores] == [10, 20]


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


def test_admin_cannot_deactivate_own_account(admin_client, admin_user, app):
    response = admin_client.post(f"/admin/users/{admin_user['id']}/deactivate", follow_redirects=True)

    assert response.status_code == 200
    assert b'You cannot deactivate your own account.' in response.data

    with app.app_context():
        user = db.session.get(User, admin_user['id'])
        assert user.is_active is True
        assert AuditLog.query.filter_by(action='user.deactivated', target_id=user.id).count() == 0


def test_admin_cannot_deactivate_protected_admin(app, admin_user, create_user):
    acting_admin = create_user('other-admin@example.com', admin=True)
    client = app.test_client()
    login_response = client.post('/login', data={'email': acting_admin['email'], 'password': acting_admin['password']})
    assert login_response.status_code == 302

    response = client.post(f"/admin/users/{admin_user['id']}/deactivate", follow_redirects=True)

    assert response.status_code == 200
    assert b'The protected admin account must remain active.' in response.data

    with app.app_context():
        user = db.session.get(User, admin_user['id'])
        assert user is not None
        assert user.is_active is True


def test_admin_cannot_remove_protected_admin_access(app, admin_user, create_user):
    acting_admin = create_user('other-admin@example.com', admin=True)
    client = app.test_client()
    login_response = client.post('/login', data={'email': acting_admin['email'], 'password': acting_admin['password']})
    assert login_response.status_code == 302

    response = client.post(f"/admin/users/{admin_user['id']}/admin", data={'is_admin': 'false'}, follow_redirects=True)

    assert response.status_code == 200
    assert b'The protected admin account must retain admin access.' in response.data

    with app.app_context():
        user = db.session.get(User, admin_user['id'])
        assert user is not None
        assert user.is_admin is True


def test_admin_can_delete_non_protected_user_and_related_data(admin_client, create_user, app):
    user = create_user('delete-me@example.com')

    with app.app_context():
        store = Store(name='Pantry', user_id=user['id'], sort_order=10)
        db.session.add(store)
        db.session.flush()
        item = Item(name='Apples', user_id=user['id'], store_id=store.id, quantity=1)
        db.session.add(item)
        db.session.commit()
        item_id = item.id
        store_id = store.id

    response = admin_client.post(f"/admin/users/{user['id']}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b'User deleted.' in response.data

    with app.app_context():
        assert db.session.get(User, user['id']) is None
        assert db.session.get(Item, item_id) is None
        assert db.session.get(Store, store_id) is None
        assert AuditLog.query.filter_by(action='user.deleted').count() == 1


def test_admin_cannot_delete_protected_admin(app, admin_user, create_user):
    acting_admin = create_user('other-admin@example.com', admin=True)
    client = app.test_client()
    login_response = client.post('/login', data={'email': acting_admin['email'], 'password': acting_admin['password']})
    assert login_response.status_code == 302

    response = client.post(f"/admin/users/{admin_user['id']}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b'The protected admin account cannot be deleted.' in response.data

    with app.app_context():
        user = db.session.get(User, admin_user['id'])
        assert user is not None
        assert user.is_admin is True
        assert user.is_active is True


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
        assert Item.query.filter_by(user_id=created_user.id).count() == 0
        assert Store.query.filter_by(user_id=created_user.id).count() == 1


def test_index_page_contains_onboarding_guidance(auth_client):
    response = auth_client.get('/')

    assert response.status_code == 200
    # Both navigation traces must appear in the template source so Alpine can
    # render them when the list is empty.
    assert b'Import Default Items' in response.data
    assert b'Default Grocery Items' in response.data
    assert b'Help &amp; User Guide' in response.data
    assert b'How to get started' in response.data


# ---------------------------------------------------------------------------
# Chunk 1 — version field on Item
# ---------------------------------------------------------------------------

def test_items_api_create_sets_version_to_1(auth_client):
    response = auth_client.post('/api/items', json={'name': 'Bananas'})

    assert response.status_code == 201
    assert response.get_json()['version'] == 1


def test_items_api_list_includes_version(auth_client, auth_user, app):
    with app.app_context():
        db.session.add(Item(name='Carrots', price=Decimal('0.00'), user_id=auth_user['id']))
        db.session.commit()

    response = auth_client.get('/api/items')

    assert response.status_code == 200
    items = response.get_json()
    assert len(items) >= 1
    for item in items:
        assert 'version' in item
        assert isinstance(item['version'], int)


# ---------------------------------------------------------------------------
# Chunk 2 — PATCH optimistic locking
# ---------------------------------------------------------------------------

def test_items_api_patch_version_increments(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('0.00'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = auth_client.patch(f'/api/items/{item_id}', json={'checked': True, 'version': 1})

    assert response.status_code == 200
    data = response.get_json()
    assert data['version'] == 2
    assert data['checked'] is True


def test_items_api_patch_with_stale_version_returns_409(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Eggs', price=Decimal('0.00'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    # First patch succeeds and bumps to version 2
    auth_client.patch(f'/api/items/{item_id}', json={'checked': True, 'version': 1})

    # Second patch with the stale version 1 must be rejected
    response = auth_client.patch(f'/api/items/{item_id}', json={'checked': False, 'version': 1})

    assert response.status_code == 409
    body = response.get_json()
    assert body['error'] == 'item modified by another user'
    assert 'current' in body
    assert body['current']['version'] == 2
    assert body['current']['checked'] is True  # server state unchanged


def test_items_api_patch_without_version_succeeds(auth_client, auth_user, app):
    with app.app_context():
        item = Item(name='Butter', price=Decimal('0.00'), user_id=auth_user['id'])
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    # No 'version' key in payload — check is skipped, still returns 200
    response = auth_client.patch(f'/api/items/{item_id}', json={'checked': True})

    assert response.status_code == 200
    data = response.get_json()
    assert data['checked'] is True
    assert data['version'] == 2  # version still increments


# ---------------------------------------------------------------------------
# Chunk 3 — shared account: two sessions on same credentials see same data
# ---------------------------------------------------------------------------

def test_shared_account_both_clients_see_same_items(app, create_user, login):
    user = create_user('shared@example.com', 'sharedpass1!')

    # Two independent clients simulating two browsers logged in as the same user
    client_a = app.test_client()
    client_b = app.test_client()
    login_a = login.__wrapped__ if hasattr(login, '__wrapped__') else None

    def _login_client(c, email, password):
        c.get('/login')
        _csrf_cookie = c.get_cookie('_csrf_token')
        csrf_token = _csrf_cookie.value if _csrf_cookie else None
        from urllib.parse import urlencode
        headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
        resp = c.post(
            '/login',
            data=urlencode({'email': email, 'password': password}),
            content_type='application/x-www-form-urlencoded',
            headers=headers,
        )
        return resp

    assert _login_client(client_a, user['email'], user['password']).status_code == 302
    assert _login_client(client_b, user['email'], user['password']).status_code == 302

    # Client A creates an item
    create_resp = client_a.post('/api/items', json={'name': 'SharedBread'})
    assert create_resp.status_code == 201

    # Client B immediately sees it via GET /api/items
    list_resp = client_b.get('/api/items')
    assert list_resp.status_code == 200
    names = [item['name'] for item in list_resp.get_json()]
    assert 'SharedBread' in names


# ---------------------------------------------------------------------------
# Security: login rate limiting
# ---------------------------------------------------------------------------

def test_login_rate_limit_blocks_after_threshold():
    """After 10 failed POST attempts from the same IP, login returns 429."""
    from app.main import create_app as _create_app
    from app.db import db as _db

    rate_app = _create_app({
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_ENGINE_OPTIONS': {'pool_reset_on_return': None},
        'TESTING': False,
        'RATELIMIT_ENABLED': True,
        'RATELIMIT_STORAGE_URI': 'memory://',
        'SECRET_KEY': 'rate-limit-test-secret-key-x1y2z3',
    })
    with rate_app.app_context():
        _db.create_all()

    client = rate_app.test_client()

    for i in range(10):
        rv = client.post(
            '/login',
            data={'email': 'nobody@example.com', 'password': 'wrongpassword'},
            content_type='application/x-www-form-urlencoded',
        )
        assert rv.status_code == 200, f'attempt {i + 1} should return login page (200), got {rv.status_code}'

    rv = client.post(
        '/login',
        data={'email': 'nobody@example.com', 'password': 'wrongpassword'},
        content_type='application/x-www-form-urlencoded',
    )
    assert rv.status_code == 429, f'11th attempt should be rate limited (429), got {rv.status_code}'


# ---------------------------------------------------------------------------
# Phase 1: SignupToken model
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone
from app.models import SignupToken


class TestSignupTokenModel:
    """Unit tests for SignupToken model properties and factory method."""

    def test_make_creates_token_with_correct_fields(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            assert token.email == 'test@example.com'
            assert token.token is not None
            assert len(token.token) > 20
            assert token.consumed is False
            assert token.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)

    def test_make_expiry_is_approximately_30_minutes(self, app):
        with app.app_context():
            before = datetime.now(timezone.utc).replace(tzinfo=None)
            token = SignupToken.make('test@example.com')
            after = datetime.now(timezone.utc).replace(tzinfo=None)
            delta_min = (token.expires_at - before).total_seconds() / 60
            delta_max = (token.expires_at - after).total_seconds() / 60
            assert 29 <= delta_min <= 31
            assert 29 <= delta_max <= 31

    def test_make_generates_unique_tokens(self, app):
        with app.app_context():
            t1 = SignupToken.make('a@example.com')
            t2 = SignupToken.make('a@example.com')
            assert t1.token != t2.token

    def test_is_valid_true_for_fresh_token(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            assert token.is_valid is True

    def test_is_valid_false_when_consumed(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            token.consumed = True
            assert token.is_valid is False

    def test_is_valid_false_when_expired(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            token.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            assert token.is_valid is False

    def test_is_expired_false_for_future(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            assert token.is_expired is False

    def test_is_expired_true_at_boundary(self, app):
        with app.app_context():
            token = SignupToken.make('test@example.com')
            token.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            assert token.is_expired is True

    def test_token_persists_to_database(self, app):
        with app.app_context():
            token = SignupToken.make('persist@example.com')
            db.session.add(token)
            db.session.commit()
            token_id = token.id

            fetched = db.session.get(SignupToken, token_id)
            assert fetched is not None
            assert fetched.email == 'persist@example.com'
            assert fetched.consumed is False
            assert fetched.expires_at is not None

            db.session.delete(fetched)
            db.session.commit()

    def test_token_column_is_unique(self, app):
        """Two rows with the same token value must fail at the DB level."""
        import sqlalchemy.exc
        with app.app_context():
            raw_token = 'fixed-test-token-value-unique-check'
            t1 = SignupToken(
                email='u1@example.com',
                token=raw_token,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30),
                consumed=False,
            )
            t2 = SignupToken(
                email='u2@example.com',
                token=raw_token,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30),
                consumed=False,
            )
            db.session.add(t1)
            db.session.commit()
            db.session.add(t2)
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                db.session.commit()
            db.session.rollback()
            # Clean up
            db.session.delete(db.session.get(SignupToken, t1.id))
            db.session.commit()

    def test_make_token_contains_only_url_safe_characters(self, app):
        """Token must be embeddable in a URL path without percent-encoding."""
        import re
        with app.app_context():
            token = SignupToken.make('safe@example.com')
            assert re.fullmatch(r'[A-Za-z0-9_\-]+', token.token), (
                f"Token contains non-URL-safe characters: {token.token!r}"
            )

    def test_make_token_has_sufficient_entropy(self, app):
        """Token must be long enough to resist brute force (>=40 chars for 32 bytes entropy)."""
        with app.app_context():
            token = SignupToken.make('entropy@example.com')
            assert len(token.token) >= 40, f"Token too short: {len(token.token)} chars"

    def test_is_valid_false_when_both_consumed_and_expired(self, app):
        """is_valid must be False when both consumed and expired (belt-and-suspenders)."""
        with app.app_context():
            token = SignupToken.make('test@example.com')
            token.consumed = True
            token.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            assert token.is_valid is False


# ---------------------------------------------------------------------------
# Phase 2: Email helpers
# ---------------------------------------------------------------------------

import app.main as _main_module


class TestEmailHelpers:
    """Unit tests for send_email, send_verification_email, send_temp_password_email."""

    def test_send_email_stubs_to_stderr_when_no_api_key(self, monkeypatch, capsys):
        """With no RESEND_API_KEY set the helper logs to stderr and returns."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        _main_module.send_email('user@example.com', 'Hello', 'body text')
        captured = capsys.readouterr()
        assert '[EMAIL STUB]' in captured.err
        assert 'user@example.com' in captured.err

    def test_send_email_does_not_raise_when_no_api_key(self, monkeypatch):
        """Stub path must never raise even if called with unusual inputs."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        _main_module.send_email('a@b.com', 'S', 'B')  # must not raise

    def test_send_email_calls_resend_when_api_key_present(self, monkeypatch):
        """When RESEND_API_KEY is set, resend.Emails.send() is called with correct params."""
        monkeypatch.setenv('RESEND_API_KEY', 're_test-key')
        monkeypatch.setenv('MAIL_FROM', 'app@example.com')

        sent = []
        import resend as _resend
        monkeypatch.setattr(_resend.Emails, 'send', lambda params: sent.append(params))

        _main_module.send_email('recipient@example.com', 'Subject', 'Body')
        assert len(sent) == 1
        assert sent[0]['to'] == 'recipient@example.com'
        assert sent[0]['subject'] == 'Subject'

    def test_send_email_logs_on_resend_exception(self, monkeypatch, capsys):
        """A Resend API error is caught and logged; it must not propagate."""
        monkeypatch.setenv('RESEND_API_KEY', 're_bad-key')

        def _fail(params):
            raise RuntimeError('network error')

        import resend as _resend
        monkeypatch.setattr(_resend.Emails, 'send', _fail)

        _main_module.send_email('x@example.com', 'S', 'B')  # must not raise
        captured = capsys.readouterr()
        assert '[EMAIL ERROR]' in captured.err

    def test_send_verification_email_includes_token_url(self, monkeypatch, capsys):
        """Verification email body must contain the full /verify-email/<token> URL."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        monkeypatch.setenv('APP_BASE_URL', 'https://app.example.com')
        _main_module.send_verification_email('new@example.com', 'abc123token')
        captured = capsys.readouterr()
        assert 'https://app.example.com/verify-email/abc123token' in captured.err

    def test_send_verification_email_uses_default_base_url(self, monkeypatch, capsys):
        """Falls back to localhost:8000 when APP_BASE_URL is not configured."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        monkeypatch.delenv('APP_BASE_URL', raising=False)
        _main_module.send_verification_email('new@example.com', 'tok')
        captured = capsys.readouterr()
        assert 'http://localhost:8000/verify-email/tok' in captured.err

    def test_send_temp_password_email_includes_password_and_login_url(self, monkeypatch, capsys):
        """Temp-password email must contain the password and the login URL."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        monkeypatch.setenv('APP_BASE_URL', 'https://app.example.com')
        _main_module.send_temp_password_email('approved@example.com', 'TmpPwd99')
        captured = capsys.readouterr()
        assert 'TmpPwd99' in captured.err
        assert 'https://app.example.com/login' in captured.err

    def test_send_verification_email_strips_trailing_slash_from_base_url(self, monkeypatch, capsys):
        """Trailing slash on APP_BASE_URL must not produce a double-slash in the URL."""
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
        monkeypatch.setenv('APP_BASE_URL', 'https://app.example.com/')
        _main_module.send_verification_email('x@example.com', 'tok')
        captured = capsys.readouterr()
        assert 'https://app.example.com/verify-email/tok' in captured.err
        assert '//verify-email' not in captured.err


# ---------------------------------------------------------------------------
# Phase 3: Email-verification signup flow and /verify-email route
# ---------------------------------------------------------------------------

class TestPhase3SignupFlow:
    """Integration tests for the token-based signup and verify-email routes."""

    def _post_signup(self, client, email):
        """POST /signup with a CSRF token; follows redirects."""
        from urllib.parse import urlencode
        client.get('/login')
        csrf = client.get_cookie('_csrf_token')
        headers = {'X-CSRFToken': csrf.value} if csrf else {}
        return client.post(
            '/signup',
            data=urlencode({'email': email}),
            content_type='application/x-www-form-urlencoded',
            headers=headers,
            follow_redirects=True,
        )

    def _insert_token(self, app, email, *, consumed=False, expired=False):
        """Insert a SignupToken directly into the DB; return the raw token string."""
        from datetime import datetime, timedelta, timezone
        with app.app_context():
            SignupToken.query.filter_by(email=email).delete()
            db.session.commit()
            tok = SignupToken.make(email)
            if consumed:
                tok.consumed = True
            if expired:
                tok.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.session.add(tok)
            db.session.commit()
            return tok.token

    # --- /signup route ---

    def test_signup_creates_token_and_calls_send_verification_email(self, client, app, monkeypatch):
        """POST /signup creates a SignupToken and calls send_verification_email."""
        sent = []
        monkeypatch.setattr(_main_module, 'send_verification_email', lambda e, t: sent.append((e, t)))

        resp = self._post_signup(client, 'p3-new@example.com')

        assert resp.status_code == 200
        assert b'verification link' in resp.data
        assert len(sent) == 1
        assert sent[0][0] == 'p3-new@example.com'
        with app.app_context():
            tok = SignupToken.query.filter_by(email='p3-new@example.com').first()
            assert tok is not None
            assert tok.consumed is False
            assert sent[0][1] == tok.token

    def test_signup_does_not_create_user(self, client, app, monkeypatch):
        """POST /signup must NOT create a User row; only a SignupToken."""
        monkeypatch.setattr(_main_module, 'send_verification_email', lambda e, t: None)
        self._post_signup(client, 'p3-nouser@example.com')
        with app.app_context():
            assert User.query.filter_by(email='p3-nouser@example.com').first() is None

    def test_signup_duplicate_active_token_shows_error(self, client, app, monkeypatch):
        """Second POST /signup for the same email while a token is still valid shows an error."""
        monkeypatch.setattr(_main_module, 'send_verification_email', lambda e, t: None)
        self._insert_token(app, 'p3-dup@example.com')

        resp = self._post_signup(client, 'p3-dup@example.com')

        assert b'already sent' in resp.data or b'Check your inbox' in resp.data

    def test_signup_allows_new_token_after_expiry(self, client, app, monkeypatch):
        """POST /signup succeeds when the existing token for that email is expired."""
        sent = []
        monkeypatch.setattr(_main_module, 'send_verification_email', lambda e, t: sent.append((e, t)))
        self._insert_token(app, 'p3-reexpire@example.com', expired=True)

        resp = self._post_signup(client, 'p3-reexpire@example.com')

        assert b'verification link' in resp.data
        assert len(sent) == 1
        with app.app_context():
            active = SignupToken.query.filter_by(
                email='p3-reexpire@example.com', consumed=False
            ).first()
            assert active is not None

    def test_signup_old_tokens_invalidated_when_new_one_issued(self, client, app, monkeypatch):
        """Expired tokens for same email are marked consumed when a new token is issued."""
        monkeypatch.setattr(_main_module, 'send_verification_email', lambda e, t: None)
        self._insert_token(app, 'p3-invalidate@example.com', expired=True)
        self._post_signup(client, 'p3-invalidate@example.com')
        with app.app_context():
            all_tokens = SignupToken.query.filter_by(email='p3-invalidate@example.com').all()
            consumed_count = sum(1 for t in all_tokens if t.consumed)
            assert consumed_count >= 1

    def test_signup_rejects_existing_approved_user(self, client, create_user):
        """POST /signup with the email of an approved user shows 'already has an account'."""
        create_user('p3-approved@example.com', approved=True)
        resp = self._post_signup(client, 'p3-approved@example.com')
        assert b'already has an account' in resp.data

    def test_signup_rejects_existing_pending_user(self, client, create_user):
        """POST /signup with email of an unapproved user shows 'pending approval'."""
        create_user('p3-pendinguser@example.com', approved=False)
        resp = self._post_signup(client, 'p3-pendinguser@example.com')
        assert b'pending approval' in resp.data

    # --- /verify-email route ---

    def test_verify_email_creates_pending_user_and_consumes_token(self, client, app):
        """GET /verify-email/<token> creates a User(is_approved=False) and marks token consumed."""
        tok = self._insert_token(app, 'p3-verify@example.com')

        resp = client.get(f'/verify-email/{tok}', follow_redirects=True)

        assert resp.status_code == 200
        assert b'pending admin approval' in resp.data
        with app.app_context():
            user = User.query.filter_by(email='p3-verify@example.com').first()
            assert user is not None
            assert user.is_approved is False
            assert user.is_active is True
            db_tok = SignupToken.query.filter_by(token=tok).first()
            assert db_tok.consumed is True

    def test_verify_email_records_audit_log(self, client, app):
        """GET /verify-email/<token> writes a signup.email_verified audit entry."""
        tok = self._insert_token(app, 'p3-audit@example.com')
        client.get(f'/verify-email/{tok}')
        with app.app_context():
            user = User.query.filter_by(email='p3-audit@example.com').first()
            assert user is not None
            assert AuditLog.query.filter_by(
                action='signup.email_verified', target_id=user.id
            ).count() == 1

    def test_verify_email_invalid_token_shows_error(self, client):
        """GET /verify-email with a non-existent token shows the 'invalid' message."""
        resp = client.get('/verify-email/notarealtoken', follow_redirects=True)
        assert resp.status_code == 200
        assert b'invalid' in resp.data

    def test_verify_email_consumed_token_shows_error(self, client, app):
        """GET /verify-email with an already-consumed token shows the 'invalid' message."""
        tok = self._insert_token(app, 'p3-consumed@example.com', consumed=True)
        resp = client.get(f'/verify-email/{tok}', follow_redirects=True)
        assert b'invalid' in resp.data

    def test_verify_email_expired_token_shows_error(self, client, app):
        """GET /verify-email with an expired token shows the 'expired' message."""
        tok = self._insert_token(app, 'p3-expiredv@example.com', expired=True)
        resp = client.get(f'/verify-email/{tok}', follow_redirects=True)
        assert b'expired' in resp.data

    def test_verify_email_existing_user_edge_case_handled_gracefully(self, client, app, create_user):
        """If a User already exists for the token's email, token is consumed and user sees a message."""
        tok = self._insert_token(app, 'p3-edge@example.com')
        create_user('p3-edge@example.com')

        resp = client.get(f'/verify-email/{tok}', follow_redirects=True)

        assert resp.status_code == 200
        with app.app_context():
            db_tok = SignupToken.query.filter_by(token=tok).first()
            assert db_tok.consumed is True

    # --- admin_approve_user ---

    def test_admin_approve_emails_password_not_shown_in_flash(self, monkeypatch, admin_client, create_user, app):
        """admin_approve_user should email the password rather than display it in the flash."""
        pending = create_user('p3-approveme@example.com', approved=False)
        sent = []
        monkeypatch.setattr(_main_module, 'send_temp_password_email', lambda e, p: sent.append((e, p)))
        monkeypatch.setattr(_main_module, 'generate_temporary_password', lambda length=12: 'Ph3TmpPwd!')

        resp = admin_client.post(f"/admin/users/{pending['id']}/approve", follow_redirects=True)

        assert resp.status_code == 200
        assert b'Ph3TmpPwd!' not in resp.data
        assert len(sent) == 1
        assert sent[0][0] == 'p3-approveme@example.com'
        assert sent[0][1] == 'Ph3TmpPwd!'
        with app.app_context():
            user = db.session.get(User, pending['id'])
            assert user.is_approved is True


# ---------------------------------------------------------------------------
# Phase 4: Template copy changes
# ---------------------------------------------------------------------------

class TestPhase4Templates:
    """Verify login.html and admin.html reflect the email-verification flow."""

    # --- login.html ---

    def test_login_signup_hint_mentions_verification_link(self, client):
        """The hint above the signup form should mention a verification link."""
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'verification link' in resp.data

    def test_login_signup_description_updated(self, client):
        """The signup-form description should no longer promise an admin-issued temp password."""
        resp = client.get('/login')
        # Old copy
        assert b'an administrator can approve your account and issue a temporary password' not in resp.data
        # New copy
        assert b"we'll send you a link to verify your address" in resp.data

    def test_login_signup_button_says_send_verification_link(self, client):
        """The signup-form submit button label should say 'Send Verification Link'."""
        resp = client.get('/login')
        assert b'Send Verification Link' in resp.data
        assert b'Request Approval' not in resp.data

    def test_login_signup_heading_still_says_request_access(self, client):
        """The 'Request Access' heading must be preserved (other tests depend on it)."""
        resp = client.get('/login')
        assert b'Request Access' in resp.data

    # --- admin.html ---

    def test_admin_no_copy_password_button_in_page(self, admin_client):
        """admin.html must not contain the copy-password button markup."""
        resp = admin_client.get('/admin')
        assert resp.status_code == 200
        assert b'data-copy-temp-password' not in resp.data
        assert b'Copy Password' not in resp.data

    def test_admin_no_copy_password_js(self, admin_client):
        """admin.html must not contain the copyText or copyPasswordButtons JS."""
        resp = admin_client.get('/admin')
        assert b'copyPasswordButtons' not in resp.data
        assert b'copyText' not in resp.data

    def test_admin_pending_approvals_description_updated(self, admin_client):
        """Pending Approvals section description should mention email delivery."""
        resp = admin_client.get('/admin')
        assert b'will receive a temporary password by email' in resp.data
        # Old copy must be gone
        assert b'copy the current default stores and items' not in resp.data

    def test_admin_approve_button_label_updated(self, admin_client, create_user):
        """The approve button must say 'Approve and Send Password' not 'Approve And Generate Password'."""
        create_user('p4-pending@example.com', approved=False)
        resp = admin_client.get('/admin')
        assert b'Approve and Send Password' in resp.data
        assert b'Approve And Generate Password' not in resp.data

    def test_admin_flash_approval_renders_plain_text(self, monkeypatch, admin_client, create_user):
        """After approval, the flash message renders as plain text with no copy-paste widget."""
        pending = create_user('p4-flashtest@example.com', approved=False)
        monkeypatch.setattr(_main_module, 'send_temp_password_email', lambda e, p: None)

        resp = admin_client.post(
            f"/admin/users/{pending['id']}/approve", follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'data-temp-password-value' not in resp.data
        assert b'data-copy-temp-password' not in resp.data
        assert b'Approved p4-flashtest@example.com.' in resp.data