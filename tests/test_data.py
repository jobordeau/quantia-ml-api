def test_last_candle(client):
    r = client.get("/data/BTCUSDT/last_candle")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["price_usdt"] > 0
    assert "timestamp_utc" in body


def test_history_default(client):
    r = client.get("/data/BTCUSDT", params={"days": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["interval"] == "1m"
    assert body["count"] >= 1
    assert isinstance(body["data"], list)
    first = body["data"][0]
    for k in ("timestamp_utc", "open", "high", "low", "close", "volume"):
        assert k in first
