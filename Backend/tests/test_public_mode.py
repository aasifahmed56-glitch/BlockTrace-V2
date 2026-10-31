"""
Tests for public deployment mode: open endpoints (no access code), rate limiting,
and the tighter budget on endpoints that spend Sepolia gas / Pinata storage.

Uses FastAPI TestClient and patches module-level flags directly instead of
touching real environment variables. Avoids /clear and other destructive or
on-chain endpoints, since the tests run against the configured Neo4j database.
"""

import pytest


# ============================================================
# Helpers: create test clients with specific mode settings
# ============================================================

def _make_app(public_mode=False):
    """Import and reconfigure the FastAPI app with mocked mode settings."""
    import api as api_module
    # Patch the module-level flag directly (it's read at import time)
    api_module.PUBLIC_MODE = public_mode
    # Clear rate limit store between tests
    api_module._rate_limit_store.clear()

    from fastapi.testclient import TestClient
    return TestClient(api_module.app), api_module


# ============================================================
# 1. /health endpoint
# ============================================================

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client, _ = _make_app(public_mode=True)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["public_mode"] is True

    def test_health_local_mode(self):
        client, _ = _make_app(public_mode=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["public_mode"] is False


# ============================================================
# 2. /contracts endpoint
# ============================================================

class TestContractsEndpoint:
    def test_contracts_returns_addresses(self):
        client, _ = _make_app(public_mode=True)
        resp = client.get("/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert "registry_contract" in data
        assert "case_contract" in data
        assert "network" in data
        assert "Sepolia" in data["network"]


# ============================================================
# 3. /sanctions/check endpoint
# ============================================================

class TestSanctionsCheckEndpoint:
    def test_sanctioned_address(self):
        client, _ = _make_app(public_mode=True)
        resp = client.get("/sanctions/check", params={
            "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sanctioned"] is True
        assert data["label"] is not None
        assert "OFAC" in data["source"]
        assert data["note"]  # non-empty disclaimer

    def test_non_sanctioned_address(self):
        client, _ = _make_app(public_mode=True)
        resp = client.get("/sanctions/check", params={
            "address": "0x0000000000000000000000000000000000000001"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sanctioned"] is False
        assert data["label"] is None

    def test_invalid_address_too_short(self):
        client, _ = _make_app()
        resp = client.get("/sanctions/check", params={"address": "0xINVALID"})
        assert resp.status_code == 400

    def test_invalid_address_no_prefix(self):
        client, _ = _make_app()
        resp = client.get("/sanctions/check", params={
            "address": "098B716B8Aaf21512996dC57EB0615e2383E2f96"
        })
        assert resp.status_code == 400

    def test_case_insensitive(self):
        client, _ = _make_app()
        resp_lower = client.get("/sanctions/check", params={
            "address": "0x098b716b8aaf21512996dc57eb0615e2383e2f96"
        })
        resp_upper = client.get("/sanctions/check", params={
            "address": "0x098B716B8AAF21512996DC57EB0615E2383E2F96"
        })
        assert resp_lower.json()["sanctioned"] is True
        assert resp_upper.json()["sanctioned"] is True


# ============================================================
# 4. Workspace endpoints are open in public mode (no access code)
# ============================================================

class TestOpenWorkspace:
    @pytest.mark.parametrize("path", ["/chains", "/curated-cases", "/summary", "/graph", "/cases"])
    def test_read_endpoints_open_in_public_mode(self, path):
        client, _ = _make_app(public_mode=True)
        resp = client.get(path)
        # 200 when Neo4j is reachable; never 401 now that the access code is gone
        assert resp.status_code != 401

    def test_access_code_header_is_ignored(self):
        client, _ = _make_app(public_mode=True)
        resp = client.get("/chains", headers={"X-Access-Code": "anything"})
        assert resp.status_code == 200

    def test_report_verify_open(self):
        client, _ = _make_app(public_mode=True)
        # POST without file — should get 422 (validation error), not 401
        resp = client.post("/report/verify")
        assert resp.status_code == 422


# ============================================================
# 5. Rate limiting
# ============================================================

class TestRateLimiting:
    def test_rate_limit_enforced_on_all_endpoints(self):
        client, mod = _make_app(public_mode=True)
        for i in range(mod.RATE_LIMIT):
            resp = client.get("/contracts")
            assert resp.status_code == 200, f"Request {i+1} failed with {resp.status_code}"
        resp = client.get("/contracts")
        assert resp.status_code == 429
        assert "Too many requests" in resp.json()["detail"]

    def test_health_exempt_from_rate_limit(self):
        # The frontend pings /health to wake the server; it must never be throttled.
        client, mod = _make_app(public_mode=True)
        for _ in range(mod.RATE_LIMIT + 5):
            assert client.get("/health").status_code == 200

    def test_rate_limit_not_enforced_in_local_mode(self):
        client, mod = _make_app(public_mode=False)
        for _ in range(mod.RATE_LIMIT + 5):
            assert client.get("/contracts").status_code == 200

    def test_clients_get_separate_buckets(self):
        client, mod = _make_app(public_mode=True)
        for _ in range(mod.RATE_LIMIT):
            client.get("/contracts", headers={"CF-Connecting-IP": "1.1.1.1"})
        assert client.get("/contracts", headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 429
        assert client.get("/contracts", headers={"CF-Connecting-IP": "2.2.2.2"}).status_code == 200
        assert client.get("/contracts", headers={"X-Forwarded-For": "3.3.3.3, 10.0.0.1"}).status_code == 200


# ============================================================
# 6. On-chain endpoints have a tighter budget
# ============================================================

class TestOnchainRateLimit:
    @pytest.fixture
    def no_onchain_budget(self):
        # A zero budget blocks the request in middleware, so the handler (which
        # would spend gas and upload to Pinata) never runs.
        import api as api_module
        original = api_module.ONCHAIN_RATE_LIMIT
        api_module.ONCHAIN_RATE_LIMIT = 0
        yield
        api_module.ONCHAIN_RATE_LIMIT = original

    @pytest.mark.parametrize("path", [
        "/report/publish",
        "/cases/BT-2026-0001/anchor",
        "/api/cases/BT-2026-0001/anchor",
        "/cases/BT-2026-0001/reanchor",
    ])
    def test_onchain_paths_use_onchain_budget(self, no_onchain_budget, path):
        client, _ = _make_app(public_mode=True)
        resp = client.post(path, json={})
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "3600"

    def test_onchain_pattern_only_matches_writes(self):
        _, mod = _make_app(public_mode=True)
        assert mod._ONCHAIN_PATH.match("/report/publish")
        assert not mod._ONCHAIN_PATH.match("/report")
        assert not mod._ONCHAIN_PATH.match("/report/verify")
        assert not mod._ONCHAIN_PATH.match("/cases/BT-2026-0001/verify")
