"""Main FastAPI application for the Agri Marketplace API.

This module wires middleware, startup behavior, public endpoints,
authenticated workflows, and admin-only operations. The code is grouped
by responsibility so it is easier to maintain during a pilot and later
split into routers if the product grows.
"""


import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import (
    build_token_expiry,
    generate_otp,
    generate_token,
    get_admin_user,
    get_current_user,
    get_optional_current_user,
    mark_failed_otp_attempt,
    normalize_phone,
    otp_is_locked,
)
from .database import Base, engine, get_db
from .logging_utils import log_event
from .models import AuditLog, Listing, ListingInteraction, Order, OTPCode, Review, SupportTicket, User, VerificationRequest
from .rate_limit import rate_limit_for_path, rate_limiter
from .schemas import (
    AuthResponse,
    HealthResponse,
    ImageUploadResponse,
    InteractionCreate,
    ListingCreate,
    ListingOut,
    RecommendationItem,
    OTPRequest,
    OTPVerify,
    OrderCreate,
    OrderOut,
    OrderUpdate,
    ReviewCreate,
    ReviewOut,
    SupportTicketCreate,
    SupportTicketOut,
    SupportTicketUpdate,
    UserCreate,
    UserOut,
    VerificationRequestCreate,
    VerificationRequestOut,
    VerificationReview,
)
from .seed import seed_data
from .settings import settings
from .sms import SMSDeliveryError, sms_client, sms_delivery_mode
from .storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.0,
            environment=settings.environment,
        )
    if settings.create_tables_on_startup:
        Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list if settings.environment == 'production' else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list if settings.environment == 'production' else ['*'])

upload_dir = Path(settings.upload_dir)
if settings.storage_backend == 'local':
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount('/media', StaticFiles(directory=str(upload_dir)), name='uploads')


def serialize_listing(listing: Listing) -> dict:
    """Convert a Listing ORM object into a stable API response payload."""
    return {
        'id': listing.id,
        'crop': listing.crop,
        'quantity': listing.quantity,
        'price': listing.price,
        'location': listing.location,
        'description': listing.description,
        'image_url': listing.image_url,
        'image_urls': json.loads(listing.image_urls or '[]'),
        'created_at': listing.created_at,
        'farmer': listing.farmer,
    }


def image_magic_ok(content: bytes, content_type: str) -> bool:
    """Perform lightweight file signature validation for supported image types."""
    signatures = {
        'image/png': [b'\x89PNG\r\n\x1a\n'],
        'image/jpeg': [b'\xff\xd8\xff'],
        'image/webp': [b'RIFF'],
    }
    allowed = signatures.get(content_type, [])
    if content_type == 'image/webp':
        return content[:4] == b'RIFF' and b'WEBP' in content[:16]
    return any(content.startswith(signature) for signature in allowed)


def create_audit_log(db: Session, user_id: int | None, action: str, entity_type: str, entity_id: str, details: str | None = None) -> None:
    """Persist an auditable business event for admin review and debugging."""
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))
    db.commit()


def current_sms_mode() -> str:
    """Describe SMS channel for health checks (file, console, twilio, placeholder)."""
    return sms_delivery_mode()


def _notify_sms_best_effort(to_phone: str, message: str) -> None:
    """Non-blocking SMS: order/verification notifications must not roll back core actions."""
    try:
        sms_client.send(to_phone, message)
    except SMSDeliveryError as exc:
        log_event('sms_delivery_failed', detail=str(exc), to=to_phone)


def get_farmer_average_rating(db: Session, farmer_id: int) -> float:
    """Compute the current average rating for a farmer."""
    reviews = db.query(Review).filter(Review.farmer_id == farmer_id).all()
    if not reviews:
        return 0.0
    return round(sum(review.score for review in reviews) / len(reviews), 2)


def record_listing_interaction(
    db: Session,
    user_id: int,
    interaction_type: str,
    listing: Listing | None = None,
    query: str | None = None,
) -> None:
    """Persist lightweight behavioral signals used for rule-based recommendations."""
    interaction = ListingInteraction(
        user_id=user_id,
        listing_id=listing.id if listing else None,
        farmer_id=listing.farmer_id if listing else None,
        crop=listing.crop if listing else None,
        interaction_type=interaction_type,
        query=query.strip() if query else None,
    )
    db.add(interaction)
    db.commit()


def listing_search_score(db: Session, listing: Listing, query: str = '', location: str = '') -> float:
    """Rank listings for search using simple marketplace rules instead of ML."""
    score = 0.0
    query_lower = query.strip().lower()
    location_lower = location.strip().lower()

    if query_lower:
        crop = listing.crop.lower()
        description = (listing.description or '').lower()
        farmer_name = (listing.farmer.name if listing.farmer else '').lower()
        if crop == query_lower:
            score += 8.0
        elif query_lower in crop:
            score += 5.0
        elif query_lower in description:
            score += 2.5
        elif query_lower in farmer_name:
            score += 2.0

    if location_lower:
        if listing.location.lower() == location_lower:
            score += 4.0
        elif location_lower in listing.location.lower():
            score += 2.0

    if listing.farmer and listing.farmer.is_verified:
        score += 2.5

    score += get_farmer_average_rating(db, listing.farmer_id) * 0.8

    age_hours = max((datetime.utcnow() - listing.created_at).total_seconds() / 3600, 0)
    score += max(0.0, 3.0 - min(age_hours / 24.0, 3.0))
    return round(score, 3)


def recommendation_bundle(db: Session, listing: Listing, current_user: User | None = None) -> tuple[float, str]:
    """Return a recommendation score and a human-readable reason for the ranking."""
    score = listing_search_score(db, listing, location=(current_user.location if current_user else ''))
    reasons: list[str] = []

    if current_user and listing.location.lower() == current_user.location.lower():
        reasons.append('near your location')
        score += 3.0

    if listing.farmer and listing.farmer.is_verified:
        reasons.append('verified farmer')

    rating = get_farmer_average_rating(db, listing.farmer_id)
    if rating >= 4:
        reasons.append('high rated')

    if current_user:
        interactions = (
            db.query(ListingInteraction)
            .filter(ListingInteraction.user_id == current_user.id)
            .order_by(ListingInteraction.created_at.desc())
            .all()
        )
        crop_signals = [item for item in interactions if item.crop]
        crop_views = sum(1 for item in crop_signals if item.crop == listing.crop and item.interaction_type in {'view', 'click', 'order'})
        farmer_views = sum(1 for item in interactions if item.farmer_id == listing.farmer_id and item.interaction_type in {'view', 'click', 'order'})
        query_matches = sum(1 for item in interactions if item.query and listing.crop.lower().find(item.query.lower()) >= 0)

        score += crop_views * 2.0
        score += farmer_views * 1.5
        score += query_matches * 0.75

        if crop_views:
            reasons.append('based on crops you viewed')
        if farmer_views:
            reasons.append('from a farmer you engaged with')
        if query_matches:
            reasons.append('similar to your searches')

    if not reasons:
        reasons.append('fresh marketplace match')

    return round(score, 3), ', '.join(dict.fromkeys(reasons))




@app.middleware('http')
async def security_and_logging_middleware(request: Request, call_next):
    client_host = request.client.host if request.client else 'unknown'
    path = request.url.path
    try:
        rate_limiter.check(f'{client_host}:{path}', rate_limit_for_path(path), settings.rate_limit_window_seconds)
        response = await call_next(request)
    except HTTPException as exc:
        log_event('http_error', path=path, method=request.method, status_code=exc.status_code, client_host=client_host)
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if settings.environment == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    log_event('http_request', path=path, method=request.method, status_code=response.status_code, client_host=client_host)
    return response


# ---------------------------------------------------------------------------
# Platform health and operations endpoints
# ---------------------------------------------------------------------------

@app.get('/health', response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    """Liveness endpoint used by deployment health checks and smoke tests."""
    database_status = 'ok'
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        database_status = 'error'
    return {
        'status': 'ok',
        'environment': settings.environment,
        'database': database_status,
        'sms_provider': current_sms_mode(),
        'storage': settings.storage_backend,
        'sentry': bool(settings.sentry_dsn),
    }


@app.get('/ready')
def readiness(db: Session = Depends(get_db)):
    """Readiness endpoint that confirms the database is reachable."""
    try:
        db.execute(text('SELECT 1'))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f'Database not ready: {exc}') from exc
    return {'status': 'ready'}


@app.get('/metrics/summary')
def metrics_summary(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Return lightweight admin metrics for pilot operations."""
    return {
        'users': db.query(User).count(),
        'listings': db.query(Listing).count(),
        'orders': db.query(Order).count(),
        'reviews': db.query(Review).count(),
        'verification_requests': db.query(VerificationRequest).count(),
        'support_tickets': db.query(SupportTicket).count(),
    }



# ---------------------------------------------------------------------------
# Public identity and authentication endpoints
# ---------------------------------------------------------------------------

@app.post('/users', response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a farmer or buyer profile. Existing users are returned idempotently."""
    phone = normalize_phone(payload.phone)
    existing_user = db.query(User).filter(User.phone == phone).first()
    if existing_user:
        return existing_user
    user = User(name=payload.name.strip(), phone=phone, role=payload.role, location=payload.location.strip())
    if phone in settings.admin_phone_list:
        user.is_admin = True
    db.add(user)
    db.commit()
    db.refresh(user)
    create_audit_log(db, user.id, 'user_created', 'user', str(user.id), user.phone)
    return user


@app.post('/auth/request-otp')
def request_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    """Issue a single active OTP for a known phone number."""
    phone = normalize_phone(payload.phone)
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail='User with this phone number not found')

    latest_otp = db.query(OTPCode).filter(OTPCode.phone == phone).order_by(OTPCode.created_at.desc()).first()
    if latest_otp:
        if otp_is_locked(latest_otp):
            raise HTTPException(status_code=429, detail='OTP temporarily locked. Please try again later.')
        if latest_otp.created_at > datetime.utcnow() - timedelta(seconds=settings.otp_resend_cooldown_seconds):
            raise HTTPException(status_code=429, detail='Please wait before requesting another OTP.')

    # Consume older pending OTPs so only one active code exists
    for row in db.query(OTPCode).filter(OTPCode.phone == phone, OTPCode.consumed.is_(False)).all():
        row.consumed = True
    code = generate_otp()
    otp = OTPCode(phone=phone, code=code, expires_at=OTPCode.default_expiry(settings.otp_expiry_minutes))
    db.add(otp)
    db.commit()
    db.refresh(otp)
    try:
        sms_client.send(phone, f'Your Agri Marketplace verification code is {code}')
    except SMSDeliveryError as exc:
        db.delete(otp)
        db.commit()
        raise HTTPException(status_code=503, detail=f'SMS delivery failed: {exc}') from exc
    create_audit_log(db, user.id, 'otp_requested', 'otp', str(otp.id), phone)
    return {'message': 'OTP sent', 'placeholder_code': code if settings.environment != 'production' else None}


@app.post('/auth/verify-otp', response_model=AuthResponse)
def verify_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    """Validate an OTP and create a short-lived bearer token session."""
    phone = normalize_phone(payload.phone)
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail='User with this phone number not found')
    otp = db.query(OTPCode).filter(OTPCode.phone == phone, OTPCode.consumed.is_(False)).order_by(OTPCode.created_at.desc()).first()
    if not otp:
        raise HTTPException(status_code=400, detail='No OTP request found')
    if otp_is_locked(otp):
        raise HTTPException(status_code=429, detail='OTP temporarily locked. Please try again later.')
    if otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail='Invalid or expired OTP')
    if otp.code != payload.code:
        mark_failed_otp_attempt(otp, db)
        raise HTTPException(status_code=400, detail='Invalid or expired OTP')

    otp.consumed = True
    user.auth_token = generate_token()
    user.token_expires_at = build_token_expiry()
    db.commit()
    db.refresh(user)
    create_audit_log(db, user.id, 'otp_verified', 'otp', str(otp.id), 'login_success')
    return AuthResponse(token=user.auth_token, user=user, expires_at=user.token_expires_at)


@app.post('/auth/logout')
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.auth_token = None
    current_user.token_expires_at = None
    db.commit()
    create_audit_log(db, current_user.id, 'logout', 'session', str(current_user.id), 'logout_success')
    return {'message': 'Logged out'}



# ---------------------------------------------------------------------------
# Authenticated user endpoints
# ---------------------------------------------------------------------------

@app.get('/me', response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get('/listings', response_model=list[ListingOut])
def get_listings(
    query: str = '',
    location: str = '',
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    listings = db.query(Listing).order_by(Listing.created_at.desc()).all()
    filtered: list[Listing] = []
    query_lower = query.strip().lower()
    location_lower = location.strip().lower()

    for listing in listings:
        query_match = not query_lower or query_lower in listing.crop.lower() or query_lower in (listing.description or '').lower() or query_lower in listing.farmer.name.lower()
        location_match = not location_lower or location_lower in listing.location.lower()
        if query_match and location_match:
            filtered.append(listing)

    ranked = sorted(filtered, key=lambda item: (listing_search_score(db, item, query, location), item.created_at), reverse=True)
    if current_user and query_lower:
        record_listing_interaction(db, current_user.id, 'search', query=query)
    return [serialize_listing(listing) for listing in ranked]


@app.post('/listings', response_model=ListingOut)
def create_listing(payload: ListingCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != 'farmer':
        raise HTTPException(status_code=403, detail='Only farmers can create listings')
    if len(payload.image_urls) > settings.max_image_count_per_listing:
        raise HTTPException(status_code=400, detail='Too many images attached to listing')
    listing = Listing(
        farmer_id=current_user.id,
        crop=payload.crop.strip(),
        quantity=payload.quantity.strip(),
        price=payload.price.strip(),
        location=payload.location.strip(),
        description=payload.description.strip() if payload.description else None,
        image_url=payload.image_url,
        image_urls=json.dumps(payload.image_urls),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    create_audit_log(db, current_user.id, 'listing_created', 'listing', str(listing.id), listing.crop)
    return serialize_listing(listing)


@app.post('/images/upload', response_model=ImageUploadResponse)
def upload_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail='Unsupported image format')
    content = image.file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=400, detail='File too large')
    if not image_magic_ok(content, image.content_type):
        raise HTTPException(status_code=400, detail='Image content did not match file type')
    extension = os.path.splitext(image.filename or 'upload.jpg')[1] or '.jpg'
    filename = f'{current_user.id}-{uuid.uuid4().hex}{extension}'
    image_url = get_storage().save(filename, content, image.content_type or 'application/octet-stream')
    create_audit_log(db, current_user.id, 'image_uploaded', 'image', filename, image.content_type)
    return ImageUploadResponse(filename=filename, image_url=image_url, placeholder=False)


@app.post('/orders', response_model=OrderOut)
def create_order(payload: OrderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != 'buyer':
        raise HTTPException(status_code=403, detail='Only buyers can place orders')
    listing = db.query(Listing).filter(Listing.id == payload.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail='Listing not found')
    order = Order(listing_id=payload.listing_id, buyer_id=current_user.id, quantity_requested=payload.quantity_requested.strip())
    db.add(order)
    db.commit()
    db.refresh(order)
    _notify_sms_best_effort(listing.farmer.phone, f'New order request for {listing.crop} from buyer {current_user.name}.')
    record_listing_interaction(db, current_user.id, 'order', listing=listing)
    create_audit_log(db, current_user.id, 'order_created', 'order', str(order.id), payload.quantity_requested)
    return order


@app.get('/orders', response_model=list[OrderOut])
def get_orders(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == 'buyer':
        return db.query(Order).filter(Order.buyer_id == current_user.id).order_by(Order.created_at.desc()).all()
    return db.query(Order).join(Listing, Listing.id == Order.listing_id).filter(Listing.farmer_id == current_user.id).order_by(Order.created_at.desc()).all()


@app.patch('/orders/{order_id}', response_model=OrderOut)
def update_order(order_id: int, payload: OrderUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    listing = db.query(Listing).filter(Listing.id == order.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail='Listing not found')
    if current_user.role != 'farmer' or listing.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail='Only the listing farmer can update this order')
    order.status = payload.status
    db.commit()
    db.refresh(order)
    buyer = db.query(User).filter(User.id == order.buyer_id).first()
    if buyer:
        _notify_sms_best_effort(buyer.phone, f'Your order for {listing.crop} is now {order.status}.')
    create_audit_log(db, current_user.id, 'order_updated', 'order', str(order.id), order.status)
    return order


@app.get('/reviews', response_model=list[ReviewOut])
def get_reviews(db: Session = Depends(get_db)):
    return db.query(Review).order_by(Review.created_at.desc()).all()


@app.post('/reviews', response_model=ReviewOut)
def create_review(payload: ReviewCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != 'buyer':
        raise HTTPException(status_code=403, detail='Only buyers can review farmers')

    completed_order = None
    if payload.order_id:
        completed_order = db.query(Order).filter(Order.id == payload.order_id, Order.buyer_id == current_user.id, Order.status == 'completed').first()
        if not completed_order:
            raise HTTPException(status_code=400, detail='A completed order is required for this review')
        listing = db.query(Listing).filter(Listing.id == completed_order.listing_id).first()
        if not listing or listing.farmer_id != payload.farmer_id:
            raise HTTPException(status_code=400, detail='Order does not belong to this farmer')
    else:
        completed_order = (
            db.query(Order)
            .join(Listing, Listing.id == Order.listing_id)
            .filter(Order.buyer_id == current_user.id, Order.status == 'completed', Listing.farmer_id == payload.farmer_id)
            .first()
        )
        if not completed_order:
            raise HTTPException(status_code=400, detail='A completed order is required before leaving a review')

    existing = db.query(Review).filter(Review.buyer_id == current_user.id, Review.order_id == completed_order.id).first()
    if existing:
        raise HTTPException(status_code=400, detail='You already reviewed this order')

    review = Review(
        farmer_id=payload.farmer_id,
        buyer_id=current_user.id,
        order_id=completed_order.id,
        buyer_name=payload.buyer_name.strip(),
        score=payload.score,
        text=payload.text.strip(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    create_audit_log(db, current_user.id, 'review_created', 'review', str(review.id), str(review.score))
    return review


@app.post('/verification/request', response_model=VerificationRequestOut)
def request_verification(payload: VerificationRequestCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.user_id == current_user.id, VerificationRequest.status == 'pending')
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail='You already have a pending verification request')
    req = VerificationRequest(user_id=current_user.id, **payload.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    create_audit_log(db, current_user.id, 'verification_requested', 'verification_request', str(req.id), req.document_type)
    return req



@app.post('/interactions')
def create_interaction(payload: InteractionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Store buyer behavior that can improve non-ML recommendations."""
    listing = None
    if payload.listing_id is not None:
        listing = db.query(Listing).filter(Listing.id == payload.listing_id).first()
        if not listing:
            raise HTTPException(status_code=404, detail='Listing not found')
    record_listing_interaction(db, current_user.id, payload.interaction_type, listing=listing, query=payload.query)
    create_audit_log(db, current_user.id, 'interaction_recorded', 'interaction', payload.interaction_type, payload.query or str(payload.listing_id or ''))
    return {'message': 'Interaction recorded'}


@app.get('/recommendations', response_model=list[RecommendationItem])
def get_recommendations(
    limit: int = 6,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Return rule-based marketplace recommendations using trust, location, and simple behavior signals."""
    limit = min(max(limit, 1), 20)
    listings = db.query(Listing).order_by(Listing.created_at.desc()).all()
    ranked = []
    for listing in listings:
        score, reason = recommendation_bundle(db, listing, current_user)
        ranked.append({'listing': serialize_listing(listing), 'score': score, 'reason': reason})
    ranked.sort(key=lambda item: (item['score'], item['listing']['created_at']), reverse=True)
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Admin-only moderation and support endpoints
# ---------------------------------------------------------------------------

@app.get('/admin/verification-requests', response_model=list[VerificationRequestOut])
def list_verification_requests(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    return db.query(VerificationRequest).order_by(VerificationRequest.created_at.desc()).all()


@app.patch('/admin/verification-requests/{request_id}', response_model=VerificationRequestOut)
def review_verification_request(
    request_id: int,
    payload: VerificationReview,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    req = db.query(VerificationRequest).filter(VerificationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail='Verification request not found')
    req.status = payload.status
    req.review_notes = payload.review_notes
    req.reviewed_at = datetime.utcnow()
    target_user = db.query(User).filter(User.id == req.user_id).first()
    if target_user:
        target_user.is_verified = payload.status == 'approved'
        _notify_sms_best_effort(target_user.phone, f'Your verification request has been {payload.status}.')
    db.commit()
    db.refresh(req)
    create_audit_log(db, admin_user.id, 'verification_reviewed', 'verification_request', str(req.id), payload.status)
    return req


@app.post('/support-tickets', response_model=SupportTicketOut)
def create_support_ticket(payload: SupportTicketCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = SupportTicket(
        user_id=current_user.id,
        category=payload.category,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    create_audit_log(db, current_user.id, 'support_ticket_created', 'support_ticket', str(ticket.id), payload.category)
    return ticket


@app.get('/support-tickets', response_model=list[SupportTicketOut])
def list_support_tickets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_admin:
        return db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()
    return db.query(SupportTicket).filter(SupportTicket.user_id == current_user.id).order_by(SupportTicket.created_at.desc()).all()


@app.patch('/admin/support-tickets/{ticket_id}', response_model=SupportTicketOut)
def update_support_ticket(ticket_id: int, payload: SupportTicketUpdate, admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail='Support ticket not found')
    ticket.status = payload.status
    ticket.admin_notes = payload.admin_notes
    db.commit()
    db.refresh(ticket)
    create_audit_log(db, admin_user.id, 'support_ticket_updated', 'support_ticket', str(ticket.id), payload.status)
    return ticket


@app.get('/admin/users', response_model=list[UserOut])
def list_users(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).limit(500).all()


@app.get('/admin/audit-logs')
def list_audit_logs(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [
        {
            'id': log.id,
            'user_id': log.user_id,
            'action': log.action,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'details': log.details,
            'created_at': log.created_at,
        }
        for log in logs
    ]
