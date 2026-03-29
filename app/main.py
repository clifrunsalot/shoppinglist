import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, render_template, jsonify, request

from app.db import db, migrate
from app.models import Item, Store


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


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://{os.environ.get('DB_USER','devuser')}:{os.environ.get('DB_PASSWORD','devpass')}@"
        f"{os.environ.get('DB_HOST','db')}:{os.environ.get('DB_PORT','5432')}/"
        f"{os.environ.get('DB_NAME','appdb')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    @app.route('/api/items', methods=['GET'])
    def api_items_list():
        items = Item.query.order_by(Item.name.asc(), Item.id.asc()).all()
        return jsonify([serialize(i) for i in items])

    @app.route('/api/items', methods=['POST'])
    def api_items_create():
        data = request.get_json(force=True)
        if not data or not str(data.get('name', '')).strip():
            return jsonify({'error': 'name is required'}), 400
        item = Item(
            name=data['name'].strip(),
            quantity=data.get('quantity', 1),
            unit=data.get('unit'),
            category=data.get('category'),
            store_id=data.get('store_id'),
            price=parse_price(data.get('price')),
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(serialize(item)), 201

    @app.route('/api/items/<int:item_id>', methods=['PATCH'])
    def api_items_update(item_id):
        item = Item.query.get_or_404(item_id)
        data = request.get_json(force=True) or {}
        for field in ('name', 'quantity', 'unit', 'category', 'checked', 'store_id'):
            if field in data:
                setattr(item, field, data[field])
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
        data = request.get_json(force=True)
        if not data or not str(data.get('name', '')).strip():
            return jsonify({'error': 'name is required'}), 400
        name = data['name'].strip()
        # Check if store already exists
        if Store.query.filter_by(name=name).first():
            return jsonify({'error': 'Store already exists'}), 409
        store = Store(name=name)
        db.session.add(store)
        db.session.commit()
        return jsonify({'id': store.id, 'name': store.name}), 201

    @app.route('/api/stores/<int:store_id>', methods=['PATCH'])
    def api_stores_update(store_id):
        store = Store.query.get_or_404(store_id)
        data = request.get_json(force=True) or {}
        if 'name' in data:
            new_name = str(data['name']).strip()
            if not new_name:
                return jsonify({'error': 'name is required'}), 400
            if new_name != store.name and Store.query.filter_by(name=new_name).first():
                return jsonify({'error': 'Store name already exists'}), 409
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
