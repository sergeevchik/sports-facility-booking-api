from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import Settings


class Database:
    def __init__(self, settings: Settings):
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
            pool_timeout=3,
            connect_args={"connect_timeout": 2, "options": "-c statement_timeout=5000"},
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
