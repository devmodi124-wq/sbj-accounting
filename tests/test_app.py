"""Phase 0 app-shell smoke tests."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Khata" in r.text


def test_static_css_served(client):
    r = client.get("/static/css/style.css")
    assert r.status_code == 200
    assert "--copper" in r.text
