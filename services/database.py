import os
from contextlib import contextmanager
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_password = quote_plus(os.getenv("DB_PASSWORD", ""))
_user = quote_plus(os.getenv("DB_USER", "root"))
_host = os.getenv("DB_HOST", "localhost")
_port = os.getenv("DB_PORT", "3306")
_database = os.getenv("DB_NAME", "matheuspersonal")

_DB_URL = f"mysql+mysqlconnector://{_user}:{_password}@{_host}:{_port}/{_database}"

engine = create_engine(
    _DB_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "2")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "3")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_pre_ping=True,
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
