from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, UniqueConstraint
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.models import Clan, TournamentGrid, ClanMatch

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class MatchIn(BaseModel):
    clan1: str
    clan2: str
    score1: int
    score2: int


class GridIn(BaseModel):
    date: date_type
    group_number: int
    region: str = "ru"
    matches: list[MatchIn]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_or_create_clan(db: AsyncSession, name: str, region: str) -> Clan:
    result = await db.execute(
        select(Clan).where(Clan.name == name, Clan.region == region)
    )
    clan = result.scalar_one_or_none()
    if not clan:
        clan = Clan(name=name, region=region)
        db.add(clan)
        await db.flush()  # получаем id без commit
    return clan


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/grids", status_code=201)
async def create_grid(body: GridIn, db: AsyncSession = Depends(get_db)):
    """Принимает данные от grid-parser'а."""

    # Проверяем дубликат (та же дата + группа + регион)
    existing = await db.execute(
        select(TournamentGrid).where(
            TournamentGrid.date == body.date,
            TournamentGrid.group_number == body.group_number,
            TournamentGrid.region == body.region,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Grid already exists")

    grid = TournamentGrid(
        date=body.date,
        group_number=body.group_number,
        region=body.region,
    )
    db.add(grid)
    await db.flush()

    for m in body.matches:
        clan1 = await get_or_create_clan(db, m.clan1, body.region)
        clan2 = await get_or_create_clan(db, m.clan2, body.region)

        if m.score1 > m.score2:
            winner_id = clan1.id
        elif m.score2 > m.score1:
            winner_id = clan2.id
        else:
            winner_id = None

        match = ClanMatch(
            grid_id=grid.id,
            clan1_id=clan1.id,
            clan2_id=clan2.id,
            score1=m.score1,
            score2=m.score2,
            winner_id=winner_id,
        )
        db.add(match)

    await db.commit()
    return {"ok": True, "grid_id": grid.id, "matches_saved": len(body.matches)}


@router.get("/clans/search")
async def search_clans(
    q: str,
    region: str = "ru",
    db: AsyncSession = Depends(get_db),
):
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    result = await db.execute(
        select(Clan)
        .where(
            Clan.region == region,
            or_(
                Clan.name.ilike(f"%{q}%"),
                Clan.tag.ilike(f"%{q}%"),
            )
        )
        .limit(20)
    )
    clans = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "tag": c.tag,
            "alliance": c.alliance,
            "leader": c.leader,
            "member_count": c.member_count,
            "region": c.region,
        }
        for c in clans
    ]


@router.get("/clans/{clan_id}/history")
async def clan_history(
    clan_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    clan = await db.get(Clan, clan_id)
    if not clan:
        raise HTTPException(status_code=404, detail="Clan not found")

    result = await db.execute(
        select(ClanMatch, TournamentGrid, Clan)
        .join(TournamentGrid, ClanMatch.grid_id == TournamentGrid.id)
        .join(Clan, or_(ClanMatch.clan1_id == clan_id, ClanMatch.clan2_id == clan_id))
        .where(or_(ClanMatch.clan1_id == clan_id, ClanMatch.clan2_id == clan_id))
        .order_by(TournamentGrid.date.desc())
        .limit(limit)
    )
    rows = result.all()

    matches_out = []
    seen_ids = set()

    for match, grid, _ in rows:
        if match.id in seen_ids:
            continue
        seen_ids.add(match.id)

        # resolve opponent
        opponent_id = match.clan2_id if match.clan1_id == clan_id else match.clan1_id
        opp_result = await db.get(Clan, opponent_id)
        opponent_name = opp_result.name if opp_result else "Unknown"

        is_clan1 = match.clan1_id == clan_id
        my_score = match.score1 if is_clan1 else match.score2
        opp_score = match.score2 if is_clan1 else match.score1

        if match.winner_id == clan_id:
            result_str = "win"
        elif match.winner_id is None:
            result_str = "draw"
        else:
            result_str = "loss"

        matches_out.append({
            "match_id": match.id,
            "date": grid.date,
            "group_number": grid.group_number,
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
            "score": f"{my_score}:{opp_score}",
            "result": result_str,
        })

    return {
        "clan": {
            "id": clan.id,
            "name": clan.name,
            "tag": clan.tag,
            "region": clan.region,
        },
        "matches": matches_out,
    }
