from datetime import datetime
from app.db import db


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30))
    category = db.Column(db.String(60))
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    checked = db.Column(db.Boolean, default=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
