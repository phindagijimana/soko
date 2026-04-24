"""Create all ORM tables (use when not relying on create_tables_on_startup).

Revision ID: 6de51aeafae6
Revises: 0001_initial_placeholder
"""

from alembic import op

from app.database import Base

revision = '6de51aeafae6'
down_revision = '0001_initial_placeholder'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
