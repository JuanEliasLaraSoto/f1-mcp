import pytest

from f1_mcp import openf1


@pytest.fixture(autouse=True)
def temporary_cache(tmp_path, monkeypatch):
    """Every test gets an empty cache in a temporary folder, never the real one."""
    monkeypatch.setattr(openf1, "CACHE_PATH", tmp_path / "cache.sqlite")
