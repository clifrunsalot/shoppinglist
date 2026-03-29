import os
from math import isfinite
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, render_template, jsonify, request

from app.db import db, migrate
from app.models import Item, Store


MAX_REQUEST_BYTES = 16 * 1024
MAX_ITEM_NAME_LENGTH = 255


def error_response(message, status_code):
    return jsonify({'error': message}), status_code


def get_json_body():
    if not request.is_json:
        return None, error_response('request must be JSON', 415)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error_response('invalid JSON body', 400)

    return data, None


def normalize_text_field(value, field_name, max_length, *, required=False):
    if value is None:
        if required:
            return None, error_response(f'{field_name} is required', 400)
        return None, None

    normalized = str(value).strip()
    if not normalized:
        if required:
            return None, error_response(f'{field_name} is required', 400)
        return None, None

    if len(normalized) > max_length:
        return None, error_response(f'{field_name} must be at most {max_length} characters', 400)

    return normalized, None


def parse_quantity(value):
    if value is None:
        return 1, None

    try:
        quantity = float(value)
    except (TypeError, ValueError):
        return None, error_response('quantity must be a finite number', 400)

    if not isfinite(quantity):
        return None, error_response('quantity must be a finite number', 400)

    if quantity < 0:
        return None, error_response('quantity must be greater than or equal to 0', 400)

    return quantity, None


def parse_checked(value):
    if isinstance(value, bool):
        return value, None

    return None, error_response('checked must be a boolean', 400)


def parse_store_id(value):
    if value in (None, ''):
        return None, None

    try:
        store_id = int(value)
    except (TypeError, ValueError):
        return None, error_response('store_id must be an integer or null', 400)

    if store_id <= 0:
        return None, error_response('store_id must be an integer or null', 400)

    if db.session.get(Store, store_id) is None:
        return None, error_response('store_id must reference an existing store', 400)

    return store_id, None


def parse_price(value):
    if value in (None, ''):
        return Decimal('0.00')

    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')

    if price < 0:
        price = Decimal('0.00')

    return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def create_app(config_overrides=None):
    app = Flask(__name__, template_folder='templates')
    app.config.update(
        SQLALCHEMY_DATABASE_URI=(
            f"postgresql://{os.environ.get('DB_USER','devuser')}:{os.environ.get('DB_PASSWORD','devpass')}@"
            f"{os.environ.get('DB_HOST','db')}:{os.environ.get('DB_PORT','5432')}/"
            f"{os.environ.get('DB_NAME','appdb')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)

    def serialize(i):
        return {
            'id': i.id,
            'name': i.name,
            'quantity': i.quantity,
            'unit': i.unit,
            'category': i.category,
            'store_id': i.store_id,
            'price': float(i.price or 0),
            'checked': i.checked,
            'created_at': i.created_at.isoformat() if i.created_at else None,
        }

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.after_request
    def apply_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    @app.route('/api/items', methods=['GET'])
    def api_items_list():
        items = Item.query.order_by(Item.name.asc(), Item.id.asc()).all()
        return jsonify([serialize(i) for i in items])

    @app.route('/api/items', methods=['POST'])
    def api_items_create():
        data, error = get_json_body()
        if error:
            return error

        name, error = normalize_text_field(data.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
        if error:
            return error

        quantity, error = parse_quantity(data.get('quantity'))
        if error:
            return error

        unit, error = normalize_text_field(data.get('unit'), 'unit', 30)
        if error:
            return error

        category, error = normalize_text_field(data.get('category'), 'category', 60)
        if error:
            return error

        store_id, error = parse_store_id(data.get('store_id'))
        if error:
            return error

        item = Item(
            name=name,
            quantity=quantity,
            unit=unit,
            category=category,
            store_id=store_id,
            price=parse_price(data.get('price')),
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(serialize(item)), 201

    @app.route('/api/items/<int:item_id>', methods=['PATCH'])
    def api_items_update(item_id):
        item = Item.query.get_or_404(item_id)
        data, error = get_json_body()
        if error:
            return error

        if 'name' in data:
            item.name, error = normalize_text_field(data.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
            if error:
                return error

        if 'quantity' in data:
            item.quantity, error = parse_quantity(data.get('quantity'))
            if error:
                return error

        if 'unit' in data:
            item.unit, error = normalize_text_field(data.get('unit'), 'unit', 30)
            if error:
                return error

        if 'category' in data:
            item.category, error = normalize_text_field(data.get('category'), 'category', 60)
            if error:
                return error

        if 'checked' in data:
            item.checked, error = parse_checked(data.get('checked'))
            if error:
                return error

        if 'store_id' in data:
            item.store_id, error = parse_store_id(data.get('store_id'))
            if error:
                return error

        if 'price' in data:
            item.price = parse_price(data['price'])
        db.session.commit()
        return jsonify(serialize(item))

    @app.route('/api/items/<int:item_id>', methods=['DELETE'])
    def api_items_delete(item_id):
        item = Item.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        return '', 204

    @app.route('/api/stores', methods=['GET'])
    def api_stores_list():
        stores = Store.query.order_by(Store.name.asc()).all()
        return jsonify([{'id': s.id, 'name': s.name} for s in stores])

    @app.route('/api/stores', methods=['POST'])
    def api_stores_create():
        data, error = get_json_body()
        if error:
            return error

        name, error = normalize_text_field(data.get('name'), 'name', 100, required=True)
        if error:
            return error

        if Store.query.filter_by(name=name).first():
            return error_response('Store already exists', 409)
        store = Store(name=name)
        db.session.add(store)
        db.session.commit()
        return jsonify({'id': store.id, 'name': store.name}), 201

    @app.route('/api/stores/<int:store_id>', methods=['PATCH'])
    def api_stores_update(store_id):
        store = Store.query.get_or_404(store_id)
        data, error = get_json_body()
        if error:
            return error

        if 'name' in data:
            new_name, error = normalize_text_field(data.get('name'), 'name', 100, required=True)
            if error:
                return error
            if new_name != store.name and Store.query.filter_by(name=new_name).first():
                return error_response('Store name already exists', 409)
            store.name = new_name
        db.session.commit()
        return jsonify({'id': store.id, 'name': store.name})

    @app.route('/api/stores/<int:store_id>', methods=['DELETE'])
    def api_stores_delete(store_id):
        store = Store.query.get_or_404(store_id)
        # Clear store_id from all items using this store
        Item.query.filter_by(store_id=store_id).update({'store_id': None})
        db.session.delete(store)
        db.session.commit()
        return '', 204

    return app


app = create_app()
