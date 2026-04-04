from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.database import get_db
from app.models import User, Item, Alert
from app.services import stalcraft
from app.services.auth import validate_init_data

router = APIRouter()


# ── Auth dependency ──────────────────────────────────────────────────────────

def get_tg_user(x_init_data: str = Header(...)) -> dict:
    data = validate_init_data(x_init_data)
    if not data or "user" not in data:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth")
    return data["user"]


# ── Regions ──────────────────────────────────────────────────────────────────

@router.get("/regions")
async def regions():
    return await stalcraft.get_regions()


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    region: str


@router.post("/users/me")
async def upsert_user(
    body: UserCreate,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    tg_id = tg_user["id"]
    user = await db.get(User, tg_id)
    if user:
        user.region = body.region
    else:
        user = User(tg_id=tg_id, region=body.region)
        db.add(user)
    await db.commit()
    return {"tg_id": tg_id, "region": body.region}


@router.get("/users/me")
async def get_user(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, tg_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"tg_id": user.tg_id, "region": user.region}


# ── Items ─────────────────────────────────────────────────────────────────────

@router.get("/items/search")
async def search_items(q: str, db: AsyncSession = Depends(get_db)):
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    result = await db.execute(
        select(Item)
        .where(Item.name_ru.ilike(f"%{q}%") | Item.name_en.ilike(f"%{q}%"))
        .limit(20)
    )
    items = result.scalars().all()
    return [
        {"id": i.id, "name_ru": i.name_ru, "name_en": i.name_en,
         "category": i.category, "icon_url": i.icon_url}
        for i in items
    ]


# ── Auction ───────────────────────────────────────────────────────────────────

@router.get("/auction/{item_id}/lots")
async def auction_lots(
    item_id: str,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, tg_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found, set region first")
    return await stalcraft.get_lots(user.region, item_id)


@router.get("/auction/{item_id}/history")
async def auction_history(
    item_id: str,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, tg_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found, set region first")
    return await stalcraft.get_history(user.region, item_id)


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    item_id: str
    price_limit: int
    qlt: int | None = None


@router.get("/alerts")
async def get_alerts(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert, Item)
        .join(Item, Alert.item_id == Item.id)
        .where(Alert.user_id == tg_user["id"])
        .order_by(Alert.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": alert.id,
            "item_id": alert.item_id,
            "name_ru": item.name_ru,
            "name_en": item.name_en,
            "icon_url": item.icon_url,
            "price_limit": alert.price_limit,
            "qlt": alert.qlt,
            "created_at": alert.created_at,
        }
        for alert, item in rows
    ]


@router.post("/alerts")
async def create_alert(
    body: AlertCreate,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    # check item exists
    item = await db.get(Item, body.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    alert = Alert(
        user_id=tg_user["id"],
        item_id=body.item_id,
        price_limit=body.price_limit,
        qlt=body.qlt,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return {"id": alert.id, "item_id": alert.item_id, "price_limit": alert.price_limit, "qlt": alert.qlt}


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == tg_user["id"]
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}
