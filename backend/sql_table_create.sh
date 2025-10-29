python3 - << 'PY'
from database import Base, engine
import models  # ensure models are imported so tables are registered
Base.metadata.create_all(engine)
print("DB created and tables initialized at:", engine.url)
PY