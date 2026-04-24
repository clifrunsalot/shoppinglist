import pytest

from app.db import db
from app.models import DefaultCategoryTemplate, DefaultItemTemplate, DefaultStoreTemplate, Item, Store


def open_detail_panel(page):
    detail_panel = page.get_by_test_id('item-detail-panel')
    if detail_panel.count() == 0:
        page.get_by_test_id('open-detail-panel').click()
    detail_panel.wait_for()
    page.get_by_test_id('detail-tab-advanced').wait_for()


def open_settings(page):
    page.get_by_label('Open settings').click()
    page.get_by_role('heading', name='Settings').wait_for()


@pytest.fixture
def seeded_store_persistence_data(app, create_user):
    user = create_user('browser-user@example.com')

    with app.app_context():
        produce_category = DefaultCategoryTemplate(name='Produce')
        bakery_category = DefaultCategoryTemplate(name='Bakery')
        db.session.add_all([produce_category, bakery_category])
        pantry_template = DefaultStoreTemplate(name='Pantry', sort_order=0)
        market_template = DefaultStoreTemplate(name='Market', sort_order=0)
        db.session.add_all([pantry_template, market_template])
        db.session.flush()

        pantry = Store(name='Pantry', user_id=user['id'], sort_order=10, template_store_id=pantry_template.id)
        market = Store(name='Market', user_id=user['id'], sort_order=20, template_store_id=market_template.id)
        db.session.add_all([pantry, market])
        db.session.flush()

        apples = Item(name='Apples', quantity=1, user_id=user['id'], sort_order=10, store_id=pantry.id)
        bread = Item(name='Bread', quantity=1, user_id=user['id'], sort_order=20, store_id=pantry.id)
        extra_items = [
            Item(name=f'Item {index}', quantity=1, user_id=user['id'], sort_order=30 + index, store_id=pantry.id)
            for index in range(1, 19)
        ]
        db.session.add_all([apples, bread, *extra_items])
        db.session.commit()

        return {
            'email': user['email'],
            'password': user['password'],
            'category_names': {'produce': produce_category.name, 'bakery': bakery_category.name},
            'item_ids': {'apples': apples.id, 'bread': bread.id},
            'store_ids': {'pantry': pantry.id, 'market': market.id},
        }


@pytest.fixture
def seeded_settings_import_default_items_data(app, create_user):
    user = create_user('settings-import-user@example.com')

    with app.app_context():
        produce_category = DefaultCategoryTemplate(name='Produce')
        db.session.add(produce_category)
        pantry_template = DefaultStoreTemplate(name='Pantry', sort_order=0)
        db.session.add(pantry_template)
        db.session.flush()

        existing_item = Item(name='Apples', quantity=9, unit='crate', category='Snacks', user_id=user['id'], sort_order=90, checked=True)
        db.session.add(existing_item)
        db.session.flush()

        default_template = DefaultItemTemplate(
            name='Apples',
            quantity=3,
            unit='bag',
            category='Produce',
            sort_order=15,
            store_template_id=pantry_template.id,
        )
        db.session.add(default_template)
        db.session.commit()

        return {
            'email': user['email'],
            'password': user['password'],
            'item_id': existing_item.id,
            'category_name': produce_category.name,
        }


@pytest.fixture
def seeded_category_filter_row_data(app, create_user):
    user = create_user('category-filter-user@example.com')

    with app.app_context():
        produce_category = DefaultCategoryTemplate(name='Produce')
        bakery_category = DefaultCategoryTemplate(name='Bakery')
        frozen_category = DefaultCategoryTemplate(name='Frozen')
        db.session.add_all([produce_category, bakery_category, frozen_category])
        db.session.flush()

        apples = Item(name='Apples', quantity=1, user_id=user['id'], sort_order=10, category='Produce')
        bread = Item(name='Bread', quantity=1, user_id=user['id'], sort_order=20, category='Bakery')
        soap = Item(name='Soap', quantity=1, user_id=user['id'], sort_order=30)
        db.session.add_all([apples, bread, soap])
        db.session.commit()

        return {
            'email': user['email'],
            'password': user['password'],
            'category_ids': {
                'produce': produce_category.id,
                'bakery': bakery_category.id,
                'frozen': frozen_category.id,
            },
            'item_ids': {
                'apples': apples.id,
                'bread': bread.id,
                'soap': soap.id,
            },
        }


@pytest.fixture
def seeded_alphabetical_item_order_data(app, create_user):
    user = create_user('alphabetical-order-user@example.com')

    with app.app_context():
        db.session.add_all(
            [
                Item(name='Zulu Apples', quantity=1, user_id=user['id'], sort_order=10),
                Item(name='bananas', quantity=1, user_id=user['id'], sort_order=1),
                Item(name='Carrots', quantity=1, user_id=user['id'], sort_order=5),
            ]
        )
        db.session.commit()

    return {
        'email': user['email'],
        'password': user['password'],
    }


def test_store_selection_persists_when_switching_items(browser_page, live_server, seeded_store_persistence_data, app):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    bread_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['bread']}")
    apples_row.wait_for()
    bread_row.wait_for()

    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()

    store_select = page.get_by_test_id('detail-store-select')
    store_select.select_option(str(seeded_store_persistence_data['store_ids']['market']))
    page.get_by_test_id('panel-close').click()
    bread_row.click()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()

    expect(store_select).to_have_value(str(seeded_store_persistence_data['store_ids']['market']))

    page.reload(wait_until='domcontentloaded')
    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()
    expect(page.get_by_test_id('detail-store-select')).to_have_value(str(seeded_store_persistence_data['store_ids']['market']))

    with app.app_context():
        apples = db.session.get(Item, seeded_store_persistence_data['item_ids']['apples'])
        assert apples.store_id == seeded_store_persistence_data['store_ids']['market']


def test_category_selection_persists_when_switching_items(browser_page, live_server, seeded_store_persistence_data, app):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    bread_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['bread']}")
    apples_row.wait_for()
    bread_row.wait_for()

    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()

    category_select = page.get_by_test_id('detail-category-select')
    category_select.select_option(seeded_store_persistence_data['category_names']['bakery'])
    page.get_by_test_id('panel-close').click()
    bread_row.click()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()

    expect(category_select).to_have_value(seeded_store_persistence_data['category_names']['bakery'])

    page.reload(wait_until='domcontentloaded')
    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()
    expect(page.get_by_test_id('detail-category-select')).to_have_value(seeded_store_persistence_data['category_names']['bakery'])

    with app.app_context():
        apples = db.session.get(Item, seeded_store_persistence_data['item_ids']['apples'])
        assert apples.category == seeded_store_persistence_data['category_names']['bakery']


def test_category_filter_row_uses_default_categories_with_items(browser_page, live_server, seeded_category_filter_row_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_category_filter_row_data['email'])
    page.locator('#password').fill(seeded_category_filter_row_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_category_filter_row_data['item_ids']['apples']}")
    bread_row = page.get_by_test_id(f"item-row-{seeded_category_filter_row_data['item_ids']['bread']}")
    soap_row = page.get_by_test_id(f"item-row-{seeded_category_filter_row_data['item_ids']['soap']}")
    apples_row.wait_for()

    expect(page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['produce']}" )).to_be_visible()
    expect(page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['bakery']}" )).to_be_visible()
    expect(page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['frozen']}" )).to_have_count(0)

    page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['produce']}").click()

    expect(apples_row).to_be_visible()
    expect(bread_row).to_be_hidden()
    expect(soap_row).to_be_hidden()


def test_category_filter_row_stays_on_one_line_on_mobile(browser_page, live_server, seeded_category_filter_row_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_category_filter_row_data['email'])
    page.locator('#password').fill(seeded_category_filter_row_data['password'])
    page.get_by_role('button', name='Sign In').click()

    rail = page.get_by_test_id('category-filter-rail')
    expect(rail).to_be_visible()
    expect(page.get_by_test_id('category-filter-all')).to_be_visible()
    expect(page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['produce']}" )).to_be_visible()
    expect(page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['bakery']}" )).to_be_visible()
    expect(page.get_by_test_id('category-filter-pending')).to_be_visible()
    expect(page.get_by_test_id('category-filter-done')).to_be_visible()

    top_positions = page.locator('[data-testid^="category-filter-"]').evaluate_all(
        "nodes => nodes.map(node => Math.round(node.getBoundingClientRect().top))"
    )

    assert len(set(top_positions)) == 1


def test_normal_mode_items_list_is_alphabetical_by_default(browser_page, live_server, seeded_alphabetical_item_order_data):
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_alphabetical_item_order_data['email'])
    page.locator('#password').fill(seeded_alphabetical_item_order_data['password'])
    page.get_by_role('button', name='Sign In').click()

    page.locator('[data-testid^="item-row-"]').first.wait_for()
    visible_rows = page.locator('[data-testid^="item-row-"]')
    visible_names = visible_rows.evaluate_all("nodes => nodes.slice(0, 3).map(node => node.querySelector('p.font-medium')?.textContent?.trim() || '')")

    assert visible_names == ['bananas', 'Carrots', 'Zulu Apples']


def test_active_filter_persists_after_refresh(browser_page, live_server, seeded_alphabetical_item_order_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_alphabetical_item_order_data['email'])
    page.locator('#password').fill(seeded_alphabetical_item_order_data['password'])
    page.get_by_role('button', name='Sign In').click()

    pending_filter = page.get_by_test_id('category-filter-pending')
    pending_filter.click()
    assert 'bg-amber-500' in (pending_filter.get_attribute('class') or '')

    page.reload(wait_until='domcontentloaded')

    reloaded_pending_filter = page.get_by_test_id('category-filter-pending')
    assert 'bg-amber-500' in (reloaded_pending_filter.get_attribute('class') or '')
    visible_rows = page.locator('[data-testid^="item-row-"]')
    labels = visible_rows.evaluate_all("nodes => nodes.slice(0, 3).map(node => node.querySelector('button[aria-label^=\"Mark \"]')?.getAttribute('aria-label') || '')")

    assert labels
    assert all(label == 'Mark done' for label in labels)


def test_category_filter_persists_after_refresh(browser_page, live_server, seeded_category_filter_row_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_category_filter_row_data['email'])
    page.locator('#password').fill(seeded_category_filter_row_data['password'])
    page.get_by_role('button', name='Sign In').click()

    produce_filter = page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['produce']}")
    produce_filter.click()
    assert 'theme-filter-active' in (produce_filter.get_attribute('class') or '')

    page.reload(wait_until='domcontentloaded')

    reloaded_produce_filter = page.get_by_test_id(f"category-filter-{seeded_category_filter_row_data['category_ids']['produce']}")
    assert 'theme-filter-active' in (reloaded_produce_filter.get_attribute('class') or '')

    visible_rows = page.locator('[data-testid^="item-row-"]')
    visible_names = visible_rows.evaluate_all("nodes => nodes.map(node => node.querySelector('p.font-medium')?.textContent?.trim() || '')")

    assert visible_names == ['Apples']


def test_desktop_checkbox_toggle_stays_visible_in_place(browser_page, live_server, seeded_alphabetical_item_order_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.set_viewport_size({'width': 1280, 'height': 900})
    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_alphabetical_item_order_data['email'])
    page.locator('#password').fill(seeded_alphabetical_item_order_data['password'])
    page.get_by_role('button', name='Sign In').click()

    first_row = page.locator('[data-testid^="item-row-"]').first
    first_row.wait_for()
    expect(first_row.locator('p.font-medium')).to_have_text('bananas')

    checkbox = first_row.get_by_role('button', name='Mark done')
    checkbox.click()

    expect(page.locator('[data-testid^="item-row-"]').first.locator('p.font-medium')).to_have_text('bananas')
    expect(page.locator('[data-testid^="item-row-"]').first.get_by_role('button', name='Mark pending')).to_be_visible()
    expect(page.get_by_test_id('item-detail-panel')).to_have_count(0)


def test_desktop_checkbox_left_edge_click_toggles_item(browser_page, live_server, seeded_alphabetical_item_order_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.set_viewport_size({'width': 1280, 'height': 900})
    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_alphabetical_item_order_data['email'])
    page.locator('#password').fill(seeded_alphabetical_item_order_data['password'])
    page.get_by_role('button', name='Sign In').click()

    first_row = page.locator('[data-testid^="item-row-"]').first
    first_row.wait_for()
    checkbox = first_row.get_by_role('button', name='Mark done')
    box = checkbox.bounding_box()

    assert box is not None

    page.mouse.click(box['x'] + 2, box['y'] + (box['height'] / 2))

    expect(first_row.get_by_role('button', name='Mark pending')).to_be_visible()
    expect(page.get_by_test_id('item-detail-panel')).to_have_count(0)


def test_settings_import_default_items_overwrites_same_name_item(browser_page, live_server, seeded_settings_import_default_items_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_settings_import_default_items_data['email'])
    page.locator('#password').fill(seeded_settings_import_default_items_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_settings_import_default_items_data['item_id']}")
    apples_row.wait_for()

    open_settings(page)
    page.get_by_test_id('settings-import-default-items').click()
    expect(page.get_by_test_id('settings-import-default-items-message')).to_contain_text('Default items imported: 1 overwritten.')
    page.get_by_role('button', name='Close settings').nth(1).click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_settings_import_default_items_data['item_id']}")
    apples_row.click()
    open_detail_panel(page)

    expect(page.get_by_test_id('detail-quantity-input')).to_have_value('3')
    expect(page.get_by_test_id('detail-unit-input')).to_have_value('bag')

    page.get_by_test_id('detail-tab-advanced').click()
    expect(page.get_by_test_id('detail-category-select')).to_have_value(seeded_settings_import_default_items_data['category_name'])
    expect(page.get_by_test_id('detail-store-select')).not_to_have_value('')


def test_detail_sheet_stays_open_after_multiple_edits(browser_page, live_server, seeded_store_persistence_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()

    detail_sheet = page.get_by_test_id('item-detail-panel')
    expect(detail_sheet).to_be_visible()

    name_input = page.get_by_test_id('detail-name-input')
    name_input.fill('Apples Gala')
    name_input.blur()

    unit_input = page.get_by_test_id('detail-unit-input')
    unit_input.fill('bag')
    unit_input.blur()

    expect(detail_sheet).to_be_visible()
    expect(name_input).to_have_value('Apples Gala')
    expect(unit_input).to_have_value('bag')


def test_detail_sheet_allows_manual_quantity_updates(browser_page, live_server, seeded_store_persistence_data, app):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)

    quantity_input = page.get_by_test_id('detail-quantity-input')
    quantity_input.click()
    quantity_input.press('Meta+A')
    quantity_input.press('Backspace')
    quantity_input.press_sequentially('7')
    quantity_input.blur()

    expect(quantity_input).to_have_value('7')

    page.reload(wait_until='domcontentloaded')
    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    expect(page.get_by_test_id('detail-quantity-input')).to_have_value('7')

    with app.app_context():
        apples = db.session.get(Item, seeded_store_persistence_data['item_ids']['apples'])
        assert apples.quantity == 7


def test_detail_sheet_allows_manual_price_updates(browser_page, live_server, seeded_store_persistence_data, app):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)

    price_input = page.get_by_test_id('detail-price-input')
    price_input.click()
    price_input.press('Meta+A')
    price_input.press('Backspace')
    price_input.press_sequentially('4.75')
    price_input.blur()

    expect(price_input).to_have_value('4.75')

    page.reload(wait_until='domcontentloaded')
    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    expect(page.get_by_test_id('detail-price-input')).to_have_value('4.75')

    with app.app_context():
        apples = db.session.get(Item, seeded_store_persistence_data['item_ids']['apples'])
        assert float(apples.price) == 4.75


def test_desktop_row_selection_opens_detail_panel(browser_page, live_server, seeded_store_persistence_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()

    detail_panel = page.get_by_test_id('item-detail-panel')
    expect(detail_panel).to_be_visible()
    expect(page.get_by_test_id('detail-name-input')).to_have_value('Apples')

    page.get_by_test_id('panel-close').click()
    expect(detail_panel).to_have_count(0)


def test_mobile_row_selection_shows_collapsed_detail_trigger(browser_page, live_server, seeded_store_persistence_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(seeded_store_persistence_data['email'])
    page.locator('#password').fill(seeded_store_persistence_data['password'])
    page.get_by_role('button', name='Sign In').click()

    apples_row = page.get_by_test_id(f"item-row-{seeded_store_persistence_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.dispatch_event('touchend')

    detail_trigger = page.get_by_test_id('open-detail-panel')
    expect(detail_trigger).to_be_visible()
    expect(detail_trigger).to_contain_text('Apples')