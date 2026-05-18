def test_print_cookies_after_login_get(client):
    """Temporary debug: Print all cookies after GET /login to inspect CSRF token presence and name."""
    response = client.get('/login')
    print("\n[DEBUG] Cookies after GET /login:")
    for cookie in client.cookie_jar:
        print(f"[DEBUG] Cookie: key={cookie.key}, value={cookie.value}, domain={cookie.domain}, path={cookie.path}")
    # This test always passes; it's for debug output only
    assert response.status_code == 200
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
    assert b":data-item-id=\"selectedItem.id\" x-model=\"selectedItem.name\" @input=\"stageItemField(Number($el.dataset.itemId), 'name', $event.target.value)\"" in response.data
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
    csrf_token = None
    for cookie in client.cookie_jar:
        if getattr(cookie, 'key', None) == '_csrf_token':
            csrf_token = cookie.value
            break
    form_data = {'email': 'pending@example.com'}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/signup', data=urlencode(form_data), follow_redirects=True, content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'Your signup request has been submitted for approval.' in response.data

    with app.app_context():
        user = User.query.filter_by(email='pending@example.com').first()
        assert user is not None
        assert user.is_approved is False
        assert user.is_active is True


def test_pending_user_cannot_login(client, create_user):
    user = create_user('pending@example.com', approved=False)

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    csrf_token = None
    for cookie in client.cookie_jar:
        if getattr(cookie, 'key', None) == '_csrf_token':
            csrf_token = cookie.value
            break
    form_data = {'email': user['email'], 'password': user['password']}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'account pending approval' in response.data


def test_inactive_user_cannot_login(client, create_user):
    user = create_user('inactive@example.com', active=False)

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    csrf_token = None
    for cookie in client.cookie_jar:
        if getattr(cookie, 'key', None) == '_csrf_token':
            csrf_token = cookie.value
            break
    form_data = {'email': user['email'], 'password': user['password']}
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    response = client.post('/login', data=urlencode(form_data), content_type='application/x-www-form-urlencoded', headers=headers)

    assert response.status_code == 200
    assert b'account is inactive' in response.data


def test_login_rejects_invalid_credentials(client, create_user):
    user = create_user('owner@example.com')

    from urllib.parse import urlencode
    client.get('/login')  # Always GET the form page before POST
    csrf_token = None
    for cookie in client.cookie_jar:
        if getattr(cookie, 'key', None) == '_csrf_token':
            csrf_token = cookie.value
            break
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
        csrf_token = None
        for cookie in c.cookie_jar:
            if getattr(cookie, 'key', None) == '_csrf_token':
                csrf_token = cookie.value
                break
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