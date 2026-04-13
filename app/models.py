from datetime import datetime
import uuid

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_approved = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    theme_preference = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('Item', backref='user', lazy=True)
    stores = db.relationship('Store', backref='user', lazy=True)
    audit_entries = db.relationship('AuditLog', backref='actor', lazy=True, foreign_keys='AuditLog.actor_user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Store(db.Model):
    __tablename__ = 'stores'

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_store_user_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    template_store_id = db.Column(db.Integer, db.ForeignKey('default_store_templates.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30))
    category = db.Column(db.String(60))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    checked = db.Column(db.Boolean, default=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    template_item_id = db.Column(db.Integer, db.ForeignKey('default_item_templates.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DefaultStoreTemplate(db.Model):
    __tablename__ = 'default_store_templates'

    __table_args__ = (
        db.UniqueConstraint('name', name='uq_default_store_template_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_key = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('DefaultItemTemplate', backref='default_store_template', lazy=True)


class DefaultCategoryTemplate(db.Model):
    __tablename__ = 'default_category_templates'

    __table_args__ = (
        db.UniqueConstraint('name', name='uq_default_category_template_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_key = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DefaultItemTemplate(db.Model):
    __tablename__ = 'default_item_templates'

    id = db.Column(db.Integer, primary_key=True)
    template_key = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=1)
    unit = db.Column(db.String(30), nullable=True)
    category = db.Column(db.String(60), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    store_template_id = db.Column(db.Integer, db.ForeignKey('default_store_templates.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSetting(db.Model):
    __tablename__ = 'app_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    summary = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
