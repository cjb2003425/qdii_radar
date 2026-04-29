import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

import server

client = TestClient(server.app)


def make_quote(code: str, price: float = 1.2345, rate: float = 1.23):
    return {
        "f12": code,
        "f2": price,
        "f3": rate,
        "f17": price,
        "f18": price,
    }


# ============================================================================
# Test 1: Cached slow fields returned without blocking
# ============================================================================

def test_api_funds_uses_cached_slow_fields_without_blocking(monkeypatch):
    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server,
        "get_cached_limit",
        lambda code: {"exists": True, "fresh": True, "value": "限额1000元"},
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {
            "exists": True,
            "fresh": True,
            "available": True,
            "value": 12.34,
        },
    )

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["limitText"] == "限额1000元"
    assert body[0]["oneYearChange"] == 12.34
    assert body[0]["oneYearChangeAvailable"] is True


# ============================================================================
# Test 2: Placeholder values on cache miss
# ============================================================================

def test_api_funds_returns_placeholders_when_slow_field_cache_missing(monkeypatch):
    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server, "get_cached_limit", lambda code: {"exists": False, "fresh": False, "value": "—"}
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
    )

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["limitText"] == "—"
    assert body[0]["oneYearChange"] == 0
    assert body[0]["oneYearChangeAvailable"] is False


# ============================================================================
# Test 3: Background refresh scheduled for missing cache
# ============================================================================

def test_api_funds_schedules_background_refresh_for_missing_cache(monkeypatch):
    scheduled = []

    def fake_schedule_limit_refresh(codes):
        scheduled.append(("limit", tuple(codes)))

    def fake_schedule_history_refresh(codes, exchange_traded_flags):
        scheduled.append(("history", tuple(codes)))

    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server, "get_cached_limit", lambda code: {"exists": False, "fresh": False, "value": "—"}
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
    )
    monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
    monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    assert ("limit", ("513100",)) in scheduled
    assert ("history", ("513100",)) in scheduled


# ============================================================================
# Test 4: Background refresh scheduled for stale cache
# ============================================================================

def test_api_funds_schedules_background_refresh_for_stale_cache(monkeypatch):
    scheduled = []

    def fake_schedule_limit_refresh(codes):
        scheduled.append(("limit", tuple(codes)))

    def fake_schedule_history_refresh(codes, exchange_traded_flags):
        scheduled.append(("history", tuple(codes)))

    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    # stale = exists but not fresh
    monkeypatch.setattr(
        server,
        "get_cached_limit",
        lambda code: {"exists": True, "fresh": False, "value": "限额1000元"},
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {
            "exists": True,
            "fresh": False,
            "available": True,
            "value": 12.34,
        },
    )
    monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
    monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    assert ("limit", ("513100",)) in scheduled
    assert ("history", ("513100",)) in scheduled


# ============================================================================
# Test 5: In-flight dedupe for limit refresh scheduling
# ============================================================================

def test_schedule_limit_refresh_skips_code_already_inflight(monkeypatch):
    # Ensure the in-flight set exists on the server module
    if not hasattr(server, "limit_refresh_inflight"):
        monkeypatch.setattr(server, "limit_refresh_inflight", set())

    server.limit_refresh_inflight.add("513100")
    try:
        scheduled = []

        def fake_schedule_limit_refresh(codes):
            # Only schedule codes not already in-flight
            codes_to_schedule = [c for c in codes if c not in server.limit_refresh_inflight]
            if codes_to_schedule:
                scheduled.append(("limit", tuple(codes_to_schedule)))

        monkeypatch.setattr(
            server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
        )
        monkeypatch.setattr(
            server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
        )
        monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
        monkeypatch.setattr(
            server,
            "get_cached_limit",
            lambda code: {"exists": False, "fresh": False, "value": "—"},
        )
        monkeypatch.setattr(
            server,
            "get_cached_one_year_change",
            lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
        )
        monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
        monkeypatch.setattr(
            server, "schedule_history_refresh", lambda codes, flags: None
        )

        response = client.get("/api/funds?codes=513100")

        assert response.status_code == 200
        # Because 513100 is already in-flight, no new scheduling should happen
        assert scheduled == []
    finally:
        server.limit_refresh_inflight.discard("513100")


# ============================================================================
# Test 6: In-flight dedupe for history refresh scheduling
# ============================================================================

def test_schedule_history_refresh_skips_code_already_inflight(monkeypatch):
    if not hasattr(server, "history_refresh_inflight"):
        monkeypatch.setattr(server, "history_refresh_inflight", set())

    server.history_refresh_inflight.add("513100")
    try:
        scheduled = []

        def fake_schedule_history_refresh(codes, exchange_traded_flags):
            codes_to_schedule = [c for c in codes if c not in server.history_refresh_inflight]
            if codes_to_schedule:
                scheduled.append(("history", tuple(codes_to_schedule)))

        monkeypatch.setattr(
            server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
        )
        monkeypatch.setattr(
            server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
        )
        monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
        monkeypatch.setattr(
            server,
            "get_cached_limit",
            lambda code: {"exists": False, "fresh": False, "value": "—"},
        )
        monkeypatch.setattr(
            server,
            "get_cached_one_year_change",
            lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
        )
        monkeypatch.setattr(server, "schedule_limit_refresh", lambda codes: None)
        monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)

        response = client.get("/api/funds?codes=513100")

        assert response.status_code == 200
        assert scheduled == []
    finally:
        server.history_refresh_inflight.discard("513100")
