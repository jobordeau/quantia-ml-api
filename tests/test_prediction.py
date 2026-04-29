def test_prediction_latest_returns_expected_schema(client):
    r = client.get("/prediction/latest", params={"symbol": "BTCUSDT"})
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "symbol", "timestamp", "prob_up", "signal",
        "confidence", "entry", "stop_loss", "take_profit",
    ):
        assert key in body, f"missing key: {key}"
    assert body["symbol"] == "BTCUSDT"
    assert 0.0 <= body["prob_up"] <= 1.0
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["signal"] in {"LONG", "SHORT"}


def test_trade_suggest(client):
    r = client.get("/trade/suggest", params={"symbol": "BTCUSDT", "risk_multiple": 1.5})
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "symbol", "side", "EntryPrice", "StopLoss",
        "TakeProfit", "PositionSize", "Confidence", "Timestamp",
    ):
        assert key in body, f"missing key: {key}"
    assert body["side"] in {"LONG", "SHORT"}
