"""Stage 1 tests: Household, HouseholdMember, HouseholdInvite models."""
from datetime import datetime, timedelta, timezone

import pytest

from app.db import db
from app.models import Household, HouseholdInvite, HouseholdMember, Item, Store, User


# ---------------------------------------------------------------------------
# Household model
# ---------------------------------------------------------------------------

class TestHouseholdModel:
    def test_household_creation(self, app):
        with app.app_context():
            h = Household()
            db.session.add(h)
            db.session.commit()
            assert h.id is not None
            assert h.created_at is not None

    def test_household_has_members_relationship(self, app):
        with app.app_context():
            h = Household()
            db.session.add(h)
            db.session.commit()
            assert h.members == []


# ---------------------------------------------------------------------------
# HouseholdMember model
# ---------------------------------------------------------------------------

class TestHouseholdMemberModel:
    def test_member_defaults(self, app, create_user, create_household):
        user = create_user('member-default@example.com')
        result = create_household(user['id'])
        with app.app_context():
            member = HouseholdMember.query.filter_by(household_id=result['household_id']).first()
            assert member is not None
            assert member.role == 'owner'
            assert member.notifications_enabled is True

    def test_member_notifications_can_be_disabled(self, app, create_user, create_household):
        user = create_user('notif-off@example.com')
        result = create_household(user['id'])
        with app.app_context():
            member = HouseholdMember.query.get(result['member_id'])
            member.notifications_enabled = False
            db.session.commit()
            refreshed = HouseholdMember.query.get(result['member_id'])
            assert refreshed.notifications_enabled is False

    def test_duplicate_member_rejected(self, app, create_user, create_household):
        from sqlalchemy.exc import IntegrityError
        user = create_user('dup-member@example.com')
        result = create_household(user['id'])
        with app.app_context():
            duplicate = HouseholdMember(
                household_id=result['household_id'],
                user_id=user['id'],
                role='member',
            )
            db.session.add(duplicate)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_household_can_have_multiple_members(self, app, create_user, create_household):
        owner = create_user('multi-owner@example.com')
        partner = create_user('multi-partner@example.com')
        result = create_household(owner['id'])
        with app.app_context():
            member2 = HouseholdMember(
                household_id=result['household_id'],
                user_id=partner['id'],
                role='member',
            )
            db.session.add(member2)
            db.session.commit()
            members = HouseholdMember.query.filter_by(household_id=result['household_id']).all()
            assert len(members) == 2

    def test_user_household_memberships_relationship(self, app, create_user, create_household):
        user = create_user('user-memberships@example.com')
        result = create_household(user['id'])
        with app.app_context():
            user_obj = db.session.get(User, user['id'])
            matching = [m for m in user_obj.household_memberships if m.household_id == result['household_id']]
            assert len(matching) == 1
            assert matching[0].role == 'owner'


# ---------------------------------------------------------------------------
# HouseholdInvite model
# ---------------------------------------------------------------------------

class TestHouseholdInviteModel:
    def test_make_creates_valid_invite(self, app, create_user, create_household):
        user = create_user('invite-owner@example.com')
        result = create_household(user['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=result['household_id'],
                invited_email='partner@example.com',
                created_by_user_id=user['id'],
            )
            db.session.add(invite)
            db.session.commit()
            assert invite.id is not None
            assert invite.is_valid is True
            assert invite.is_expired is False
            assert invite.consumed is False
            assert len(invite.token) > 20

    def test_consumed_invite_is_not_valid(self, app, create_user, create_household):
        user = create_user('invite-consumed@example.com')
        result = create_household(user['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=result['household_id'],
                invited_email='x@example.com',
                created_by_user_id=user['id'],
            )
            db.session.add(invite)
            db.session.commit()
            invite.consumed = True
            db.session.commit()
            assert invite.is_valid is False

    def test_expired_invite_is_not_valid(self, app, create_user, create_household):
        user = create_user('invite-expired@example.com')
        result = create_household(user['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=result['household_id'],
                invited_email='y@example.com',
                created_by_user_id=user['id'],
            )
            # Manually expire
            invite.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.session.add(invite)
            db.session.commit()
            assert invite.is_expired is True
            assert invite.is_valid is False

    def test_invite_token_is_unique(self, app, create_user, create_household):
        from sqlalchemy.exc import IntegrityError
        user = create_user('invite-unique@example.com')
        result = create_household(user['id'])
        with app.app_context():
            invite1 = HouseholdInvite.make(
                household_id=result['household_id'],
                invited_email='a@example.com',
                created_by_user_id=user['id'],
            )
            db.session.add(invite1)
            db.session.commit()

            invite2 = HouseholdInvite(
                household_id=result['household_id'],
                invited_email='b@example.com',
                token=invite1.token,  # reuse same token
                expires_at=invite1.expires_at,
                consumed=False,
            )
            db.session.add(invite2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


# ---------------------------------------------------------------------------
# New columns on Item and Store
# ---------------------------------------------------------------------------

class TestHouseholdIdColumns:
    def test_item_has_household_id_column(self, app, create_user, create_household):
        user = create_user('item-hid@example.com')
        result = create_household(user['id'])
        with app.app_context():
            item = Item(
                name='Household Test Item',
                quantity=1,
                price=0,
                user_id=user['id'],
                household_id=result['household_id'],
            )
            db.session.add(item)
            db.session.commit()
            refreshed = Item.query.get(item.id)
            assert refreshed.household_id == result['household_id']

    def test_item_household_id_is_nullable(self, app, create_user):
        user = create_user('item-hid-null@example.com')
        with app.app_context():
            item = Item(
                name='No Household Item',
                quantity=1,
                price=0,
                user_id=user['id'],
                household_id=None,
            )
            db.session.add(item)
            db.session.commit()
            assert item.household_id is None

    def test_store_has_household_id_column(self, app, create_user, create_household):
        user = create_user('store-hid@example.com')
        result = create_household(user['id'])
        with app.app_context():
            store = Store(
                name='Household Store',
                user_id=user['id'],
                household_id=result['household_id'],
            )
            db.session.add(store)
            db.session.commit()
            refreshed = Store.query.get(store.id)
            assert refreshed.household_id == result['household_id']


# ---------------------------------------------------------------------------
# Stage 2: household-scoped API behaviour
# ---------------------------------------------------------------------------

def _login_client(app, email, password):
    """Return a logged-in Flask test client for the given credentials."""
    from urllib.parse import urlencode
    client = app.test_client()
    client.get('/login')  # sets CSRF cookie
    csrf_cookie = client.get_cookie('_csrf_token')
    csrf_token = csrf_cookie.value if csrf_cookie else None
    headers = {'X-CSRFToken': csrf_token} if csrf_token else {}
    resp = client.post(
        '/login',
        data=urlencode({'email': email, 'password': password}),
        content_type='application/x-www-form-urlencoded',
        headers=headers,
    )
    assert resp.status_code == 302, f'login failed for {email}: status {resp.status_code}'
    return client


class TestHouseholdScopedAPI:
    """Stage 2: items and stores are scoped to a household."""

    def test_item_created_via_api_has_household_id(self, app, create_user):
        user = create_user('api-hh-item@example.com')
        client = _login_client(app, user['email'], user['password'])
        resp = client.post('/api/items', json={'name': 'HouseholdApples'})
        assert resp.status_code == 201
        item_id = resp.get_json()['id']
        with app.app_context():
            item = db.session.get(Item, item_id)
            assert item.household_id is not None

    def test_two_users_in_same_household_share_items(self, app, create_user):
        user_a = create_user('share-hh-a@example.com')
        user_b = create_user('share-hh-b@example.com')

        # Create an item as user_a — POST commits user_a's household via db.session.commit()
        client_a = _login_client(app, user_a['email'], user_a['password'])
        resp = client_a.post('/api/items', json={'name': 'SharedBananas'})
        assert resp.status_code == 201

        # Read the exact household used by the route (from the item itself, not
        # from user_a's membership list, which may have stale rows from ID recycling).
        item_id = resp.get_json()['id']
        with app.app_context():
            item = db.session.get(Item, item_id)
            assert item.household_id is not None
            household_id = item.household_id
            member_b = HouseholdMember(
                household_id=household_id,
                user_id=user_b['id'],
                role='member',
                notifications_enabled=True,
            )
            db.session.add(member_b)
            db.session.commit()

        # user_b is now a member of user_a's household and should see the item.
        client_b = _login_client(app, user_b['email'], user_b['password'])
        resp = client_b.get('/api/items')
        assert resp.status_code == 200
        names = [i['name'] for i in resp.get_json()]
        assert 'SharedBananas' in names

    def test_cross_household_item_isolation(self, app, create_user):
        user_a = create_user('iso-hh-a@example.com')
        user_b = create_user('iso-hh-b@example.com')

        client_a = _login_client(app, user_a['email'], user_a['password'])
        resp = client_a.post('/api/items', json={'name': 'PrivateCarrots'})
        assert resp.status_code == 201
        item_id = resp.get_json()['id']

        client_b = _login_client(app, user_b['email'], user_b['password'])
        resp = client_b.get('/api/items')
        assert resp.status_code == 200
        ids = [i['id'] for i in resp.get_json()]
        assert item_id not in ids

    def test_cross_household_cannot_delete_other_users_item(self, app, create_user):
        user_a = create_user('del-hh-a@example.com')
        user_b = create_user('del-hh-b@example.com')

        client_a = _login_client(app, user_a['email'], user_a['password'])
        resp = client_a.post('/api/items', json={'name': 'PrivatePears'})
        assert resp.status_code == 201
        item_id = resp.get_json()['id']

        client_b = _login_client(app, user_b['email'], user_b['password'])
        resp = client_b.delete(f'/api/items/{item_id}')
        assert resp.status_code == 404

    def test_cross_household_cannot_update_other_users_item(self, app, create_user):
        user_a = create_user('patch-hh-a@example.com')
        user_b = create_user('patch-hh-b@example.com')

        client_a = _login_client(app, user_a['email'], user_a['password'])
        resp = client_a.post('/api/items', json={'name': 'PrivatePeaches'})
        assert resp.status_code == 201
        item_id = resp.get_json()['id']

        client_b = _login_client(app, user_b['email'], user_b['password'])
        resp = client_b.patch(f'/api/items/{item_id}', json={'name': 'Hacked'})
        assert resp.status_code == 404

    def test_stores_are_scoped_to_household(self, app, create_user):
        user = create_user('stores-hh@example.com')
        client = _login_client(app, user['email'], user['password'])
        # POST commits the household so the subsequent GET assertion holds
        client.post('/api/items', json={'name': '_seed_for_stores_test'})
        resp = client.get('/api/stores')
        assert resp.status_code == 200
        # All returned stores should belong to this user's household
        with app.app_context():
            member = HouseholdMember.query.filter_by(user_id=user['id']).first()
            assert member is not None
            store_ids = [s['id'] for s in resp.get_json()]
            if store_ids:
                stores = Store.query.filter(Store.id.in_(store_ids)).all()
                for store in stores:
                    assert store.household_id == member.household_id


# ---------------------------------------------------------------------------
# Stage 3: Invitation flow
# ---------------------------------------------------------------------------

class TestInvitationFlow:
    """Stage 3: POST /api/account/invite and GET /join/<token>."""

    def test_invite_requires_auth(self, app):
        client = app.test_client()
        resp = client.post('/api/account/invite', json={'email': 'x@example.com'})
        assert resp.status_code == 401

    def test_invite_missing_email_returns_400(self, app, create_user):
        user = create_user('inv-missing@example.com')
        client = _login_client(app, user['email'], user['password'])
        resp = client.post('/api/account/invite', json={})
        assert resp.status_code == 400
        assert 'email' in resp.get_json()['error']

    def test_invite_invalid_email_returns_400(self, app, create_user):
        user = create_user('inv-bademail@example.com')
        client = _login_client(app, user['email'], user['password'])
        resp = client.post('/api/account/invite', json={'email': 'notanemail'})
        assert resp.status_code == 400

    def test_invite_self_blocked(self, app, create_user):
        user = create_user('inv-self@example.com')
        client = _login_client(app, user['email'], user['password'])
        resp = client.post('/api/account/invite', json={'email': user['email']})
        assert resp.status_code == 400
        assert 'yourself' in resp.get_json()['error']

    def test_invite_creates_token_and_returns_200(self, app, create_user):
        user = create_user('inv-owner@example.com')
        client = _login_client(app, user['email'], user['password'])
        resp = client.post('/api/account/invite', json={'email': 'partner@example.com'})
        assert resp.status_code == 200
        assert resp.get_json()['message'] == 'invite sent'
        with app.app_context():
            invite = HouseholdInvite.query.filter_by(
                invited_email='partner@example.com'
            ).first()
            assert invite is not None
            assert invite.is_valid
            assert invite.consumed is False

    def test_invite_duplicate_blocked(self, app, create_user):
        user = create_user('inv-dup@example.com')
        client = _login_client(app, user['email'], user['password'])
        client.post('/api/account/invite', json={'email': 'dup-target@example.com'})
        resp = client.post('/api/account/invite', json={'email': 'dup-target@example.com'})
        assert resp.status_code == 409
        assert 'active invite' in resp.get_json()['error']

    def test_join_invalid_token_redirects(self, app):
        client = app.test_client()
        resp = client.get('/join/nonexistent-token-xyz')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_join_consumed_token_redirects(self, app, create_user, create_household):
        owner = create_user('join-consumed-owner@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=hh['household_id'],
                invited_email='already-used@example.com',
                created_by_user_id=owner['id'],
            )
            invite.consumed = True
            db.session.add(invite)
            db.session.commit()
            token = invite.token
        client = app.test_client()
        resp = client.get(f'/join/{token}')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_join_expired_token_redirects(self, app, create_user, create_household):
        owner = create_user('join-expired-owner@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=hh['household_id'],
                invited_email='expired-invitee@example.com',
                created_by_user_id=owner['id'],
            )
            invite.expires_at = datetime(2000, 1, 1)
            db.session.add(invite)
            db.session.commit()
            token = invite.token
        client = app.test_client()
        resp = client.get(f'/join/{token}')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_join_no_account_redirects_with_info(self, app, create_user, create_household):
        owner = create_user('join-nouser-owner@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=hh['household_id'],
                invited_email='no-account-yet@example.com',
                created_by_user_id=owner['id'],
            )
            db.session.add(invite)
            db.session.commit()
            token = invite.token
        client = app.test_client()
        resp = client.get(f'/join/{token}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'account' in resp.data.lower()

    def test_join_adds_existing_user_to_household(self, app, create_user, create_household):
        owner = create_user('join-owner@example.com')
        invitee = create_user('join-invitee@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            invite = HouseholdInvite.make(
                household_id=hh['household_id'],
                invited_email=invitee['email'],
                created_by_user_id=owner['id'],
            )
            db.session.add(invite)
            db.session.commit()
            token = invite.token
        client = app.test_client()
        resp = client.get(f'/join/{token}')
        assert resp.status_code == 302
        with app.app_context():
            member = HouseholdMember.query.filter_by(
                household_id=hh['household_id'],
                user_id=invitee['id'],
            ).first()
            assert member is not None
            assert member.role == 'member'
            used_invite = HouseholdInvite.query.filter_by(token=token).first()
            assert used_invite.consumed is True

    def test_join_already_member_consumes_invite_idempotently(self, app, create_user, create_household):
        owner = create_user('join-idem-owner@example.com')
        invitee = create_user('join-idem-invitee@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            # Pre-add invitee as a member
            db.session.add(HouseholdMember(
                household_id=hh['household_id'],
                user_id=invitee['id'],
                role='member',
                notifications_enabled=True,
            ))
            invite = HouseholdInvite.make(
                household_id=hh['household_id'],
                invited_email=invitee['email'],
                created_by_user_id=owner['id'],
            )
            db.session.add(invite)
            db.session.commit()
            token = invite.token
        client = app.test_client()
        resp = client.get(f'/join/{token}')
        assert resp.status_code == 302
        with app.app_context():
            members = HouseholdMember.query.filter_by(
                household_id=hh['household_id'],
                user_id=invitee['id'],
            ).all()
            assert len(members) == 1  # no duplicate
            used_invite = HouseholdInvite.query.filter_by(token=token).first()
            assert used_invite.consumed is True


# ---------------------------------------------------------------------------
# Stage 4: Notify route
# ---------------------------------------------------------------------------

class TestHouseholdNotify:
    """Stage 4: POST /api/household/notify."""

    def test_notify_requires_auth(self, app):
        client = app.test_client()
        resp = client.post('/api/household/notify')
        assert resp.status_code == 401

    def test_notify_returns_200_and_recipient_count(self, app, create_user, create_household):
        owner = create_user('notify-owner@example.com')
        partner = create_user('notify-partner@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            db.session.add(HouseholdMember(
                household_id=hh['household_id'],
                user_id=partner['id'],
                role='member',
                notifications_enabled=True,
            ))
            db.session.commit()
        client = _login_client(app, owner['email'], owner['password'])
        resp = client.post('/api/household/notify')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['message'] == 'notifications sent'
        assert data['recipients'] == 1  # partner only, not caller

    def test_notify_cooldown_returns_429(self, app, create_user):
        user = create_user('notify-cd@example.com')
        client = _login_client(app, user['email'], user['password'])
        # Seed a POST to commit the household first
        client.post('/api/items', json={'name': '_seed'})
        resp1 = client.post('/api/household/notify')
        assert resp1.status_code == 200
        # Immediate second call should be rate-limited
        resp2 = client.post('/api/household/notify')
        assert resp2.status_code == 429
        assert 'wait' in resp2.get_json()['error']

    def test_notify_skips_member_with_notifications_disabled(self, app, create_user, create_household):
        owner = create_user('notify-skip-owner@example.com')
        silent = create_user('notify-skip-silent@example.com')
        hh = create_household(owner['id'])
        with app.app_context():
            db.session.add(HouseholdMember(
                household_id=hh['household_id'],
                user_id=silent['id'],
                role='member',
                notifications_enabled=False,
            ))
            db.session.commit()
        client = _login_client(app, owner['email'], owner['password'])
        resp = client.post('/api/household/notify')
        assert resp.status_code == 200
        assert resp.get_json()['recipients'] == 0
