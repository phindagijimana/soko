
import io
import os

import pytest
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite:///./test_agri_marketplace.db'
os.environ['SMS_PROVIDER'] = 'file'
os.environ['SMS_LOG_PATH'] = './test_sms_log.txt'
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'
os.environ['ALLOWED_ORIGINS'] = 'http://127.0.0.1:5173'
os.environ['TRUSTED_HOSTS'] = '127.0.0.1,localhost,testserver'
os.environ['ADMIN_PHONE_NUMBERS'] = '+250700000001'
os.environ['AUTH_RATE_LIMIT_MAX_REQUESTS'] = '50'
os.environ['OTP_RESEND_COOLDOWN_SECONDS'] = '0'

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Order
from app.rate_limit import rate_limiter
from app.seed import seed_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database_and_limits():
    rate_limiter.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_data(db)
    yield
    rate_limiter.clear()


def auth_headers(phone: str, code: str = '123456'):
    client.post('/auth/request-otp', json={'phone': phone})
    res = client.post('/auth/verify-otp', json={'phone': phone, 'code': code})
    assert res.status_code == 200, res.text
    token = res.json()['token']
    return {'Authorization': f"Bearer {token}"}


def test_health_and_ready():
    res = client.get('/health')
    assert res.status_code == 200
    body = res.json()
    assert body['status'] == 'ok'
    assert body['storage'] == 'local'
    assert body['sentry'] is False
    ready = client.get('/ready')
    assert ready.status_code == 200


def test_farmer_can_create_listing_and_upload_image():
    headers = auth_headers('+250788000111')
    upload = client.post(
        '/images/upload',
        headers=headers,
        files={'image': ('harvest.png', io.BytesIO(b'\x89PNG\r\n\x1a\nabc'), 'image/png')},
    )
    assert upload.status_code == 200, upload.text
    image_url = upload.json()['image_url']

    res = client.post(
        '/listings',
        headers=headers,
        json={
            'crop': 'Beans',
            'quantity': '50 kg',
            'price': '500 RWF / kg',
            'location': 'Kigali',
            'description': 'Red beans',
            'image_url': image_url,
            'image_urls': [f'http://127.0.0.1:2500{image_url}'],
        },
    )
    assert res.status_code == 200
    assert res.json()['crop'] == 'Beans'
    assert len(res.json()['image_urls']) == 1


def test_buyer_cannot_create_listing():
    headers = auth_headers('+250788555444')
    res = client.post('/listings', headers=headers, json={'crop': 'Beans', 'quantity': '20kg', 'price': '200', 'location': 'Kigali'})
    assert res.status_code == 403


def test_buyer_can_place_order_and_farmer_updates_it():
    buyer_headers = auth_headers('+250788555444')
    listings = client.get('/listings').json()
    listing_id = listings[0]['id']
    order = client.post('/orders', headers=buyer_headers, json={'listing_id': listing_id, 'quantity_requested': '40 kg'})
    assert order.status_code == 200
    order_id = order.json()['id']

    farmer_phone = listings[0]['farmer']['phone']
    farmer_headers = auth_headers(farmer_phone)
    update = client.patch(f'/orders/{order_id}', headers=farmer_headers, json={'status': 'accepted'})
    assert update.status_code == 200
    assert update.json()['status'] == 'accepted'


def test_completed_order_required_for_review():
    buyer_headers = auth_headers('+250788555444')
    listings = client.get('/listings').json()
    listing_id = listings[0]['id']
    listing_farmer_id = listings[0]['farmer']['id']
    order = client.post('/orders', headers=buyer_headers, json={'listing_id': listing_id, 'quantity_requested': '40 kg'})
    assert order.status_code == 200
    order_id = order.json()['id']

    create_review = client.post(
        '/reviews',
        headers=buyer_headers,
        json={'farmer_id': listing_farmer_id, 'order_id': order_id, 'buyer_name': 'Kigali Fresh Market', 'score': 5, 'text': 'Great'},
    )
    assert create_review.status_code == 400

    farmer_headers = auth_headers(listings[0]['farmer']['phone'])
    complete = client.patch(f'/orders/{order_id}', headers=farmer_headers, json={'status': 'completed'})
    assert complete.status_code == 200

    create_review = client.post(
        '/reviews',
        headers=buyer_headers,
        json={'farmer_id': listing_farmer_id, 'order_id': order_id, 'buyer_name': 'Kigali Fresh Market', 'score': 5, 'text': 'Great produce'},
    )
    assert create_review.status_code == 200
    duplicate = client.post(
        '/reviews',
        headers=buyer_headers,
        json={'farmer_id': listing_farmer_id, 'order_id': order_id, 'buyer_name': 'Kigali Fresh Market', 'score': 4, 'text': 'Second try'},
    )
    assert duplicate.status_code == 400


def test_otp_lockout_after_invalid_attempts():
    client.post('/auth/request-otp', json={'phone': '+250788555444'})
    for idx in range(5):
        res = client.post('/auth/verify-otp', json={'phone': '+250788555444', 'code': '000000'})
        assert res.status_code == 400
    locked = client.post('/auth/verify-otp', json={'phone': '+250788555444', 'code': '123456'})
    assert locked.status_code == 429


def test_request_otp_for_unknown_user_fails():
    res = client.post('/auth/request-otp', json={'phone': '+250799999999'})
    assert res.status_code == 404


def test_admin_can_approve_verification_request_and_view_metrics():
    farmer_headers = auth_headers('+250788000111')
    create_req = client.post(
        '/verification/request',
        headers=farmer_headers,
        json={'document_type': 'national_id', 'document_reference': 'placeholder:1234'},
    )
    assert create_req.status_code == 200
    request_id = create_req.json()['id']

    admin_headers = auth_headers('+250700000001')
    review = client.patch(
        f'/admin/verification-requests/{request_id}',
        headers=admin_headers,
        json={'status': 'approved', 'review_notes': 'Looks good'},
    )
    assert review.status_code == 200
    metrics = client.get('/metrics/summary', headers=admin_headers)
    assert metrics.status_code == 200
    assert metrics.json()['verification_requests'] >= 1


def test_support_ticket_flow():
    buyer_headers = auth_headers('+250788555444')
    create = client.post('/support-tickets', headers=buyer_headers, json={'category': 'dispute', 'subject': 'Order issue', 'message': 'Need help'})
    assert create.status_code == 200
    ticket_id = create.json()['id']

    my_tickets = client.get('/support-tickets', headers=buyer_headers)
    assert my_tickets.status_code == 200
    assert len(my_tickets.json()) == 1

    admin_headers = auth_headers('+250700000001')
    update = client.patch(f'/admin/support-tickets/{ticket_id}', headers=admin_headers, json={'status': 'resolved', 'admin_notes': 'Handled'})
    assert update.status_code == 200
    assert update.json()['status'] == 'resolved'


def test_logout_invalidates_token():
    headers = auth_headers('+250788555444')
    logout = client.post('/auth/logout', headers=headers)
    assert logout.status_code == 200
    me = client.get('/me', headers=headers)
    assert me.status_code == 401


def test_public_browse_still_works():
    listings = client.get('/listings')
    reviews = client.get('/reviews')
    assert listings.status_code == 200
    assert reviews.status_code == 200


def test_search_endpoint_ranks_verified_location_match_higher():
    farmer_headers = auth_headers('+250788000111')
    create_listing = client.post(
        '/users',
        json={'name': 'Unverified Farmer', 'phone': '+250788999111', 'role': 'farmer', 'location': 'Rubavu'},
    )
    assert create_listing.status_code == 200
    other_headers = auth_headers('+250788999111')
    low_signal = client.post(
        '/listings',
        headers=other_headers,
        json={'crop': 'Tomatoes', 'quantity': '60 kg', 'price': '280 RWF / kg', 'location': 'Rubavu', 'description': 'Fresh tomatoes'},
    )
    assert low_signal.status_code == 200

    res = client.get('/listings', params={'query': 'Tomatoes', 'location': 'Kigali'})
    assert res.status_code == 200
    payload = res.json()
    assert payload[0]['location'] == 'Kigali'
    assert payload[0]['farmer']['is_verified'] is True


def test_recommendations_use_behavioral_signals_for_signed_in_buyer():
    buyer_headers = auth_headers('+250788555444')
    listings = client.get('/listings').json()
    tomatoes = next(item for item in listings if item['crop'] == 'Tomatoes')
    avocados = next(item for item in listings if item['crop'] == 'Avocados')

    first_rec = client.get('/recommendations', headers=buyer_headers)
    assert first_rec.status_code == 200

    for _ in range(3):
        tracked = client.post('/interactions', headers=buyer_headers, json={'interaction_type': 'view', 'listing_id': avocados['id']})
        assert tracked.status_code == 200

    searched = client.get('/listings', headers=buyer_headers, params={'query': 'Avocados'})
    assert searched.status_code == 200

    after = client.get('/recommendations', headers=buyer_headers)
    assert after.status_code == 200
    top = after.json()[0]
    assert top['listing']['crop'] == 'Avocados'
    assert 'based on crops you viewed' in top['reason'] or 'similar to your searches' in top['reason']


def test_interaction_requires_authentication():
    listings = client.get('/listings').json()
    res = client.post('/interactions', json={'interaction_type': 'view', 'listing_id': listings[0]['id']})
    assert res.status_code == 401
