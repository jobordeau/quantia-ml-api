def _range_params():
    return {
        "symbol": "BTCUSDT",
        "start_date": "2025-01-01T00:00",
        "end_date": "2025-01-01T03:00",
    }


def test_pattern_load_data(client):
    r = client.get("/pattern/load-data", params=_range_params())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["count"] >= 1
    assert "candle_type" in body["data"][0]


def test_pattern_load_data_patterns(client):
    r = client.get("/pattern/load-data-patterns", params=_range_params())
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["patterns_detected"], list)


def test_classic_patterns(client):
    params = _range_params() | {"atr_min_pct": 0.01}
    r = client.get("/pattern/load-data-patterns-classic", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["patterns_detected"], list)


def test_pattern_invalid_dates(client):
    r = client.get(
        "/pattern/load-data",
        params={"symbol": "BTCUSDT", "start_date": "2025-01-02T00:00", "end_date": "2025-01-01T00:00"},
    )
    assert r.status_code == 400
