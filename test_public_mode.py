"""
Tests for Phase 2 — public deployment mode: access code auth, rate limiting,
public endpoints (/health, /contracts, /sanctions/check), and protected endpoints.

Uses FastAPI TestClient and unittest.mock.patch to toggle PUBLIC_MODE/ACCESS_CODE
without touching real environment variables.
"""

import time
import pytest
from unittest.mock import patch


# ============================================================
# Helpers: create test clients with specific mode settings
# ============================================================

def _make_app(public_mode=False, access_code=""):
    """Import and reconfigure the FastAPI app with mocked mode settings."""
    with patch.dict("os.environ", {
        "PUBLIC_MODE": "true" if public_mode else "false",
        "ACCESS_CODE": access_code,
    }):
        # Re-import to pick up patched env vars at module level
        import importlib
        import api as api_module
        # Patch the module-level flags directly (they're read at import time)
        api_module.PUBLIC_MODE = public_mode
        api_module.ACCESS_CODE = access_code
        # Clear rate limit store between tests
        api_module._rate_limit_store.clear()

        from fastapi.testclient import TestClient
        return TestClient(api_module.app), api_module


# ============================================================
# 1. /health endpoint
# ============================================================

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["public_mode"] is True

    def test_health_no_code_needed(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        # No X-Access-Code header — should still work
        resp = client.get("/health")
        assert resp.status_code == 200

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
        client, _ = _make_app(public_mode=True, access_code="secret123")
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
        client, _ = _make_app(public_mode=True, access_code="secret123")
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

    def test_no_code_needed(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        # No X-Access-Code — public endpoint
        resp = client.get("/sanctions/check", params={
            "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
        })
        assert resp.status_code == 200

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
# 4. Protected endpoints return 401 in public mode without code
# ============================================================

class TestProtectedEndpoints:
    def test_clear_requires_code_in_public_mode(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.post("/clear")
        assert resp.status_code == 401
        assert "Access code required" in resp.json()["detail"]

    def test_clear_works_with_correct_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.post("/clear", headers={"X-Access-Code": "secret123"})
        # Will either be 200 (if Neo4j connected) or 500 (if not), but NOT 401
        assert resp.status_code != 401

    def test_clear_rejects_wrong_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.post("/clear", headers={"X-Access-Code": "wrong"})
        assert resp.status_code == 401

    def test_summary_requires_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.get("/summary")
        assert resp.status_code == 401

    def test_cases_list_requires_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.get("/cases")
        assert resp.status_code == 401

    def test_graph_requires_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.get("/graph")
        assert resp.status_code == 401

    def test_expand_requires_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.post("/expand", json={"wallet": "0x0000000000000000000000000000000000000001"})
        assert resp.status_code == 401

    def test_report_requires_code(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        resp = client.get("/report")
        assert resp.status_code == 401


# ============================================================
# 5. Local mode: everything works without a code
# ============================================================

class TestLocalMode:
    def test_clear_no_code_needed(self):
        client, _ = _make_app(public_mode=False)
        resp = client.post("/clear")
        # Won't be 401 — might be 500 if Neo4j isn't running, but that's fine
        assert resp.status_code != 401

    def test_summary_no_code_needed(self):
        client, _ = _make_app(public_mode=False)
        resp = client.get("/summary")
        assert resp.status_code != 401

    def test_cases_list_no_code_needed(self):
        client, _ = _make_app(public_mode=False)
        resp = client.get("/cases")
        assert resp.status_code != 401


# ============================================================
# 6. Rate limiting
# ============================================================

class TestRateLimiting:
    def test_rate_limit_enforced_on_public_endpoints(self):
        client, mod = _make_app(public_mode=True, access_code="secret123")
        mod._rate_limit_store.clear()
        # Make RATE_LIMIT requests — all should succeed
        for i in range(30):
            resp = client.get("/health")
            assert resp.status_code == 200, f"Request {i+1} failed with {resp.status_code}"
        # 31st request should be rate-limited
        resp = client.get("/health")
        assert resp.status_code == 429
        assert "Too many requests" in resp.json()["detail"]

    def test_rate_limit_not_enforced_in_local_mode(self):
        client, mod = _make_app(public_mode=False)
        mod._rate_limit_store.clear()
        # Even 35 requests should succeed
        for i in range(35):
            resp = client.get("/health")
            assert resp.status_code == 200


# ============================================================
# 7. /report/verify is public (no access code needed)
# ============================================================

class TestReportVerifyPublic:
    def test_report_verify_no_code_needed(self):
        client, _ = _make_app(public_mode=True, access_code="secret123")
        # POST without file — should get 422 (validation error), not 401
        resp = client.post("/report/verify")
        assert resp.status_code != 401  # 422 expected (missing file)

