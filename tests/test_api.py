INN = "7707083893"


async def test_requires_api_key(client):
    response = await client.get("/api/v1/checks", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


async def test_rejects_invalid_inn(client):
    response = await client.post("/api/v1/checks", json={"inn": "1234567890"})
    assert response.status_code == 422


async def test_check_collects_report_from_all_providers(client):
    created = await client.post("/api/v1/checks", json={"inn": INN})
    assert created.status_code == 202

    check = (await client.get(f"/api/v1/checks/{created.json()['id']}")).json()
    assert check["status"] == "done"
    assert {c["provider"] for c in check["calls"]} == {"registry", "courts", "bankruptcy", "debts"}
    assert all(c["status"] == "ok" for c in check["calls"])
    assert check["total_cost_rub"] == 7.5
    assert check["risk_level"] in {"low", "medium", "high"}
    assert check["report"]["registry"]["inn"] == INN
    assert check["report"]["failed_providers"] == []


async def test_repeated_check_is_free_thanks_to_cache(client):
    await client.post("/api/v1/checks", json={"inn": INN})
    second = await client.post("/api/v1/checks", json={"inn": INN})

    check = (await client.get(f"/api/v1/checks/{second.json()['id']}")).json()
    assert check["total_cost_rub"] == 0
    assert all(c["status"] == "cached" for c in check["calls"])


async def test_provider_failures_give_partial_report(make_client):
    async for client in make_client(mock_failure_rate=1.0, provider_retries=2):
        created = await client.post("/api/v1/checks", json={"inn": INN})
        check = (await client.get(f"/api/v1/checks/{created.json()['id']}")).json()

        assert check["status"] == "done"
        assert all(c["status"] == "failed" for c in check["calls"])
        assert all(c["attempts"] == 3 for c in check["calls"])  # 1 запрос + 2 повтора
        assert check["total_cost_rub"] == 0
        assert len(check["report"]["failed_providers"]) == 4
        assert "Нет данных из реестра — проверка неполная" in check["risk_factors"]


async def test_circuit_breaker_stops_calling_dead_provider(make_client):
    async for client in make_client(mock_failure_rate=1.0, provider_retries=0, breaker_threshold=2):
        for _ in range(2):
            await client.post("/api/v1/checks", json={"inn": INN})
        created = await client.post("/api/v1/checks", json={"inn": INN})

        check = (await client.get(f"/api/v1/checks/{created.json()['id']}")).json()
        assert all(c["status"] == "skipped" for c in check["calls"])
        assert all(c["attempts"] == 0 for c in check["calls"])


async def test_stats_show_cost_and_cache_hits(client):
    await client.post("/api/v1/checks", json={"inn": INN})
    await client.post("/api/v1/checks", json={"inn": INN})

    stats = (await client.get("/api/v1/stats")).json()
    assert stats["checks_total"] == 2
    assert stats["cost_total_rub"] == 7.5
    assert stats["cache_hit_rate"] == 0.5
    registry = next(p for p in stats["providers"] if p["provider"] == "registry")
    assert (registry["calls"], registry["ok"], registry["cached"]) == (2, 1, 1)


async def test_list_checks_filters_by_inn(client):
    await client.post("/api/v1/checks", json={"inn": INN})
    await client.post("/api/v1/checks", json={"inn": "7736207543"})

    checks = (await client.get("/api/v1/checks", params={"inn": INN})).json()
    assert [c["inn"] for c in checks] == [INN]


async def test_rate_limit(make_client):
    async for client in make_client(rate_limit_per_minute=2):
        codes = [(await client.get("/api/v1/checks")).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


async def test_health_is_public(client):
    response = await client.get("/health", headers={"X-API-Key": ""})
    assert response.json() == {"status": "ok", "db": True, "redis": True}
