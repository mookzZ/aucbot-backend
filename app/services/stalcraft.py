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


async def get_lots(region: str, item_id: str, limit: int = 50) -> dict:
    token = await _get_token()
    url = f"{settings.stalcraft_api_url}/{region}/auction/{item_id}/lots"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"limit": limit, "sort": "current_price", "order": "asc", "additional": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_history(region: str, item_id: str, limit: int = 200) -> dict:
    token = await _get_token()
    url = f"{settings.stalcraft_api_url}/{region}/auction/{item_id}/history"
    async with httpx.AsyncClient() as client:
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
