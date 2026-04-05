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

def get_lot_price(lot: dict) -> int | None:
    """Get the best available price from a lot."""
    # Try buyoutPrice first, then currentPrice, then startPrice
    for key in ('buyoutPrice', 'currentPrice', 'startPrice'):
        val = lot.get(key)
        if val is not None and val > 0:
            return val
    return None

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

    if not rows:
        return

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
                    lot_ptn = add.get("ptn", 0) or 0

                    if alert.qlt is not None and lot_qlt != alert.qlt:
                        continue
                    if alert.ptn_min is not None and lot_ptn < alert.ptn_min:
                        continue
                    matching.append(lot)

                if not matching:
                    continue

                # Find minimum price among matching lots
                prices = [get_lot_price(lot) for lot in matching]
                prices = [p for p in prices if p is not None]

                if not prices:
                    continue

                min_price = min(prices)

                logger.info(f"Alert check: item={item_id} user={user.tg_id} min_price={min_price} limit={alert.price_limit}")

                if min_price <= alert.price_limit:
                    name = item.name_ru or item.name_en
                    qlt_str = f" [{QLT_NAMES[alert.qlt]}]" if alert.qlt is not None and alert.qlt in QLT_NAMES else ""
                    ptn_str = f" +{alert.ptn_min}+" if alert.ptn_min else ""
                    try:
                        await _bot.send_message(
                            user.tg_id,
                            f"🔔 <b>{name}{qlt_str}{ptn_str}</b>\n"
                            f"Цена: <b>{min_price:,}</b> ₽\n"
                            f"Твой лимит: {alert.price_limit:,} ₽",
                            parse_mode="HTML",
                        )
                        logger.info(f"Notified {user.tg_id} for {item_id}")
                    except Exception as e:
                        logger.warning(f"Failed to notify {user.tg_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to check {region}/{item_id}: {e}")

        await asyncio.sleep(0.3)
