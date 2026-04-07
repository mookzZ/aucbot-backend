from datetime import datetime, date
from typing import Optional
from sqlalchemy import BigInteger, String, Integer, ForeignKey, DateTime, Date, func, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    ptn_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="alerts")


# --- Clan tournament tables ---

class Clan(Base):
    __tablename__ = "clans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    tag: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    alliance: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    leader: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    member_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    region: Mapped[str] = mapped_column(String(16), default="ru")
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    matches_as_clan1: Mapped[list["ClanMatch"]] = relationship(
        back_populates="clan1", foreign_keys="ClanMatch.clan1_id"
    )
    matches_as_clan2: Mapped[list["ClanMatch"]] = relationship(
        back_populates="clan2", foreign_keys="ClanMatch.clan2_id"
    )


class TournamentGrid(Base):
    __tablename__ = "tournament_grids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    group_number: Mapped[int] = mapped_column(SmallInteger)
    region: Mapped[str] = mapped_column(String(16), default="ru")

    matches: Mapped[list["ClanMatch"]] = relationship(back_populates="grid")


class ClanMatch(Base):
    __tablename__ = "clan_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[int] = mapped_column(Integer, ForeignKey("tournament_grids.id"))
    clan1_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id"))
    clan2_id: Mapped[int] = mapped_column(Integer, ForeignKey("clans.id"))
    score1: Mapped[int] = mapped_column(Integer)
    score2: Mapped[int] = mapped_column(Integer)
    winner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clans.id"), nullable=True)

    grid: Mapped["TournamentGrid"] = relationship(back_populates="matches")
    clan1: Mapped["Clan"] = relationship(back_populates="matches_as_clan1", foreign_keys=[clan1_id])
    clan2: Mapped["Clan"] = relationship(back_populates="matches_as_clan2", foreign_keys=[clan2_id])
