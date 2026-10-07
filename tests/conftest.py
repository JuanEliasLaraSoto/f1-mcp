import pytest

from f1_mcp import openf1


@pytest.fixture(autouse=True)
def cache_temporal(tmp_path, monkeypatch):
    """Cada test usa una caché vacía en una carpeta temporal, nunca la real."""
    monkeypatch.setattr(openf1, "CACHE_PATH", tmp_path / "cache.sqlite")
