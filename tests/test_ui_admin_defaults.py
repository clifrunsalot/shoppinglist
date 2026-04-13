import pytest

from app.db import db
from app.models import DefaultCategoryTemplate, DefaultStoreTemplate, Item, Store


def login(page, live_server, email, password):
    page.goto(f'{live_server}/login', wait_until='domcontentloaded')
    page.locator('#email').fill(email)
    page.locator('#password').fill(password)
    page.get_by_role('button', name='Sign In').click()


def open_detail_panel(page):
    page.get_by_test_id('open-detail-panel').click()
    page.get_by_test_id('item-detail-panel').wait_for()
    page.get_by_test_id('detail-tab-advanced').wait_for()


@pytest.fixture
def seeded_admin_store_delete_data(app, create_user):
    admin_user = create_user('admin-ui@example.com', admin=True)
    regular_user = create_user('user-ui@example.com')

    with app.app_context():
        produce_category = DefaultCategoryTemplate(name='Produce')
        db.session.add(produce_category)
        pantry_template = DefaultStoreTemplate(name='Pantry', sort_order=0)
        market_template = DefaultStoreTemplate(name='Market', sort_order=0)
        db.session.add_all([pantry_template, market_template])
        db.session.flush()

        pantry_store = Store(name='Pantry', user_id=regular_user['id'], sort_order=10, template_store_id=pantry_template.id)
        market_store = Store(name='Market', user_id=regular_user['id'], sort_order=20, template_store_id=market_template.id)
        db.session.add_all([pantry_store, market_store])
        db.session.flush()

        apples = Item(name='Apples', quantity=1, user_id=regular_user['id'], sort_order=10, store_id=pantry_store.id)
        db.session.add(apples)
        db.session.commit()

        return {
            'admin': admin_user,
            'regular': regular_user,
            'template_ids': {'pantry': pantry_template.id, 'market': market_template.id},
            'item_ids': {'apples': apples.id},
            'store_ids': {'market': market_store.id},
        }


@pytest.fixture
def seeded_admin_default_item_data(app, create_user):
    admin_user = create_user('admin-item-ui@example.com', admin=True)
    regular_user = create_user('user-item-ui@example.com')

    with app.app_context():
        produce_category = DefaultCategoryTemplate(name='Produce')
        db.session.add(produce_category)
        pantry_template = DefaultStoreTemplate(name='Pantry', sort_order=0)
        db.session.add(pantry_template)
        db.session.flush()

        pantry_store = Store(name='Pantry', user_id=regular_user['id'], sort_order=10, template_store_id=pantry_template.id)
        db.session.add(pantry_store)
        db.session.commit()

        return {
            'admin': admin_user,
            'regular': regular_user,
            'category_names': {'produce': produce_category.name},
            'template_ids': {'pantry': pantry_template.id},
        }


def test_admin_deleted_store_becomes_unknown_until_user_reassigns(browser_page, live_server, seeded_admin_store_delete_data, app):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    login(page, live_server, seeded_admin_store_delete_data['admin']['email'], seeded_admin_store_delete_data['admin']['password'])
    page.goto(f'{live_server}/admin', wait_until='domcontentloaded')
    page.get_by_test_id(f"default-store-delete-{seeded_admin_store_delete_data['template_ids']['pantry']}").click()
    expect(page.get_by_text('Default store deleted.')).to_be_visible()
    page.locator('[data-logout-button]').click()

    with app.app_context():
        unknown_store = Store.query.filter_by(user_id=seeded_admin_store_delete_data['regular']['id'], template_store_id=None, name='unknown').first()
        market_store = Store.query.filter_by(user_id=seeded_admin_store_delete_data['regular']['id'], template_store_id=seeded_admin_store_delete_data['template_ids']['market']).first()
        assert unknown_store is not None
        assert market_store is not None
        unknown_store_id = unknown_store.id
        market_store_id = market_store.id

    login(page, live_server, seeded_admin_store_delete_data['regular']['email'], seeded_admin_store_delete_data['regular']['password'])
    apples_row = page.get_by_test_id(f"item-row-{seeded_admin_store_delete_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()

    store_select = page.get_by_test_id('detail-store-select')
    expect(store_select).to_have_value(str(unknown_store_id))
    expect(store_select.locator('option:checked')).to_have_text('unknown')

    store_select.select_option(str(market_store_id))
    page.reload(wait_until='domcontentloaded')
    apples_row = page.get_by_test_id(f"item-row-{seeded_admin_store_delete_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()
    open_detail_panel(page)
    page.get_by_test_id('detail-tab-advanced').click()
    expect(page.get_by_test_id('detail-store-select')).to_have_value(str(market_store_id))


def test_bottom_panels_are_collapsed_until_expanded(browser_page, live_server, seeded_admin_store_delete_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    login(page, live_server, seeded_admin_store_delete_data['regular']['email'], seeded_admin_store_delete_data['regular']['password'])

    add_item_panel = page.get_by_test_id('add-item-panel')
    expect(add_item_panel).to_have_count(0)

    page.get_by_test_id('open-add-panel').click()
    expect(add_item_panel).to_be_visible()

    page.get_by_test_id('panel-close').click()
    expect(add_item_panel).to_have_count(0)

    apples_row = page.get_by_test_id(f"item-row-{seeded_admin_store_delete_data['item_ids']['apples']}")
    apples_row.wait_for()
    apples_row.click()

    expect(add_item_panel).to_have_count(0)
    expect(page.get_by_test_id('item-detail-panel')).to_have_count(0)
    expect(page.get_by_test_id('open-detail-panel')).to_be_visible()

    open_detail_panel(page)
    expect(page.get_by_test_id('item-detail-panel')).to_be_visible()

    page.get_by_test_id('panel-close').click()
    expect(page.get_by_test_id('item-detail-panel')).to_have_count(0)
    expect(page.get_by_test_id('add-item-panel')).to_have_count(0)



def test_admin_added_default_item_is_merged_into_existing_user_account(browser_page, live_server, seeded_admin_default_item_data):
    sync_api = pytest.importorskip('playwright.sync_api')
    expect = sync_api.expect
    page = browser_page

    login(page, live_server, seeded_admin_default_item_data['admin']['email'], seeded_admin_default_item_data['admin']['password'])
    page.goto(f'{live_server}/admin', wait_until='domcontentloaded')
    page.get_by_test_id('default-item-create-name').fill('Bananas')
    page.get_by_test_id('default-item-create-quantity').fill('2')
    page.get_by_test_id('default-item-create-unit').fill('lb')
    page.get_by_test_id('default-item-create-category').select_option(seeded_admin_default_item_data['category_names']['produce'])
    page.get_by_test_id('default-item-create-sort-order').fill('25')
    page.get_by_test_id('default-item-create-store-template').select_option(str(seeded_admin_default_item_data['template_ids']['pantry']))
    page.get_by_test_id('default-item-create-submit').click()
    expect(page.get_by_text('Default item added.')).to_be_visible()
    page.locator('[data-logout-button]').click()

    login(page, live_server, seeded_admin_default_item_data['regular']['email'], seeded_admin_default_item_data['regular']['password'])
    expect(page.get_by_text('Bananas')).to_be_visible()
