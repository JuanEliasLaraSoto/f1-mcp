"""Cliente de la API de OpenF1 con caché en SQLite y reintento ante 429."""

import asyncio
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://api.openf1.org/v1"
CACHE_PATH = Path.home() / ".cache" / "f1-mcp" / "openf1.sqlite"
MAX_RETRIES = 3

# Alias para poder sustituirlo en los tests y no esperar de verdad
_sleep = asyncio.sleep


def _cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """'laps?{"driver_number": 16, "session_key": 9912}'. sort_keys hace que el
    orden de los parámetros no cambie la clave."""
    return f"{endpoint}?{json.dumps(params, sort_keys=True)}"


def _connect() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        " key TEXT PRIMARY KEY, body TEXT NOT NULL, fetched_at REAL NOT NULL)"
    )
    return conn


def cache_get(key: str) -> list[dict[str, Any]] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT body FROM cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def cache_put(key: str, data: list[dict[str, Any]]) -> None:
    with closing(_connect()) as conn:
        with conn:  # abre una transacción y hace commit al salir
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, body, fetched_at) VALUES (?, ?, ?)",
                (key, json.dumps(data), time.time()),
            )


async def get(endpoint: str, **params: Any) -> list[dict[str, Any]]:
    """GET a un endpoint de OpenF1. Primero mira la caché; si no está, pide a la API
    (reintentando con espera exponencial ante 429) y guarda la respuesta.
    Parámetros None se ignoran. 404 = sin resultados."""
    clean = {k: v for k, v in params.items() if v is not None}
    key = _cache_key(endpoint, clean)

    cached = cache_get(key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        for attempt in range(MAX_RETRIES):
            r = await client.get(f"/{endpoint}", params=clean)
            if r.status_code == 429 and attempt < MAX_RETRIES - 1:
                await _sleep(2**attempt)  # 1 s, 2 s...
                continue
            break

    if r.status_code == 404:
        return []
    r.raise_for_status()
    data: list[dict[str, Any]] = r.json()
    if data:  # no cacheamos vacíos: pueden ser una sesión aún sin datos
        cache_put(key, data)
    return data
