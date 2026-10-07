"""Server configuration: a single place for URLs, paths and limits."""

from pathlib import Path

BASE_URL = "https://api.openf1.org/v1"
CACHE_PATH = Path.home() / ".cache" / "f1-mcp" / "openf1.sqlite"
MAX_RETRIES = 3
