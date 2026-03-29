from decimal import Decimal

import pytest

from app.db import db
from app.main import parse_price
from app.models import Item, Store


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


def test_items_api_creates_and_lists_items(client):
    response = client.post(
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
        'store_id': None,
        'price': 2.35,
        'checked': False,
        'created_at': response.get_json()['created_at'],
    }
    assert response.get_json()['created_at'] is not None

    list_response = client.get('/api/items')

    assert list_response.status_code == 200
    assert list_response.get_json() == [response.get_json()]


def test_items_api_rejects_missing_name(client):
    response = client.post('/api/items', json={'name': '   '})

    assert response.status_code == 400
    assert response.get_json() == {'error': 'name is required'}


def test_items_api_updates_fields_and_normalizes_negative_price(client, app):
    with app.app_context():
        item = Item(name='Milk', price=Decimal('3.99'))
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = client.patch(
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


def test_items_api_deletes_item(client, app):
    with app.app_context():
        item = Item(name='Bread', price=Decimal('1.25'))
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = client.delete(f'/api/items/{item_id}')

    assert response.status_code == 204

    with app.app_context():
        assert db.session.get(Item, item_id) is None


def test_stores_api_prevents_duplicate_names(client):
    first_response = client.post('/api/stores', json={'name': 'Corner Market'})
    duplicate_response = client.post('/api/stores', json={'name': 'Corner Market'})

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.get_json() == {'error': 'Store already exists'}


def test_deleting_store_clears_store_id_from_items(client, app):
    with app.app_context():
        store = Store(name='Neighborhood Grocer')
        db.session.add(store)
        db.session.flush()
        item = Item(name='Eggs', store_id=store.id, price=Decimal('4.50'))
        db.session.add(item)
        db.session.commit()
        store_id = store.id
        item_id = item.id

    response = client.delete(f'/api/stores/{store_id}')

    assert response.status_code == 204

    with app.app_context():
        refreshed_item = db.session.get(Item, item_id)
        assert refreshed_item is not None
        assert refreshed_item.store_id is None