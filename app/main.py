import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from urllib.parse import urlsplit

import click
from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_seasurf import SeaSurf
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.db import db, migrate
from app.models import AppSetting, AuditLog, DefaultCategoryTemplate, DefaultItemTemplate, DefaultStoreTemplate, Household, HouseholdInvite, HouseholdMember, Item, SignupToken, Store, User


MAX_REQUEST_BYTES = 16 * 1024
MAX_ITEM_NAME_LENGTH = 255
THEME_OPTIONS = ('meadow', 'ocean', 'sunset', 'berry')
UNKNOWN_STORE_NAME = 'unknown'


def env_flag(name, default=False):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}


def build_database_uri():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if database_url:
        return database_url.replace('postgres://', 'postgresql://', 1)

    return (
        f"postgresql://{os.environ.get('DB_USER', 'devuser')}:{os.environ.get('DB_PASSWORD', 'devpass')}@"
        f"{os.environ.get('DB_HOST', 'db')}:{os.environ.get('DB_PORT', '5432')}/"
        f"{os.environ.get('DB_NAME', 'appdb')}"
    )


def error_response(message, status_code):
    return jsonify({'error': message}), status_code


def error_message(error):
    response, _ = error
    payload = response.get_json(silent=True) or {}
    return payload.get('error', 'request failed')


def default_store_ordering():
    return (DefaultStoreTemplate.name.asc(), DefaultStoreTemplate.id.asc())


def default_category_ordering():
    return (DefaultCategoryTemplate.name.asc(), DefaultCategoryTemplate.id.asc())


def admin_default_stores_anchor():
    return f"{url_for('admin_dashboard')}#default-stores"


def admin_default_categories_anchor():
    return f"{url_for('admin_dashboard')}#default-categories"


def admin_default_items_anchor():
    return f"{url_for('admin_dashboard')}#default-items"


def admin_users_anchor():
    return f"{url_for('admin_dashboard')}#users"


def wants_json_response():
    return request.path.startswith('/api/')


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


def normalize_email(value):
    email, error = normalize_text_field(value, 'email', 255, required=True)
    if error or email is None:
        return None, error
    return email.lower(), None


def parse_quantity(value):
    if value is None:
        return 1, None

    if isinstance(value, str) and not value.strip():
        return 1, None

    try:
        quantity = float(value)
    except (TypeError, ValueError):
        return None, error_response('quantity must be a finite number', 400)

    if not isfinite(quantity):
        return None, error_response('quantity must be a finite number', 400)

    if quantity <= 0:
        return None, error_response('quantity must be greater than 0', 400)

    return quantity, None


def parse_checked(value):
    if isinstance(value, bool):
        return value, None
    return None, error_response('checked must be a boolean', 400)


def parse_sort_order(value, *, default=0):
    if value in (None, ''):
        return default

    try:
        sort_order = int(value)
    except (TypeError, ValueError):
        raise ValueError('sort order must be an integer')

    if sort_order < 0:
        raise ValueError('sort order must be 0 or greater')

    return sort_order


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


def validate_password_change(current_password, new_password, confirmation_password):
    if not current_password:
        return error_response('current password is required', 400)
    if not new_password:
        return error_response('new password is required', 400)
    if len(new_password) < 8:
        return error_response('new password must be at least 8 characters long', 400)
    if new_password != confirmation_password:
        return error_response('new password confirmation does not match', 400)
    if current_password == new_password:
        return error_response('new password must be different from current password', 400)
    return None


def build_next_target():
    return request.args.get('next') or request.form.get('next') or ''


def resolve_next_target(target):
    if not target:
        return url_for('index')

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return url_for('index')
    if not target.startswith('/'):
        return url_for('index')

    return target


def generate_temporary_password(length=12):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _get_app_base_url():
    return os.environ.get('APP_BASE_URL', 'http://localhost:8000').rstrip('/')


def send_email(to_email, subject, text_body):
    """Send a plain-text email via Resend.

    Falls back to stderr logging when RESEND_API_KEY is absent so that
    local development and automated tests work without a live API key.
    Any Resend exception is caught and logged rather than propagated so
    that email failures never surface as unhandled 500 errors to users.
    """
    import sys
    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    mail_from = os.environ.get('MAIL_FROM', 'no-reply@example.com').strip()

    if not api_key:
        print(
            f'[EMAIL STUB] To: {to_email} | Subject: {subject}\n{text_body}',
            file=sys.stderr,
        )
        return

    try:
        import resend as _resend
        _resend.api_key = api_key
        _resend.Emails.send({
            'from': mail_from,
            'to': to_email,
            'subject': subject,
            'text': text_body,
        })
    except Exception as exc:
        print(f'[EMAIL ERROR] Failed to send to {to_email}: {exc}', file=sys.stderr)


def send_verification_email(to_email, token):
    """Send the email-verification link to a prospective account holder."""
    verify_url = f'{_get_app_base_url()}/verify-email/{token}'
    subject = 'Verify your email – Grocery List'
    text_body = (
        'Hi,\n\n'
        'Someone requested an account on Grocery List using this email address.\n\n'
        'Click the link below to verify your email. '
        'The link expires in 30 minutes.\n\n'
        f'{verify_url}\n\n'
        'If you did not request this, you can safely ignore this email.\n'
    )
    send_email(to_email, subject, text_body)


def send_temp_password_email(to_email, temp_password):
    """Send an approved user their temporary password."""
    login_url = f'{_get_app_base_url()}/login'
    subject = 'Your Grocery List account is ready'
    text_body = (
        'Hi,\n\n'
        'Your Grocery List account has been approved.\n\n'
        f'Your temporary password is:  {temp_password}\n\n'
        f'Sign in at: {login_url}\n\n'
        'Please change your password after signing in.\n'
    )
    send_email(to_email, subject, text_body)


def send_household_invite_email(to_email, inviter_email, token):
    """Send a household invitation link."""
    join_url = f'{_get_app_base_url()}/join/{token}'
    subject = f'{inviter_email} invited you to a shared shopping list'
    text_body = (
        'Hi,\n\n'
        f'{inviter_email} has invited you to join their shopping list on Grocery List.\n\n'
        'Click the link below to accept the invitation:\n\n'
        f'{join_url}\n\n'
        "This link expires in 7 days. If you don't have an account yet, "
        "you'll need to sign up first.\n\n"
        'If you did not expect this invitation, you can safely ignore this email.\n'
    )
    send_email(to_email, subject, text_body)


def send_household_notify_email(to_email, requester_email):
    """Nudge a household member to check the shared shopping list."""
    login_url = f'{_get_app_base_url()}/login'
    subject = f'{requester_email} wants you to check the shopping list'
    text_body = (
        'Hi,\n\n'
        f'{requester_email} is asking you to check the shared shopping list on Grocery List.\n\n'
        f'Sign in to review and update the list: {login_url}\n'
    )
    send_email(to_email, subject, text_body)


_INSECURE_DEFAULT_KEY = 'dev-secret-key-change-me'


def create_app(config_overrides=None):
    app = Flask(__name__, template_folder='templates')
    # Allow forcing CSRF in tests by passing SEASURF_FORCE in config_overrides
    csrf = SeaSurf()
    secret_key = os.environ.get('SECRET_KEY', _INSECURE_DEFAULT_KEY)
    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=build_database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_pre_ping': True,
            'pool_recycle': 1800,
        },
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=env_flag('SESSION_COOKIE_SECURE', False),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_SECURE=env_flag('SESSION_COOKIE_SECURE', False),
        SEASURF_FORCE=False,  # Default to False, can be overridden for tests
    )
    if config_overrides:
        app.config.update(config_overrides)

    # Rate limiting: disabled during automated tests to keep the suite fast
    # and to avoid cross-test interference.  Enable explicitly when needed.
    app.config.setdefault('RATELIMIT_ENABLED', not app.config.get('TESTING', False))
    app.config.setdefault('RATELIMIT_STORAGE_URI', 'memory://')
    limiter = Limiter(key_func=get_remote_address)
    limiter.init_app(app)
    # Anchor the Limiter to the app so it isn't garbage-collected after
    # create_app() returns (the decorator closures hold only weak references).
    app.extensions['_limiter_instance'] = limiter

    # Guard against the insecure default secret key being used outside of
    # local development / automated tests.  A leaked or guessable key lets
    # anyone forge session cookies and CSRF tokens.
    if app.config['SECRET_KEY'] == _INSECURE_DEFAULT_KEY and not app.config.get('TESTING'):
        import warnings
        warnings.warn(
            'SECRET_KEY is set to the insecure default value. '
            'Set the SECRET_KEY environment variable to a strong random secret '
            'before deploying this application.',
            stacklevel=2,
        )

    # Guard against running over plain HTTP in production.  SESSION_COOKIE_SECURE
    # must be True whenever the app is served over HTTPS so that session cookies
    # are never transmitted over an unencrypted connection.
    if not app.config.get('SESSION_COOKIE_SECURE') and not app.config.get('TESTING'):
        import warnings
        warnings.warn(
            'SESSION_COOKIE_SECURE is not enabled. '
            'Set the SESSION_COOKIE_SECURE environment variable to 1 '
            'when deploying behind HTTPS to prevent session cookie theft.',
            stacklevel=2,
        )

    # If SEASURF_FORCE is True, force CSRF even in testing
    if app.config.get('SEASURF_FORCE'):
        app.config['TESTING'] = False

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    # Login and signup routes are exempt from CSRF: they don't act on behalf of
    # an authenticated user, so CSRF does not apply to them.
    csrf.exempt_urls(('/login', '/signup'))

    login_manager = LoginManager()
    # login_manager.login_view = 'login'  # Removed: not supported by this LoginManager
    login_manager.init_app(app)

    def get_setting(key, default):
        setting = AppSetting.query.filter_by(key=key).first()
        if setting is None:
            setting = AppSetting(key=key, value=default)
            db.session.add(setting)
            db.session.commit()
        return setting

    def get_default_theme():
        setting = get_setting('default_theme', 'meadow')
        if setting.value not in THEME_OPTIONS:
            setting.value = 'meadow'
            db.session.commit()
        return setting.value

    def get_protected_admin_user():
        return User.query.filter_by(is_admin=True).order_by(User.created_at.asc(), User.id.asc()).first()

    def is_protected_admin_user(user):
        protected_admin = get_protected_admin_user()
        return protected_admin is not None and user is not None and protected_admin.id == user.id

    def get_user_theme(user):
        if user.theme_preference in THEME_OPTIONS:
            return user.theme_preference
        return get_default_theme()

    def record_audit(action, target_type, summary, *, actor=None, target_id=None, details=None):
        db.session.add(
            AuditLog(
                actor_user_id=actor.id if actor is not None else None,
                action=action,
                target_type=target_type,
                target_id=target_id,
                summary=summary,
                details=json.dumps(details, sort_keys=True) if details else None,
            )
        )

    def clone_defaults_to_user(user):
        created_stores = 0
        household = get_or_create_household_for_user(user)

        templates = DefaultStoreTemplate.query.order_by(*default_store_ordering()).all()
        for index, template in enumerate(templates, start=1):
            store = Store(
                name=template.name,
                sort_order=index * 10,
                user_id=user.id,
                household_id=household.id,
                template_store_id=template.id,
            )
            db.session.add(store)
            db.session.flush()
            created_stores += 1

        return {'stores': created_stores, 'items': 0}

    def create_missing_default_store_for_user(user, template):
        existing_store = Store.query.filter_by(user_id=user.id, template_store_id=template.id).first()
        if existing_store is not None:
            return None

        next_sort_order = (db.session.query(db.func.max(Store.sort_order)).filter_by(user_id=user.id).scalar() or 0) + 10
        household = get_or_create_household_for_user(user)
        store = Store(
            name=template.name,
            sort_order=next_sort_order,
            user_id=user.id,
            household_id=household.id,
            template_store_id=template.id,
        )
        db.session.add(store)
        db.session.flush()
        return store

    def get_or_create_unknown_store_for_user(user_id):
        unknown_store = Store.query.filter_by(user_id=user_id, template_store_id=None, name=UNKNOWN_STORE_NAME).first()
        if unknown_store is not None:
            return unknown_store

        user = db.session.get(User, user_id)
        household_id = None
        if user is not None:
            household_id = get_or_create_household_for_user(user).id
        next_sort_order = (db.session.query(db.func.max(Store.sort_order)).filter_by(user_id=user_id).scalar() or 0) + 10
        unknown_store = Store(name=UNKNOWN_STORE_NAME, sort_order=next_sort_order, user_id=user_id, household_id=household_id)
        db.session.add(unknown_store)
        db.session.flush()
        return unknown_store

    def create_missing_default_item_for_user(user, template):
        existing_item = Item.query.filter_by(user_id=user.id, template_item_id=template.id).first()
        if existing_item is not None:
            return None, False

        matching_item = find_user_item_by_name(user.id, template.name)
        if matching_item is not None:
            if matching_item.template_item_id is None:
                matching_item.template_item_id = template.id
                db.session.flush()
                return matching_item, True
            return None, False

        store_id = None
        if template.store_template_id is not None:
            store = Store.query.filter_by(user_id=user.id, template_store_id=template.store_template_id).first()
            if store is not None:
                store_id = store.id

        household = get_or_create_household_for_user(user)
        item = Item(
            name=template.name,
            quantity=template.quantity,
            unit=template.unit,
            category=template.category,
            sort_order=template.sort_order,
            price=Decimal('0.00'),
            checked=False,
            user_id=user.id,
            household_id=household.id,
            store_id=store_id,
            template_item_id=template.id,
        )
        db.session.add(item)
        db.session.flush()
        return item, False

    def merge_item_records(primary_item, duplicate_item):
        if primary_item.template_item_id is None and duplicate_item.template_item_id is not None:
            primary_item.template_item_id = duplicate_item.template_item_id
        if primary_item.store_id is None and duplicate_item.store_id is not None:
            primary_item.store_id = duplicate_item.store_id
        if not primary_item.unit and duplicate_item.unit:
            primary_item.unit = duplicate_item.unit
        if not primary_item.category and duplicate_item.category:
            primary_item.category = duplicate_item.category
        if (primary_item.price is None or Decimal(primary_item.price or 0) <= 0) and Decimal(duplicate_item.price or 0) > 0:
            primary_item.price = duplicate_item.price
        if not primary_item.checked and duplicate_item.checked:
            primary_item.checked = duplicate_item.checked

    def deduplicate_user_items_for_user(user_id):
        items = Item.query.filter_by(user_id=user_id).order_by(Item.id.asc()).all()
        if not items:
            return False

        changed = False
        by_template_id = {}
        items_to_delete = []

        for item in items:
            if item.template_item_id is None:
                continue
            primary_item = by_template_id.get(item.template_item_id)
            if primary_item is None:
                by_template_id[item.template_item_id] = item
                continue
            merge_item_records(primary_item, item)
            items_to_delete.append(item)
            changed = True

        remaining_items = [item for item in items if item not in items_to_delete]
        by_name = {}
        for item in remaining_items:
            normalized_name = (item.name or '').strip().lower()
            if not normalized_name:
                continue
            primary_item = by_name.get(normalized_name)
            if primary_item is None:
                by_name[normalized_name] = item
                continue
            merge_item_records(primary_item, item)
            items_to_delete.append(item)
            changed = True

        for item in items_to_delete:
            db.session.delete(item)

        return changed

    def deduplicate_all_user_items():
        user_ids = [user_id for (user_id,) in db.session.query(Item.user_id).filter(Item.user_id.is_not(None)).distinct().all()]
        changed = False
        for user_id in user_ids:
            changed = deduplicate_user_items_for_user(user_id) or changed
        return changed

    def deduplicate_default_item_templates():
        templates = DefaultItemTemplate.query.order_by(DefaultItemTemplate.name.asc(), DefaultItemTemplate.id.asc()).all()
        if not templates:
            return False

        changed = False
        grouped_templates = {}
        for template in templates:
            normalized_name = (template.name or '').strip().lower()
            grouped_templates.setdefault(normalized_name, []).append(template)

        for duplicates in grouped_templates.values():
            if len(duplicates) < 2:
                continue

            ordered_duplicates = sorted(
                duplicates,
                key=lambda template: (template.name != template.name.strip(), template.id),
            )
            primary_template = ordered_duplicates[0]
            primary_template.name = primary_template.name.strip()

            for duplicate_template in ordered_duplicates[1:]:
                affected_items = Item.query.filter_by(template_item_id=duplicate_template.id).order_by(Item.id.asc()).all()
                for item in affected_items:
                    primary_item = Item.query.filter_by(user_id=item.user_id, template_item_id=primary_template.id).first()
                    if primary_item is not None:
                        merge_item_records(primary_item, item)
                        db.session.delete(item)
                    else:
                        item.template_item_id = primary_template.id
                db.session.delete(duplicate_template)
                changed = True

        changed = deduplicate_all_user_items() or changed
        return changed

    def ensure_user_has_default_stores(user):
        templates = DefaultStoreTemplate.query.order_by(*default_store_ordering()).all()
        template_ids = {template.id for template in templates}
        existing_stores = Store.query.filter_by(user_id=user.id).order_by(Store.sort_order.asc(), Store.id.asc()).all()

        template_store_by_id = {}
        extra_stores = []
        unknown_store = None
        for store in existing_stores:
            if store.template_store_id is None and store.name == UNKNOWN_STORE_NAME:
                if unknown_store is None:
                    unknown_store = store
                else:
                    extra_stores.append(store)
                continue
            if store.template_store_id not in template_ids:
                extra_stores.append(store)
                continue
            if store.template_store_id in template_store_by_id:
                extra_stores.append(store)
                continue
            template_store_by_id[store.template_store_id] = store

        created_stores = []
        for template in templates:
            store = template_store_by_id.get(template.id)
            if store is None:
                store = create_missing_default_store_for_user(user, template)
                template_store_by_id[template.id] = store
                created_stores.append(store)

        updated = False
        for index, template in enumerate(templates, start=1):
            store = template_store_by_id.get(template.id)
            if store is None:
                continue
            expected_sort_order = index * 10
            if store.name != template.name:
                store.name = template.name
                updated = True
            if store.sort_order != expected_sort_order:
                store.sort_order = expected_sort_order
                updated = True
            if store.template_store_id != template.id:
                store.template_store_id = template.id
                updated = True

        if extra_stores:
            redirect_to_unknown = [store.id for store in extra_stores if store.name != UNKNOWN_STORE_NAME or store.template_store_id is not None]
            if redirect_to_unknown:
                unknown_store = unknown_store or get_or_create_unknown_store_for_user(user.id)
                Item.query.filter(Item.user_id == user.id, Item.store_id.in_(redirect_to_unknown)).update({'store_id': unknown_store.id}, synchronize_session=False)
            for store in extra_stores:
                db.session.delete(store)
            updated = True

        if unknown_store is not None:
            expected_unknown_sort_order = (len(templates) + 1) * 10
            if unknown_store.name != UNKNOWN_STORE_NAME:
                unknown_store.name = UNKNOWN_STORE_NAME
                updated = True
            if unknown_store.sort_order != expected_unknown_sort_order:
                unknown_store.sort_order = expected_unknown_sort_order
                updated = True

        if created_stores or updated:
            db.session.commit()

        return created_stores

    def ensure_user_has_default_items(user):
        changed = deduplicate_user_items_for_user(user.id)
        templates = DefaultItemTemplate.query.order_by(
            DefaultItemTemplate.sort_order.asc(),
            DefaultItemTemplate.name.asc(),
            DefaultItemTemplate.id.asc(),
        ).all()

        created_items = []
        linked_existing_items = False
        for template in templates:
            item, linked_existing = create_missing_default_item_for_user(user, template)
            if item is not None and not linked_existing:
                created_items.append(item)
            linked_existing_items = linked_existing_items or linked_existing

        if created_items or linked_existing_items or changed:
            db.session.commit()

        return created_items

    def import_default_items_for_user(user):
        created_stores = ensure_user_has_default_stores(user)
        changed = deduplicate_user_items_for_user(user.id)
        household = get_or_create_household_for_user(user)
        templates = DefaultItemTemplate.query.order_by(
            db.func.lower(DefaultItemTemplate.name).asc(),
            DefaultItemTemplate.id.asc(),
        ).all()

        created_items = []
        overwritten_items = []

        for index, template in enumerate(templates, start=1):
            normalized_template_name = (template.name or '').strip().lower()
            imported_sort_order = index * 10
            store_id = None
            if template.store_template_id is not None:
                store = Store.query.filter_by(user_id=user.id, template_store_id=template.store_template_id).first()
                if store is not None:
                    store_id = store.id

            item = Item.query.filter_by(user_id=user.id, template_item_id=template.id).first()
            name_matched_unlinked = False
            if item is None:
                item = Item.query.filter(
                    Item.user_id == user.id,
                    Item.template_item_id == None,
                    db.func.lower(db.func.trim(Item.name)) == normalized_template_name,
                ).first()
                name_matched_unlinked = item is not None

            if item is None:
                item = Item(
                    name=template.name,
                    quantity=template.quantity,
                    unit=template.unit,
                    category=template.category,
                    sort_order=imported_sort_order,
                    price=Decimal('0.00'),
                    checked=False,
                    user_id=user.id,
                    household_id=household.id,
                    store_id=store_id,
                    template_item_id=template.id,
                )
                db.session.add(item)
                db.session.flush()
                created_items.append(item)
                continue

            if name_matched_unlinked:
                # User-created item whose name matches a template. Preserve the
                # user's data and only link it to the template so that no
                # duplicate is created.
                item.template_item_id = template.id
            else:
                # Item was previously imported from this template; reset it to
                # the current template defaults.
                item.name = template.name
                item.quantity = template.quantity
                item.unit = template.unit
                item.category = template.category
                item.sort_order = imported_sort_order
                item.price = Decimal('0.00')
                item.checked = False
                item.store_id = store_id
                item.template_item_id = template.id
            overwritten_items.append(item)

        if created_items or overwritten_items or changed:
            db.session.commit()

        return {
            'created_stores': created_stores,
            'created_items': created_items,
            'overwritten_items': overwritten_items,
        }

    def stores_are_admin_managed_error():
        return error_response('stores are managed by an administrator', 403)

    def categories_are_admin_managed_error():
        return error_response('categories are managed by an administrator', 403)

    def serialize(item):
        return {
            'id': item.id,
            'name': item.name,
            'quantity': item.quantity,
            'unit': item.unit,
            'category': item.category,
            'sort_order': item.sort_order,
            'store_id': item.store_id,
            'price': float(item.price or 0),
            'checked': item.checked,
            'version': item.version if item.version is not None else 1,
            'template_item_id': item.template_item_id,
            'created_at': item.created_at.isoformat() if item.created_at else None,
        }

    def serialize_store(store):
        return {
            'id': store.id,
            'name': store.name,
            'template_store_id': store.template_store_id,
        }

    def serialize_category(category):
        return {
            'id': category.id,
            'name': category.name,
        }

    def find_user_store_by_name(user_id, name):
        return Store.query.filter(
            Store.user_id == user_id,
            db.func.lower(Store.name) == name.lower(),
        ).first()

    def find_user_item_by_name(user_id, name, *, exclude_item_id=None):
        query = Item.query.filter(
            Item.user_id == user_id,
            db.func.lower(Item.name) == name.lower(),
        )
        if exclude_item_id is not None:
            query = query.filter(Item.id != exclude_item_id)
        return query.first()

    def find_default_item_template_by_name(name, *, exclude_item_id=None):
        query = DefaultItemTemplate.query.filter(
            db.func.lower(DefaultItemTemplate.name) == name.lower(),
        )
        if exclude_item_id is not None:
            query = query.filter(DefaultItemTemplate.id != exclude_item_id)
        return query.first()

    def find_default_category_template_by_name(name, *, exclude_category_id=None):
        normalized_name = (name or '').strip()
        if not normalized_name:
            return None

        query = DefaultCategoryTemplate.query.filter(
            db.func.lower(DefaultCategoryTemplate.name) == normalized_name.lower(),
        )
        if exclude_category_id is not None:
            query = query.filter(DefaultCategoryTemplate.id != exclude_category_id)
        return query.first()

    def get_or_create_household_for_user(user):
        """Return the user's primary household, creating one if none exists."""
        member = HouseholdMember.query.filter_by(user_id=user.id).order_by(
            HouseholdMember.id.asc()
        ).first()
        if member is not None:
            return db.session.get(Household, member.household_id)
        household = Household()
        db.session.add(household)
        db.session.flush()
        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role='owner',
            notifications_enabled=True,
        )
        db.session.add(membership)
        db.session.flush()
        return household

    def find_household_item_by_name(household_id, name, *, user_id=None, exclude_item_id=None):
        """Find an item by name within a household.

        When *user_id* is supplied a fallback clause is added so that items
        that were created before household_id was backfilled (household_id IS
        NULL, user_id matches) are also considered.
        """
        if user_id is not None:
            scope = db.or_(
                Item.household_id == household_id,
                db.and_(Item.household_id.is_(None), Item.user_id == user_id),
            )
        else:
            scope = (Item.household_id == household_id)
        query = Item.query.filter(scope, db.func.lower(Item.name) == name.lower())
        if exclude_item_id is not None:
            query = query.filter(Item.id != exclude_item_id)
        return query.first()

    def parse_category_name(value):
        category, error = normalize_text_field(value, 'category', 60)
        if error:
            return None, error
        if category is None:
            return None, None
        if find_default_category_template_by_name(category) is None:
            return None, error_response('category must reference an existing category', 400)
        return category, None

    def parse_store_id(value):
        if value in (None, ''):
            return None, None

        try:
            store_id = int(value)
        except (TypeError, ValueError):
            return None, error_response('store_id must be an integer or null', 400)

        if store_id <= 0:
            return None, error_response('store_id must be an integer or null', 400)

        store = Store.query.filter_by(id=store_id, user_id=current_user.id).first()
        if store is None:
            # Fall back to household-scoped lookup for stores created after migration
            household = get_or_create_household_for_user(current_user)
            store = Store.query.filter_by(id=store_id, household_id=household.id).first()
        if store is None:
            return None, error_response('store_id must reference an existing store', 400)

        return store_id, None

    def admin_required(view_func):
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if not current_user.is_admin:
                flash('Administrator access is required for that page.', 'error')
                return redirect(url_for('index'))
            return view_func(*args, **kwargs)

        wrapped.__name__ = view_func.__name__
        wrapped.__doc__ = view_func.__doc__
        wrapped.__module__ = view_func.__module__
        return wrapped

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if wants_json_response():
            return error_response('authentication required', 401)
        return redirect(url_for('login', next=build_next_target() or request.full_path.rstrip('?')))

    @app.before_request
    def enforce_account_status():
        if not current_user.is_authenticated:
            return None
        if current_user.is_active and current_user.is_approved:
            return None

        pending = not current_user.is_approved
        logout_user()
        if wants_json_response():
            return error_response('account access unavailable', 403)

        flash('Your account is pending approval.' if pending else 'Your account is inactive.', 'error')
        return redirect(url_for('login'))

    @app.cli.command('create-user')
    @click.argument('email')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option('--admin', is_flag=True, default=False, help='Create the user with admin access.')
    def create_user_command(email, password, admin):
        normalized_email, error = normalize_email(email)
        if error:
            raise click.ClickException('email is required')
        if len(password) < 8:
            raise click.ClickException('password must be at least 8 characters long')
        if User.query.filter_by(email=normalized_email).first() is not None:
            raise click.ClickException('user already exists')

        user = User()
        user.email = normalized_email
        user.is_admin = admin
        user.is_approved = True
        user.is_active = True
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        copied = clone_defaults_to_user(user)
        record_audit(
            'user.created_cli',
            'user',
            f'Created user {normalized_email} from the CLI.',
            target_id=user.id,
            details={'is_admin': admin, 'defaults_copied': copied},
        )
        db.session.commit()
        click.echo(f'Created user {normalized_email}')

    @app.route('/healthz')
    def healthz():
        return jsonify({'status': 'ok'})

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit('10 per minute', methods=['POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(resolve_next_target(build_next_target()))

        error_message = None
        next_target = build_next_target()
        if request.method == 'POST':
            email, error = normalize_email(request.form.get('email'))
            password = request.form.get('password', '')
            remember_me = request.form.get('remember_me') == 'on'

            if error:
                error_message = 'email is required'
            elif not password:
                error_message = 'password is required'
            else:
                user = User.query.filter_by(email=email).first()
                if user is not None and not user.is_approved:
                    error_message = 'account pending approval'
                elif user is not None and not user.is_active:
                    error_message = 'account is inactive'
                elif user is None or not user.check_password(password):
                    error_message = 'invalid email or password'
                else:
                    login_user(user, remember=remember_me)
                    return redirect(resolve_next_target(next_target))

        return render_template('login.html', error_message=error_message, next_target=next_target)

    @limiter.limit('5 per hour', methods=['POST'])
    @app.route('/signup', methods=['POST'])
    def signup():
        email, error = normalize_email(request.form.get('email'))
        if error:
            flash('An email address is required to request access.', 'error')
            return redirect(url_for('login'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user is not None:
            if existing_user.is_approved and existing_user.is_active:
                flash('That email already has an account. Sign in instead.', 'error')
            elif not existing_user.is_approved:
                flash('That email is already pending approval.', 'error')
            else:
                flash('That email belongs to an inactive account. Contact an administrator.', 'error')
            return redirect(url_for('login'))

        # Block duplicate active tokens to prevent email flooding.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active_token = SignupToken.query.filter_by(email=email, consumed=False).filter(
            SignupToken.expires_at > now
        ).first()
        if active_token is not None:
            flash(
                'A verification link was already sent to that address. '
                'Check your inbox (and spam folder).',
                'error',
            )
            return redirect(url_for('login'))

        # Soft-invalidate any leftover tokens for this email before issuing a new one.
        SignupToken.query.filter_by(email=email, consumed=False).update({'consumed': True})

        token = SignupToken.make(email)
        db.session.add(token)
        db.session.commit()
        send_verification_email(email, token.token)
        flash(
            "We've sent a verification link to that address. "
            'Check your inbox and follow the link to continue.',
            'success',
        )
        return redirect(url_for('login'))

    @app.route('/verify-email/<string:token_str>')
    def verify_email(token_str):
        sig_token = SignupToken.query.filter_by(token=token_str).first()
        if sig_token is None or sig_token.consumed:
            flash('This verification link is invalid or has already been used.', 'error')
            return redirect(url_for('login'))
        if sig_token.is_expired:
            flash('This verification link has expired. Please request a new one.', 'error')
            return redirect(url_for('login'))

        existing = User.query.filter_by(email=sig_token.email).first()
        if existing is not None:
            sig_token.consumed = True
            db.session.commit()
            flash('That email already has an account. Sign in instead.', 'error')
            return redirect(url_for('login'))

        user = User()
        user.email = sig_token.email
        user.is_admin = False
        user.is_approved = False
        user.is_active = True
        user.set_password(generate_temporary_password())
        sig_token.consumed = True
        db.session.add(user)
        db.session.flush()
        record_audit(
            'signup.email_verified',
            'user',
            f'Email verified for {sig_token.email}. Pending admin approval.',
            target_id=user.id,
            details={'email': sig_token.email},
        )
        db.session.commit()
        flash('Email verified. Your account is pending admin approval.', 'success')
        return redirect(url_for('login'))

    @app.route('/logout', methods=['POST'])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def index():
        return render_template('index.html', initial_theme=get_user_theme(current_user))

    @app.route('/help')
    @login_required
    def help_page():
        ref = request.args.get('ref', '')
        return render_template('help.html', ref=ref)

    @app.route('/admin')
    @login_required
    @admin_required
    def admin_dashboard():
        if deduplicate_default_item_templates():
            db.session.commit()
        protected_admin = get_protected_admin_user()
        return render_template(
            'admin.html',
            users=User.query.order_by(User.email.asc()).all(),
            pending_users=User.query.filter_by(is_approved=False).order_by(User.created_at.desc()).all(),
            default_stores=DefaultStoreTemplate.query.order_by(*default_store_ordering()).all(),
            default_categories=DefaultCategoryTemplate.query.order_by(*default_category_ordering()).all(),
            default_items=DefaultItemTemplate.query.order_by(db.func.lower(DefaultItemTemplate.name).asc(), DefaultItemTemplate.id.asc()).all(),
            protected_admin_user_id=protected_admin.id if protected_admin is not None else None,
            current_default_theme=get_default_theme(),
            theme_options=THEME_OPTIONS,
        )

    @app.route('/admin/settings/theme', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_default_theme():
        theme = request.form.get('theme', '').strip()
        if theme not in THEME_OPTIONS:
            flash('Choose a valid default theme.', 'error')
            return redirect(url_for('admin_dashboard'))

        setting = get_setting('default_theme', 'meadow')
        setting.value = theme
        record_audit('settings.theme.updated', 'app_setting', f'Default theme changed to {theme}.', actor=current_user, target_id=setting.id, details={'theme': theme})
        db.session.commit()
        flash('Default theme updated.', 'success')
        return redirect(url_for('admin_dashboard'))

    # CSRF protection is enforced on this route by default (no @csrf.exempt)
    @app.route('/admin/default-stores', methods=['POST'])
    @login_required
    @admin_required
    def admin_create_default_store():
        name, error = normalize_text_field(request.form.get('name'), 'name', 100, required=True)
        if error:
            flash('A store name is required.', 'error')
            return redirect(admin_default_stores_anchor())
        if DefaultStoreTemplate.query.filter_by(name=name).first() is not None:
            flash('That default store already exists.', 'error')
            return redirect(admin_default_stores_anchor())

        store = DefaultStoreTemplate(name=name, sort_order=0)
        db.session.add(store)
        db.session.flush()
        copied_user_ids = []
        existing_users = User.query.filter_by(is_approved=True, _is_active=True).all()
        for user in existing_users:
            created_store = create_missing_default_store_for_user(user, store)
            if created_store is not None:
                copied_user_ids.append(user.id)

        record_audit(
            'default_store.created',
            'default_store',
            f'Created default store {name}.',
            actor=current_user,
            target_id=store.id,
            details={'copied_user_ids': copied_user_ids},
        )
        db.session.commit()
        flash('Default store added.', 'success')
        return redirect(admin_default_stores_anchor())

    @app.route('/admin/default-stores/<int:store_id>/update', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_default_store(store_id):
        store = db.session.get(DefaultStoreTemplate, store_id)
        if store is None:
            flash('Default store not found.', 'error')
            return redirect(admin_default_stores_anchor())

        name, error = normalize_text_field(request.form.get('name'), 'name', 100, required=True)
        if error:
            flash('A store name is required.', 'error')
            return redirect(admin_default_stores_anchor())

        duplicate = DefaultStoreTemplate.query.filter_by(name=name).first()
        if duplicate is not None and duplicate.id != store.id:
            flash('That default store name is already in use.', 'error')
            return redirect(admin_default_stores_anchor())

        previous = {'name': store.name}
        store.name = name
        store.sort_order = 0
        for user_store in Store.query.filter_by(template_store_id=store.id).all():
            user_store.name = name
        record_audit('default_store.updated', 'default_store', f'Updated default store {name}.', actor=current_user, target_id=store.id, details={'before': previous, 'after': {'name': name}})
        db.session.commit()
        flash('Default store updated.', 'success')
        return redirect(admin_default_stores_anchor())

    @app.route('/admin/default-stores/<int:store_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_default_store(store_id):
        store = db.session.get(DefaultStoreTemplate, store_id)
        if store is None:
            flash('Default store not found.', 'error')
            return redirect(admin_default_stores_anchor())

        affected_items = DefaultItemTemplate.query.filter_by(store_template_id=store.id).all()
        for item in affected_items:
            item.store_template_id = None

        affected_user_stores = Store.query.filter_by(template_store_id=store.id).all()
        affected_user_store_ids = [user_store.id for user_store in affected_user_stores]
        if affected_user_store_ids:
            for user_store in affected_user_stores:
                unknown_store = get_or_create_unknown_store_for_user(user_store.user_id)
                Item.query.filter_by(store_id=user_store.id, user_id=user_store.user_id).update({'store_id': unknown_store.id}, synchronize_session=False)
                db.session.delete(user_store)

        db.session.flush()

        record_audit(
            'default_store.deleted',
            'default_store',
            f'Deleted default store {store.name}.',
            actor=current_user,
            target_id=store.id,
            details={
                'affected_item_ids': [item.id for item in affected_items],
                'affected_user_store_ids': affected_user_store_ids,
            },
        )
        db.session.delete(store)
        db.session.commit()
        flash('Default store deleted.', 'success')
        return redirect(admin_default_stores_anchor())

    @app.route('/admin/default-categories', methods=['POST'])
    @login_required
    @admin_required
    def admin_create_default_category():
        name, error = normalize_text_field(request.form.get('name'), 'name', 60, required=True)
        if error:
            flash('A category name is required.', 'error')
            return redirect(admin_default_categories_anchor())
        if find_default_category_template_by_name(name) is not None:
            flash('That default category already exists.', 'error')
            return redirect(admin_default_categories_anchor())

        category = DefaultCategoryTemplate(name=name)
        db.session.add(category)
        db.session.flush()
        record_audit(
            'default_category.created',
            'default_category',
            f'Created default category {name}.',
            actor=current_user,
            target_id=category.id,
        )
        db.session.commit()
        flash('Default category added.', 'success')
        return redirect(admin_default_categories_anchor())

    @app.route('/admin/default-categories/<int:category_id>/update', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_default_category(category_id):
        category = db.session.get(DefaultCategoryTemplate, category_id)
        if category is None:
            flash('Default category not found.', 'error')
            return redirect(admin_default_categories_anchor())

        name, error = normalize_text_field(request.form.get('name'), 'name', 60, required=True)
        if error:
            flash('A category name is required.', 'error')
            return redirect(admin_default_categories_anchor())

        duplicate = find_default_category_template_by_name(name, exclude_category_id=category.id)
        if duplicate is not None:
            flash('That default category name is already in use.', 'error')
            return redirect(admin_default_categories_anchor())

        previous = {'name': category.name}
        previous_name = category.name
        category.name = name
        DefaultItemTemplate.query.filter(db.func.lower(DefaultItemTemplate.category) == previous_name.lower()).update({'category': name}, synchronize_session=False)
        Item.query.filter(db.func.lower(Item.category) == previous_name.lower()).update({'category': name}, synchronize_session=False)
        record_audit(
            'default_category.updated',
            'default_category',
            f'Updated default category {name}.',
            actor=current_user,
            target_id=category.id,
            details={'before': previous, 'after': {'name': name}},
        )
        db.session.commit()
        flash('Default category updated.', 'success')
        return redirect(admin_default_categories_anchor())

    @app.route('/admin/default-categories/<int:category_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_default_category(category_id):
        category = db.session.get(DefaultCategoryTemplate, category_id)
        if category is None:
            flash('Default category not found.', 'error')
            return redirect(admin_default_categories_anchor())

        default_item_ids = [item_id for (item_id,) in db.session.query(DefaultItemTemplate.id).filter(db.func.lower(DefaultItemTemplate.category) == category.name.lower()).all()]
        item_ids = [item_id for (item_id,) in db.session.query(Item.id).filter(db.func.lower(Item.category) == category.name.lower()).all()]
        DefaultItemTemplate.query.filter(db.func.lower(DefaultItemTemplate.category) == category.name.lower()).update({'category': None}, synchronize_session=False)
        Item.query.filter(db.func.lower(Item.category) == category.name.lower()).update({'category': None}, synchronize_session=False)
        record_audit(
            'default_category.deleted',
            'default_category',
            f'Deleted default category {category.name}.',
            actor=current_user,
            target_id=category.id,
            details={'affected_default_item_ids': default_item_ids, 'affected_item_ids': item_ids},
        )
        db.session.delete(category)
        db.session.commit()
        flash('Default category deleted.', 'success')
        return redirect(admin_default_categories_anchor())

    @app.route('/admin/default-items', methods=['POST'])
    @login_required
    @admin_required
    def admin_create_default_item():
        name, error = normalize_text_field(request.form.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
        if error:
            flash('An item name is required.', 'error')
            return redirect(admin_default_items_anchor())
        if find_default_item_template_by_name(name) is not None:
            flash('That default item already exists.', 'error')
            return redirect(admin_default_items_anchor())

        quantity, quantity_error = parse_quantity(request.form.get('quantity'))
        if quantity_error:
            flash(f"{error_message(quantity_error).capitalize()}.", 'error')
            return redirect(admin_default_items_anchor())

        unit, unit_error = normalize_text_field(request.form.get('unit'), 'unit', 30)
        if unit_error:
            flash('Unit is too long.', 'error')
            return redirect(admin_default_items_anchor())

        category, category_error = parse_category_name(request.form.get('category'))
        if category_error:
            flash('Choose a valid default category.', 'error')
            return redirect(admin_default_items_anchor())

        try:
            sort_order = parse_sort_order(request.form.get('sort_order'), default=0)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(admin_default_items_anchor())

        store_template_id = request.form.get('store_template_id') or None
        if store_template_id:
            try:
                store_template_id = int(store_template_id)
            except (TypeError, ValueError):
                flash('Choose a valid default store.', 'error')
                return redirect(admin_default_items_anchor())
            if db.session.get(DefaultStoreTemplate, store_template_id) is None:
                flash('Choose a valid default store.', 'error')
                return redirect(admin_default_items_anchor())

        item = DefaultItemTemplate(name=name, quantity=quantity, unit=unit, category=category, sort_order=sort_order, store_template_id=store_template_id)
        db.session.add(item)
        db.session.flush()
        copied_user_ids = []
        existing_users = User.query.filter_by(is_approved=True, _is_active=True).all()
        for user in existing_users:
            created_item, linked_existing = create_missing_default_item_for_user(user, item)
            if created_item is not None and not linked_existing:
                copied_user_ids.append(user.id)
        record_audit('default_item.created', 'default_item', f'Created default item {name}.', actor=current_user, target_id=item.id, details={'sort_order': sort_order, 'store_template_id': store_template_id, 'copied_user_ids': copied_user_ids})
        db.session.commit()
        flash('Default item added.', 'success')
        return redirect(admin_default_items_anchor())

    @app.route('/admin/default-items/<int:item_id>/update', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_default_item(item_id):
        item = db.session.get(DefaultItemTemplate, item_id)
        if item is None:
            flash('Default item not found.', 'error')
            return redirect(admin_default_items_anchor())

        name, error = normalize_text_field(request.form.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
        if error:
            flash('An item name is required.', 'error')
            return redirect(admin_default_items_anchor())
        if find_default_item_template_by_name(name, exclude_item_id=item.id) is not None:
            flash('That default item name is already in use.', 'error')
            return redirect(admin_default_items_anchor())

        quantity, quantity_error = parse_quantity(request.form.get('quantity'))
        if quantity_error:
            flash(f"{error_message(quantity_error).capitalize()}.", 'error')
            return redirect(admin_default_items_anchor())

        unit, unit_error = normalize_text_field(request.form.get('unit'), 'unit', 30)
        if unit_error:
            flash('Unit is too long.', 'error')
            return redirect(admin_default_items_anchor())

        category, category_error = parse_category_name(request.form.get('category'))
        if category_error:
            flash('Choose a valid default category.', 'error')
            return redirect(admin_default_items_anchor())

        try:
            sort_order = parse_sort_order(request.form.get('sort_order'), default=item.sort_order)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(admin_default_items_anchor())

        store_template_id = request.form.get('store_template_id') or None
        if store_template_id:
            try:
                store_template_id = int(store_template_id)
            except (TypeError, ValueError):
                flash('Choose a valid default store.', 'error')
                return redirect(admin_default_items_anchor())
            if db.session.get(DefaultStoreTemplate, store_template_id) is None:
                flash('Choose a valid default store.', 'error')
                return redirect(admin_default_items_anchor())

        previous = {'name': item.name, 'quantity': item.quantity, 'unit': item.unit, 'category': item.category, 'sort_order': item.sort_order, 'store_template_id': item.store_template_id}
        item.name = name
        item.quantity = quantity
        item.unit = unit
        item.category = category
        item.sort_order = sort_order
        item.store_template_id = store_template_id
        record_audit('default_item.updated', 'default_item', f'Updated default item {name}.', actor=current_user, target_id=item.id, details={'before': previous, 'after': {'name': name, 'quantity': quantity, 'unit': unit, 'category': category, 'sort_order': sort_order, 'store_template_id': store_template_id}})
        db.session.commit()
        flash('Default item updated.', 'success')
        return redirect(admin_default_items_anchor())

    @app.route('/admin/default-items/<int:item_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_default_item(item_id):
        item = db.session.get(DefaultItemTemplate, item_id)
        if item is None:
            flash('Default item not found.', 'error')
            return redirect(admin_default_items_anchor())

        affected_item_ids = [linked_item_id for (linked_item_id,) in db.session.query(Item.id).filter_by(template_item_id=item.id).all()]
        if affected_item_ids:
            Item.query.filter_by(template_item_id=item.id).update({'template_item_id': None}, synchronize_session=False)

        record_audit(
            'default_item.deleted',
            'default_item',
            f'Deleted default item {item.name}.',
            actor=current_user,
            target_id=item.id,
            details={'affected_item_ids': affected_item_ids},
        )
        db.session.delete(item)
        db.session.commit()
        flash('Default item deleted.', 'success')
        return redirect(admin_default_items_anchor())

    @app.route('/admin/default-items/bulk-delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_bulk_delete_default_items():
        raw_item_ids = request.form.getlist('item_ids')
        item_ids = []
        for raw_item_id in raw_item_ids:
            try:
                item_id = int(raw_item_id)
            except (TypeError, ValueError):
                continue
            if item_id not in item_ids:
                item_ids.append(item_id)

        if not item_ids:
            flash('Select at least one default item to delete.', 'error')
            return redirect(admin_default_items_anchor())

        items = (
            DefaultItemTemplate.query
            .filter(DefaultItemTemplate.id.in_(item_ids))
            .order_by(DefaultItemTemplate.sort_order.asc(), DefaultItemTemplate.name.asc())
            .all()
        )
        if not items:
            flash('Default items not found.', 'error')
            return redirect(admin_default_items_anchor())

        deleted_item_ids = [item.id for item in items]
        deleted_item_names = [item.name for item in items]
        affected_user_item_ids = [item_id for (item_id,) in db.session.query(Item.id).filter(Item.template_item_id.in_(deleted_item_ids)).all()]
        if affected_user_item_ids:
            Item.query.filter(Item.template_item_id.in_(deleted_item_ids)).update({'template_item_id': None}, synchronize_session=False)

        for item in items:
            db.session.delete(item)

        record_audit(
            'default_item.bulk_deleted',
            'default_item',
            f'Deleted {len(items)} default items.',
            actor=current_user,
            details={'item_ids': deleted_item_ids, 'item_names': deleted_item_names, 'affected_item_ids': affected_user_item_ids},
        )
        db.session.commit()
        flash(f'Deleted {len(items)} default item{"s" if len(items) != 1 else ""}.', 'success')
        return redirect(admin_default_items_anchor())

    @app.route('/admin/users/<int:user_id>/approve', methods=['POST'])
    @login_required
    @admin_required
    def admin_approve_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(url_for('admin_dashboard'))
        if user.is_approved:
            flash('That user is already approved.', 'error')
            return redirect(url_for('admin_dashboard'))

        temporary_password = generate_temporary_password()
        user.set_password(temporary_password)
        user.is_approved = True
        user.is_active = True
        copied = clone_defaults_to_user(user)
        record_audit('user.approved', 'user', f'Approved {user.email} and assigned default data.', actor=current_user, target_id=user.id, details={'defaults_copied': copied})
        db.session.commit()
        send_temp_password_email(user.email, temporary_password)
        flash(f'Approved {user.email}. Their temporary password has been sent by email.', 'success')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
    @login_required
    @admin_required
    def admin_deactivate_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(url_for('admin_dashboard'))
        if user.id == current_user.id:
            flash('You cannot deactivate your own account.', 'error')
            return redirect(admin_users_anchor())
        if is_protected_admin_user(user):
            flash('The protected admin account must remain active.', 'error')
            return redirect(admin_users_anchor())

        user.is_active = False
        record_audit('user.deactivated', 'user', f'Deactivated {user.email}.', actor=current_user, target_id=user.id)
        db.session.commit()
        flash('User deactivated.', 'success')
        return redirect(admin_users_anchor())

    @app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
    @login_required
    @admin_required
    def admin_activate_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(admin_users_anchor())

        user.is_active = True
        record_audit('user.activated', 'user', f'Activated {user.email}.', actor=current_user, target_id=user.id)
        db.session.commit()
        flash('User activated.', 'success')
        return redirect(admin_users_anchor())

    @app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
    @login_required
    @admin_required
    def admin_reset_user_password(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(admin_users_anchor())

        temporary_password = generate_temporary_password()
        user.set_password(temporary_password)
        record_audit('user.password_reset', 'user', f'Generated a temporary password for {user.email}.', actor=current_user, target_id=user.id)
        db.session.commit()
        flash(f'Temporary password for {user.email}: {temporary_password}', 'success')
        return redirect(admin_users_anchor())

    @app.route('/admin/users/<int:user_id>/admin', methods=['POST'])
    @login_required
    @admin_required
    def admin_toggle_admin(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(admin_users_anchor())

        make_admin = request.form.get('is_admin') == 'true'
        if user.id == current_user.id and not make_admin:
            flash('You cannot remove your own admin access.', 'error')
            return redirect(admin_users_anchor())
        if is_protected_admin_user(user) and not make_admin:
            flash('The protected admin account must retain admin access.', 'error')
            return redirect(admin_users_anchor())

        user.is_admin = make_admin
        action = 'Granted' if make_admin else 'Removed'
        record_audit('user.admin_changed', 'user', f'{action} admin access for {user.email}.', actor=current_user, target_id=user.id, details={'is_admin': make_admin})
        db.session.commit()
        flash('User access updated.', 'success')
        return redirect(admin_users_anchor())

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(admin_users_anchor())
        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'error')
            return redirect(admin_users_anchor())
        if is_protected_admin_user(user):
            flash('The protected admin account cannot be deleted.', 'error')
            return redirect(admin_users_anchor())

        deleted_email = user.email
        deleted_item_ids = [item.id for item in Item.query.filter_by(user_id=user.id).all()]
        deleted_store_ids = [store.id for store in Store.query.filter_by(user_id=user.id).all()]

        AuditLog.query.filter_by(actor_user_id=user.id).update({'actor_user_id': None}, synchronize_session=False)
        Item.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Store.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.flush()
        record_audit(
            'user.deleted',
            'user',
            f'Deleted {deleted_email}.',
            actor=current_user,
            details={'deleted_email': deleted_email, 'item_ids': deleted_item_ids, 'store_ids': deleted_store_ids},
        )
        db.session.commit()
        flash('User deleted.', 'success')
        return redirect(admin_users_anchor())

    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_csp_nonce():
        return {'csp_nonce': g.get('csp_nonce', '')}

    @app.after_request
    def apply_security_headers(response):
        nonce = g.get('csp_nonce', '')
        response.headers['Content-Security-Policy'] = (
            f"default-src 'none'; "
            f"script-src 'nonce-{nonce}' 'unsafe-eval' "
            f"https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            f"style-src 'unsafe-inline'; "
            f"connect-src 'self'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"frame-ancestors 'none'; "
            f"object-src 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        return response

    @app.route('/api/items', methods=['GET'])
    @login_required
    def api_items_list():
        ensure_user_has_default_stores(current_user)
        changed = deduplicate_user_items_for_user(current_user.id)
        if changed:
            db.session.commit()
        household = get_or_create_household_for_user(current_user)
        _item_scope = db.or_(
            Item.household_id == household.id,
            db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
        )
        items = Item.query.filter(_item_scope).order_by(db.func.lower(Item.name).asc(), Item.id.asc()).all()
        return jsonify([serialize(item) for item in items])

    @app.route('/api/items', methods=['POST'])
    @login_required
    def api_items_create():
        data, error = get_json_body()
        if error:
            return error

        if not data:
            return error_response('invalid JSON body', 400)
        household = get_or_create_household_for_user(current_user)
        name, error = normalize_text_field(data.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
        if error:
            return error
        if find_household_item_by_name(household.id, name, user_id=current_user.id) is not None:
            return error_response('item already exists', 409)
        quantity, error = parse_quantity(data.get('quantity'))
        if error:
            return error
        unit, error = normalize_text_field(data.get('unit'), 'unit', 30)
        if error:
            return error
        category, error = parse_category_name(data.get('category'))
        if error:
            return error
        store_id, error = parse_store_id(data.get('store_id'))
        if error:
            return error

        template_item_id = data.get('template_item_id')
        if template_item_id is not None:
            try:
                template_item_id = int(template_item_id)
            except (TypeError, ValueError):
                return error_response('template_item_id must be an integer', 400)
            if db.session.get(DefaultItemTemplate, template_item_id) is None:
                return error_response('template_item_id does not reference a known template', 404)
            _create_scope = db.or_(
                Item.household_id == household.id,
                db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
            )
            if Item.query.filter(_create_scope, Item.template_item_id == template_item_id).first() is not None:
                return error_response('item already exists', 409)

        next_sort_order = (db.session.query(db.func.max(Item.sort_order)).filter(
            db.or_(
                Item.household_id == household.id,
                db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
            )
        ).scalar() or 0) + 10
        price = parse_price(data.get('price')) if data else None
        item = Item(name=name, quantity=quantity, unit=unit, category=category, sort_order=next_sort_order, store_id=store_id, price=price, user_id=current_user.id, household_id=household.id, template_item_id=template_item_id)
        db.session.add(item)
        db.session.commit()
        return jsonify(serialize(item)), 201

    @app.route('/api/items/<int:item_id>', methods=['PATCH'])
    @login_required
    def api_items_update(item_id):
        household = get_or_create_household_for_user(current_user)
        item = Item.query.filter(
            Item.id == item_id,
            db.or_(
                Item.household_id == household.id,
                db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
            ),
        ).first_or_404()
        data, error = get_json_body()
        if error:
            return error

        if not data:
            return error_response('invalid JSON body', 400)

        # Optimistic locking: if the caller supplies a version, it must match
        # the current row version before any mutations are applied.
        if 'version' in data:
            try:
                request_version = int(data['version'])
            except (TypeError, ValueError):
                return error_response('version must be an integer', 400)
            current_version = item.version if item.version is not None else 1
            if current_version != request_version:
                return jsonify({
                    'error': 'item modified by another user',
                    'current': serialize(item),
                }), 409

        if 'name' in data:
            name, error = normalize_text_field(data.get('name'), 'name', MAX_ITEM_NAME_LENGTH, required=True)
            if error:
                return error
            if find_household_item_by_name(household.id, name, user_id=current_user.id, exclude_item_id=item.id) is not None:
                return error_response('item already exists', 409)
            item.name = name
        if 'quantity' in data:
            item.quantity, error = parse_quantity(data.get('quantity'))
            if error:
                return error
        if 'unit' in data:
            item.unit, error = normalize_text_field(data.get('unit'), 'unit', 30)
            if error:
                return error
        if 'category' in data:
            item.category, error = parse_category_name(data.get('category'))
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

        item.version = (item.version if item.version is not None else 1) + 1
        db.session.commit()
        return jsonify(serialize(item))

    @app.route('/api/items/<int:item_id>', methods=['DELETE'])
    @login_required
    def api_items_delete(item_id):
        household = get_or_create_household_for_user(current_user)
        item = Item.query.filter(
            Item.id == item_id,
            db.or_(
                Item.household_id == household.id,
                db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
            ),
        ).first_or_404()
        db.session.delete(item)
        db.session.commit()
        return '', 204

    @app.route('/api/items/delete-all', methods=['POST'])
    @login_required
    def api_items_delete_all():
        household = get_or_create_household_for_user(current_user)
        items = Item.query.filter(
            db.or_(
                Item.household_id == household.id,
                db.and_(Item.household_id.is_(None), Item.user_id == current_user.id),
            )
        ).all()
        for item in items:
            db.session.delete(item)
        db.session.commit()
        return jsonify({'deleted_count': len(items)}), 200

    @app.route('/api/stores', methods=['GET'])
    @login_required
    def api_stores_list():
        ensure_user_has_default_stores(current_user)
        household = get_or_create_household_for_user(current_user)
        stores = Store.query.filter(
            db.or_(
                Store.household_id == household.id,
                db.and_(Store.household_id.is_(None), Store.user_id == current_user.id),
            )
        ).order_by(Store.sort_order.asc(), Store.name.asc(), Store.id.asc()).all()
        return jsonify([serialize_store(store) for store in stores])

    @app.route('/api/stores', methods=['POST'])
    @login_required
    def api_stores_create():
        return stores_are_admin_managed_error()

    @app.route('/api/stores/<int:store_id>', methods=['PATCH'])
    @login_required
    def api_stores_update(store_id):
        return stores_are_admin_managed_error()

    @app.route('/api/stores/<int:store_id>', methods=['DELETE'])
    @login_required
    def api_stores_delete(store_id):
        return stores_are_admin_managed_error()

    @app.route('/api/categories', methods=['GET'])
    @login_required
    def api_categories_list():
        categories = DefaultCategoryTemplate.query.order_by(*default_category_ordering()).all()
        return jsonify([serialize_category(category) for category in categories])

    @app.route('/api/categories', methods=['POST'])
    @login_required
    def api_categories_create():
        return categories_are_admin_managed_error()

    @app.route('/api/categories/<int:category_id>', methods=['PATCH'])
    @login_required
    def api_categories_update(category_id):
        return categories_are_admin_managed_error()

    @app.route('/api/categories/<int:category_id>', methods=['DELETE'])
    @login_required
    def api_categories_delete(category_id):
        return categories_are_admin_managed_error()

    @app.route('/api/default-items', methods=['GET'])
    @login_required
    def api_default_items_list():
        templates = DefaultItemTemplate.query.order_by(
            db.func.lower(DefaultItemTemplate.name).asc(),
            DefaultItemTemplate.id.asc(),
        ).all()
        return jsonify([
            {
                'id': t.id,
                'name': t.name,
                'quantity': t.quantity,
                'unit': t.unit,
                'category': t.category,
                'store_template_id': t.store_template_id,
            }
            for t in templates
        ])

    @app.route('/api/preferences/theme', methods=['PATCH'])
    @login_required
    def api_update_theme_preference():
        data, error = get_json_body()
        if error:
            return error

        theme = str(data.get('theme', '')).strip() if data else ''
        if theme not in THEME_OPTIONS:
            return error_response('theme must be one of the supported options', 400)

        current_user.theme_preference = theme
        db.session.commit()
        return jsonify({'theme': theme})

    @app.route('/api/account/password', methods=['PATCH'])
    @login_required
    def api_update_password():
        data, error = get_json_body()
        if error:
            return error

        current_password = data.get('current_password', '') if data else ''
        new_password = data.get('new_password', '') if data else ''
        confirmation_password = data.get('confirmation_password', '') if data else ''

        validation_error = validate_password_change(current_password, new_password, confirmation_password)
        if validation_error:
            return validation_error

        if not current_user.check_password(current_password):
            return error_response('current password is incorrect', 400)

        current_user.set_password(new_password)
        record_audit(
            'user.password_changed_self',
            'user',
            f'{current_user.email} changed their password.',
            actor=current_user,
            target_id=current_user.id,
        )
        db.session.commit()
        return jsonify({'message': 'password updated'})

    @app.route('/api/account/import-default-items', methods=['POST'])
    @login_required
    def api_import_default_items():
        imported = import_default_items_for_user(current_user)
        created_item_ids = [item.id for item in imported['created_items']]
        overwritten_item_ids = [item.id for item in imported['overwritten_items']]
        record_audit(
            'user.default_items_imported',
            'user',
            f'{current_user.email} imported default items.',
            actor=current_user,
            target_id=current_user.id,
            details={
                'created_store_ids': [store.id for store in imported['created_stores']],
                'created_item_ids': created_item_ids,
                'overwritten_item_ids': overwritten_item_ids,
            },
        )
        db.session.commit()
        return jsonify(
            {
                'message': 'default items imported',
                'created_count': len(created_item_ids),
                'overwritten_count': len(overwritten_item_ids),
            }
        )

    # ------------------------------------------------------------------
    # Stage 3: Household invitation flow
    # ------------------------------------------------------------------

    @app.route('/api/account/invite', methods=['POST'])
    @login_required
    def api_account_invite():
        data, error = get_json_body()
        if error:
            return error
        if data is None:
            return error_response('invalid JSON body', 400)
        raw_email = data.get('email', '')
        if not raw_email or not isinstance(raw_email, str):
            return error_response('email is required', 400)
        invited_email = raw_email.strip().lower()
        parts = invited_email.split('@', 1)
        if len(parts) != 2 or not parts[0] or '.' not in parts[1] or not parts[1].split('.', 1)[1]:
            return error_response('invalid email address', 400)
        if invited_email == current_user.email:
            return error_response('you cannot invite yourself', 400)
        household = get_or_create_household_for_user(current_user)
        existing = HouseholdInvite.query.filter_by(
            household_id=household.id,
            invited_email=invited_email,
            consumed=False,
        ).filter(
            HouseholdInvite.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
        ).first()
        if existing is not None:
            return error_response('an active invite already exists for that email', 409)
        invite = HouseholdInvite.make(
            household_id=household.id,
            invited_email=invited_email,
            created_by_user_id=current_user.id,
        )
        db.session.add(invite)
        db.session.commit()
        send_household_invite_email(invited_email, current_user.email, invite.token)
        return jsonify({'message': 'invite sent'}), 200

    _NOTIFY_COOLDOWN_SECONDS = 300  # 5 minutes

    @app.route('/api/household/notify', methods=['POST'])
    @login_required
    def api_household_notify():
        household = get_or_create_household_for_user(current_user)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if household.last_notified_at is not None:
            elapsed = (now - household.last_notified_at).total_seconds()
            if elapsed < _NOTIFY_COOLDOWN_SECONDS:
                wait = int(_NOTIFY_COOLDOWN_SECONDS - elapsed)
                return error_response(f'please wait {wait} seconds before sending another notification', 429)
        members = HouseholdMember.query.filter_by(
            household_id=household.id,
            notifications_enabled=True,
        ).all()
        member_user_ids = [m.user_id for m in members if m.user_id != current_user.id]
        recipients = User.query.filter(User.id.in_(member_user_ids)).all() if member_user_ids else []
        for recipient in recipients:
            send_household_notify_email(recipient.email, current_user.email)
        household.last_notified_at = now
        db.session.commit()
        return jsonify({'message': 'notifications sent', 'recipients': len(recipients)}), 200

    @app.route('/join/<string:token>')
    def join_household(token):
        invite = HouseholdInvite.query.filter_by(token=token).first()
        if invite is None or invite.consumed:
            flash('This invitation link is invalid or has already been used.', 'error')
            return redirect(url_for('login'))
        if invite.is_expired:
            flash('This invitation link has expired.', 'error')
            return redirect(url_for('login'))
        invited_user = User.query.filter_by(email=invite.invited_email).first()
        if invited_user is None:
            flash(
                'You need a Grocery List account before you can accept an invitation. '
                'Request access, then follow the invitation link again after your account is approved.',
                'info',
            )
            return redirect(url_for('login'))
        already_member = HouseholdMember.query.filter_by(
            household_id=invite.household_id,
            user_id=invited_user.id,
        ).first()
        if already_member is None:
            db.session.add(HouseholdMember(
                household_id=invite.household_id,
                user_id=invited_user.id,
                role='member',
                notifications_enabled=True,
            ))
        invite.consumed = True
        db.session.commit()
        flash('Invitation accepted. Sign in to access the shared shopping list.', 'success')
        return redirect(url_for('login'))

    return app


app = create_app()
