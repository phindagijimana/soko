"""Pydantic request and response schemas used by the FastAPI app.

Validation rules live here so route handlers can stay concise and easier to read.
"""


from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

VALID_ROLES = {'farmer', 'buyer'}
VALID_ORDER_STATUSES = {'pending', 'accepted', 'rejected', 'completed'}
VALID_VERIFICATION_STATUSES = {'pending', 'approved', 'rejected'}
VALID_SUPPORT_CATEGORIES = {'dispute', 'abuse', 'general', 'bug'}
VALID_SUPPORT_STATUSES = {'open', 'in_progress', 'resolved', 'closed'}
VALID_INTERACTION_TYPES = {'view', 'click', 'search', 'order'}


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=32)
    role: str
    location: str = Field(min_length=2, max_length=120)

    @field_validator('role')
    @classmethod
    def validate_role(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_ROLES:
            raise ValueError('Role must be farmer or buyer')
        return value


class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    location: str
    is_verified: bool
    is_admin: bool = False

    class Config:
        from_attributes = True


class OTPRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)


class OTPVerify(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    expires_at: datetime


class ListingCreate(BaseModel):
    crop: str = Field(min_length=2, max_length=120)
    quantity: str = Field(min_length=1, max_length=120)
    price: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    image_url: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)


class ListingOut(BaseModel):
    id: int
    crop: str
    quantity: str
    price: str
    location: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)
    created_at: datetime
    farmer: UserOut

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    listing_id: int
    quantity_requested: str = Field(min_length=1, max_length=120)


class OrderUpdate(BaseModel):
    status: str

    @field_validator('status')
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_ORDER_STATUSES:
            raise ValueError('Unsupported status')
        return value


class OrderOut(BaseModel):
    id: int
    listing_id: int
    buyer_id: int
    quantity_requested: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    farmer_id: int
    order_id: Optional[int] = None
    buyer_name: str = Field(min_length=2, max_length=120)
    score: float = Field(ge=1, le=5)
    text: str = Field(min_length=2, max_length=1500)


class ReviewOut(BaseModel):
    id: int
    farmer_id: int
    buyer_id: Optional[int] = None
    order_id: Optional[int] = None
    buyer_name: str
    score: float
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class VerificationRequestCreate(BaseModel):
    document_type: str = Field(min_length=2, max_length=80)
    document_reference: str = Field(min_length=2, max_length=255)


class VerificationRequestOut(BaseModel):
    id: int
    user_id: int
    document_type: str
    document_reference: str
    status: str
    review_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VerificationReview(BaseModel):
    status: str
    review_notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator('status')
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_VERIFICATION_STATUSES:
            raise ValueError('Unsupported verification status')
        return value


class ImageUploadResponse(BaseModel):
    filename: str
    image_url: str
    placeholder: bool = False


class SupportTicketCreate(BaseModel):
    category: str
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=3000)

    @field_validator('category')
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_SUPPORT_CATEGORIES:
            raise ValueError('Unsupported support category')
        return value


class SupportTicketUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator('status')
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_SUPPORT_STATUSES:
            raise ValueError('Unsupported support status')
        return value


class SupportTicketOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    category: str
    subject: str
    message: str
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    sms_provider: str
    storage: str = 'local'
    sentry: bool = False


class InteractionCreate(BaseModel):
    listing_id: Optional[int] = None
    interaction_type: str
    query: Optional[str] = Field(default=None, max_length=255)

    @field_validator('interaction_type')
    @classmethod
    def validate_interaction_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_INTERACTION_TYPES:
            raise ValueError('Unsupported interaction type')
        return value


class RecommendationItem(BaseModel):
    listing: ListingOut
    score: float
    reason: str
