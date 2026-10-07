"""Cliente de la API de OpenF1 con caché en SQLite y reintento ante 429."""

import asyncio
import json
import sqlite3
import time
from contextlib import closing
from typing import Any

import httpx

from f1_mcp.config import BASE_URL, CACHE_PATH, MAX_RETRIES

# Alias para poder sustituirlo en los tests y no esperar de verdad
_sleep = asyncio.sleep


class OpenF1Error(Exception):
    """OpenF1 no ha podido dar los datos: caída, timeout o límite de peticiones.
    El mensaje está pensado para mostrárselo al usuario tal cual."""


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
    Parámetros None se ignoran. 404 = sin resultados. Cualquier otro fallo
    (red, timeout, 429 persistente, 5xx) se convierte en OpenF1Error."""
    clean = {k: v for k, v in params.items() if v is not None}
    key = _cache_key(endpoint, clean)

    cached = cache_get(key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
            for attempt in range(MAX_RETRIES):
                r = await client.get(f"/{endpoint}", params=clean)
                if r.status_code == 429 and attempt < MAX_RETRIES - 1:
                    await _sleep(2**attempt)  # 1 s, 2 s...
                    continue
                break
    except httpx.TimeoutException as exc:
        raise OpenF1Error("OpenF1 está tardando demasiado en responder.") from exc
    except httpx.RequestError as exc:
        raise OpenF1Error("No se puede conectar con OpenF1 (¿hay conexión a internet?).") from exc

    if r.status_code == 404:
        return []
    if r.status_code == 429:
        raise OpenF1Error("Se ha alcanzado el límite de peticiones de OpenF1; espera un minuto.")
    if r.status_code >= 400:
        raise OpenF1Error(f"OpenF1 ha devuelto un error {r.status_code}.")
    data: list[dict[str, Any]] = r.json()
    if data:  # no cacheamos vacíos: pueden ser una sesión aún sin datos
        cache_put(key, data)
    return data
