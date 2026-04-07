"""
Merges duplicate clan entries created by the grid parser.

The parser creates clans by name only (no tag/alliance/leader),
while sync_clans pulls full data. This script:
  1. Finds pairs where one clan has synced data and the other doesn't
  2. Re-links all ClanMatch rows to the synced clan
  3. Deletes the empty duplicate

Run once after initial data load:
    python scripts/merge_clan_dupes.py
"""
import asyncio
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import select, update, delete, func
from app.database import engine, AsyncSessionLocal
from app.models import Base, Clan, ClanMatch


async def merge():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Load all clans grouped by (name_lower, region)
        result = await db.execute(select(Clan).order_by(Clan.id))
        all_clans = result.scalars().all()

        groups = defaultdict(list)
        for c in all_clans:
            key = (c.name.strip().lower(), c.region)
            groups[key].append(c)

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Found {len(dupes)} duplicate groups")

        merged = 0
        deleted = 0

        for key, clans in dupes.items():
            # Pick the "master" — prefer the one with synced_at or tag
            master = next((c for c in clans if c.synced_at or c.tag), clans[0])
            others = [c for c in clans if c.id != master.id]

            print(f"  '{master.name}' ({master.region}): master={master.id}, dupes={[c.id for c in others]}")

            for dupe in others:
                # Re-link clan1_id
                await db.execute(
                    update(ClanMatch)
                    .where(ClanMatch.clan1_id == dupe.id)
                    .values(clan1_id=master.id)
                )
                # Re-link clan2_id
                await db.execute(
                    update(ClanMatch)
                    .where(ClanMatch.clan2_id == dupe.id)
                    .values(clan2_id=master.id)
                )
                # Re-link winner_id
                await db.execute(
                    update(ClanMatch)
                    .where(ClanMatch.winner_id == dupe.id)
                    .values(winner_id=master.id)
                )
                # Delete dupe
                await db.execute(delete(Clan).where(Clan.id == dupe.id))
                deleted += 1
                merged += 1

        await db.commit()
        print(f"\n✅ Merged {merged} duplicates, deleted {deleted} clan rows")


if __name__ == "__main__":
    asyncio.run(merge())
