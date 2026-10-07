from typing import Any

import httpx

BASE_URL = "https://api.openf1.org/v1"


async def get(endpoint: str, **params: Any) -> list[dict[str, Any]]:
    """GET a un endpoint de OpenF1. Ignora parámetros None. 404 = sin resultados."""
    clean = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        r = await client.get(f"/{endpoint}", params=clean)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()
