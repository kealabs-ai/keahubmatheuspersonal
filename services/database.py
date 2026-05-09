import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

_DB_URL = (
    "mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
).format(
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "3306"),
    database=os.getenv("DB_NAME", "matheuspersonal"),
)

engine = create_engine(
    _DB_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "2")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "3")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),  # recicla conexões a cada 30min
    pool_pre_ping=True,   # SELECT 1 antes de usar — sem nova conexão física
    pool_timeout=30,
    echo=False,
)

_Session = sessionmaker(bind=engine)


def get_db():
    """Retorna uma conexão raw compatível com o código existente (cursor-based)."""
    conn = engine.raw_connection()
    return conn


@contextmanager
def db_session():
    """Context manager para uso com SQLAlchemy ORM (uso futuro)."""
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
