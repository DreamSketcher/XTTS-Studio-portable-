import pytest

from engine.env_core import get_site_packages


def test_get_site_packages(monkeypatch):
    monkeypatch.setattr("engine.env_core.SITE_PACKAGES", "/fake/site")
    result = get_site_packages()
    assert result == ["/fake/site"]
    assert isinstance(result, list)
