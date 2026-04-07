"""
Sync clans from Stalcraft API into the DB.

Run once manually, then daily via cron or APScheduler:
    python scripts/sync_clans.py          # sync region ru
    python scripts/sync_clans.py eu       # sync region eu
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.database import engine, AsyncSessionLocal
from app.models import Base, Clan
from app.config import settings

REGION = sys.argv[1] if len(sys.argv) > 1 else "ru"
PAGE_SIZE = 100


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.stalcraft_auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.stalcraft_client_id,
                "client_secret": settings.stalcraft_client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def fetch_all_clans(token: str, region: str) -> list[dict]:
    url = f"{settings.stalcraft_api_url}/{region}/clans"
    clans = []
    offset = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                url,
                params={"limit": PAGE_SIZE, "offset": offset},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()

            batch = data.get("data", [])
            clans.extend(batch)

            total = data.get("total", 0)
            offset += PAGE_SIZE

            print(f"  Fetched {len(clans)}/{total}...")

            if len(clans) >= total or len(batch) < PAGE_SIZE:
                break

            await asyncio.sleep(0.2)

    return clans


async def sync(region: str):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Fetching token...")
    token = await get_token()

    print(f"Fetching clans for region={region}...")
    raw_clans = await fetch_all_clans(token, region)
    print(f"Got {len(raw_clans)} clans")

    if not raw_clans:
        print("No clans returned from API")
        return

    now = datetime.utcnow()
    rows = []
    for c in raw_clans:
        rows.append({
            "name": c.get("name", ""),
            "tag": c.get("tag") or None,
            "alliance": c.get("alliance") or None,
            "leader": c.get("leader") or None,
            "member_count": c.get("memberCount") or c.get("member_count") or None,
            "region": region,
            "synced_at": now,
        })

    async with AsyncSessionLocal() as db:
        stmt = insert(Clan).values(rows)
        stmt = stmt.on_conflict_do_update(
            # name+region уникально идентифицирует клан
            index_elements=["name", "region"],
            set_={
                "tag": stmt.excluded.tag,
                "alliance": stmt.excluded.alliance,
                "leader": stmt.excluded.leader,
                "member_count": stmt.excluded.member_count,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        await db.execute(stmt)
        await db.commit()

    print(f"✅ Synced {len(rows)} clans for region={region}")


if __name__ == "__main__":
    asyncio.run(sync(REGION))
