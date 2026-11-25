"""Idempotent demo facilities. Run explicitly with python -m app.seed."""

from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import Database
from app.models import Facility


def main():
    database = Database(get_settings())
    with database.sessions.begin() as session:
        for name, sport, capacity in (
            ("Tennis court A", "tennis", 4),
            ("Tennis court B", "tennis", 4),
            ("Football pitch", "football", 22),
            ("Basketball court", "basketball", 10),
        ):
            session.execute(
                insert(Facility)
                .values(
                    name=name,
                    sport=sport,
                    capacity=capacity,
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )
    database.engine.dispose()
    print("Demo facilities ready; existing facilities preserved.")


if __name__ == "__main__":
    main()
