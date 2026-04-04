from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    alerts: Mapped[list["Alert"]] = relationship(back_populates="user")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(256), index=True)
    name_en: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str] = mapped_column(String(128))
    icon_url: Mapped[str] = mapped_column(String(512))


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"))
    item_id: Mapped[str] = mapped_column(String(32), ForeignKey("items.id"))
    price_limit: Mapped[int] = mapped_column(Integer)
    qlt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="alerts")
