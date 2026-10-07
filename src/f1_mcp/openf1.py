"""OpenF1 API client with a SQLite cache and retries on 429."""

import asyncio
import json
import sqlite3
import time
from contextlib import closing
from typing import Any

import httpx

from f1_mcp.config import BASE_URL, CACHE_PATH, MAX_RETRIES

# Alias so tests can replace it and not actually wait
_sleep = asyncio.sleep


class OpenF1Error(Exception):
    """OpenF1 could not provide the data: outage, timeout or rate limit.
    The message is meant to be shown to the user as is."""


def _cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """'laps?{"driver_number": 16, "session_key": 9912}'. sort_keys makes the key
    independent of parameter order."""
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
        with conn:  # opens a transaction and commits on exit
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, body, fetched_at) VALUES (?, ?, ?)",
                (key, json.dumps(data), time.time()),
            )


async def get(endpoint: str, **params: Any) -> list[dict[str, Any]]:
    """GET an OpenF1 endpoint. Checks the cache first; otherwise calls the API
    (retrying with exponential backoff on 429) and stores the response.
    None parameters are ignored. 404 = no results. Any other failure
    (network, timeout, persistent 429, 5xx) is raised as OpenF1Error."""
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
        raise OpenF1Error("OpenF1 is taking too long to respond.") from exc
    except httpx.RequestError as exc:
        raise OpenF1Error("Cannot connect to OpenF1 (is there an internet connection?).") from exc

    if r.status_code == 404:
        return []
    if r.status_code == 429:
        raise OpenF1Error("OpenF1's rate limit has been reached; wait a minute.")
    if r.status_code >= 400:
        raise OpenF1Error(f"OpenF1 returned an error {r.status_code}.")
    data: list[dict[str, Any]] = r.json()
    if data:  # empty responses are not cached: the session may not have data yet
        cache_put(key, data)
    return data
