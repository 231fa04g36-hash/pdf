"""add_metadata_columns_to_document

Revision ID: 104f735713e6
Revises: 5b12740a8fd2
Create Date: 2026-07-19 00:16:28.999225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '104f735713e6'
down_revision: Union[str, None] = '5b12740a8fd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('extracted_title', sa.String(length=500), nullable=True))
    op.add_column('documents', sa.Column('extracted_authors', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'extracted_title')
    op.drop_column('documents', 'extracted_authors')

