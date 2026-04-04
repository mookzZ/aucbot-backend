import asyncio
import logging
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Alert, User, Item
from app.services import stalcraft

logger = logging.getLogger(__name__)

# bot instance injected from main.py
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def check_alerts():
    if not _bot:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Alert, User, Item)
            .join(User, Alert.user_id == User.tg_id)
            .join(Item, Alert.item_id == Item.id)
        )
        rows = result.all()

    # group by (region, item_id) to minimize API calls
    groups: dict[tuple, list] = {}
    for alert, user, item in rows:
        key = (user.region, alert.item_id)
        groups.setdefault(key, []).append((alert, user, item))

    for (region, item_id), alerts in groups.items():
        try:
            data = await stalcraft.get_lots(region, item_id, limit=1)
            lots = data.get("lots", [])
            if not lots:
                continue

            min_price = lots[0].get("currentPrice") or lots[0].get("buyoutPrice")
            if min_price is None:
                continue

            for alert, user, item in alerts:
                if min_price <= alert.price_limit:
                    name = item.name_ru or item.name_en
                    try:
                        await _bot.send_message(
                            user.tg_id,
                            f"🔔 <b>{name}</b>\n"
                            f"Цена: <b>{min_price:,}</b> ₽\n"
                            f"Твой лимит: {alert.price_limit:,} ₽",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to notify {user.tg_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to check {region}/{item_id}: {e}")

        await asyncio.sleep(0.2)  # небольшая пауза между запросами к API
