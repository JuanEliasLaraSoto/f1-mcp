"""Server configuration: a single place for URLs, paths and limits."""

import os
from pathlib import Path

BASE_URL = "https://api.openf1.org/v1"
CACHE_PATH = Path.home() / ".cache" / "f1-mcp" / "openf1.sqlite"
MAX_RETRIES = 3

# "stdio" for local clients, "http" for the deployed server
TRANSPORT = os.environ.get("F1_MCP_TRANSPORT", "stdio")
HOST = os.environ.get("F1_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("F1_MCP_PORT", "8000"))
