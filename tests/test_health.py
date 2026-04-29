def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "utc" in body
    assert body["data_source"] in {"binance", "bigquery"}
    assert "version" in body
