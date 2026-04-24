from sqlalchemy.orm import Session

from .models import Listing, Review, User
from .settings import settings


def seed_data(db: Session) -> None:
    if not settings.enable_seed_data or db.query(User).count() > 0:
        return

    admin = User(
        name='Platform Admin',
        phone=settings.admin_phone_list[0] if settings.admin_phone_list else '+250700000001',
        role='buyer',
        location='Kigali',
        is_verified=True,
        is_admin=True,
    )
    farmer1 = User(name='Mukamana Chantal', phone='+250788000111', role='farmer', location='Kigali', is_verified=True)
    farmer2 = User(name='Uwase Diane', phone='+250788000333', role='farmer', location='Musanze', is_verified=True)
    buyer = User(name='Kigali Fresh Market', phone='+250788555444', role='buyer', location='Kigali', is_verified=True)
    db.add_all([admin, farmer1, farmer2, buyer])
    db.flush()

    db.add_all([
        Listing(
            farmer_id=farmer1.id,
            crop='Tomatoes',
            quantity='120 kg',
            price='300 RWF / kg',
            location='Kigali',
            description='Fresh harvest from this week. Good for wholesalers and restaurants.',
            image_url='https://images.unsplash.com/photo-1546094096-0df4bcaaa337?auto=format&fit=crop&w=1200&q=80',
            image_urls='[]',
        ),
        Listing(
            farmer_id=farmer2.id,
            crop='Avocados',
            quantity='500 pieces',
            price='250 RWF / piece',
            location='Musanze',
            description='Export-quality avocados. Consistent size and fresh stock.',
            image_url='https://images.unsplash.com/photo-1519162808019-7de1683fa2ad?auto=format&fit=crop&w=1200&q=80',
            image_urls='[]',
        ),
    ])
    db.add_all([
        Review(farmer_id=farmer1.id, buyer_name='Kigali Fresh Market', score=5, text='Good quality and arrived as described.'),
        Review(farmer_id=farmer2.id, buyer_name='Musanze Grocers', score=4, text='Reliable seller and smooth communication.'),
    ])
    db.commit()
