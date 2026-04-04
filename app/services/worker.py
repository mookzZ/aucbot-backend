import asyncio
import logging
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Alert, User, Item
from app.services import stalcraft

logger = logging.getLogger(__name__)

_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

QLT_NAMES = {0:'Обычный',1:'Необычный',2:'Особый',3:'Редкий',4:'Исключительный',5:'Легендарный'}

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

    groups: dict[tuple, list] = {}
    for alert, user, item in rows:
        key = (user.region, alert.item_id)
        groups.setdefault(key, []).append((alert, user, item))

    for (region, item_id), alerts in groups.items():
        try:
            data = await stalcraft.get_lots(region, item_id)
            lots = data.get("lots", [])
            if not lots:
                continue

            for alert, user, item in alerts:
                matching = []
                for lot in lots:
                    add = lot.get("additional", {})
                    lot_qlt = add.get("qlt")
                    lot_ptn = add.get("ptn", 0)

                    if alert.qlt is not None and lot_qlt != alert.qlt:
                        continue
                    if alert.ptn_min is not None and lot_ptn < alert.ptn_min:
                        continue
                    matching.append(lot)

                if not matching:
                    continue

                min_price = min(
                    lot.get("buyoutPrice") or lot.get("currentPrice") or 999_999_999
                    for lot in matching
                )

                if min_price <= alert.price_limit:
                    name = item.name_ru or item.name_en
                    qlt_str = f" [{QLT_NAMES[alert.qlt]}]" if alert.qlt is not None and alert.qlt in QLT_NAMES else ""
                    ptn_str = f" +{alert.ptn_min}" if alert.ptn_min else ""
                    try:
                        await _bot.send_message(
                            user.tg_id,
                            f"🔔 <b>{name}{qlt_str}{ptn_str}</b>\n"
                            f"Цена: <b>{min_price:,}</b> ₽\n"
                            f"Твой лимит: {alert.price_limit:,} ₽",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to notify {user.tg_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to check {region}/{item_id}: {e}")

        await asyncio.sleep(0.3)
