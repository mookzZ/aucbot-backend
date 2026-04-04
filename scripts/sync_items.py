"""
Run once before starting the server (and optionally by cron):
    python scripts/sync_items.py
"""
import asyncio
import httpx
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.dialects.postgresql import insert
from app.database import engine, AsyncSessionLocal
from app.models import Base, Item
from app.config import settings

GITHUB_API = "https://api.github.com/repos/EXBO-Studio/stalcraft-database/contents"
RAW_BASE = "https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main"
REALM = "ru"  # ru has both ru and en names

headers = {}
if settings.github_token:
    headers["Authorization"] = f"Bearer {settings.github_token}"


async def list_dir(client: httpx.AsyncClient, path: str) -> list[dict]:
    resp = await client.get(f"{GITHUB_API}/{path}", headers=headers)
    resp.raise_for_status()
    return resp.json()


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def extract_name(name_obj: dict) -> tuple[str, str]:
    if name_obj.get("type") == "translation":
        lines = name_obj.get("lines", {})
        return lines.get("ru", ""), lines.get("en", "")
    text = name_obj.get("text", "")
    return text, text


async def sync():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with httpx.AsyncClient(timeout=30) as client:
        categories = await list_dir(client, f"{REALM}/items")
        items_to_upsert = []

        for cat in categories:
            if cat["type"] != "dir":
                continue
            cat_name = cat["name"]

            try:
                subcats = await list_dir(client, f"{REALM}/items/{cat_name}")
            except Exception:
                continue

            # handle both flat (items directly) and nested (subcategories)
            async def process_dir(path: str, category: str):
                try:
                    entries = await list_dir(client, path)
                except Exception as e:
                    print(f"  skip {path}: {e}")
                    return

                for entry in entries:
                    if entry["type"] == "dir":
                        await process_dir(f"{path}/{entry['name']}", f"{category}/{entry['name']}")
                    elif entry["type"] == "file" and entry["name"].endswith(".json"):
                        item_id = entry["name"].replace(".json", "")
                        raw_url = f"{RAW_BASE}/{REALM}/items/{path.split(f'{REALM}/items/')[-1]}/{entry['name']}"
                        try:
                            data = await fetch_json(client, entry["download_url"])
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
                            print(f"  skip item {item_id}: {e}")

            await process_dir(f"{REALM}/items/{cat_name}", cat_name)
            print(f"Processed category: {cat_name} ({len(items_to_upsert)} items so far)")

        # bulk upsert
        if items_to_upsert:
            async with AsyncSessionLocal() as db:
                stmt = insert(Item).values(items_to_upsert)
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
            print(f"\n✅ Synced {len(items_to_upsert)} items")
        else:
            print("No items found")


if __name__ == "__main__":
    asyncio.run(sync())
