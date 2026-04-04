import time
import httpx
from app.config import settings

_token: str | None = None
_token_expires_at: float = 0


async def _get_token() -> str:
    global _token, _token_expires_at

    if _token and time.time() < _token_expires_at:
        return _token

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
        data = resp.json()
        _token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 3600) - 60
        return _token


async def get_lots(region: str, item_id: str) -> dict:
    """Fetch ALL active lots using pagination (max 200 per request)."""
    token = await _get_token()
    url = f"{settings.stalcraft_api_url}/{region}/auction/{item_id}/lots"
    PAGE = 200
    all_lots = []
    offset = 0
    total = None

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                url,
                params={
                    "limit": PAGE,
                    "offset": offset,
                    "sort": "current_price",
                    "order": "asc",
                    "additional": "true",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()

            if total is None:
                total = data.get("total", 0)
                # Stalcraft returns weird huge negative numbers when total is unknown
                if total < 0:
                    total = 9999

            lots = data.get("lots", [])
            all_lots.extend(lots)

            if not lots or len(all_lots) >= total or len(lots) < PAGE:
                break

            offset += PAGE

    return {"total": len(all_lots), "lots": all_lots}


async def get_history(region: str, item_id: str, limit: int = 200) -> dict:
    token = await _get_token()
    url = f"{settings.stalcraft_api_url}/{region}/auction/{item_id}/history"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            params={"limit": limit, "additional": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_regions() -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.stalcraft_api_url}/regions")
        resp.raise_for_status()
        return resp.json()
