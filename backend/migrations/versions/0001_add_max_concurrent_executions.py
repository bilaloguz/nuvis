from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# Keep revision <= 32 chars to fit default alembic_version.version_num
revision = '0001_max_concurrent_exec'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        op.execute("ALTER TABLE IF EXISTS settings ADD COLUMN IF NOT EXISTS max_concurrent_executions INTEGER DEFAULT 8")
    else:
        # SQLite lacks IF NOT EXISTS on ALTER; try-catch via raw execute
        try:
            op.execute("ALTER TABLE settings ADD COLUMN max_concurrent_executions INTEGER DEFAULT 8")
        except Exception:
            pass


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    try:
        if dialect == 'postgresql':
            op.execute("ALTER TABLE IF EXISTS settings DROP COLUMN IF EXISTS max_concurrent_executions")
        else:
            # SQLite: dropping columns is non-trivial; skip
            pass
    except Exception:
        pass
