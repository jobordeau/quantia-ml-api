def test_get_model_metrics_default(client):
    r = client.get("/get_model_metrics", params={"symbol": "BTCUSDT", "days": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "model_path" in body
    assert "metrics" in body
    metrics = body["metrics"]
    assert "logloss" in metrics
    assert "accuracy" in metrics
