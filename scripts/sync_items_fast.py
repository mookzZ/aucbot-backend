"""
Sync from local ZIP file.
Usage: python scripts/sync_items_fast.py <path_to_zip>
Example: python scripts/sync_items_fast.py stalcraft-database-main.zip
"""
import asyncio
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.dialects.postgresql import insert
from app.database import engine, AsyncSessionLocal
from app.models import Base, Item

REALM = "ru"


def extract_name(name_obj: dict) -> tuple[str, str]:
    if name_obj.get("type") == "translation":
        lines = name_obj.get("lines", {})
        return lines.get("ru", ""), lines.get("en", "")
    text = name_obj.get("text", "")
    return text, text


async def sync(zip_path: str):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Reading {zip_path}...")
    items_to_upsert = []
    seen_ids = set()

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            parts = name.split("/")
            if (
                len(parts) >= 5
                and parts[1] == REALM
                and parts[2] == "items"
                and name.endswith(".json")
                and "_variants" not in parts
            ):
                item_id = parts[-1].replace(".json", "")
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                category = "/".join(parts[3:-1])
                try:
                    with zf.open(name) as f:
                        data = json.load(f)
                    name_ru, name_en = extract_name(data.get("name", {}))
                    icon_url = (
                        f"https://github.com/EXBO-Studio/stalcraft-database"
                        f"/raw/main/{REALM}/icons/{category}/{item_id}.png"
                    )
                    items_to_upsert.append({
                        "id": item_id,
                        "name_ru": name_ru,
                        "name_en": name_en,
                        "category": category,
                        "icon_url": icon_url,
                    })
                except Exception as e:
                    print(f"  skip {item_id}: {e}")

    print(f"Parsed {len(items_to_upsert)} items, inserting into DB...")

    async with AsyncSessionLocal() as db:
        for i in range(0, len(items_to_upsert), 500):
            batch = items_to_upsert[i:i + 500]
            stmt = insert(Item).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name_ru": stmt.excluded.name_ru,
                    "name_en": stmt.excluded.name_en,
                    "category": stmt.excluded.category,
                    "icon_url": stmt.excluded.icon_url,
                },
            )
            await db.execute(stmt)
        await db.commit()

    print(f"✅ Synced {len(items_to_upsert)} items")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/sync_items_fast.py <path_to_zip>")
        sys.exit(1)
    asyncio.run(sync(sys.argv[1]))
