"""Database ownership and default data for a single local profile."""

from pathlib import Path

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine, select

from .models import Category, PaymentMode, ProfileInfo


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.engine: Engine = create_engine(f"sqlite:///{path}")
        event.listen(self.engine, "connect", self._enable_foreign_keys)

    @staticmethod
    def _enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    def initialize(self, profile_name: str) -> None:
        SQLModel.metadata.create_all(self.engine)
        with self.session() as session:
            if session.get(ProfileInfo, 1) is None:
                session.add(ProfileInfo(name=profile_name))
            for name in ("UPI", "Bank", "Cash", "Crypto", "Other"):
                if not session.exec(select(PaymentMode).where(PaymentMode.name == name)).first():
                    session.add(PaymentMode(name=name))
            for name in ("Food", "Travel", "Fees", "Misc", "Rent"):
                category = session.exec(
                    select(Category).where(Category.name == name, Category.parent_id.is_(None))
                ).first()
                if category is None:
                    category = Category(name=name)
                    session.add(category)
                    session.flush()
                if name == "Food":
                    for child in ("Breakfast", "Lunch", "Snacks", "Dinner"):
                        if not session.exec(
                            select(Category).where(
                                Category.name == child, Category.parent_id == category.id
                            )
                        ).first():
                            session.add(Category(name=child, parent_id=category.id))
            session.commit()

    def session(self) -> Session:
        return Session(self.engine)

    def close(self) -> None:
        self.engine.dispose()
