"""SQLAlchemy models for the Agri Marketplace domain.

The schema is intentionally compact for an MVP, but organized around the
main product concepts: users, listings, orders, trust signals, and support.
"""


from datetime import datetime, timedelta
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(32), unique=True, index=True, nullable=False)
    role = Column(String(20), nullable=False)
    location = Column(String(120), nullable=False)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    auth_token = Column(String(128), nullable=True, unique=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listings = relationship('Listing', back_populates='farmer')
    verification_requests = relationship('VerificationRequest', back_populates='user')
    interactions = relationship('ListingInteraction', foreign_keys='ListingInteraction.user_id')


class OTPCode(Base):
    __tablename__ = 'otp_codes'
    id = Column(Integer, primary_key=True)
    phone = Column(String(32), index=True, nullable=False)
    code = Column(String(8), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def default_expiry(minutes: int = 5):
        return datetime.utcnow() + timedelta(minutes=minutes)


class Listing(Base):
    __tablename__ = 'listings'
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    crop = Column(String(120), nullable=False)
    quantity = Column(String(120), nullable=False)
    price = Column(String(120), nullable=False)
    location = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    image_urls = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    farmer = relationship('User', back_populates='listings')
    orders = relationship('Order', back_populates='listing')


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), nullable=False)
    buyer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    quantity_requested = Column(String(120), nullable=False)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing = relationship('Listing', back_populates='orders')


class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    buyer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    buyer_name = Column(String(120), nullable=False)
    score = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class VerificationRequest(Base):
    __tablename__ = 'verification_requests'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    document_type = Column(String(80), nullable=False)
    document_reference = Column(String(255), nullable=False)
    status = Column(String(20), default='pending')
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='verification_requests')


class SupportTicket(Base):
    __tablename__ = 'support_tickets'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    category = Column(String(40), nullable=False)
    subject = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default='open')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_notes = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(120), nullable=False)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(80), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ListingInteraction(Base):
    __tablename__ = 'listing_interactions'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), nullable=True, index=True)
    farmer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    interaction_type = Column(String(20), nullable=False)
    crop = Column(String(120), nullable=True)
    query = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
