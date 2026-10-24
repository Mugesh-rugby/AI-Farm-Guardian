from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

try:
    from config import DATABASE_URL
except ImportError:
    from backend.config import DATABASE_URL

Base = declarative_base()


def initialize_engine():
    database_url = DATABASE_URL
    url_text = str(database_url)
    if url_text.startswith("sqlite") and __import__("os").getenv("APP_ENV") != "test":
        raise RuntimeError("MySQL is required. SQLite is supported only for isolated tests.")

    if isinstance(database_url, str) and database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )
    db_type = getattr(database_url, "drivername", url_text.split("://")[0])
    print(f"[Database] Configured using {db_type}")
    return engine


engine = initialize_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
